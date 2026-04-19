from __future__ import annotations


def get_query_templates() -> list[dict]:
    return [
        {
            "id": "revenue_last_6_months",
            "title": "Revenue over time",
            "prompt": "Покажи выручку по месяцам за последние 6 месяцев",
        },
        {
            "id": "top_regions",
            "title": "Top regions",
            "prompt": "Покажи выручку по регионам за этот квартал",
        },
        {
            "id": "channel_comparison",
            "title": "Campaign performance",
            "prompt": "Сравни выручку по каналам за последние 3 месяца с аналогичным периодом прошлого года",
        },
    ]
