# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-22T23:35:42.217212+00:00`
- Duration: `60.079` sec
- Scores: overall `0.828`, understanding `0.667`, sql `0.928`, chart `0.889`

## Priority issues

### execution_required_column_missing (2)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Expected one of columns ['not_completed_orders', 'failed_after_accept', 'not_done_orders']; actual columns=['accepted_count', 'driver_id', 'not_completed_count', 'not_completed_rate']
- `hourly_pickup_vs_ride_duration#step1`: Expected one of columns ['avg_ride_minutes', 'ride_minutes', 'avg_ride_time']; actual columns=['avg_accept_to_arrival_minutes', 'avg_start_to_done_minutes', 'hour']

### chart_y_mismatch (1)
Неверно выбрана метрика на оси Y.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Chart y=accepted_count, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate']

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

### top_drivers_non_completion_rate#step1 (0.533)
Prompt: За 14 апреля 2026 найди топ-10 водителей с самой высокой долей принятых, но не завершённых поездок среди всех принятых ими заказов. Учитывай только водителей минимум с 20 принятыми заказами. Нужен bar chart.
Actual clarification: True
Actual SQL: `SELECT
  driver_id,
  COUNT(*) FILTER(WHERE
    NOT driveraccept_timestamp IS NULL) AS accepted_count,
  COUNT(*) FILTER(WHERE
    NOT driveraccept_timestamp IS NULL AND driverdone_timestamp IS NULL) AS not_completed_count,
  CAST((
    COU`
Actual chart: type=`bar` x=`driver_id` y=`accepted_count` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `execution_required_column_missing`: Expected one of columns ['not_completed_orders', 'failed_after_accept', 'not_done_orders']; actual columns=['accepted_count', 'driver_id', 'not_completed_count', 'not_completed_rate']
- `chart_y_mismatch`: Chart y=accepted_count, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate']

### hourly_completion_conversion#step1 (0.974)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  COUNT(*) FILTER(WHERE
    NOT status_order IS NULL) AS total_orders,
  COUNT(*) FILTER(WHERE
    status_order = 'done') AS completed_orders,
  (
    CAST(COUNT(*) FILTER(WHERE
      st`
Actual chart: type=`line` x=`hour` y=`total_orders` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `driverdone_timestamp` missing.

### hourly_pickup_vs_ride_duration#step1 (0.976)
Prompt: За 14 апреля 2026 сравни по часам среднее время подачи от принятия водителем до прибытия и среднее время поездки от старта до завершения только для завершённых заказов. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  AVG(EXTRACT(EPOCH FROM (
    driverarrived_timestamp - driveraccept_timestamp
  )) / 60) AS avg_accept_to_arrival_minutes,
  AVG(
    EXTRACT(EPOCH FROM (
      driverdone_timestamp - `
Actual chart: type=`line` x=`hour` y=`avg_accept_to_arrival_minutes` series=`None`
Failed checks:
- `execution_required_column_missing`: Expected one of columns ['avg_ride_minutes', 'ride_minutes', 'avg_ride_time']; actual columns=['avg_accept_to_arrival_minutes', 'avg_start_to_done_minutes', 'hour']

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
