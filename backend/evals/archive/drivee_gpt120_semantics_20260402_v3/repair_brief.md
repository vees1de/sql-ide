# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql_20260402

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-22T08:28:33.784533+00:00`
- Duration: `45.635` sec
- Scores: overall `0.849`, understanding `1.000`, sql `0.881`, chart `0.667`

## Priority issues

### execution_required_column_missing (5)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Expected one of columns ['completed_orders', 'done_orders', 'completed_rides', 'completed_count']; actual columns=['completed_trips', 'conversion_rate', 'created_orders', 'hour']
- `top_drivers_non_completion_rate#step1`: Expected one of columns ['non_completion_rate', 'not_completed_rate', 'fail_rate']; actual columns=['accepted_orders', 'driver_id', 'not_completed_orders', 'share_not_completed']
- `hourly_pickup_vs_ride_duration#step1`: Expected one of columns ['hour', 'hour_bucket', 'order_hour', 'bucket']; actual columns=['avg_accept_to_arrival_min', 'avg_ride_duration_min', 'hour_of_day']
- `hourly_pickup_vs_ride_duration#step1`: Expected one of columns ['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_pickup_time']; actual columns=['avg_accept_to_arrival_min', 'avg_ride_duration_min', 'hour_of_day']
- `hourly_pickup_vs_ride_duration#step1`: Expected one of columns ['avg_ride_minutes', 'ride_minutes', 'avg_ride_time']; actual columns=['avg_accept_to_arrival_min', 'avg_ride_duration_min', 'hour_of_day']

### chart_y_mismatch (3)
Неверно выбрана метрика на оси Y.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Chart y=completed_trips, acceptable=['created_orders', 'total_orders', 'orders_created', 'completed_orders', 'completion_rate']
- `top_drivers_non_completion_rate#step1`: Chart y=share_not_completed, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate']
- `hourly_pickup_vs_ride_duration#step1`: Chart y=avg_accept_to_arrival_min, acceptable=['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_ride_minutes', 'ride_minutes']

## Worst steps

### hourly_pickup_vs_ride_duration#step1 (0.818)
Prompt: За 2 апреля 2026 сравни по часам среднее время подачи от принятия водителем до прибытия и среднее время поездки от старта до завершения только для завершённых заказов. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  EXTRACT(HOUR FROM order_timestamp) AS hour_of_day,
  AVG(EXTRACT(EPOCH FROM driverarrived_timestamp - driveraccept_timestamp)) / 60.0 AS avg_accept_to_arrival_min,
  AVG(EXTRACT(EPOCH FROM driverdone_timestamp - driverstarttheride_`
Actual chart: type=`line` x=`hour_of_day` y=`avg_accept_to_arrival_min` series=`None`
Failed checks:
- `execution_required_column_missing`: Expected one of columns ['hour', 'hour_bucket', 'order_hour', 'bucket']; actual columns=['avg_accept_to_arrival_min', 'avg_ride_duration_min', 'hour_of_day']
- `execution_required_column_missing`: Expected one of columns ['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_pickup_time']; actual columns=['avg_accept_to_arrival_min', 'avg_ride_duration_min', 'hour_of_day']
- `execution_required_column_missing`: Expected one of columns ['avg_ride_minutes', 'ride_minutes', 'avg_ride_time']; actual columns=['avg_accept_to_arrival_min', 'avg_ride_duration_min', 'hour_of_day']
- `chart_y_mismatch`: Chart y=avg_accept_to_arrival_min, acceptable=['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_ride_minutes', 'ride_minutes']

### hourly_completion_conversion#step1 (0.863)
Prompt: За 2 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT date_trunc('hour', order_timestamp) AS hour,
       COUNT(*) AS created_orders,
       SUM(CASE WHEN driverdone_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS completed_trips,
       SUM(CASE WHEN driverdone_timestamp IS NOT NULL THEN 1`
Actual chart: type=`line` x=`hour` y=`completed_trips` series=`None`
Failed checks:
- `execution_required_column_missing`: Expected one of columns ['completed_orders', 'done_orders', 'completed_rides', 'completed_count']; actual columns=['completed_trips', 'conversion_rate', 'created_orders', 'hour']
- `chart_y_mismatch`: Chart y=completed_trips, acceptable=['created_orders', 'total_orders', 'orders_created', 'completed_orders', 'completion_rate']

### top_drivers_non_completion_rate#step1 (0.867)
Prompt: За 2 апреля 2026 найди топ-10 водителей с самой высокой долей принятых, но не завершённых поездок среди всех принятых ими заказов. Учитывай только водителей минимум с 20 принятыми заказами. Нужен bar chart.
Actual clarification: False
Actual SQL: `SELECT
  driver_id,
  COUNT(*) FILTER (WHERE driveraccept_timestamp IS NOT NULL) AS accepted_orders,
  COUNT(*) FILTER (WHERE driveraccept_timestamp IS NOT NULL AND driverdone_timestamp IS NULL) AS not_completed_orders,
  (COUNT(*) FILTER (`
Actual chart: type=`bar` x=`driver_id` y=`share_not_completed` series=`None`
Failed checks:
- `execution_required_column_missing`: Expected one of columns ['non_completion_rate', 'not_completed_rate', 'fail_rate']; actual columns=['accepted_orders', 'driver_id', 'not_completed_orders', 'share_not_completed']
- `chart_y_mismatch`: Chart y=share_not_completed, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate']

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
