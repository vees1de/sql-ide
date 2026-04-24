from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.agents.clarification import ClarificationAgent
from app.agents.insight import InsightAgent
from app.agents.intent import IntentAgent
from app.agents.semantic import SemanticMappingAgent
from app.agents.sql_generation import SQLGenerationAgent
from app.agents.validation import SQLValidationAgent
from app.core.config import settings
from app.schemas.chat import AgentState
from app.schemas.analytics import (
    AnalyticsContext,
    AnalyticsQueryRequest,
    AnalyticsResponse,
    ClarificationQuestion,
    ClarificationResponse,
    DashboardMetadata,
    DashboardRecommendationResponse,
)
from app.schemas.dictionary import DictionaryEntryRead
from app.schemas.metadata import SchemaMetadataResponse
from app.schemas.query import (
    ClarificationAnswerRecord,
    ChartSpec,
    IntentPayload,
    QueryExecutionResult,
    QuerySemantics,
    SemanticColumnRolePayload,
    SemanticComparisonPayload,
    SemanticDataRolesPayload,
    SemanticFlagsPayload,
    SemanticMetricPayload,
    SemanticTimePayload,
    ValidationPayload,
)
from app.services.analytics import AnalyticsExecutionService
from app.services.clarification_resolver import apply_answers
from app.services.chart_data_adapter import ChartDataAdapter
from app.services.chart_decision_service import ChartDecisionService
from app.services.dashboard_recommendation_service import DashboardRecommendationService
from app.services.database_resolution import resolve_allowed_tables, resolve_dialect
from app.services.dictionary_service import DictionaryService
from app.services.metadata_service import MetadataService
from app.services.notebook_service import NotebookService
from app.services.schema_context_provider import SchemaContextProvider
from app.services.semantic_catalog_service import SemanticCatalogService


logger = logging.getLogger(__name__)


@dataclass
class AnalyticsPlan:
    intent: IntentPayload
    semantic: Any
    sql: str | None
    dialect: str
    validation_errors: list[str]
    validation_warnings: list[str]
    validation: ValidationPayload | None
    clarification: ClarificationResponse | None
    dashboard_recommendation: DashboardRecommendationResponse | None
    status: str
    state: AgentState
    error: str | None = None


