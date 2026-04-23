from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import normalize_llm_model_alias, resolve_llm_model_from_alias
from app.db.models import ChatMessageModel, ChatSessionModel
from app.schemas.analytics import AnalyticsContext, AnalyticsQueryRequest
from app.schemas.chat import (
    CreateSqlAction,
    ClarificationAnswerRequest,
    ClarificationBlock,
    ClarificationOption,
    DebugTraceStep,
    Interpretation,
    SaveReportAction,
    SemanticParse,
    SemanticTermBinding,
    ShowChartPreviewAction,
    ShowRunButtonAction,
    ShowSqlAction,
    StructuredPayload,
    TableUsage,
)
from app.schemas.dictionary import DictionaryEntryRead
from app.schemas.query import (
    ClarificationAnswerRecord,
    IntentPayload,
    QueryMode,
    SemanticMappingPayload,
    ValidationPayload,
    normalize_query_mode,
)
from app.services.chat_service import ChatService
from app.services.clarification_policy import ClarificationPolicy
from app.services.llm_service import LLMQueryPlan, LLMService
from app.services.llm_schema_recon_service import LLMSchemaReconService
from app.services.schema_truth_guard import SchemaTruthGuard
from app.services.dictionary_service import DictionaryService
from app.services.analytics_agent_service import AnalyticsAgentService
from app.services.semantic_catalog_service import SemanticCatalogService


@dataclass
class AdapterResult:
    session: ChatSessionModel
    user_message: ChatMessageModel
    assistant_message: ChatMessageModel
    structured_payload: StructuredPayload
    sql_draft: str | None
    sql_draft_version: int


@dataclass
class PreparedSqlResult:
    session: ChatSessionModel
    assistant_message: ChatMessageModel
    structured_payload: StructuredPayload
    sql_draft: str | None
    sql_draft_version: int


