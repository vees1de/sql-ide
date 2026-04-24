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
    MONTH_NAME_TO_NUMBER: dict[str, int] = {
        "январ": 1,
        "феврал": 2,
        "март": 3,
        "апрел": 4,
        "ма": 5,
        "июн": 6,
        "июл": 7,
        "август": 8,
        "сентябр": 9,
        "октябр": 10,
        "ноябр": 11,
        "декабр": 12,
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    ALL_TIME_MARKERS: tuple[str, ...] = (
        "за все время",
        "за всё время",
        "весь период",
        "за весь период",
        "по всей истории",
        "за всю историю",
        "all time",
        "entire history",
        "full history",
        "whole period",
    )
    BROAD_ANALYTICS_MARKERS: tuple[str, ...] = (
        "конверси",
        "доля",
        "средн",
        "average",
        "avg",
        "rate",
        "funnel",
        "воронк",
        "цикл",
        "этап",
        "где",
        "where",
        "как часто",
        "how often",
        "как меня",
        "how does",
        "compare",
        "сравни",
        "сравнит",
        "успеш",
        "стоим",
        "отлича",
        "завис",
        "паттер",
        "проблем",
        "wait",
        "ожидан",
        "скорост",
        "долг",
    )
    METRIC_PATTERNS: dict[str, tuple[str, ...]] = {
        "completion_rate": (
            "completion rate",
            "completion_rate",
            "conversion rate",
            "conversion",
            "конверси",
            "доля заверш",
            "доля выполн",
            "коэффициент заверш",
        ),
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
            "количеств",
            "число заказ",
            "orders count",
            "number of orders",
            "order count",
            "count",
            "сколько",
            "records",
            "rows",
            "запис",
            "топ",
            "top",
        ),
        "avg_ride_duration": (
            "длительност",
            "duration",
            "ride duration",
            "trip duration",
            "время поездк",
            "среднее время поездк",
        ),
        "avg_pickup_minutes": (
            "время подачи",
            "время до подачи",
            "accept to arrival",
            "pickup",
            "подач",
            "прибыт",
            "arrival time",
        ),
        "avg_order_value": ("средний чек", "average order value", "aov", "average", "avg", "mean", "средн"),
    }
    DIMENSION_PATTERNS: dict[str, tuple[str, ...]] = {
        "hour": ("по часам", "hourly", "by hour", "часам", "час"),
        "month": ("по месяц", "monthly", "by month", "помесяч"),
        "week": ("по недел", "weekly", "by week"),
        "day": ("по дням", "ежеднев", "daily", "by day"),
        "region": ("по регион", "by region", "regions"),
        "city": ("по город", "город", "city", "by city", "cities"),
        "driver_id": ("по водител", "водителям", "driver", "drivers", "driver_id"),
        "tariff_type": ("по тариф", "тариф", "tariff", "tariff_type"),
        "segment": ("по сегмент", "by segment", "segments"),
        "channel": ("по канал", "by channel", "channels", "источник"),
        "campaign": ("по кампан", "by campaign", "campaigns"),
    }
    COMPARISON_PATTERNS: dict[str, tuple[str, ...]] = {
        "previous_year": ("прошлого года", "прошлым годом", "year over year", "yoy", "аналогичным периодом"),
        "previous_period": ("предыдущим периодом", "previous period"),
    }
    CITY_VALUES = {
        "москв": "Moscow",
        "moscow": "Moscow",
        "санкт-петербург": "Saint Petersburg",
        "saint petersburg": "Saint Petersburg",
        "петербург": "Saint Petersburg",
        "казан": "Kazan",
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
    TARIFF_VALUES = {
        "economy": "economy",
        "эконом": "economy",
        "comfort": "comfort",
        "комфорт": "comfort",
        "business": "business",
        "бизнес": "business",
        "premium": "premium",
        "премиум": "premium",
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
        if previous_intent and intent.follow_up:
            intent.confidence = max(intent.confidence, previous_intent.confidence * 0.95)
        if intent.metric is None and previous_intent and intent.follow_up:
            intent.metric = previous_intent.metric
            intent.confidence = max(intent.confidence, previous_intent.confidence * 0.95)
        if self.requires_explicit_time_range(prompt, intent, previous_intent=previous_intent):
            if "time_range" not in intent.ambiguities:
                intent.ambiguities.append("time_range")
            intent.clarification_question = intent.clarification_question or "За какой период показать данные?"
            intent.confidence = min(intent.confidence, 0.65)
        if intent.metric is None:
            intent.clarification_question = (
                intent.clarification_question
                or "Какую метрику нужно посчитать: выручку, количество заказов или средний чек?"
            )
        return intent

    @classmethod
    def requires_explicit_time_range(
        cls,
        prompt: str,
        intent: IntentPayload,
        *,
        previous_intent: IntentPayload | None = None,
    ) -> bool:
        lowered = normalize_text(prompt)
        if intent.date_range is not None:
            return False
        if intent.follow_up and previous_intent and previous_intent.date_range is not None:
            return False
        if any(marker in lowered for marker in cls.ALL_TIME_MARKERS):
            return False
        if not cls._looks_like_analytics_request(lowered, intent):
            return False
        return True

    @classmethod
    def _looks_like_analytics_request(cls, prompt: str, intent: IntentPayload) -> bool:
        if not (intent.metric or intent.dimensions or intent.filters or intent.comparison):
            return False
        if any(marker in prompt for marker in cls.BROAD_ANALYTICS_MARKERS):
            return True
        if intent.comparison:
            return True
        if len(intent.dimensions) > 0:
            return True
        return bool(intent.metric and len(prompt.split()) >= 4)

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

        remove_markers = ("убери", "remove", "without", "без", "drop")
        if any(marker in prompt for marker in remove_markers):
            if "city" in dimensions and ("tariff" in prompt or "тариф" in prompt):
                dimensions = [dimension for dimension in dimensions if dimension != "city"]
        return dimensions

    def _extract_comparison(self, prompt: str) -> str | None:
        for comparison_key, markers in self.COMPARISON_PATTERNS.items():
            if any(marker in prompt for marker in markers):
                return comparison_key
        return None

    def _extract_visualization(self, prompt: str) -> str | None:
        if "pie" in prompt or "круг" in prompt or "распределен" in prompt or "долю" in prompt or "доля" in prompt:
            return "pie"
        if "bar" in prompt or "столб" in prompt:
            return "bar"
        if "table" in prompt or "таблиц" in prompt:
            return "table"
        if (
            "line" in prompt
            or "линей" in prompt
            or "график" in prompt
            or "динамик" in prompt
            or "менялся" in prompt
            or "менялос" in prompt
            or "со временем" in prompt
            or "по годам" in prompt
            or "по месяцам" in prompt
            or "по неделям" in prompt
            or "по дням" in prompt
        ):
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
        for token, value in self.TARIFF_VALUES.items():
            if token in prompt:
                filters.append(FilterCondition(field="tariff_type", value=value))
                break
        for token, value in self.SEGMENT_VALUES.items():
            if token in prompt:
                filters.append(FilterCondition(field="segment", value=value))
                break

        if "banned" in prompt or "забан" in prompt or "blocked" in prompt:
            if "водител" in prompt or "driver" in prompt or "драйвер" in prompt:
                filters.append(FilterCondition(field="driver_status", value="banned"))
        ride_completion_markers = ("завершен", "завершён", "completed", "done", "status")
        if any(marker in prompt for marker in ride_completion_markers) and (
            "поезд" in prompt or "ride" in prompt or "trip" in prompt
        ):
            if (
                "не заверш" not in prompt
                and "not completed" not in prompt
                and "not done" not in prompt
                and ("только" in prompt or "only" in prompt or "лишь" in prompt or "заверш" in prompt or "completed" in prompt or "done" in prompt)
            ):
                filters.append(FilterCondition(field="status", value="completed"))

        campaign_match = re.search(r"(?:campaign|кампан(?:ии|ия)|кампании)\s+([a-z0-9\-\s]+)", prompt)
        if campaign_match:
            filters.append(FilterCondition(field="campaign", value=campaign_match.group(1).strip().title()))

        return filters

    def _extract_date_range(self, prompt: str) -> DateRange | None:
        today = date.today()

        iso_match = re.search(r"\b((?:19|20)\d{2})-(\d{1,2})-(\d{1,2})\b", prompt)
        if iso_match:
            year = int(iso_match.group(1))
            month = int(iso_match.group(2))
            day = int(iso_match.group(3))
            exact_day = date(year, month, day)
            return DateRange(kind="absolute", start=exact_day, end=exact_day, lookback_value=1, lookback_unit="days")

        dotted_match = re.search(r"\b(\d{1,2})[./](\d{1,2})[./]((?:19|20)\d{2})\b", prompt)
        if dotted_match:
            day = int(dotted_match.group(1))
            month = int(dotted_match.group(2))
            year = int(dotted_match.group(3))
            exact_day = date(year, month, day)
            return DateRange(kind="absolute", start=exact_day, end=exact_day, lookback_value=1, lookback_unit="days")

        named_month_match = re.search(
            r"\b(\d{1,2})\s+([a-zа-яё]+)\s+((?:19|20)\d{2})\b",
            prompt,
        )
        if named_month_match:
            day = int(named_month_match.group(1))
            month_token = named_month_match.group(2)
            year = int(named_month_match.group(3))
            month = next(
                (value for token, value in self.MONTH_NAME_TO_NUMBER.items() if month_token.startswith(token)),
                None,
            )
            if month is not None:
                exact_day = date(year, month, day)
                return DateRange(
                    kind="absolute",
                    start=exact_day,
                    end=exact_day,
                    lookback_value=1,
                    lookback_unit="days",
                )

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

        if any(p in prompt for p in ("this year", "в этом году", "за этот год", "в этом год")):
            return DateRange(kind="absolute", start=date(today.year, 1, 1), end=today)
        if any(p in prompt for p in ("last year", "в прошлом году", "прошлого года", "за прошлый год")):
            return DateRange(kind="absolute", start=date(today.year - 1, 1, 1), end=date(today.year - 1, 12, 31))
        if any(p in prompt for p in ("this quarter", "в этом квартале", "за этот квартал")):
            return DateRange(kind="absolute", start=start_of_current_quarter(today), end=today)
        if any(p in prompt for p in ("last quarter", "в прошлом квартале", "прошлого квартала", "за прошлый квартал")):
            return DateRange(kind="absolute", start=start_of_previous_quarter(today), end=end_of_previous_quarter(today))

        if "вчера" in prompt or "yesterday" in prompt:
            yesterday = today - timedelta(days=1)
            return DateRange(kind="absolute", start=yesterday, end=yesterday, lookback_value=1, lookback_unit="days")
        if "сегодня" in prompt or "today" in prompt:
            return DateRange(kind="absolute", start=today, end=today, lookback_value=1, lookback_unit="days")
        if any(p in prompt for p in ("последнюю неделю", "прошлую неделю", "за неделю", "last week")):
            return DateRange(kind="relative", start=today - timedelta(weeks=1), end=today, lookback_value=1, lookback_unit="weeks")
        if any(p in prompt for p in ("последний месяц", "прошлый месяц", "за месяц", "last month")):
            return DateRange(kind="relative", start=subtract_months(today, 1), end=today, lookback_value=1, lookback_unit="months")
        if any(p in prompt for p in ("2 недели", "две недели", "two weeks")):
            return DateRange(kind="relative", start=today - timedelta(weeks=2), end=today, lookback_value=2, lookback_unit="weeks")
        if any(p in prompt for p in ("30 дней", "тридцать дней", "30 days")):
            return DateRange(kind="relative", start=today - timedelta(days=30), end=today, lookback_value=30, lookback_unit="days")
        if any(p in prompt for p in ("7 дней", "семь дней", "7 days")):
            return DateRange(kind="relative", start=today - timedelta(days=7), end=today, lookback_value=7, lookback_unit="days")

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
