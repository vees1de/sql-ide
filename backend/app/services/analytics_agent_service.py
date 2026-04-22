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
    SemanticComparisonPayload,
    SemanticFlagsPayload,
    SemanticMetricPayload,
    SemanticTimePayload,
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
    validation_errors: list[str]
    validation_warnings: list[str]
    clarification: ClarificationResponse | None
    dashboard_recommendation: DashboardRecommendationResponse | None
    status: str
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
        database_id = context.database or settings.demo_database_id
        catalog_context = self.semantic_catalog_service.build_retrieval_context(
            db,
            database_id,
            normalized_query,
            base_dictionary_entries,
        )
        schema = catalog_context.schema
        dialect = schema.dialect
        allowed_tables = [table.name for table in schema.tables]
        catalog_dictionary_entries = [
            DictionaryEntryRead.model_validate(entry) for entry in catalog_context.dictionary_entries
        ]
        dictionary_entries = self._merge_dictionary_entries(base_dictionary_entries, catalog_dictionary_entries)
        previous_intent = self._resolve_previous_intent(db, context)

        intent = self.intent_agent.run(normalized_query, previous_intent=previous_intent)
        intent = self._apply_context(intent, context)

        if answers:
            intent = apply_answers(intent, answers)

        if self._needs_clarification(intent, schema, skip_confidence_check=bool(answers)):
            return AnalyticsPlan(
                intent=intent,
                semantic=None,
                sql=None,
                validation_errors=[],
                validation_warnings=[],
                clarification=ClarificationResponse(questions=self._build_clarification_questions(intent, schema)),
                dashboard_recommendation=self.dashboard_service.recommend(intent, context),
                status="clarification_required",
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
                validation_errors=[str(exc)],
                validation_warnings=[],
                clarification=None,
                dashboard_recommendation=self.dashboard_service.recommend(intent, context),
                status="error",
                error=str(exc),
            )

        validation = self.validation_agent.run(sql, dialect, allowed_tables=allowed_tables, schema=schema)
        if not validation.valid:
            return AnalyticsPlan(
                intent=intent,
                semantic=semantic,
                sql=None,
                validation_errors=validation.errors,
                validation_warnings=validation.warnings,
                clarification=None,
                dashboard_recommendation=self.dashboard_service.recommend(intent, context),
                status="error",
                error="; ".join(validation.errors) if validation.errors else "SQL validation failed.",
            )

        return AnalyticsPlan(
            intent=intent,
            semantic=semantic,
            sql=validation.sql,
            validation_errors=validation.errors,
            validation_warnings=validation.warnings,
            clarification=None,
            dashboard_recommendation=self.dashboard_service.recommend(intent, context),
            status="success",
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
        database_id = context.database or settings.demo_database_id
        catalog_context = self.semantic_catalog_service.build_retrieval_context(
            db,
            database_id,
            "",
            base_dictionary_entries,
        )
        return {
            "schema": catalog_context.schema,
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

    def _build_chart(self, intent: IntentPayload, semantic: Any, execution: Any) -> ChartSpec:
        semantics = QuerySemantics(
            intent="comparison" if getattr(intent, "comparison", None) else None,
            metric=SemanticMetricPayload(name=intent.metric, aggregation="sum") if intent.metric else None,
            dimensions=[{"name": dimension, "role": "category"} for dimension in intent.dimensions],
            time=SemanticTimePayload(column=None, granularity=None, range=intent.date_range) if intent.date_range else None,
            comparison=SemanticComparisonPayload(
                kind="period_over_period" if intent.comparison in {"previous_year", "previous_period"} else "entity_vs_entity",
                entities=[],
                series_column="comparison_series" if intent.comparison in {"previous_year", "previous_period"} else None,
            )
            if intent.comparison
            else None,
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
            rule_id=decision.rule_id,
            confidence=decision.confidence,
        )

    def _apply_context(self, intent: IntentPayload, context: AnalyticsContext) -> IntentPayload:
        patched = intent.model_copy(deep=True)
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
                    text="How should the result be grouped?",
                    options=self._dimension_options(schema),
                )
            )

        if not intent.date_range:
            questions.append(
                ClarificationQuestion(
                    id="time_range",
                    text="Which time range should we use?",
                    options=["Last 30 days", "Last 90 days", "Year to date", "All time"],
                )
            )

        if not questions:
            questions.append(
                ClarificationQuestion(
                    id="metric",
                    text="What metric do you want to analyze?",
                    options=["Revenue", "Number of orders", "Average order value"],
                )
            )
        return questions[:3]

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
