# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-22T23:45:07.503101+00:00`
- Duration: `48.649` sec
- Scores: overall `0.917`, understanding `1.000`, sql `0.974`, chart `0.778`

## Priority issues

### chart_y_mismatch (2)
Неверно выбрана метрика на оси Y.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Chart y=completed_trip_count, acceptable=['created_orders', 'total_orders', 'orders_created', 'completed_orders', 'completion_rate']
- `top_drivers_non_completion_rate#step1`: Chart y=total_accepted, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate', 'not_completed_count']

### sql_required_substring_missing (1)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `hourly_completion_conversion#step1`: Required SQL substring `driverdone_timestamp` missing.

## Worst steps

### hourly_completion_conversion#step1 (0.863)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  COUNT(*) AS created_order_count,
  COUNT(*) FILTER(WHERE
    status_order = 'done') AS completed_trip_count,
  CASE
    WHEN COUNT(*) = 0
    THEN 0
    ELSE CAST(COUNT(*) FILTER(WHERE`
Actual chart: type=`line` x=`hour` y=`completed_trip_count` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `driverdone_timestamp` missing.
- `chart_y_mismatch`: Chart y=completed_trip_count, acceptable=['created_orders', 'total_orders', 'orders_created', 'completed_orders', 'completion_rate']

### top_drivers_non_completion_rate#step1 (0.889)
Prompt: За 14 апреля 2026 найди топ-10 водителей с самой высокой долей принятых, но не завершённых поездок среди всех принятых ими заказов. Учитывай только водителей минимум с 20 принятыми заказами. Нужен bar chart.
Actual clarification: False
Actual SQL: `SELECT
  driver_id,
  COUNT(*) AS total_accepted,
  COUNT(*) FILTER(WHERE
    driverdone_timestamp IS NULL) AS not_completed_count,
  CAST(COUNT(*) FILTER(WHERE
    driverdone_timestamp IS NULL) AS DOUBLE PRECISION) / NULLIF(COUNT(*), 0) AS`
Actual chart: type=`bar` x=`driver_id` y=`total_accepted` series=`None`
Failed checks:
- `chart_y_mismatch`: Chart y=total_accepted, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate', 'not_completed_count']

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
