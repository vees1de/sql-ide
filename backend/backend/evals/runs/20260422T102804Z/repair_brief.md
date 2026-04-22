# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql

- API: `http://localhost:8000/api`
- Started: `2026-04-22T10:28:04.448341+00:00`
- Duration: `34.919` sec
- Scores: overall `0.891`, understanding `1.000`, sql `0.908`, chart `1.000`

## Priority issues

### sql_required_substring_missing (3)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `hourly_completion_conversion#step1`: Required SQL substring `driverdone_timestamp` missing.
- `top_drivers_non_completion_rate#step1`: Required SQL substring `driveraccept_timestamp` missing.
- `top_drivers_non_completion_rate#step1`: Required SQL substring `driverdone_timestamp` missing.

### execution_required_column_missing (1)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Expected one of columns ['not_completed_orders', 'failed_after_accept', 'not_done_orders']; actual columns=['accepted_not_done', 'accepted_total', 'driver_id', 'share_not_done']

## Worst steps

### top_drivers_non_completion_rate#step1 (0.802)
Prompt: За 14 апреля 2026 найди топ-10 водителей с самой высокой долей принятых, но не завершённых поездок среди всех принятых ими заказов. Учитывай только водителей минимум с 20 принятыми заказами. Нужен bar chart.
Actual clarification: False
Actual SQL: `SELECT
    driver_id,
    COUNT(*) FILTER (WHERE status_order IN ('accept', 'done')) AS accepted_total,
    COUNT(*) FILTER (WHERE status_order = 'accept') AS accepted_not_done,
    (COUNT(*) FILTER (WHERE status_order = 'accept')::DECIMAL)`
Actual chart: type=`bar` x=`driver_id` y=`share_not_done` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `driveraccept_timestamp` missing.
- `sql_required_substring_missing`: Required SQL substring `driverdone_timestamp` missing.
- `execution_required_column_missing`: Expected one of columns ['not_completed_orders', 'failed_after_accept', 'not_done_orders']; actual columns=['accepted_not_done', 'accepted_total', 'driver_id', 'share_not_done']

### hourly_completion_conversion#step1 (0.872)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT date_trunc('hour', order_timestamp) AS hour,
       COUNT(*) AS total_orders,
       COUNT(*) FILTER (WHERE status_order = 'done') AS completed_orders,
       COUNT(*) FILTER (WHERE status_order = 'done')::float / NULLIF(COUNT(*), 0)`
Actual chart: type=`line` x=`hour` y=`total_orders` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `driverdone_timestamp` missing.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