class ChatSqlAdapter:
    def __init__(self) -> None:
        self.chat_service = ChatService()
        self.dictionary_service = DictionaryService()
        self.analytics_agent = AnalyticsAgentService()
        self.clarification_agent = self.analytics_agent.clarification_agent
        self.clarification_policy = ClarificationPolicy()
        self.llm_service = LLMService()
        self.schema_recon_service = LLMSchemaReconService()
        self.semantic_catalog_service = SemanticCatalogService()
        self.schema_truth_guard = SchemaTruthGuard()

    def generate_response(
        self,
        db: Session,
        session_id: str,
        user_text: str,
        *,
        query_mode: QueryMode = "fast",
        llm_model_alias: str | None = None,
    ) -> AdapterResult:
        query_mode = normalize_query_mode(query_mode)
        normalized_model_alias = normalize_llm_model_alias(llm_model_alias)
        llm_model = resolve_llm_model_from_alias(normalized_model_alias)
        session = self.chat_service.get_session(db, session_id)
        if session is None:
            raise ValueError("Chat session not found.")

        previous_intent = self._load_previous_intent(session.last_intent_json)
        history_text = self._build_history_text(session.messages)
        dictionary_entries = self._load_dictionary_entries(db)
        complexity = self._classify_prompt_complexity(user_text, previous_intent)
        mode_warnings: list[str] = []

        if query_mode == "thinking":
            catalog_context = None
            thinking_dictionary_entries = list(dictionary_entries)
            try:
                catalog_context = self.semantic_catalog_service.build_retrieval_context(
                    db,
                    session.database_connection_id,
                    user_text,
                    dictionary_entries,
                )
            except Exception:
                catalog_context = None
            if catalog_context is not None:
                schema = catalog_context.schema
                catalog_dictionary_entries = [
                    DictionaryEntryRead.model_validate(entry)
                    for entry in catalog_context.dictionary_entries
                ]
                thinking_dictionary_entries = self._merge_dictionary_entries(
                    dictionary_entries,
                    catalog_dictionary_entries,
                )
            else:
                schema = self.analytics_agent.schema_provider.get_schema_for_llm(db, session.database_connection_id)
            semantic_catalog = getattr(catalog_context, "catalog", None)
            semantic_contract = getattr(catalog_context, "semantic_contract", None)
            semantic_notes = getattr(catalog_context, "notes", [])
            # Thinking mode tolerates a few retries so transient LLM planning/validation
            # failures do not immediately degrade into the rule-based clarification flow.
            for _attempt in range(5):
                plan = self._try_llm_plan(
                    db=db,
                    database_connection_id=session.database_connection_id,
                    user_text=user_text,
                    schema=schema,
                    semantic_catalog=semantic_catalog,
                    semantic_contract=semantic_contract,
                    semantic_notes=semantic_notes,
                    previous_intent=previous_intent,
                    history_text=history_text,
                    llm_model=llm_model,
                )
                if plan is None:
                    continue
                result = self._from_plan(
                    db=db,
                    session=session,
                    plan=plan,
                    schema=schema,
                    semantic_catalog=semantic_catalog,
                    semantic_contract=semantic_contract,
                    semantic_notes=semantic_notes,
                    dictionary_entries=thinking_dictionary_entries,
                    user_text=user_text,
                    previous_intent=previous_intent,
                    history_text=history_text,
                    query_mode=query_mode,
                    complexity=complexity,
                    llm_model=llm_model,
                    llm_model_alias=normalized_model_alias,
                )
                if result is not None:
                    return result

        plan = self.analytics_agent.prepare_query(
            db,
            AnalyticsQueryRequest(
                query=user_text,
                context=AnalyticsContext(
                    previous_intent=previous_intent,
                    database=session.database_connection_id,
                    notebook_id=None,
                ),
            ),
        )

        if plan.status == "clarification_required" and plan.clarification is not None:
            payload = self._build_clarification_payload(
                intent=plan.intent,
                clarification=plan.clarification,
                query_mode=query_mode,
                complexity=complexity,
                llm_model_alias=normalized_model_alias,
                dialect=plan.dialect,
            )
            assistant_text = payload.assistant_message or payload.clarification_question or "Нужны дополнительные детали."
            return self._persist_result(
                db=db,
                session=session,
                user_text=user_text,
                intent=plan.intent,
                payload=payload,
                sql_draft=None,
                assistant_text=assistant_text,
                commit_updates=True,
            )

        plan_actions = list(getattr(plan, "actions", []) or [])

        if plan.status == "error" or (plan.sql is None and not (plan.assistant_message or plan_actions)):
            payload = self._build_structured_payload(
                state=plan.state,
                intent=plan.intent,
                semantic=plan.semantic,
                sql=None,
                validation_warnings=plan.validation_warnings,
                validation_errors=plan.validation_errors,
                validation=plan.validation,
                dialect=plan.dialect,
                query_mode=query_mode,
                complexity=complexity,
                mode_warnings=mode_warnings,
                llm_model_alias=normalized_model_alias,
                assistant_message=plan.error or (
                    plan.validation_errors[0] if plan.validation_errors else "Не удалось безопасно подготовить SQL."
                ),
                actions=plan_actions,
            )
            assistant_text = payload.assistant_message or "Не удалось безопасно подготовить SQL."
            return self._persist_result(
                db=db,
                session=session,
                user_text=user_text,
                intent=plan.intent,
                payload=payload,
                sql_draft=None,
                assistant_text=assistant_text,
                commit_updates=True,
            )

        payload = self._build_structured_payload(
            state=plan.state,
            intent=plan.intent,
            semantic=plan.semantic,
            sql=plan.sql,
            validation_warnings=plan.validation_warnings,
            validation_errors=plan.validation_errors,
            validation=plan.validation,
            dialect=plan.dialect,
            query_mode=query_mode,
            complexity=complexity,
            mode_warnings=mode_warnings,
            llm_model_alias=normalized_model_alias,
            assistant_message=self._build_assistant_text(query_mode, complexity),
            actions=plan_actions,
        )
        assistant_text = payload.assistant_message or self._build_assistant_text(query_mode, complexity)
        return self._persist_result(
            db=db,
            session=session,
            user_text=user_text,
            intent=plan.intent,
            payload=payload,
            sql_draft=plan.sql,
            assistant_text=assistant_text,
            commit_updates=True,
        )

    def answer_clarification(
        self,
        db: Session,
        session_id: str,
        clarification_id: str,
        answer: ClarificationAnswerRequest,
    ) -> AdapterResult:
        session = self.chat_service.get_session(db, session_id)
        if session is None:
            raise ValueError("Chat session not found.")

        previous_intent = self._load_previous_intent(session.last_intent_json)
        if previous_intent is None:
            raise ValueError("No clarification context found for this chat session.")

        last_payload = self._latest_assistant_payload(session.messages)
        clarification_payload = last_payload.get("clarification") or {}
        raw_options = clarification_payload.get("options") or last_payload.get("clarification_options") or []
        selected_option = next(
            (
                option for option in raw_options
                if str((option or {}).get("id") or "").strip() == str(answer.selected_option_id or "").strip()
            ),
            None,
        )
        selected_label = str((selected_option or {}).get("label") or "").strip() or None
        ambiguity_type = str(clarification_payload.get("ambiguity_type") or "other")
        answer_record = ClarificationAnswerRecord(
            clarification_id=clarification_id,
            ambiguity_type=ambiguity_type,
            option_id=answer.selected_option_id,
            option_label=selected_label,
            text_answer=answer.text_answer,
        )

        query_mode = normalize_query_mode(last_payload.get("query_mode"))
        llm_model_alias = normalize_llm_model_alias(last_payload.get("llm_model_alias"))
        complexity = self._classify_prompt_complexity(previous_intent.raw_prompt, previous_intent)
        plan = self.analytics_agent.prepare_query(
            db,
            AnalyticsQueryRequest(
                query=previous_intent.raw_prompt,
                context=AnalyticsContext(
                    previous_intent=previous_intent,
                    database=session.database_connection_id,
                    notebook_id=None,
                ),
            ),
            answers=[answer_record],
        )

        if plan.state == "CLARIFYING":
            payload = self._build_clarification_payload(
                intent=plan.intent,
                clarification=plan.clarification,
                query_mode=query_mode,
                complexity=complexity,
                llm_model_alias=llm_model_alias,
                dialect=self._resolve_dialect_from_payload(last_payload),
                answered_clarification_id=clarification_id,
            )
            assistant_text = payload.assistant_message or payload.clarification_question or "Нужно дополнительное уточнение."
            return self._persist_result(
                db=db,
                session=session,
                user_text=answer.text_answer or selected_label or answer.selected_option_id or "",
                intent=plan.intent,
                payload=payload,
                sql_draft=None,
                assistant_text=assistant_text,
                commit_updates=True,
            )

        if plan.state == "ERROR" or plan.sql is None:
            payload = self._build_structured_payload(
                state=plan.state,
                intent=plan.intent,
                semantic=plan.semantic,
                sql=None,
                validation_warnings=plan.validation_warnings,
                validation_errors=plan.validation_errors,
                validation=plan.validation,
                dialect=self._resolve_dialect_from_payload(last_payload),
                query_mode=query_mode,
                complexity=complexity,
                mode_warnings=[],
                llm_model_alias=llm_model_alias,
                assistant_message=plan.error or "Не удалось безопасно подготовить SQL после уточнения.",
                answered_clarification_id=clarification_id,
                actions=plan_actions,
            )
            assistant_text = payload.assistant_message or "Не удалось подготовить SQL."
            return self._persist_result(
                db=db,
                session=session,
                user_text=answer.text_answer or selected_label or answer.selected_option_id or "",
                intent=plan.intent,
                payload=payload,
                sql_draft=None,
                assistant_text=assistant_text,
                commit_updates=True,
            )

        payload = self._build_structured_payload(
            state=plan.state,
            intent=plan.intent,
            semantic=plan.semantic,
            sql=plan.sql,
            validation_warnings=plan.validation_warnings,
            validation_errors=plan.validation_errors,
            validation=plan.validation,
            dialect=self._resolve_dialect_from_payload(last_payload),
            query_mode=query_mode,
            complexity=complexity,
            mode_warnings=[],
            llm_model_alias=llm_model_alias,
            assistant_message=self._build_assistant_text(query_mode, complexity),
            answered_clarification_id=clarification_id,
            actions=plan_actions,
        )
        assistant_text = payload.assistant_message or "SQL готов."
        return self._persist_result(
            db=db,
            session=session,
            user_text=answer.text_answer or selected_label or answer.selected_option_id or "",
            intent=plan.intent,
            payload=payload,
            sql_draft=plan.sql,
            assistant_text=assistant_text,
            commit_updates=True,
        )

    def _try_llm_plan(
        self,
        db: Session,
        database_connection_id: str,
        user_text: str,
        schema,
        semantic_catalog,
        semantic_contract,
        semantic_notes: list[str],
        previous_intent: IntentPayload | None,
        history_text: str,
        llm_model: str,
    ) -> LLMQueryPlan | None:
        return self.llm_service.plan_query(
            prompt=user_text,
            schema=schema,
            semantic_catalog=semantic_catalog,
            semantic_contract=semantic_contract,
            semantic_notes=semantic_notes,
            previous_intent=previous_intent,
            history_text=history_text,
            temperature=0.0,
            model=llm_model,
            schema_toolbox=self.schema_recon_service.build_toolbox(db, database_connection_id),
        )

    def _from_plan(
        self,
        db: Session,
        session: ChatSessionModel,
        plan: LLMQueryPlan,
        schema,
        semantic_catalog,
        semantic_contract,
        semantic_notes: list[str],
        dictionary_entries: list[DictionaryEntryRead],
        user_text: str,
        previous_intent: IntentPayload | None,
        history_text: str,
        query_mode: QueryMode,
        complexity: str,
        llm_model: str,
        llm_model_alias: str,
    ) -> AdapterResult | None:
        intent = plan.intent
        mode_warnings: list[str] = []
        if intent.clarification_question and not plan.sql:
            if query_mode == "fast":
                intent, mode_warnings = self._apply_fast_mode_defaults(intent, previous_intent)
                if complexity == "complex":
                    mode_warnings.append("Сложный запрос выполнен в Fast режиме. Результат может быть приближённым.")
            else:
                suppression = self.clarification_policy.should_suppress(
                    prompt=user_text,
                    intent=intent,
                    question=intent.clarification_question,
                )
                if suppression.suppress:
                    return None
                if self.schema_truth_guard.clarification_conflicts_with_schema_truth(
                    question=intent.clarification_question,
                    contract=semantic_contract,
                ):
                    return None
                return self._build_llm_clarification_result(
                    db=db,
                    session=session,
                    intent=intent,
                    user_text=user_text,
                    dialect=schema.dialect,
                    schema=schema,
                    query_mode=query_mode,
                    complexity=complexity,
                    llm_model_alias=llm_model_alias,
                )
        if not plan.sql:
            if plan.assistant_message or getattr(plan, "actions", None):
                explanation_actions = plan_actions or [
                    CreateSqlAction(
                        label="Выгрузить таблицу",
                        primary=True,
                        disabled=False,
                        payload={"reason": "Prepare a table export from the current chat context."},
                    )
                ]
                payload = self._build_structured_payload(
                    state=plan.state or "SQL_DRAFTING",
                    intent=intent,
                    semantic=None,
                    sql=None,
                    actions=explanation_actions,
                    validation_warnings=list(dict.fromkeys([*getattr(plan, "warnings", [])])),
                    validation_errors=[],
                    validation=None,
                    dialect=schema.dialect,
                    query_mode=query_mode,
                    complexity=complexity,
                    mode_warnings=mode_warnings,
                    llm_model_alias=llm_model_alias,
                    assistant_message=plan.assistant_message or self._build_assistant_text(query_mode, complexity),
                )
                assistant_text = payload.assistant_message or self._build_assistant_text(query_mode, complexity)
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
            return None
        semantic = self.analytics_agent.semantic_agent.run(
            intent,
            dictionary_entries,
            schema.dialect,
            schema,
        )
        validation = self._validate_llm_sql(
            db=db,
            session=session,
            user_text=user_text,
            history_text=history_text,
            previous_intent=previous_intent,
            sql=plan.sql,
            schema=schema,
            semantic_catalog=semantic_catalog,
            semantic_notes=semantic_notes,
            llm_model=llm_model,
        )
        if validation is None or not validation.valid:
            return None
        payload = self._build_structured_payload(
            state=plan.state or ("SQL_READY" if validation.sql else "ERROR"),
            intent=intent,
            semantic=semantic,
            sql=validation.sql,
            actions=plan_actions or None,
            validation_warnings=list(dict.fromkeys([*getattr(plan, "warnings", [])])),
            validation_errors=[],
            validation=validation,
            dialect=schema.dialect,
            query_mode=query_mode,
            complexity=complexity,
            mode_warnings=mode_warnings,
            llm_model_alias=llm_model_alias,
            assistant_message=plan.assistant_message or self._build_assistant_text(query_mode, complexity),
        )
        assistant_text = payload.assistant_message or self._build_assistant_text(query_mode, complexity)
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

    def prepare_sql(self, db: Session, session_id: str) -> PreparedSqlResult:
        session = self.chat_service.get_session(db, session_id)
        if session is None:
            raise ValueError("Chat session not found.")

        previous_intent = self._load_previous_intent(session.last_intent_json)
        if previous_intent is None:
            raise ValueError("No prior intent found for this chat session.")

        latest_payload = self._latest_assistant_payload(session.messages)
        query_mode = normalize_query_mode(latest_payload.get("query_mode"))
        llm_model_alias = normalize_llm_model_alias(latest_payload.get("llm_model_alias"))
        llm_model = resolve_llm_model_from_alias(llm_model_alias) if llm_model_alias else settings.llm_model
        complexity = self._classify_prompt_complexity(previous_intent.raw_prompt, previous_intent)
        schema = self.analytics_agent.schema_provider.get_schema_for_llm(db, session.database_connection_id)
        history_text = self._build_history_text(session.messages)
        dictionary_entries = self._load_dictionary_entries(db)
        semantic_catalog = None
        semantic_contract = None
        semantic_notes: list[str] = []

        try:
            catalog_context = self.semantic_catalog_service.build_retrieval_context(
                db,
                session.database_connection_id,
                previous_intent.raw_prompt,
                dictionary_entries,
            )
            semantic_catalog = getattr(catalog_context, "catalog", None)
            semantic_contract = getattr(catalog_context, "semantic_contract", None)
            semantic_notes = list(getattr(catalog_context, "notes", []) or [])
            dictionary_entries = self._merge_dictionary_entries(
                dictionary_entries,
                [DictionaryEntryRead.model_validate(entry) for entry in getattr(catalog_context, "dictionary_entries", [])],
            )
        except Exception:  # noqa: BLE001
            pass

        plan = self.analytics_agent.prepare_query(
            db,
            AnalyticsQueryRequest(
                query=previous_intent.raw_prompt,
                context=AnalyticsContext(
                    previous_intent=previous_intent,
                    database=session.database_connection_id,
                    notebook_id=None,
                ),
            ),
        )
        if plan.status != "success" or plan.sql is None:
            raise ValueError("Unable to prepare SQL from the current chat context.")

        semantic = self.analytics_agent.semantic_agent.run(
            plan.intent,
            dictionary_entries,
            schema.dialect,
            schema,
        )
        validation = self._validate_llm_sql(
            db=db,
            session=session,
            user_text=previous_intent.raw_prompt,
            history_text=history_text,
            previous_intent=previous_intent,
            sql=plan.sql,
            schema=schema,
            semantic_catalog=semantic_catalog,
            semantic_notes=semantic_notes,
            llm_model=llm_model,
        )
        if validation is None or not validation.valid:
            raise ValueError("Unable to validate prepared SQL from the current chat context.")

        payload = self._build_structured_payload(
            state="SQL_READY",
            intent=plan.intent,
            semantic=semantic,
            sql=validation.sql,
            actions=None,
            validation_warnings=list(dict.fromkeys([*getattr(plan, "warnings", [])])),
            validation_errors=[],
            validation=validation,
            dialect=schema.dialect,
            query_mode=query_mode,
            complexity=complexity,
            mode_warnings=[],
            llm_model_alias=llm_model_alias,
            assistant_message=plan.assistant_message or self._build_assistant_text(query_mode, complexity),
        )
        assistant_message = self.chat_service.append_message(
            db,
            session,
            "assistant",
            payload.assistant_message or "SQL готов. Он не будет выполнен автоматически.",
            structured_payload=payload,
            commit=False,
        )
        session.last_intent_json = plan.intent.model_dump(mode="json")
        session.current_sql_draft = validation.sql
        session.sql_draft_version = (session.sql_draft_version or 0) + 1
        db.commit()
        db.refresh(session)
        db.refresh(assistant_message)
        return PreparedSqlResult(
            session=session,
            assistant_message=assistant_message,
            structured_payload=payload,
            sql_draft=validation.sql,
            sql_draft_version=session.sql_draft_version,
        )

    def _validate_llm_sql(
        self,
        *,
        db: Session,
        session: ChatSessionModel,
        user_text: str,
        history_text: str,
        previous_intent: IntentPayload | None,
        sql: str,
        schema,
        semantic_catalog,
        semantic_notes: list[str],
        llm_model: str,
    ) -> ValidationPayload | None:
        allowed_tables = [table.name for table in schema.tables]
        validation = self.analytics_agent.validation_agent.run(
            sql,
            schema.dialect,
            allowed_tables=allowed_tables,
            schema=schema,
            semantic_catalog=semantic_catalog,
        )
        if validation.valid:
            return validation

        repaired = self.llm_service.repair_sql(
            prompt=user_text,
            schema=schema,
            failed_sql=sql,
            failure_reason="; ".join(validation.errors) or "SQL validation failed.",
            semantic_catalog=semantic_catalog,
            semantic_notes=semantic_notes,
            previous_intent=previous_intent,
            history_text=history_text,
            attempt_index=1,
            model=llm_model,
            schema_toolbox=self.schema_recon_service.build_toolbox(db, session.database_connection_id),
        )
        if repaired is None or not repaired.retryable or not repaired.sql:
            return None

        return self.analytics_agent.validation_agent.run(
            repaired.sql,
            schema.dialect,
            allowed_tables=allowed_tables,
            schema=schema,
            semantic_catalog=semantic_catalog,
        )

    def _build_llm_clarification_result(
        self,
        db: Session,
        session: ChatSessionModel,
        intent: IntentPayload,
        user_text: str,
        dialect: str,
        schema,
        query_mode: QueryMode,
        complexity: str,
        llm_model_alias: str | None,
    ) -> AdapterResult:
        llm_options = list(intent.clarification_options or [])
        if llm_options:
            ambiguity_type = self._infer_clarification_ambiguity(intent)
            options = [
                self._normalize_clarification_option(
                    ClarificationOption(
                        id=(option.id or option.label or f"option-{index + 1}"),
                        label=option.label or option.id or f"Вариант {index + 1}",
                        detail=getattr(option, "detail", None),
                        reason=getattr(option, "reason", None),
                    ),
                    ambiguity_type=ambiguity_type,
                )
                for index, option in enumerate(llm_options)
            ]
        else:
            return self._build_clarification_result(
                db=db,
                session=session,
                intent=intent,
                schema=schema,
                user_text=user_text,
                dialect=dialect,
                commit_updates=True,
                query_mode=query_mode,
                complexity=complexity,
                llm_model_alias=llm_model_alias,
            )
        payload = StructuredPayload(
            state="CLARIFYING",
            assistant_message=intent.clarification_question or "Нужны дополнительные детали.",
            semantic_parse=self._build_semantic_parse(intent=intent, semantic=None),
            actions=self._build_actions(state="CLARIFYING", sql=None),
            interpretation=self._build_interpretation(intent),
            tables_used=[],
            sql=None,
            warnings=list(dict.fromkeys([*(intent.ambiguities or [])])),
            debug_trace=[
                DebugTraceStep(
                    stage="clarification",
                    status="warning",
                    code="llm_clarification_requested",
                    detail=intent.clarification_question or "LLM requested clarification.",
                )
            ],
            message_kind="clarification",
            clarification=self._build_clarification_block(
                clarification_id="clarification:pending",
                question=intent.clarification_question,
                ambiguity_type=ambiguity_type,
                options=options,
            ),
            needs_clarification=True,
            clarification_question=intent.clarification_question,
            clarification_options=options or None,
            dialect=dialect,
            query_mode=query_mode,
            llm_model_alias=llm_model_alias,
            complexity=complexity,
            mode_suggestion=None,
            mode_suggestion_reason=None,
        )
        assistant_text = payload.assistant_message or payload.clarification_question or "Нужны дополнительные детали."
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

    def _build_clarification_payload(
        self,
        intent: IntentPayload,
        clarification: Any,
        query_mode: QueryMode,
        complexity: str,
        llm_model_alias: str | None,
        dialect: str,
        answered_clarification_id: str | None = None,
    ) -> StructuredPayload:
        first_question = clarification.questions[0] if getattr(clarification, "questions", None) else None
        ambiguity_type = self._infer_clarification_ambiguity(intent, first_question=getattr(first_question, "id", None))
        options = [
            self._normalize_clarification_option(
                ClarificationOption(
                    id=option if isinstance(option, str) else option.label,
                    label=option if isinstance(option, str) else option.label,
                    detail=None,
                ),
                ambiguity_type=ambiguity_type,
            )
            for option in getattr(first_question, "options", [])[:6]
        ] if first_question else []
        return StructuredPayload(
            state="CLARIFYING",
            assistant_message=getattr(first_question, "text", None) or intent.clarification_question or "Нужны дополнительные детали.",
            semantic_parse=self._build_semantic_parse(intent=intent, semantic=None),
            actions=self._build_actions(state="CLARIFYING", sql=None),
            interpretation=self._build_interpretation(intent),
            tables_used=[],
            sql=None,
            warnings=list(dict.fromkeys([*(intent.ambiguities or [])])),
            debug_trace=[
                DebugTraceStep(
                    stage="clarification",
                    status="warning",
                    code="rule_clarification_requested",
                    detail=getattr(first_question, "text", None) or intent.clarification_question or "Clarification requested.",
                )
            ],
            message_kind="clarification",
            clarification=self._build_clarification_block(
                clarification_id=getattr(first_question, "id", None) or "clarification:pending",
                question=getattr(first_question, "text", None) or intent.clarification_question,
                ambiguity_type=ambiguity_type,
                options=options,
                answered_clarification_id=answered_clarification_id,
            ),
            needs_clarification=True,
            clarification_question=getattr(first_question, "text", None) or intent.clarification_question,
            clarification_options=options or None,
            answered_clarification_id=answered_clarification_id,
            dialect=dialect,
            query_mode=query_mode,
            llm_model_alias=llm_model_alias,
            complexity=complexity,
            mode_suggestion=None,
            mode_suggestion_reason=None,
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
        query_mode: QueryMode = "thinking",
        complexity: str = "complex",
        llm_model_alias: str | None = None,
    ) -> AdapterResult:
        clarification = self.clarification_agent.run(intent, schema=schema)
        question = self._clarification_value(clarification, "question") or intent.clarification_question
        raw_options = self._clarification_value(clarification, "options", []) or []
        ambiguity_type = self._infer_clarification_ambiguity(intent)
        options = [
            self._normalize_clarification_option(
                ClarificationOption(
                    id=self._clarification_value(option, "id") or f"option-{index + 1}",
                    label=self._clarification_value(option, "label") or str(option),
                    detail=self._clarification_value(option, "detail"),
                    reason=self._clarification_value(option, "reason"),
                ),
                ambiguity_type=ambiguity_type,
            )
            for index, option in enumerate(raw_options)
        ]
        payload = StructuredPayload(
            state="CLARIFYING",
            assistant_message=question or "Нужны дополнительные детали.",
            semantic_parse=self._build_semantic_parse(intent=intent, semantic=None),
            actions=self._build_actions(state="CLARIFYING", sql=None),
            interpretation=self._build_interpretation(intent),
            tables_used=[],
            sql=None,
            warnings=list(dict.fromkeys([*(intent.ambiguities or [])])),
            debug_trace=[
                DebugTraceStep(
                    stage="clarification",
                    status="warning",
                    code="clarification_agent_requested",
                    detail=question or "Clarification requested.",
                )
            ],
            message_kind="clarification",
            clarification=self._build_clarification_block(
                clarification_id="clarification:pending",
                question=question,
                ambiguity_type=ambiguity_type,
                options=options,
            ),
            needs_clarification=True,
            clarification_question=question,
            clarification_options=options or None,
            dialect=dialect,
            query_mode=query_mode,
            llm_model_alias=llm_model_alias,
            complexity=complexity,
            mode_suggestion=None,
            mode_suggestion_reason=None,
        )
        assistant_text = payload.assistant_message or payload.clarification_question or "Нужны дополнительные детали."
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

    @staticmethod
    def _clarification_value(source: Any, key: str, default: Any | None = None) -> Any | None:
        if source is None:
            return default
        if isinstance(source, dict):
            return source.get(key, default)
        return getattr(source, key, default)

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
        elif payload.state in {"CLARIFYING", "ERROR"} and session.current_sql_draft is not None:
            session.current_sql_draft = None
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

    def _apply_fast_mode_defaults(
        self,
        intent: IntentPayload,
        previous_intent: IntentPayload | None,
    ) -> tuple[IntentPayload, list[str]]:
        adjusted = intent.model_copy(deep=True)
        warnings: list[str] = []

        if adjusted.metric is None:
            fallback_metric = previous_intent.metric if previous_intent and previous_intent.metric else "revenue"
            adjusted.metric = fallback_metric
            warnings.append(f"Метрика не указана явно. В Fast режиме выбрана «{fallback_metric}».")

        if adjusted.clarification_question:
            warnings.append("Clarification пропущен для ускорения ответа в Fast режиме.")
        adjusted.clarification_question = None
        adjusted.ambiguities = []
        adjusted.confidence = max(0.45, adjusted.confidence - 0.05)
        return adjusted, warnings

    def _classify_prompt_complexity(
        self,
        prompt: str,
        previous_intent: IntentPayload | None,
    ) -> str:
        lowered = prompt.lower()
        score = 0
        if len(prompt) > 120:
            score += 1
        markers = (
            "compare",
            "vs",
            "growth",
            "trend",
            "anomaly",
            "cohort",
            "retention",
            "против",
            "сравн",
            "рост",
            "динам",
            "аномал",
            "когорт",
        )
        if any(marker in lowered for marker in markers):
            score += 2
        if any(token in lowered for token in (" and ", " и ", " against ", " между ", "по сравнению")):
            score += 1
        if previous_intent and previous_intent.follow_up:
            score += 1
        return "complex" if score >= 3 else "simple"

    def _build_assistant_text(self, query_mode: QueryMode, complexity: str) -> str:
        if query_mode == "fast":
            if complexity == "complex":
                return "SQL быстро подготовлен в Fast режиме. Для более точной интерпретации можно переключиться на Thinking."
            return "SQL быстро подготовлен в Fast режиме. Запуск останется ручным."
        return "SQL подготовлен в Thinking режиме с более глубокой интерпретацией. Запуск останется ручным."

    def _build_structured_payload(
        self,
        state: str,
        intent: IntentPayload,
        semantic: SemanticMappingPayload | None,
        sql: str | None,
        actions: list[Any] | None,
        validation_warnings: list[str],
        validation_errors: list[str],
        validation: ValidationPayload | None,
        dialect: str,
        query_mode: QueryMode,
        complexity: str,
        mode_warnings: list[str] | None = None,
        llm_model_alias: str | None = None,
        assistant_message: str | None = None,
        answered_clarification_id: str | None = None,
    ) -> StructuredPayload:
        semantic_warnings = list(getattr(semantic, "warnings", []) or [])
        tables_used = self._derive_table_usage(semantic) if semantic is not None else []
        warnings = list(
            dict.fromkeys(
                [
                    *semantic_warnings,
                    *((validation.warnings if validation is not None else [])),
                    *((validation.errors if validation is not None else [])),
                    *validation_warnings,
                    *validation_errors,
                    *(mode_warnings or []),
                ]
            )
        )
        mode_suggestion = "thinking" if query_mode == "fast" and complexity == "complex" else None
        mode_suggestion_reason = (
            "Запрос выглядит сложным: для более точной интерпретации лучше использовать Thinking режим."
            if mode_suggestion == "thinking"
            else None
        )
        confidence_level = self._confidence_level(validation, intent.confidence)
        confidence_reasons = list(getattr(validation, "semantic_confidence_reasons", []) or [])
        if confidence_level == "low":
            warnings = list(
                dict.fromkeys(
                    [
                        "Низкая уверенность в семантической интерпретации. Проверьте метрику и JOIN перед запуском.",
                        *warnings,
                    ]
                )
            )
        return StructuredPayload(
            state="SQL_READY" if state == "success" else state,  # backward-compat safety
            assistant_message=assistant_message or self._build_default_assistant_message(state=state, sql=sql),
            semantic_parse=self._build_semantic_parse(intent=intent, semantic=semantic),
            actions=list(actions) if actions is not None else self._build_actions(state=state, sql=sql),
            interpretation=self._build_interpretation(intent),
            tables_used=tables_used,
            sql=sql,
            warnings=warnings,
            confidence_level=confidence_level,
            confidence_reasons=confidence_reasons,
            debug_trace=self._build_debug_trace(
                intent=intent,
                semantic=semantic,
                validation=validation,
                query_mode=query_mode,
                complexity=complexity,
                warnings=warnings,
            ),
            needs_clarification=False,
            clarification_question=None,
            clarification_options=None,
            answered_clarification_id=answered_clarification_id,
            dialect=dialect,
            query_mode=query_mode,
            llm_model_alias=llm_model_alias,
            complexity=complexity,
            mode_suggestion=mode_suggestion,
            mode_suggestion_reason=mode_suggestion_reason,
        )

    def _build_debug_trace(
        self,
        *,
        intent: IntentPayload,
        semantic: SemanticMappingPayload | None,
        validation: ValidationPayload | None,
        query_mode: QueryMode,
        complexity: str,
        warnings: list[str],
    ) -> list[DebugTraceStep]:
        trace: list[DebugTraceStep] = [
            DebugTraceStep(
                stage="intent",
                status="success",
                code="intent_parsed",
                detail=(
                    f"metric={intent.metric or 'none'}; "
                    f"dimensions={','.join(intent.dimensions or []) or 'none'}; "
                    f"query_mode={query_mode}; complexity={complexity}"
                ),
            )
        ]
        if semantic is not None:
            trace.append(
                DebugTraceStep(
                    stage="semantic",
                    status="success",
                    code="semantic_mapping_built",
                    detail=(
                        f"base_table={semantic.base_table or 'none'}; "
                        f"tables={','.join(semantic.tables or []) or 'none'}"
                    ),
                )
            )
        if validation is not None:
            trace.append(
                DebugTraceStep(
                    stage="validation",
                    status="success" if validation.valid else "error",
                    code="sql_validated",
                    detail=(
                        f"valid={validation.valid}; "
                        f"confidence={validation.semantic_confidence_level or 'unknown'}"
                    ),
                )
            )
        for warning in warnings[:3]:
            trace.append(
                DebugTraceStep(
                    stage="warning",
                    status="warning",
                    code="warning",
                    detail=warning,
                )
            )
        return trace

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

    def _build_semantic_parse(
        self,
        *,
        intent: IntentPayload,
        semantic: SemanticMappingPayload | None,
    ) -> SemanticParse:
        resolved_terms: list[SemanticTermBinding] = []
        unresolved_terms: list[SemanticTermBinding] = []

        if intent.metric:
            resolved_terms.append(
                SemanticTermBinding(
                    term=intent.metric,
                    kind="metric",
                    match=getattr(semantic, "metric_expression", None) or intent.metric,
                    source="semantic_catalog" if semantic else "unknown",
                    confidence=float(intent.confidence or 0.0),
                )
            )
        for dimension in intent.dimensions:
            resolved_terms.append(
                SemanticTermBinding(
                    term=dimension,
                    kind="dimension",
                    match=dimension,
                    source="semantic_catalog" if semantic else "unknown",
                    confidence=float(intent.confidence or 0.0),
                )
            )
        for ambiguity in intent.ambiguities:
            unresolved_terms.append(
                SemanticTermBinding(
                    term=ambiguity,
                    kind="term",
                    source="unknown",
                    confidence=float(intent.confidence or 0.0),
                    note="Requires user clarification before SQL drafting.",
                )
            )

        notes: list[str] = []
        if semantic is not None and getattr(semantic, "base_table", None):
            notes.append(f"Base table: {semantic.base_table}")
        if semantic is not None and getattr(semantic, "warnings", None):
            notes.extend(list(semantic.warnings[:3]))

        return SemanticParse(
            intent_summary=self._semantic_intent_summary(intent),
            metric=intent.metric,
            dimensions=list(intent.dimensions or []),
            date_range=intent.date_range,
            filters=list(intent.filters or []),
            comparison=intent.comparison,
            resolved_terms=resolved_terms,
            unresolved_terms=unresolved_terms,
            candidate_tables=list(dict.fromkeys(getattr(semantic, "tables", []) or [])),
            notes=notes,
            confidence=float(intent.confidence or 0.0),
        )

    def _semantic_intent_summary(self, intent: IntentPayload) -> str | None:
        parts: list[str] = []
        if intent.metric:
            parts.append(f"metric={intent.metric}")
        if intent.dimensions:
            parts.append(f"dimensions={', '.join(intent.dimensions)}")
        if intent.date_range:
            parts.append(f"time={intent.date_range.kind}")
        if intent.comparison:
            parts.append(f"comparison={intent.comparison}")
        return "; ".join(parts) or None

    def _build_actions(self, *, state: str, sql: str | None) -> list[Any]:
        normalized_state = "SQL_READY" if state == "success" else state
        if normalized_state == "CLARIFYING":
            return [
                CreateSqlAction(
                    primary=False,
                    disabled=True,
                    payload={"reason": "SQL drafting is blocked until the clarification is answered."},
                ),
            ]
        if normalized_state == "SQL_READY" and sql:
            return [
                ShowRunButtonAction(),
                ShowSqlAction(),
                ShowChartPreviewAction(),
                SaveReportAction(
                    primary=False,
                    disabled=True,
                    payload={"title_suggestion": "SQL draft report"},
                ),
            ]
        return [
            CreateSqlAction(
                primary=False,
                disabled=not bool(sql),
                payload={"reason": "Agent is still preparing a valid SQL draft."},
            )
        ]

    def _build_default_assistant_message(self, *, state: str, sql: str | None) -> str:
        normalized_state = "SQL_READY" if state == "success" else state
        if normalized_state == "CLARIFYING":
            return "Нужны дополнительные детали, прежде чем готовить SQL."
        if normalized_state == "SQL_READY" and sql:
            return "SQL готов. Он не будет выполнен автоматически."
        return "Не удалось подготовить безопасный SQL."

    def _build_clarification_block(
        self,
        *,
        clarification_id: str | None,
        question: str | None,
        ambiguity_type: str,
        options: list[ClarificationOption],
        answered_clarification_id: str | None = None,
    ) -> ClarificationBlock:
        return ClarificationBlock(
            clarification_id=clarification_id or "clarification:pending",
            question=question or "Нужны дополнительные детали.",
            ambiguity_type=ambiguity_type if ambiguity_type in {"metric", "dimension", "time_range", "aggregation", "other"} else "other",
            answer_type="single_select",
            options=options,
            status="answered" if answered_clarification_id else "pending",
        )

    def _normalize_clarification_option(
        self,
        option: ClarificationOption,
        *,
        ambiguity_type: str,
    ) -> ClarificationOption:
        raw_id = str(option.id or "").strip()
        if ":" not in raw_id and ambiguity_type in {"metric", "dimension", "time_range"}:
            slug = re.sub(r"[^a-z0-9_]+", "_", raw_id.lower() or option.label.lower()).strip("_")
            option = option.model_copy(update={"id": f"{ambiguity_type}:{slug or 'option'}"})
        return option

    def _infer_clarification_ambiguity(
        self,
        intent: IntentPayload,
        *,
        first_question: str | None = None,
    ) -> str:
        if first_question in {"metric", "dimension", "time_range", "aggregation"}:
            return first_question
        ambiguities = {item.lower() for item in (intent.ambiguities or [])}
        if "metric" in ambiguities or intent.metric is None:
            return "metric"
        if "dimension" in ambiguities or not intent.dimensions:
            return "dimension"
        if "time_range" in ambiguities or intent.date_range is None:
            return "time_range"
        return "other"

    def _confidence_level(
        self,
        validation: ValidationPayload | None,
        intent_confidence: float,
    ) -> str:
        if validation is not None and validation.semantic_confidence_level:
            return validation.semantic_confidence_level
        if intent_confidence >= 0.85:
            return "high"
        if intent_confidence >= 0.6:
            return "medium"
        return "low"

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

    def _latest_assistant_payload(self, messages: list[ChatMessageModel]) -> dict[str, Any]:
        for message in reversed(messages):
            if message.role != "assistant":
                continue
            payload = getattr(message, "structured_payload", None)
            if isinstance(payload, dict):
                return payload
        return {}

    def _resolve_dialect_from_payload(self, payload: dict[str, Any]) -> str:
        return str(payload.get("dialect") or "postgresql")

    def _load_dictionary_entries(self, db: Session) -> list[DictionaryEntryRead]:
        return [
            DictionaryEntryRead.model_validate(entry)
            for entry in self.dictionary_service.list_entries(db)
        ]

    def _merge_dictionary_entries(
        self,
        base_entries: list[DictionaryEntryRead],
        generated_entries: list[DictionaryEntryRead],
    ) -> list[DictionaryEntryRead]:
        merged: dict[str, DictionaryEntryRead] = {}
        for entry in [*base_entries, *generated_entries]:
            merged[entry.term.lower()] = entry
        return list(merged.values())
