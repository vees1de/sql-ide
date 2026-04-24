# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-22T07:20:13.204791+00:00`
- Duration: `26.049` sec
- Scores: overall `0.237`, understanding `0.333`, sql `0.267`, chart `0.111`

## Priority issues

### execution_required_column_missing (3)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Expected one of columns ['accepted_orders', 'accepted_count', 'total_accepted']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_unfinished']
- `top_drivers_non_completion_rate#step1`: Expected one of columns ['not_completed_orders', 'failed_after_accept', 'not_done_orders']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_unfinished']
- `top_drivers_non_completion_rate#step1`: Expected one of columns ['non_completion_rate', 'not_completed_rate', 'fail_rate']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_unfinished']

### chart_missing (2)
Chart recommendation отсутствует или не может быть построен.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `hourly_completion_conversion#step1`: Chart cannot be evaluated without execution payload.
- `hourly_pickup_vs_ride_duration#step1`: Chart cannot be evaluated without execution payload.

### clarification_unexpected (2)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `hourly_completion_conversion#step1`: Expected a direct answer, but the system asked for clarification.
- `hourly_pickup_vs_ride_duration#step1`: Expected a direct answer, but the system asked for clarification.

### execution_missing (2)
Тестер не получил execution payload, хотя он нужен для проверки результата.

Suggested files:
- `backend/app/api/routes/chat.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `hourly_completion_conversion#step1`: Execution payload is missing.
- `hourly_pickup_vs_ride_duration#step1`: Execution payload is missing.

### sql_missing (2)
SQL вообще не был сгенерирован там, где ожидался ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/services/chat_sql_adapter.py`
- `backend/app/services/analytics_agent_service.py`

Examples:
- `hourly_completion_conversion#step1`: SQL draft is empty.
- `hourly_pickup_vs_ride_duration#step1`: SQL draft is empty.

### chart_type_mismatch (1)
Выбран неподходящий тип графика.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`
- `backend/app/services/llm_service.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Chart type=line, acceptable=['bar']

### chart_y_mismatch (1)
Неверно выбрана метрика на оси Y.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `top_drivers_non_completion_rate#step1`: Chart y=accepted_cnt, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate']

## Worst steps

### hourly_completion_conversion#step1 (0.000)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
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

### top_drivers_non_completion_rate#step1 (0.711)
Prompt: За 14 апреля 2026 найди топ-10 водителей с самой высокой долей принятых, но не завершённых поездок среди всех принятых ими заказов. Учитывай только водителей минимум с 20 принятыми заказами. Нужен bar chart.
Actual clarification: False
Actual SQL: `SELECT
  driver_id,
  COUNT(*) FILTER (WHERE driveraccept_timestamp IS NOT NULL) AS accepted_cnt,
  COUNT(*) FILTER (WHERE driveraccept_timestamp IS NOT NULL AND driverdone_timestamp IS NULL) AS not_completed_cnt,
  (COUNT(*) FILTER (WHERE `
Actual chart: type=`line` x=`driver_id` y=`accepted_cnt` series=`driver_id`
Failed checks:
- `execution_required_column_missing`: Expected one of columns ['accepted_orders', 'accepted_count', 'total_accepted']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_unfinished']
- `execution_required_column_missing`: Expected one of columns ['not_completed_orders', 'failed_after_accept', 'not_done_orders']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_unfinished']
- `execution_required_column_missing`: Expected one of columns ['non_completion_rate', 'not_completed_rate', 'fail_rate']; actual columns=['accepted_cnt', 'driver_id', 'not_completed_cnt', 'share_unfinished']
- `chart_type_mismatch`: Chart type=line, acceptable=['bar']
- `chart_y_mismatch`: Chart y=accepted_cnt, acceptable=['non_completion_rate', 'not_completed_rate', 'fail_rate']

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