class AnalyticsAgentService:
    clarification_threshold = 0.7

    def __init__(self) -> None:
        self.intent_agent = IntentAgent()
        self.clarification_agent = ClarificationAgent()
        self.semantic_agent = SemanticMappingAgent()
        self.sql_generation_agent = SQLGenerationAgent()
        self.validation_agent = SQLValidationAgent()
        self.chart_decision_service = ChartDecisionService()
        self.chart_data_adapter = ChartDataAdapter()
        self.insight_agent = InsightAgent()
        self.execution_service = AnalyticsExecutionService()
        self.metadata_service = MetadataService()
        self.dictionary_service = DictionaryService()
        self.schema_provider = SchemaContextProvider()
        self.semantic_catalog_service = SemanticCatalogService()
        self.notebook_service = NotebookService()
        self.dashboard_service = DashboardRecommendationService()

    def run_query(
        self,
        db: Session,
        request: AnalyticsQueryRequest,
        answers: list[ClarificationAnswerRecord] | None = None,
    ) -> AnalyticsResponse:
        plan = self.prepare_query(db, request, answers=answers)
        if plan.status != "success" or plan.sql is None:
            return AnalyticsResponse(
                intent=plan.intent,
                sql=plan.sql,
                confidence=round(plan.intent.confidence, 4),
                clarification=plan.clarification,
                dashboard_recommendation=plan.dashboard_recommendation,
                status=plan.status,  # type: ignore[arg-type]
                error=plan.error,
            )

        try:
            execution = self.execution_service.execute(plan.sql)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SQL execution failed: %s", exc)
            return AnalyticsResponse(
                intent=plan.intent,
                sql=plan.sql,
                confidence=round(plan.intent.confidence, 4),
                clarification=plan.clarification,
                dashboard_recommendation=plan.dashboard_recommendation,
                status="error",
                error=str(exc),
            )

        chart = self._build_chart(plan.intent, plan.semantic, execution)
        insight = self.insight_agent.run(plan.intent, plan.semantic, execution)
        return AnalyticsResponse(
            intent=plan.intent,
            sql=plan.sql,
            data=execution.rows,
            chart=chart,
            insight=insight,
            confidence=max(round(plan.intent.confidence, 4), 0.0),
            dashboard_recommendation=plan.dashboard_recommendation,
            status="success",
        )

    def prepare_query(
        self,
        db: Session,
        request: AnalyticsQueryRequest,
        answers: list[ClarificationAnswerRecord] | None = None,
    ) -> AnalyticsPlan:
        context = request.context
        base_dictionary_entries = self._load_dictionary_entries(db)
        normalized_query = self._normalize_with_dictionary(request.query, base_dictionary_entries)
        database_id = context.database or settings.analytics_database_id
        fallback_schema, fallback_dialect, fallback_allowed_tables = self._resolve_schema_context(db, context)
        catalog_context = None
        semantic_catalog = None
        try:
            catalog_context = self.semantic_catalog_service.build_retrieval_context(
                db,
                database_id,
                normalized_query,
                base_dictionary_entries,
            )
        except Exception:
            catalog_context = None
        if catalog_context is not None:
            schema = catalog_context.schema_metadata
            semantic_catalog = catalog_context.catalog
            catalog_dictionary_entries = [
                DictionaryEntryRead.model_validate(entry) for entry in catalog_context.dictionary_entries
            ]
            dictionary_entries = self._merge_dictionary_entries(base_dictionary_entries, catalog_dictionary_entries)
        else:
            schema = fallback_schema
            dictionary_entries = list(base_dictionary_entries)
        dialect = fallback_dialect or schema.dialect
        allowed_tables = list(fallback_allowed_tables or [table.name for table in schema.tables])
        previous_intent = self._resolve_previous_intent(db, context)

        intent = self.intent_agent.run(normalized_query, previous_intent=previous_intent)
        intent = self._apply_context(intent, context)

        if answers:
            intent = apply_answers(intent, answers)

        unresolved_terms = self.semantic_catalog_service.resolve_intent_terms(
            intent,
            semantic_catalog,
            dictionary_entries,
        )
        if unresolved_terms.requires_clarification:
            clarification = self._build_term_clarification(intent, unresolved_terms)
            return AnalyticsPlan(
                intent=intent,
                semantic=None,
                sql=None,
                dialect=dialect,
                validation_errors=[],
                validation_warnings=[],
                validation=None,
                clarification=clarification,
                dashboard_recommendation=self.dashboard_service.recommend(intent, context),
                status="clarification_required",
                state="CLARIFYING",
            )

        if self._needs_clarification(intent, schema, skip_confidence_check=bool(answers)):
            return AnalyticsPlan(
                intent=intent,
                semantic=None,
                sql=None,
                dialect=dialect,
                validation_errors=[],
                validation_warnings=[],
                validation=None,
                clarification=ClarificationResponse(questions=self._build_clarification_questions(intent, schema)),
                dashboard_recommendation=self.dashboard_service.recommend(intent, context),
                status="clarification_required",
                state="CLARIFYING",
            )

        semantic = self.semantic_agent.run(intent, dictionary_entries, dialect, schema)
        try:
            sql = self.sql_generation_agent.run(intent, semantic)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SQL generation failed: %s", exc)
            return AnalyticsPlan(
                intent=intent,
                semantic=semantic,
                sql=None,
                dialect=dialect,
                validation_errors=[str(exc)],
                validation_warnings=[],
                validation=None,
                clarification=None,
                dashboard_recommendation=self.dashboard_service.recommend(intent, context),
                status="error",
                state="ERROR",
                error=str(exc),
            )

        validation = self.validation_agent.run(
            sql,
            dialect,
            allowed_tables=allowed_tables,
            schema=schema,
            semantic_catalog=semantic_catalog,
        )
        if not validation.valid:
            return AnalyticsPlan(
                intent=intent,
                semantic=semantic,
                sql=None,
                dialect=dialect,
                validation_errors=validation.errors,
                validation_warnings=validation.warnings,
                validation=validation,
                clarification=None,
                dashboard_recommendation=self.dashboard_service.recommend(intent, context),
                status="error",
                state="ERROR",
                error="; ".join(validation.errors) if validation.errors else "SQL validation failed.",
            )

        return AnalyticsPlan(
            intent=intent,
            semantic=semantic,
            sql=validation.sql,
            dialect=dialect,
            validation_errors=validation.errors,
            validation_warnings=validation.warnings,
            validation=validation,
            clarification=None,
            dashboard_recommendation=self.dashboard_service.recommend(intent, context),
            status="success",
            state="SQL_READY",
        )

    def recommend_dashboards(
        self,
        intent: IntentPayload,
        context: AnalyticsContext | None = None,
        dashboards: list[DashboardMetadata] | None = None,
    ) -> DashboardRecommendationResponse:
        if dashboards is None:
            return self.dashboard_service.recommend(intent, context)

        return self.dashboard_service.recommend(intent, context, dashboards)

    def list_metadata(self, db: Session, context: AnalyticsContext | None = None) -> dict[str, Any]:
        context = context or AnalyticsContext()
        base_dictionary_entries = self._load_dictionary_entries(db)
        database_id = context.database or settings.analytics_database_id
        catalog_context = self.semantic_catalog_service.build_retrieval_context(
            db,
            database_id,
            "",
            base_dictionary_entries,
        )
        return {
            "schema": catalog_context.schema_metadata,
            "dictionary": catalog_context.dictionary_entries,
            "catalog": catalog_context.catalog.model_dump(mode="json"),
            "notes": catalog_context.notes,
        }

    def _merge_dictionary_entries(
        self,
        base_entries: list[DictionaryEntryRead],
        generated_entries: list[DictionaryEntryRead],
    ) -> list[DictionaryEntryRead]:
        merged: dict[str, DictionaryEntryRead] = {}
        for entry in [*base_entries, *generated_entries]:
            merged[entry.term.lower()] = entry
        return list(merged.values())

    def _load_dictionary_entries(self, db: Session) -> list[DictionaryEntryRead]:
        entries = self.dictionary_service.list_entries(db)
        return [DictionaryEntryRead.model_validate(entry) for entry in entries]

    def _resolve_previous_intent(self, db: Session, context: AnalyticsContext) -> IntentPayload | None:
        if context.previous_intent is not None:
            if isinstance(context.previous_intent, IntentPayload):
                return context.previous_intent
            try:
                return IntentPayload.model_validate(context.previous_intent)
            except Exception:  # noqa: BLE001
                logger.warning("Failed to parse previous intent from request context.")
        if context.notebook_id:
            try:
                raw = self.notebook_service.get_last_successful_intent(db, context.notebook_id)
                if raw is not None:
                    return IntentPayload.model_validate(raw)
            except Exception:  # noqa: BLE001
                logger.warning("Failed to resolve previous notebook intent.")
                return None

    def _resolve_schema_context(
        self,
        db: Session,
        context: AnalyticsContext,
    ) -> tuple[SchemaMetadataResponse, str, list[str]]:
        database_id = context.database or settings.analytics_database_id
        schema = self.schema_provider.get_schema_for_llm(db, database_id)
        dialect = schema.dialect
        allowed_tables = [table.name for table in schema.tables]
        return schema, dialect, allowed_tables

    def _build_chart(self, intent: IntentPayload, semantic: Any, execution: Any) -> ChartSpec:
        semantic_intent = (
            "delta" if intent.comparison in {"previous_year", "previous_period"} else
            "comparison_over_time" if bool(intent.date_range or intent.dimensions) and bool(intent.comparison) else
            "ranking" if any(token in intent.raw_prompt.lower() for token in ("top", "bottom", "топ", "луч", "худ")) else
            "share" if any(token in intent.raw_prompt.lower() for token in ("доля", "share", "%", "процент")) else
            "trend" if bool(intent.date_range or intent.dimensions) else
            "comparison" if bool(intent.comparison) else
            None
        )
        analysis_mode = (
            "delta" if semantic_intent == "delta" else
            "rank" if semantic_intent == "ranking" else
            "compose" if semantic_intent in {"share", "composition_over_time"} else
            "trend" if semantic_intent == "trend" else
            "compare"
        )
        comparison_goal = (
            "delta" if semantic_intent == "delta" else
            "rank" if semantic_intent == "ranking" else
            "composition" if semantic_intent in {"share", "composition_over_time"} else
            "absolute"
        )
        semantics = QuerySemantics(
            intent=semantic_intent,
            visual_goal=(
                "compare_between_groups_over_time" if semantic_intent == "comparison_over_time" else
                "compare_deltas_between_periods" if semantic_intent == "delta" else
                "show_change_over_time" if semantic_intent == "trend" else
                "show_composition" if semantic_intent == "share" else
                "compare_ranked_categories" if semantic_intent == "ranking" else
                "compare_categories"
            ),
            analysis_mode=analysis_mode,
            time_role="primary" if bool(intent.date_range or intent.dimensions) else "none",
            comparison_goal=comparison_goal,
            preferred_mark="line" if bool(intent.date_range or intent.dimensions) else ("arc" if semantic_intent == "share" else "bar"),
            metric=SemanticMetricPayload(name=intent.metric, aggregation="sum") if intent.metric else None,
            dimensions=[{"name": dimension, "role": "category"} for dimension in intent.dimensions],
            columns=[
                *[
                    SemanticColumnRolePayload(
                        name=dimension,
                        role="dimension_time" if dimension in {"day", "week", "month", "quarter", "year"} else "dimension_series",
                    )
                    for dimension in intent.dimensions
                ],
                *([SemanticColumnRolePayload(name=intent.metric, role="metric_primary")] if intent.metric else []),
            ],
            data_roles=SemanticDataRolesPayload(
                x=intent.dimensions[0] if intent.dimensions else None,
                y=intent.metric,
                series_key="comparison_series" if intent.comparison in {"previous_year", "previous_period"} else None,
                facet_key=None,
                label=intent.dimensions[0] if intent.dimensions else None,
                value=intent.metric,
            ),
            time=SemanticTimePayload(column=None, granularity=None, range=intent.date_range) if intent.date_range else None,
            comparison=SemanticComparisonPayload(
                kind="period_over_period" if intent.comparison in {"previous_year", "previous_period"} else "entity_vs_entity",
                entities=[],
                series_column="comparison_series" if intent.comparison in {"previous_year", "previous_period"} else None,
                facet_column=None,
            )
            if intent.comparison
            else None,
            assumptions=[
                *(["Metric is aggregated using sum."] if intent.metric else []),
                *(["Time range will follow the SQL result if the user did not specify one."] if bool(intent.date_range or intent.dimensions) and not intent.date_range else []),
            ],
            ambiguities=list(intent.ambiguities or []),
            flags=SemanticFlagsPayload(
                is_time_series=bool(intent.date_range or intent.dimensions),
                is_comparison=bool(intent.comparison),
                explicit_chart_request=bool(intent.visualization_preference),
            ),
            visualization_hint=intent.visualization_preference,
            confidence_score=float(intent.confidence or 0.0),
        )
        execution_result = QueryExecutionResult(
            sql=execution.sql,
            rows=execution.rows,
            columns=execution.columns,
            row_count=execution.row_count,
            execution_time_ms=execution.execution_time_ms,
        )
        decision = self.chart_decision_service.decide(semantics, execution_result)
        chart_payload = self.chart_data_adapter.build(execution_result, decision)
        return ChartSpec(
            chart_type=decision.chart_type,
            title="Analytics Result",
            encoding=decision.encoding,
            options={"rowCount": execution.row_count},
            data=chart_payload,
            variant=decision.variant,
            explanation=decision.explanation,
            reason=decision.reason,
            rule_id=decision.rule_id,
            confidence=decision.confidence,
            semantic_intent=decision.semantic_intent,
            analysis_mode=decision.analysis_mode,
            visual_goal=decision.visual_goal,
            time_role=decision.time_role,
            comparison_goal=decision.comparison_goal,
            preferred_mark=decision.preferred_mark,
            alternatives=list(decision.alternatives),
            candidates=list(decision.candidates),
            constraints_applied=list(decision.constraints_applied),
            visual_load=decision.visual_load,
            query_interpretation=decision.query_interpretation,
            decision_summary=decision.decision_summary,
            reason_codes=list(decision.reason_codes),
        )

    def _apply_context(self, intent: IntentPayload, context: AnalyticsContext) -> IntentPayload:
        patched = intent.model_copy(deep=True)
        if not patched.dimensions:
            for dimension in context.active_dimensions:
                if dimension not in patched.dimensions:
                    patched.dimensions.append(dimension)
        if context.active_filters:
            merged_filters = {item.field: item for item in patched.filters}
            for filter_item in context.active_filters:
                merged_filters[filter_item.field] = filter_item
            patched.filters = list(merged_filters.values())
        return patched

    def _needs_clarification(
        self,
        intent: IntentPayload,
        schema: SchemaMetadataResponse,
        *,
        skip_confidence_check: bool = False,
    ) -> bool:
        if intent.clarification_question:
            return True
        if not skip_confidence_check and intent.confidence < self.clarification_threshold:
            return True
        if not intent.metric:
            return True
        if not intent.dimensions and not intent.date_range:
            return True
        if not schema.tables:
            return True
        return False

    def _build_clarification_questions(
        self,
        intent: IntentPayload,
        schema: SchemaMetadataResponse,
    ) -> list[ClarificationQuestion]:
        questions: list[ClarificationQuestion] = []

        if not intent.metric or "metric" in {item.lower() for item in intent.ambiguities}:
            clarification = self.clarification_agent.run(intent, schema=schema)
            questions.append(
                ClarificationQuestion(
                    id="metric",
                    text=clarification.question,
                    options=[option.label for option in clarification.options[:6]],
                )
            )

        if not intent.dimensions:
            questions.append(
                ClarificationQuestion(
                    id="dimension",
                    text="Как сгруппировать результат?",
                    options=self._dimension_options(schema),
                )
            )

        if not intent.date_range:
            questions.append(
                ClarificationQuestion(
                    id="time_range",
                    text="Какой временной диапазон использовать?",
                    options=["Последние 30 дней", "Последние 90 дней", "С начала года", "За всё время"],
                )
            )

        if not questions:
            questions.append(
                ClarificationQuestion(
                    id="metric",
                    text="Какую метрику нужно проанализировать?",
                    options=["Выручка", "Количество заказов", "Средний чек"],
                )
            )
        return questions[:3]

    def _build_term_clarification(
        self,
        intent: IntentPayload,
        resolution: Any,
    ) -> ClarificationResponse:
        questions: list[ClarificationQuestion] = []
        for missing in resolution.unresolved_terms[:3]:
            options = [candidate.match or candidate.term for candidate in missing.candidates[:4] if candidate.match or candidate.term]
            if not options:
                options = ["Уточнить вручную"]
            questions.append(
                ClarificationQuestion(
                    id=missing.kind,
                    text=missing.question or f"Что означает «{missing.term}» в этом запросе?",
                    options=options,
                )
            )
        if not questions:
            questions.append(
                ClarificationQuestion(
                    id="metric",
                    text=intent.clarification_question or "Уточните, что именно нужно посчитать.",
                    options=["Уточнить метрику", "Уточнить измерение", "Уточнить период"],
                )
            )
        return ClarificationResponse(questions=questions[:3])

    def _dimension_options(self, schema: SchemaMetadataResponse) -> list[str]:
        options = ["Month", "Week", "Day"]
        for table in schema.tables:
            for column in table.columns:
                name = column.name.lower()
                if name.endswith("_id") or name in {"id", "created_at", "updated_at"}:
                    continue
                if any(token in name for token in ("amount", "revenue", "total", "count", "price", "value")):
                    continue
                label = f"{table.name}.{column.name}"
                if label not in options:
                    options.append(label)
                if len(options) >= 6:
                    return options
        return options

    def _normalize_with_dictionary(self, query: str, entries: list[DictionaryEntryRead]) -> str:
        normalized = query
        replacements: list[tuple[str, str]] = []
        for entry in entries:
            canonical = entry.term.strip()
            if canonical:
                replacements.append((canonical, canonical))
            for synonym in entry.synonyms:
                synonym_text = str(synonym).strip()
                if synonym_text and synonym_text.lower() != canonical.lower():
                    replacements.append((synonym_text, canonical))

        for source, target in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
            pattern = re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE)
            normalized = pattern.sub(target, normalized)
        return normalized
