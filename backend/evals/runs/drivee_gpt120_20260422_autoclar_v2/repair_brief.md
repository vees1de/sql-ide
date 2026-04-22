# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-22T07:26:15.376504+00:00`
- Duration: `63.7` sec
- Scores: overall `0.472`, understanding `0.000`, sql `0.860`, chart `0.556`

## Priority issues

### execution_required_column_missing (6)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Expected one of columns ['completed_orders', 'done_orders', 'completed_rides', 'completed_count']; actual columns=['conversion_rate', 'hour', 'orders_created', 'rides_completed']
- `top_drivers_non_completion_rate#step1`: Expected one of columns ['accepted_orders', 'accepted_count', 'total_accepted']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_not_completed']
- `top_drivers_non_completion_rate#step1`: Expected one of columns ['not_completed_orders', 'failed_after_accept', 'not_done_orders']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_not_completed']
- `top_drivers_non_completion_rate#step1`: Expected one of columns ['non_completion_rate', 'not_completed_rate', 'fail_rate']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_not_completed']
- `hourly_pickup_vs_ride_duration#step1`: Expected one of columns ['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_pickup_time']; actual columns=['avg_accept_to_arrival_sec', 'avg_ride_duration_sec', 'hour']

### chart_y_mismatch (3)
Неверно выбрана метрика на оси Y.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Chart y=rides_completed, acceptable=['created_orders', 'total_orders', 'orders_created', 'completed_orders', 'completion_rate']
- `top_drivers_non_completion_rate#step1`: Chart y=accepted_cnt, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate']
- `hourly_pickup_vs_ride_duration#step1`: Chart y=avg_accept_to_arrival_sec, acceptable=['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_ride_minutes', 'ride_minutes']

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

### chart_type_mismatch (1)
Выбран неподходящий тип графика.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`
- `backend/app/services/llm_service.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Chart type=line, acceptable=['bar']

## Worst steps

### top_drivers_non_completion_rate#step1 (0.378)
Prompt: За 14 апреля 2026 найди топ-10 водителей с самой высокой долей принятых, но не завершённых поездок среди всех принятых ими заказов. Учитывай только водителей минимум с 20 принятыми заказами. Нужен bar chart.
Actual clarification: True
Actual SQL: `SELECT
  driver_id,
  COUNT(*) FILTER (WHERE driveraccept_timestamp IS NOT NULL) AS accepted_cnt,
  COUNT(*) FILTER (WHERE driveraccept_timestamp IS NOT NULL AND driverdone_timestamp IS NULL) AS not_completed_cnt,
  (COUNT(*) FILTER (WHERE `
Actual chart: type=`line` x=`driver_id` y=`accepted_cnt` series=`driver_id`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `execution_required_column_missing`: Expected one of columns ['accepted_orders', 'accepted_count', 'total_accepted']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_not_completed']
- `execution_required_column_missing`: Expected one of columns ['not_completed_orders', 'failed_after_accept', 'not_done_orders']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_not_completed']
- `execution_required_column_missing`: Expected one of columns ['non_completion_rate', 'not_completed_rate', 'fail_rate']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_not_completed']
- `chart_type_mismatch`: Chart type=line, acceptable=['bar']
- `chart_y_mismatch`: Chart y=accepted_cnt, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate']

### hourly_pickup_vs_ride_duration#step1 (0.508)
Prompt: За 14 апреля 2026 сравни по часам среднее время подачи от принятия водителем до прибытия и среднее время поездки от старта до завершения только для завершённых заказов. Нужен line chart.
Actual clarification: True
Actual SQL: `SELECT date_trunc('hour', order_timestamp) AS hour,
       AVG(EXTRACT(EPOCH FROM (driverarrived_timestamp - driveraccept_timestamp))) AS avg_accept_to_arrival_sec,
       AVG(EXTRACT(EPOCH FROM (driverdone_timestamp - driverstarttheride_ti`
Actual chart: type=`line` x=`hour` y=`avg_accept_to_arrival_sec` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `execution_required_column_missing`: Expected one of columns ['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_pickup_time']; actual columns=['avg_accept_to_arrival_sec', 'avg_ride_duration_sec', 'hour']
- `execution_required_column_missing`: Expected one of columns ['avg_ride_minutes', 'ride_minutes', 'avg_ride_time']; actual columns=['avg_accept_to_arrival_sec', 'avg_ride_duration_sec', 'hour']
- `chart_y_mismatch`: Chart y=avg_accept_to_arrival_sec, acceptable=['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_ride_minutes', 'ride_minutes']

### hourly_completion_conversion#step1 (0.530)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
Actual clarification: True
Actual SQL: `SELECT date_trunc('hour', order_timestamp) AS hour,
       COUNT(*) AS orders_created,
       COUNT(CASE WHEN driverdone_timestamp IS NOT NULL THEN 1 END) AS rides_completed,
       COUNT(CASE WHEN driverdone_timestamp IS NOT NULL THEN 1 EN`
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
