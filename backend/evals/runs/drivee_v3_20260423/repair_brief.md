# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-22T23:47:39.005864+00:00`
- Duration: `81.763` sec
- Scores: overall `0.880`, understanding `0.667`, sql `0.974`, chart `1.000`

## Priority issues

### clarification_unexpected (1)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Expected a direct answer, but the system asked for clarification.

### sql_required_substring_missing (1)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `hourly_completion_conversion#step1`: Required SQL substring `driverdone_timestamp` missing.

## Worst steps

### top_drivers_non_completion_rate#step1 (0.667)
Prompt: За 14 апреля 2026 найди топ-10 водителей с самой высокой долей принятых, но не завершённых поездок среди всех принятых ими заказов. Учитывай только водителей минимум с 20 принятыми заказами. Нужен bar chart.
Actual clarification: True
Actual SQL: `SELECT
  driver_id,
  COUNT(*) FILTER(WHERE
    NOT driveraccept_timestamp IS NULL) AS accepted_count,
  COUNT(*) FILTER(WHERE
    NOT driverdone_timestamp IS NULL) AS completed_count,
  CAST((
    COUNT(*) FILTER(WHERE
      NOT driveracce`
Actual chart: type=`bar` x=`driver_id` y=`not_completed_share` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.

### hourly_completion_conversion#step1 (0.974)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  COUNT(*) AS total_orders_count,
  COUNT(*) FILTER(WHERE
    status_order = 'done') AS completed_count,
  (
    CAST(COUNT(*) FILTER(WHERE
      status_order = 'done') AS DECIMAL) / NUL`
Actual chart: type=`line` x=`hour` y=`total_orders_count` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `driverdone_timestamp` missing.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
