from __future__ import annotations

import re
from datetime import date, timedelta

from app.agents.helpers import (
    end_of_previous_quarter,
    looks_like_follow_up,
    merge_with_context,
    normalize_text,
    start_of_current_quarter,
    start_of_previous_quarter,
    subtract_months,
)
from app.schemas.query import DateRange, FilterCondition, IntentPayload


class IntentAgent:
    METRIC_PATTERNS: dict[str, tuple[str, ...]] = {
        "revenue": (
            "выруч",
            "revenue",
            "оборот",
            "доход",
            "сумм",
            "sum",
            "amount",
            "total",
            "sales",
            "price",
            "value",
            "cost",
            "fee",
        ),
        "order_count": (
            "количеств заказ",
            "число заказ",
            "orders count",
            "number of orders",
            "order count",
            "count",
            "сколько",
            "records",
            "rows",
            "запис",
        ),
        "avg_order_value": ("средний чек", "average order value", "aov", "average", "avg", "mean", "средн"),
    }
    DIMENSION_PATTERNS: dict[str, tuple[str, ...]] = {
        "month": ("по месяц", "monthly", "by month", "помесяч"),
        "week": ("по недел", "weekly", "by week"),
        "day": ("по дням", "ежеднев", "daily", "by day"),
        "region": ("по регион", "by region", "regions"),
        "city": ("по город", "by city", "cities"),
        "segment": ("по сегмент", "by segment", "segments"),
        "channel": ("по канал", "by channel", "channels", "источник"),
        "campaign": ("по кампан", "by campaign", "campaigns"),
    }
    COMPARISON_PATTERNS: dict[str, tuple[str, ...]] = {
        "previous_year": ("прошлого года", "прошлым годом", "year over year", "yoy", "аналогичным периодом"),
        "previous_period": ("предыдущим периодом", "previous period"),
    }
    CITY_VALUES = {
        "москва": "Moscow",
        "moscow": "Moscow",
        "санкт-петербург": "Saint Petersburg",
        "saint petersburg": "Saint Petersburg",
        "петербург": "Saint Petersburg",
        "казань": "Kazan",
        "kazan": "Kazan",
        "новосибирск": "Novosibirsk",
        "novosibirsk": "Novosibirsk",
        "екатеринбург": "Yekaterinburg",
        "yekaterinburg": "Yekaterinburg",
        "якутск": "Yakutsk",
        "yakutsk": "Yakutsk",
    }
    REGION_VALUES = {
        "central": "Central",
        "центр": "Central",
        "north-west": "North-West",
        "северо-запад": "North-West",
        "volga": "Volga",
        "поволжье": "Volga",
        "siberia": "Siberia",
        "сибир": "Siberia",
        "ural": "Ural",
        "урал": "Ural",
        "far east": "Far East",
        "дальний восток": "Far East",
    }
    CHANNEL_VALUES = {
        "seo": "SEO",
        "paid ads": "Paid Ads",
        "реклама": "Paid Ads",
        "ads": "Paid Ads",
        "email": "Email",
        "почта": "Email",
        "social": "Social",
        "соцсет": "Social",
        "referral": "Referral",
        "партнер": "Referral",
    }
    SEGMENT_VALUES = {
        "enterprise": "Enterprise",
        "энтерпрайз": "Enterprise",
        "smb": "SMB",
        "малый бизнес": "SMB",
        "retail": "Retail",
        "ритейл": "Retail",
    }

    def run(self, prompt: str, previous_intent: IntentPayload | None = None) -> IntentPayload:
        lowered = normalize_text(prompt)
        metric = self._extract_metric(lowered)
        dimensions = self._extract_dimensions(lowered)
        filters = self._extract_filters(lowered)
        comparison = self._extract_comparison(lowered)
        date_range = self._extract_date_range(lowered)
        visualization_preference = self._extract_visualization(lowered)
        ambiguities, clarification_question = self._detect_ambiguity(lowered, metric, previous_intent)
        follow_up = looks_like_follow_up(lowered)

        intent = IntentPayload(
            raw_prompt=prompt,
            metric=metric,
            dimensions=dimensions,
            filters=filters,
            comparison=comparison,
            date_range=date_range,
            visualization_preference=visualization_preference,
            ambiguities=ambiguities,
            clarification_question=clarification_question,
            confidence=self._estimate_confidence(metric, dimensions, filters, date_range, ambiguities),
            follow_up=follow_up,
        )

        intent = merge_with_context(intent, previous_intent)

        if intent.comparison and not intent.dimensions:
            intent.dimensions = ["month"]
        if intent.metric is None and previous_intent and intent.follow_up:
            intent.metric = previous_intent.metric
            intent.confidence = max(intent.confidence, previous_intent.confidence * 0.95)
        if intent.metric is None:
            intent.clarification_question = (
                intent.clarification_question
                or "Какую метрику нужно посчитать: выручку, количество заказов или средний чек?"
            )
        return intent

    def _extract_metric(self, prompt: str) -> str | None:
        for metric_key, markers in self.METRIC_PATTERNS.items():
            if any(marker in prompt for marker in markers):
                return metric_key
        return None

    def _extract_dimensions(self, prompt: str) -> list[str]:
        dimensions: list[str] = []
        for dimension_key, markers in self.DIMENSION_PATTERNS.items():
            if any(marker in prompt for marker in markers):
                dimensions.append(dimension_key)
        return dimensions

    def _extract_comparison(self, prompt: str) -> str | None:
        for comparison_key, markers in self.COMPARISON_PATTERNS.items():
            if any(marker in prompt for marker in markers):
                return comparison_key
        return None

    def _extract_visualization(self, prompt: str) -> str | None:
        if "pie" in prompt or "круг" in prompt:
            return "pie"
        if "bar" in prompt or "столб" in prompt:
            return "bar"
        if "table" in prompt or "таблиц" in prompt:
            return "table"
        if "line" in prompt or "линей" in prompt or "график" in prompt:
            return "line"
        return None

    def _extract_filters(self, prompt: str) -> list[FilterCondition]:
        filters: list[FilterCondition] = []

        for token, value in self.CITY_VALUES.items():
            if token in prompt:
                filters.append(FilterCondition(field="city", value=value))
                break
        for token, value in self.REGION_VALUES.items():
            if token in prompt:
                filters.append(FilterCondition(field="region", value=value))
                break
        for token, value in self.CHANNEL_VALUES.items():
            if token in prompt:
                filters.append(FilterCondition(field="channel", value=value))
                break
        for token, value in self.SEGMENT_VALUES.items():
            if token in prompt:
                filters.append(FilterCondition(field="segment", value=value))
                break

        campaign_match = re.search(r"(?:campaign|кампан(?:ии|ия)|кампании)\s+([a-z0-9\-\s]+)", prompt)
        if campaign_match:
            filters.append(FilterCondition(field="campaign", value=campaign_match.group(1).strip().title()))

        return filters

    def _extract_date_range(self, prompt: str) -> DateRange | None:
        today = date.today()

        relative_match = re.search(
            r"(?:последн(?:ие|их)?|last)\s+(\d+)\s+(месяц(?:ев|а)?|months?|дн(?:ей|я)?|days?|недел(?:ь|и)?|weeks?)",
            prompt,
        )
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2)
            if "меся" in unit or "month" in unit:
                return DateRange(
                    kind="relative",
                    start=subtract_months(today, amount),
                    end=today,
                    lookback_value=amount,
                    lookback_unit="months",
                )
            if "нед" in unit or "week" in unit:
                return DateRange(
                    kind="relative",
                    start=today - timedelta(weeks=amount),
                    end=today,
                    lookback_value=amount,
                    lookback_unit="weeks",
                )
            return DateRange(
                kind="relative",
                start=today - timedelta(days=amount),
                end=today,
                lookback_value=amount,
                lookback_unit="days",
            )

        year_match = re.search(r"(?:за|в|for|during)\s+((?:19|20)\d{2})\s+год(?:а|у|ом)?", prompt)
        if year_match:
            year = int(year_match.group(1))
            return DateRange(kind="absolute", start=date(year, 1, 1), end=date(year, 12, 31))

        if "this year" in prompt or "в этом году" in prompt:
            return DateRange(kind="absolute", start=date(today.year, 1, 1), end=today)
        if "last year" in prompt or "в прошлом году" in prompt:
            return DateRange(kind="absolute", start=date(today.year - 1, 1, 1), end=date(today.year - 1, 12, 31))
        if "this quarter" in prompt or "в этом квартале" in prompt:
            return DateRange(kind="absolute", start=start_of_current_quarter(today), end=today)
        if "last quarter" in prompt or "в прошлом квартале" in prompt:
            return DateRange(kind="absolute", start=start_of_previous_quarter(today), end=end_of_previous_quarter(today))

        return None

    def _detect_ambiguity(
        self,
        prompt: str,
        metric: str | None,
        previous_intent: IntentPayload | None,
    ) -> tuple[list[str], str | None]:
        ambiguities: list[str] = []
        clarification_question: str | None = None

        if metric is None and ("продаж" in prompt or "sales" in prompt):
            ambiguities.append("sales")
            clarification_question = "Под продажами вы имеете в виду выручку или количество заказов?"
        if metric is None and previous_intent is None and not ambiguities:
            clarification_question = "Не удалось понять метрику. Уточните, что считать: выручку, количество заказов или средний чек?"

        return ambiguities, clarification_question

    def _estimate_confidence(
        self,
        metric: str | None,
        dimensions: list[str],
        filters: list[FilterCondition],
        date_range: DateRange | None,
        ambiguities: list[str],
    ) -> float:
        confidence = 0.35
        if metric:
            confidence += 0.3
        if dimensions:
            confidence += 0.1
        if filters:
            confidence += 0.1
        if date_range:
            confidence += 0.1
        if ambiguities:
            confidence -= 0.2
        return max(0.05, min(confidence, 0.95))
