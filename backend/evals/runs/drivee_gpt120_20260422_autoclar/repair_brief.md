# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-22T07:24:43.530560+00:00`
- Duration: `52.236` sec
- Scores: overall `0.288`, understanding `0.333`, sql `0.308`, chart `0.222`

## Priority issues

### chart_missing (2)
Chart recommendation отсутствует или не может быть построен.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Chart cannot be evaluated without execution payload.
- `hourly_pickup_vs_ride_duration#step1`: Chart cannot be evaluated without execution payload.

### clarification_unexpected (2)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Expected a direct answer, but the system asked for clarification.
- `hourly_pickup_vs_ride_duration#step1`: Expected a direct answer, but the system asked for clarification.

### execution_missing (2)
Тестер не получил execution payload, хотя он нужен для проверки результата.

Suggested files:
- `backend/app/api/routes/chat.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Execution payload is missing.
- `hourly_pickup_vs_ride_duration#step1`: Execution payload is missing.

### sql_missing (2)
SQL вообще не был сгенерирован там, где ожидался ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/services/chat_sql_adapter.py`
- `backend/app/services/analytics_agent_service.py`

Examples:
- `top_drivers_non_completion_rate#step1`: SQL draft is empty.
- `hourly_pickup_vs_ride_duration#step1`: SQL draft is empty.

### chart_y_mismatch (1)
Неверно выбрана метрика на оси Y.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Chart y=trips_completed, acceptable=['created_orders', 'total_orders', 'orders_created', 'completed_orders', 'completion_rate']

### execution_required_column_missing (1)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Expected one of columns ['completed_orders', 'done_orders', 'completed_rides', 'completed_count']; actual columns=['conversion_rate', 'hour', 'orders_created', 'trips_completed']

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

### hourly_pickup_vs_ride_duration#step1 (0.000)
Prompt: За 14 апреля 2026 сравни по часам среднее время подачи от принятия водителем до прибытия и среднее время поездки от старта до завершения только для завершённых заказов. Нужен line chart.
Actual clarification: True
Actual SQL: ``
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_missing`: SQL draft is empty.
- `execution_missing`: Execution payload is missing.
- `chart_missing`: Chart cannot be evaluated without execution payload.

### hourly_completion_conversion#step1 (0.863)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT date_trunc('hour', order_timestamp) AS hour,
       COUNT(*) AS orders_created,
       COUNT(CASE WHEN driverdone_timestamp IS NOT NULL THEN 1 END) AS trips_completed,
       (COUNT(CASE WHEN driverdone_timestamp IS NOT NULL THEN 1 E`
Actual chart: type=`line` x=`hour` y=`trips_completed` series=`None`
Failed checks:
- `execution_required_column_missing`: Expected one of columns ['completed_orders', 'done_orders', 'completed_rides', 'completed_count']; actual columns=['conversion_rate', 'hour', 'orders_created', 'trips_completed']
- `chart_y_mismatch`: Chart y=trips_completed, acceptable=['created_orders', 'total_orders', 'orders_created', 'completed_orders', 'completion_rate']

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
