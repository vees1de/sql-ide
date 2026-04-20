from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.agents.clarification import ClarificationAgent
from app.agents.intent import IntentAgent
from app.agents.semantic import SemanticMappingAgent
from app.agents.sql_generation import SQLGenerationAgent
from app.agents.validation import SQLValidationAgent
from app.core.config import settings
from app.db.models import ChatMessageModel, ChatSessionModel
from app.schemas.chat import (
    ClarificationOption,
    ChatMessageRead,
    ChatSessionRead,
    ChatSessionUpdate,
    Interpretation,
    StructuredPayload,
    TableUsage,
)
from app.schemas.dictionary import DictionaryEntryRead
from app.schemas.query import IntentPayload, SemanticMappingPayload
from app.services.chat_service import ChatService
from app.services.database_resolution import resolve_allowed_tables, resolve_dialect, resolve_engine
from app.services.llm_service import LLMQueryPlan, LLMService
from app.services.schema_context_provider import SchemaContextProvider
from app.services.dictionary_service import DictionaryService


@dataclass
class AdapterResult:
    session: ChatSessionModel
    user_message: ChatMessageModel
    assistant_message: ChatMessageModel
    structured_payload: StructuredPayload
    sql_draft: str | None
    sql_draft_version: int


class ChatSqlAdapter:
    def __init__(self) -> None:
        self.chat_service = ChatService()
        self.schema_provider = SchemaContextProvider()
        self.dictionary_service = DictionaryService()
        self.intent_agent = IntentAgent()
        self.semantic_agent = SemanticMappingAgent()
        self.sql_generation_agent = SQLGenerationAgent()
        self.validation_agent = SQLValidationAgent()
        self.clarification_agent = ClarificationAgent()
        self.llm_service = LLMService()

    def generate_response(self, db: Session, session_id: str, user_text: str) -> AdapterResult:
        session = self.chat_service.get_session(db, session_id)
        if session is None:
            raise ValueError("Chat session not found.")

        previous_intent = self._load_previous_intent(session.last_intent_json)
        history_text = self._build_history_text(session.messages)
        dialect = resolve_dialect(db, session.database_connection_id)
        engine = resolve_engine(db, session.database_connection_id)
        allowed_tables = resolve_allowed_tables(db, session.database_connection_id, engine)
        schema = self.schema_provider.get_schema_for_llm(db, session.database_connection_id)
        dictionary_entries = self._load_dictionary_entries(db)

        plan = self._try_llm_plan(user_text, schema, previous_intent, history_text)
        if plan is not None:
            result = self._from_plan(
                db=db,
                session=session,
                plan=plan,
                dialect=dialect,
                allowed_tables=allowed_tables,
                schema=schema,
                dictionary_entries=dictionary_entries,
                user_text=user_text,
                previous_intent=previous_intent,
            )
            if result is not None:
                return result

        intent = self.intent_agent.run(user_text, previous_intent=previous_intent)
        if intent.clarification_question:
            return self._build_clarification_result(
                db=db,
                session=session,
                intent=intent,
                schema=schema,
                user_text=user_text,
                dialect=dialect,
                commit_updates=True,
            )

        semantic = self.semantic_agent.run(intent, dictionary_entries, dialect, schema)
        try:
            sql = self.sql_generation_agent.run(intent, semantic)
        except Exception as exc:  # noqa: BLE001
            payload = self._build_structured_payload(
                intent=intent,
                semantic=semantic,
                sql=None,
                validation_warnings=[str(exc)],
                dialect=dialect,
                validation_errors=[str(exc)],
            )
            return self._persist_result(
                db=db,
                session=session,
                user_text=user_text,
                intent=intent,
                payload=payload,
                sql_draft=None,
                assistant_text=str(exc),
                commit_updates=True,
            )

        validation = self.validation_agent.run(sql, dialect, allowed_tables=allowed_tables)
        if not validation.valid:
            payload = self._build_structured_payload(
                intent=intent,
                semantic=semantic,
                sql=None,
                validation_warnings=validation.warnings,
                validation_errors=validation.errors,
                dialect=dialect,
            )
            assistant_text = validation.errors[0] if validation.errors else "Не удалось безопасно подготовить SQL."
            return self._persist_result(
                db=db,
                session=session,
                user_text=user_text,
                intent=intent,
                payload=payload,
                sql_draft=None,
                assistant_text=assistant_text,
                commit_updates=True,
            )

        payload = self._build_structured_payload(
            intent=intent,
            semantic=semantic,
            sql=validation.sql,
            validation_warnings=validation.warnings,
            validation_errors=validation.errors,
            dialect=dialect,
        )
        assistant_text = "SQL подготовлен и подставлен в редактор. Запуск останется ручным."
        return self._persist_result(
            db=db,
            session=session,
            user_text=user_text,
            intent=intent,
            payload=payload,
            sql_draft=validation.sql,
            assistant_text=assistant_text,
            commit_updates=True,
        )

    def _try_llm_plan(
        self,
        user_text: str,
        schema,
        previous_intent: IntentPayload | None,
        history_text: str,
    ) -> LLMQueryPlan | None:
        if not self.llm_service.configured:
            return None
        return self.llm_service.plan_query(
            prompt=user_text,
            schema=schema,
            previous_intent=previous_intent,
            history_text=history_text,
            temperature=0.0,
        )

    def _from_plan(
        self,
        db: Session,
        session: ChatSessionModel,
        plan: LLMQueryPlan,
        dialect: str,
        allowed_tables: list[str],
        schema,
        dictionary_entries: list[DictionaryEntryRead],
        user_text: str,
        previous_intent: IntentPayload | None,
    ) -> AdapterResult | None:
        intent = plan.intent
        if intent.clarification_question and not plan.sql:
            return self._build_clarification_result(
                db=db,
                session=session,
                intent=intent,
                schema=schema,
                user_text=user_text,
                dialect=dialect,
                commit_updates=True,
                previous_intent=previous_intent,
            )
        semantic = self.semantic_agent.run(intent, dictionary_entries, dialect, schema)
        if not plan.sql:
            try:
                sql = self.sql_generation_agent.run(intent, semantic)
            except Exception as exc:  # noqa: BLE001
                payload = self._build_structured_payload(
                    intent=intent,
                    semantic=semantic,
                    sql=None,
                    validation_warnings=[str(exc)],
                    validation_errors=[str(exc)],
                    dialect=dialect,
                )
                return self._persist_result(
                    db=db,
                    session=session,
                    user_text=user_text,
                    intent=intent,
                    payload=payload,
                    sql_draft=None,
                    assistant_text=str(exc),
                    commit_updates=True,
                )
        else:
            sql = plan.sql

        validation = self.validation_agent.run(sql, dialect, allowed_tables=allowed_tables)
        if not validation.valid:
            payload = self._build_structured_payload(
                intent=intent,
                semantic=semantic,
                sql=None,
                validation_warnings=list(dict.fromkeys([*plan.warnings, *validation.warnings])),
                validation_errors=validation.errors,
                dialect=dialect,
            )
            assistant_text = validation.errors[0] if validation.errors else "Не удалось безопасно подготовить SQL."
            return self._persist_result(
                db=db,
                session=session,
                user_text=user_text,
                intent=intent,
                payload=payload,
                sql_draft=None,
                assistant_text=assistant_text,
                commit_updates=True,
            )

        payload = self._build_structured_payload(
            intent=intent,
            semantic=semantic,
            sql=validation.sql,
            validation_warnings=list(dict.fromkeys([*plan.warnings, *validation.warnings])),
            validation_errors=validation.errors,
            dialect=dialect,
        )
        assistant_text = "SQL подготовлен и подставлен в редактор. Запуск останется ручным."
        return self._persist_result(
            db=db,
            session=session,
            user_text=user_text,
            intent=intent,
            payload=payload,
            sql_draft=validation.sql,
            assistant_text=assistant_text,
            commit_updates=True,
        )

    def _build_clarification_result(
        self,
        db: Session,
        session: ChatSessionModel,
        intent: IntentPayload,
        schema,
        user_text: str,
        dialect: str,
        commit_updates: bool,
        previous_intent: IntentPayload | None = None,
    ) -> AdapterResult:
        clarification = self.clarification_agent.run(intent, schema=schema)
        options = [
            ClarificationOption(
                id=f"option-{index + 1}",
                label=str(option),
                detail=str(option),
            )
            for index, option in enumerate(clarification.get("options", []))
        ]
        payload = StructuredPayload(
            interpretation=self._build_interpretation(intent),
            tables_used=[],
            sql=None,
            warnings=list(dict.fromkeys([*(intent.ambiguities or [])])),
            needs_clarification=True,
            clarification_question=clarification.get("question") or intent.clarification_question,
            clarification_options=options or None,
            dialect=dialect,
        )
        assistant_text = payload.clarification_question or "Нужны дополнительные детали."
        return self._persist_result(
            db=db,
            session=session,
            user_text=user_text,
            intent=intent,
            payload=payload,
            sql_draft=None,
            assistant_text=assistant_text,
            commit_updates=commit_updates,
        )

    def _persist_result(
        self,
        db: Session,
        session: ChatSessionModel,
        user_text: str,
        intent: IntentPayload,
        payload: StructuredPayload,
        sql_draft: str | None,
        assistant_text: str,
        commit_updates: bool,
    ) -> AdapterResult:
        if session.title == "Новый чат":
            auto_title = self.chat_service.title_from_prompt(user_text)
            if auto_title:
                session.title = auto_title

        user_message = self.chat_service.append_message(
            db,
            session,
            "user",
            user_text,
            structured_payload=None,
            commit=False,
        )
        assistant_message = self.chat_service.append_message(
            db,
            session,
            "assistant",
            assistant_text,
            structured_payload=payload,
            commit=False,
        )

        session.last_intent_json = intent.model_dump(mode="json")
        if sql_draft is not None:
            session.current_sql_draft = sql_draft
            session.sql_draft_version = (session.sql_draft_version or 0) + 1
        db.flush()
        if commit_updates:
            db.commit()
            db.refresh(session)
            db.refresh(user_message)
            db.refresh(assistant_message)

        return AdapterResult(
            session=session,
            user_message=user_message,
            assistant_message=assistant_message,
            structured_payload=payload,
            sql_draft=sql_draft,
            sql_draft_version=session.sql_draft_version,
        )

    def _build_structured_payload(
        self,
        intent: IntentPayload,
        semantic: SemanticMappingPayload,
        sql: str | None,
        validation_warnings: list[str],
        validation_errors: list[str],
        dialect: str,
    ) -> StructuredPayload:
        tables_used = self._derive_table_usage(semantic)
        warnings = list(dict.fromkeys([*semantic.warnings, *validation_warnings, *validation_errors]))
        return StructuredPayload(
            interpretation=self._build_interpretation(intent),
            tables_used=tables_used,
            sql=sql,
            warnings=warnings,
            needs_clarification=False,
            clarification_question=None,
            clarification_options=None,
            dialect=dialect,
        )

    def _build_interpretation(self, intent: IntentPayload) -> Interpretation:
        return Interpretation(
            metric=intent.metric,
            dimensions=list(intent.dimensions or []),
            date_range=intent.date_range,
            filters=list(intent.filters or []),
            comparison=intent.comparison,
            ambiguities=list(intent.ambiguities or []),
            confidence=float(intent.confidence or 0.0),
        )

    def _derive_table_usage(self, semantic: SemanticMappingPayload) -> list[TableUsage]:
        reasons: "OrderedDict[str, list[str]]" = OrderedDict()

        def add(table: str | None, reason: str) -> None:
            if not table:
                return
            key = str(table)
            reasons.setdefault(key, [])
            if reason not in reasons[key]:
                reasons[key].append(reason)

        add(semantic.base_table, "основная таблица метрики")
        alias_map = self._build_alias_map(semantic)

        for mapping in semantic.dimension_mappings:
            if mapping.requires_join:
                add(mapping.requires_join, f"нужна для измерения «{mapping.label}»")

        for mapping in semantic.filter_mappings:
            if mapping.requires_join:
                add(mapping.requires_join, f"нужна для фильтра «{mapping.field}»")

        if semantic.metric_expression:
            for alias, _column in re.findall(r"\b([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)\b", semantic.metric_expression):
                table = alias_map.get(alias, alias)
                add(table, "используется в выражении метрики")

        for table in semantic.tables:
            add(table, "используется в семантическом слое")

        return [
            TableUsage(table=table, reason="; ".join(reasons_list))
            for table, reasons_list in reasons.items()
        ]

    def _build_alias_map(self, semantic: SemanticMappingPayload) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        if semantic.base_table:
            alias_map[semantic.base_table] = semantic.base_table
        if semantic.base_alias and semantic.base_table:
            alias_map[semantic.base_alias] = semantic.base_table
        for join in semantic.joins:
            match = re.search(
                r"\b(?:FROM|JOIN|LEFT JOIN|RIGHT JOIN|INNER JOIN|FULL JOIN)\s+([A-Za-z_][\w.]*)\s+([A-Za-z_][\w]*)",
                join,
                flags=re.IGNORECASE,
            )
            if not match:
                continue
            alias_map[match.group(2)] = match.group(1).split(".")[-1]
        return alias_map

    def _load_previous_intent(self, payload: Any | None) -> IntentPayload | None:
        if not isinstance(payload, dict):
            return None
        try:
            return IntentPayload.model_validate(payload)
        except Exception:  # noqa: BLE001
            return None

    def _build_history_text(self, messages: list[ChatMessageModel]) -> str:
        recent_messages = messages[-6:]
        if not recent_messages:
            return ""
        lines: list[str] = []
        for message in recent_messages:
            role = "user" if message.role == "user" else "assistant"
            lines.append(f"[{role}] {message.text.strip()}")
        return "\n".join(lines)

    def _load_dictionary_entries(self, db: Session) -> list[DictionaryEntryRead]:
        return [
            DictionaryEntryRead.model_validate(entry)
            for entry in self.dictionary_service.list_entries(db)
        ]
