# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql

- API: `http://localhost:8000/api`
- Started: `2026-04-22T08:51:53.759740+00:00`
- Duration: `40.197` sec
- Scores: overall `0.569`, understanding `0.667`, sql `0.597`, chart `0.445`

## Priority issues

### execution_required_column_missing (3)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Expected one of columns ['completed_orders', 'done_orders', 'completed_rides', 'completed_count']; actual columns=['completed_trips', 'conversion_rate', 'created_orders', 'hour']
- `top_drivers_non_completion_rate#step1`: Expected one of columns ['not_completed_orders', 'failed_after_accept', 'not_done_orders']; actual columns=['driver_id', 'not_completed', 'share_not_completed', 'total_accepted']
- `top_drivers_non_completion_rate#step1`: Expected one of columns ['non_completion_rate', 'not_completed_rate', 'fail_rate']; actual columns=['driver_id', 'not_completed', 'share_not_completed', 'total_accepted']

### chart_y_mismatch (2)
Неверно выбрана метрика на оси Y.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Chart y=completed_trips, acceptable=['created_orders', 'total_orders', 'orders_created', 'completed_orders', 'completion_rate']
- `top_drivers_non_completion_rate#step1`: Chart y=share_not_completed, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate']

### chart_missing (1)
Chart recommendation отсутствует или не может быть построен.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `hourly_pickup_vs_ride_duration#step1`: Chart cannot be evaluated without execution payload.

### clarification_unexpected (1)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `hourly_pickup_vs_ride_duration#step1`: Expected a direct answer, but the system asked for clarification.

### execution_missing (1)
Тестер не получил execution payload, хотя он нужен для проверки результата.

Suggested files:
- `backend/app/api/routes/chat.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `hourly_pickup_vs_ride_duration#step1`: Execution payload is missing.

### sql_missing (1)
SQL вообще не был сгенерирован там, где ожидался ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/services/chat_sql_adapter.py`
- `backend/app/services/analytics_agent_service.py`

Examples:
- `hourly_pickup_vs_ride_duration#step1`: SQL draft is empty.

## Worst steps

### hourly_pickup_vs_ride_duration#step1 (0.000)
Prompt: За 14 апреля 2026 сравни по часам среднее время подачи от принятия водителем до прибытия и среднее время поездки от старта до завершения только для завершённых заказов. Нужен line chart.
Actual clarification: True
Actual SQL: ``
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_missing`: SQL draft is empty.
- `execution_missing`: Execution payload is missing.
- `chart_missing`: Chart cannot be evaluated without execution payload.

### top_drivers_non_completion_rate#step1 (0.845)
Prompt: За 14 апреля 2026 найди топ-10 водителей с самой высокой долей принятых, но не завершённых поездок среди всех принятых ими заказов. Учитывай только водителей минимум с 20 принятыми заказами. Нужен bar chart.
Actual clarification: False
Actual SQL: `SELECT
  t.driver_id,
  COUNT(*) FILTER (WHERE t.driveraccept_timestamp IS NOT NULL) AS total_accepted,
  COUNT(*) FILTER (WHERE t.driveraccept_timestamp IS NOT NULL AND t.driverdone_timestamp IS NULL) AS not_completed,
  (COUNT(*) FILTER (`
Actual chart: type=`bar` x=`driver_id` y=`share_not_completed` series=`None`
Failed checks:
- `execution_required_column_missing`: Expected one of columns ['not_completed_orders', 'failed_after_accept', 'not_done_orders']; actual columns=['driver_id', 'not_completed', 'share_not_completed', 'total_accepted']
- `execution_required_column_missing`: Expected one of columns ['non_completion_rate', 'not_completed_rate', 'fail_rate']; actual columns=['driver_id', 'not_completed', 'share_not_completed', 'total_accepted']
- `chart_y_mismatch`: Chart y=share_not_completed, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate']

### hourly_completion_conversion#step1 (0.863)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  date_trunc('hour', order_timestamp) AS hour,
  COUNT(*) AS created_orders,
  COUNT(CASE WHEN driverdone_timestamp IS NOT NULL THEN 1 END) AS completed_trips,
  COUNT(CASE WHEN driverdone_timestamp IS NOT NULL THEN 1 END)::DECIMAL /`
Actual chart: type=`line` x=`hour` y=`completed_trips` series=`None`
Failed checks:
- `execution_required_column_missing`: Expected one of columns ['completed_orders', 'done_orders', 'completed_rides', 'completed_count']; actual columns=['completed_trips', 'conversion_rate', 'created_orders', 'hour']
- `chart_y_mismatch`: Chart y=completed_trips, acceptable=['created_orders', 'total_orders', 'orders_created', 'completed_orders', 'completion_rate']

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
