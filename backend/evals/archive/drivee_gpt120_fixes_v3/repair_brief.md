# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-22T07:48:07.919442+00:00`
- Duration: `80.046` sec
- Scores: overall `0.309`, understanding `0.000`, sql `0.593`, chart `0.333`

## Priority issues

### clarification_unexpected (3)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Expected a direct answer, but the system asked for clarification.
- `top_drivers_non_completion_rate#step1`: Expected a direct answer, but the system asked for clarification.
- `hourly_pickup_vs_ride_duration#step1`: Expected a direct answer, but the system asked for clarification.

### execution_required_column_missing (3)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Expected one of columns ['completed_orders', 'done_orders', 'completed_rides', 'completed_count']; actual columns=['conversion_rate', 'hour', 'orders_created', 'rides_completed']
- `hourly_pickup_vs_ride_duration#step1`: Expected one of columns ['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_pickup_time']; actual columns=['avg_accept_to_arrival_seconds', 'avg_start_to_done_seconds', 'hour']
- `hourly_pickup_vs_ride_duration#step1`: Expected one of columns ['avg_ride_minutes', 'ride_minutes', 'avg_ride_time']; actual columns=['avg_accept_to_arrival_seconds', 'avg_start_to_done_seconds', 'hour']

### chart_y_mismatch (2)
Неверно выбрана метрика на оси Y.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Chart y=rides_completed, acceptable=['created_orders', 'total_orders', 'orders_created', 'completed_orders', 'completion_rate']
- `hourly_pickup_vs_ride_duration#step1`: Chart y=hour, acceptable=['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_ride_minutes', 'ride_minutes']

### chart_missing (1)
Chart recommendation отсутствует или не может быть построен.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Chart cannot be evaluated without execution payload.

### chart_type_mismatch (1)
Выбран неподходящий тип графика.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`
- `backend/app/services/llm_service.py`

Examples:
- `hourly_pickup_vs_ride_duration#step1`: Chart type=table, acceptable=['line']

### execution_missing (1)
Тестер не получил execution payload, хотя он нужен для проверки результата.

Suggested files:
- `backend/app/api/routes/chat.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Execution payload is missing.

### sql_missing (1)
SQL вообще не был сгенерирован там, где ожидался ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/services/chat_sql_adapter.py`
- `backend/app/services/analytics_agent_service.py`

Examples:
- `top_drivers_non_completion_rate#step1`: SQL draft is empty.

## Worst steps

### top_drivers_non_completion_rate#step1 (0.000)
Prompt: За 14 апреля 2026 найди топ-10 водителей с самой высокой долей принятых, но не завершённых поездок среди всех принятых ими заказов. Учитывай только водителей минимум с 20 принятыми заказами. Нужен bar chart.
Actual clarification: True
Actual SQL: ``
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_missing`: SQL draft is empty.
- `execution_missing`: Execution payload is missing.
- `chart_missing`: Chart cannot be evaluated without execution payload.

### hourly_pickup_vs_ride_duration#step1 (0.397)
Prompt: За 14 апреля 2026 сравни по часам среднее время подачи от принятия водителем до прибытия и среднее время поездки от старта до завершения только для завершённых заказов. Нужен line chart.
Actual clarification: True
Actual SQL: `SELECT
  EXTRACT(HOUR FROM order_timestamp) AS hour,
  AVG(EXTRACT(EPOCH FROM (driverarrived_timestamp - driveraccept_timestamp))) AS avg_accept_to_arrival_seconds,
  AVG(EXTRACT(EPOCH FROM (driverdone_timestamp - driverstarttheride_timesta`
Actual chart: type=`table` x=`hour` y=`hour` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `execution_required_column_missing`: Expected one of columns ['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_pickup_time']; actual columns=['avg_accept_to_arrival_seconds', 'avg_start_to_done_seconds', 'hour']
- `execution_required_column_missing`: Expected one of columns ['avg_ride_minutes', 'ride_minutes', 'avg_ride_time']; actual columns=['avg_accept_to_arrival_seconds', 'avg_start_to_done_seconds', 'hour']
- `chart_type_mismatch`: Chart type=table, acceptable=['line']
- `chart_y_mismatch`: Chart y=hour, acceptable=['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_ride_minutes', 'ride_minutes']

### hourly_completion_conversion#step1 (0.530)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
Actual clarification: True
Actual SQL: `SELECT
  date_trunc('hour', order_timestamp) AS hour,
  COUNT(*) AS orders_created,
  COUNT(CASE WHEN driverdone_timestamp IS NOT NULL THEN 1 END) AS rides_completed,
  COUNT(CASE WHEN driverdone_timestamp IS NOT NULL THEN 1 END)::DECIMAL /`
Actual chart: type=`line` x=`hour` y=`rides_completed` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `execution_required_column_missing`: Expected one of columns ['completed_orders', 'done_orders', 'completed_rides', 'completed_count']; actual columns=['conversion_rate', 'hour', 'orders_created', 'rides_completed']
- `chart_y_mismatch`: Chart y=rides_completed, acceptable=['created_orders', 'total_orders', 'orders_created', 'completed_orders', 'completion_rate']

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
