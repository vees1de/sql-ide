from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from app.schemas.analytics import (
    AnalyticsContext,
    DashboardMetadata,
    DashboardRecommendationResponse,
    ScoredDashboard,
)
from app.schemas.query import IntentPayload


@dataclass(frozen=True)
class _DashboardSignals:
    metric_match: float
    dimension_match: float
    analysis_match: float
    filter_match: float
    semantic_similarity: float
    recency: float
    popularity: float


class DashboardRecommendationService:
    def __init__(self) -> None:
        self._catalog: list[DashboardMetadata] = [
            DashboardMetadata(
                id="sales_overview",
                metrics=["revenue", "order_count"],
                dimensions=["month", "region"],
                analysis_types=["trend", "comparison"],
                tags=["sales", "finance"],
                recency=0.82,
                popularity=0.93,
            ),
            DashboardMetadata(
                id="store_performance",
                metrics=["revenue", "avg_order_value"],
                dimensions=["store", "category"],
                analysis_types=["comparison", "breakdown"],
                tags=["retail", "stores"],
                recency=0.74,
                popularity=0.88,
            ),
            DashboardMetadata(
                id="customer_mix",
                metrics=["customer_count", "revenue"],
                dimensions=["segment", "channel"],
                analysis_types=["distribution", "breakdown"],
                tags=["audience", "marketing"],
                recency=0.61,
                popularity=0.72,
            ),
        ]

    def list_dashboards(self) -> list[DashboardMetadata]:
        return list(self._catalog)

    def recommend(
        self,
        intent: IntentPayload,
        user_context: AnalyticsContext | None,
        dashboards: list[DashboardMetadata] | None = None,
    ) -> DashboardRecommendationResponse:
        candidates = dashboards or self._catalog
        scored = [self._score_dashboard(intent, user_context, dashboard) for dashboard in candidates]
        scored.sort(key=lambda item: item.score, reverse=True)
        best_match = scored[0] if scored else None
        return DashboardRecommendationResponse(
            best_match=best_match,
            alternatives=scored[1:],
        )

    def _score_dashboard(
        self,
        intent: IntentPayload,
        user_context: AnalyticsContext | None,
        dashboard: DashboardMetadata,
    ) -> ScoredDashboard:
        signals = self._calculate_signals(intent, user_context, dashboard)
        score = (
            0.35 * signals.metric_match
            + 0.20 * signals.dimension_match
            + 0.15 * signals.analysis_match
            + 0.10 * signals.filter_match
            + 0.10 * signals.semantic_similarity
            + 0.05 * signals.recency
            + 0.05 * signals.popularity
        )
        return ScoredDashboard(**dashboard.model_dump(), score=round(score, 4))

    def _calculate_signals(
        self,
        intent: IntentPayload,
        user_context: AnalyticsContext | None,
        dashboard: DashboardMetadata,
    ) -> _DashboardSignals:
        metric_match = self._overlap_score([intent.metric] if intent.metric else [], dashboard.metrics)
        dimensions = list(intent.dimensions)
        if user_context:
            dimensions.extend(user_context.active_dimensions)
        dimension_match = self._overlap_score(dimensions, dashboard.dimensions)

        analysis_tokens = [intent.comparison or "", "trend" if dimensions and any(dim in {"day", "week", "month"} for dim in dimensions) else ""]
        analysis_match = self._overlap_score(analysis_tokens, dashboard.analysis_types)

        filter_tokens = [item.field for item in (user_context.active_filters if user_context else [])]
        filter_match = self._overlap_score(filter_tokens, dashboard.tags + dashboard.dimensions)

        semantic_similarity = self._semantic_similarity(
            " ".join(
                token
                for token in [
                    intent.metric or "",
                    " ".join(intent.dimensions),
                    " ".join(filter_tokens),
                    intent.comparison or "",
                ]
                if token
            ),
            " ".join([*dashboard.metrics, *dashboard.dimensions, *dashboard.analysis_types, *dashboard.tags]),
        )

        return _DashboardSignals(
            metric_match=metric_match,
            dimension_match=dimension_match,
            analysis_match=analysis_match,
            filter_match=filter_match,
            semantic_similarity=semantic_similarity,
            recency=self._clamp(dashboard.recency),
            popularity=self._clamp(dashboard.popularity),
        )

    def _overlap_score(self, left: Iterable[str], right: Iterable[str]) -> float:
        left_tokens = {self._normalize(token) for token in left if self._normalize(token)}
        right_tokens = {self._normalize(token) for token in right if self._normalize(token)}
        if not left_tokens or not right_tokens:
            return 0.0
        intersection = len(left_tokens & right_tokens)
        if intersection == 0:
            return 0.0
        return intersection / max(len(left_tokens), len(right_tokens))

    def _semantic_similarity(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        return SequenceMatcher(None, self._normalize(left), self._normalize(right)).ratio()

    def _normalize(self, value: str) -> str:
        return value.strip().lower().replace(" ", "_")

    def _clamp(self, value: float) -> float:
        if value < 0:
            return 0.0
        if value > 1:
            return 1.0
        return value

