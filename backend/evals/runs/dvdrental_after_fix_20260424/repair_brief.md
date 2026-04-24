# Chat Text-to-SQL Eval: dvdrental_complex_chat_text_to_sql

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-24T01:22:45.736143+00:00`
- Duration: `290.697` sec
- Scores: overall `0.000`, understanding `0.000`, sql `0.000`, chart `0.000`

## Priority issues

### chart_missing (3)
Chart recommendation отсутствует или не может быть построен.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `daily_store_revenue_march_2007#step1`: Chart cannot be evaluated without execution payload.
- `top_categories_revenue_april_2007#step1`: Chart cannot be evaluated without execution payload.
- `weekly_late_return_rate_august_2005#step1`: Chart cannot be evaluated without execution payload.

### clarification_unexpected (3)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `daily_store_revenue_march_2007#step1`: Expected a direct answer, but the system asked for clarification.
- `top_categories_revenue_april_2007#step1`: Expected a direct answer, but the system asked for clarification.
- `weekly_late_return_rate_august_2005#step1`: Expected a direct answer, but the system asked for clarification.

### execution_missing (3)
Тестер не получил execution payload, хотя он нужен для проверки результата.

Suggested files:
- `backend/app/api/routes/chat.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `daily_store_revenue_march_2007#step1`: Execution payload is missing.
- `top_categories_revenue_april_2007#step1`: Execution payload is missing.
- `weekly_late_return_rate_august_2005#step1`: Execution payload is missing.

### sql_missing (3)
SQL вообще не был сгенерирован там, где ожидался ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/services/chat_sql_adapter.py`
- `backend/app/services/analytics_agent_service.py`

Examples:
- `daily_store_revenue_march_2007#step1`: SQL draft is empty.
- `top_categories_revenue_april_2007#step1`: SQL draft is empty.
- `weekly_late_return_rate_august_2005#step1`: SQL draft is empty.

## Worst steps

### daily_store_revenue_march_2007#step1 (0.000)
Prompt: За март 2007 покажи по дням выручку и количество платежей по магазинам. Нужен line chart.
Actual clarification: True
Actual SQL: ``
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_missing`: SQL draft is empty.
- `execution_missing`: Execution payload is missing.
- `chart_missing`: Chart cannot be evaluated without execution payload.

### top_categories_revenue_april_2007#step1 (0.000)
Prompt: За апрель 2007 найди топ-10 категорий фильмов по выручке и количеству платежей. Нужен bar chart.
Actual clarification: True
Actual SQL: ``
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_missing`: SQL draft is empty.
- `execution_missing`: Execution payload is missing.
- `chart_missing`: Chart cannot be evaluated without execution payload.

### weekly_late_return_rate_august_2005#step1 (0.000)
Prompt: За август 2005 покажи по неделям среднее фактическое число дней аренды и долю просроченных возвратов. Считать аренду просроченной, если return_date > rental_date + rental_duration дней. Нужен line chart.
Actual clarification: True
Actual SQL: ``
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_missing`: SQL draft is empty.
- `execution_missing`: Execution payload is missing.
- `chart_missing`: Chart cannot be evaluated without execution payload.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
