# Chat Text-to-SQL Eval: drivee_agentic_chat_suite

- API: `http://127.0.0.1:8001/api`
- Started: `2026-04-23T18:10:52.211390+00:00`
- Duration: `60.195` sec
- Scores: overall `0.942`, understanding `0.933`, sql `0.950`, chart `0.917`

## Priority issues

### sql_required_substring_missing (2)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `status_order` missing.
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `driverarrived_timestamp` missing.

### chart_y_mismatch (1)
Неверно выбрана метрика на оси Y.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Chart y=avg_submit_minutes, acceptable=['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_ride_minutes', 'ride_minutes', 'avg_accept_to_arrival_minutes', 'avg_start_to_done_minutes']

### dimension_missing (1)
LLM потеряла нужную группировку или не сохранила контекст follow-up запроса.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/agents/semantic.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Missing dimensions: hour

### execution_required_column_missing (1)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Expected one of columns ['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_pickup_time', 'avg_accept_to_arrival_minutes']; actual columns=['avg_ride_minutes', 'avg_submit_minutes', 'hour']

### filter_missing (1)
Фильтр по строкам/срезу не дошёл до intent или SQL.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/agents/semantic.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Expected filter {'field': 'status_order', 'operator': '=', 'value': 'done', 'value_any_of': [], 'value_contains': []}; actual filters=[]

## Worst steps

### hourly_followup_done_only_metrics#step2 (0.711)
Prompt: А теперь оставь только завершённые заказы и сравни по часам среднее время подачи и среднее время поездки.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  AVG(EXTRACT(EPOCH FROM driveraccept_timestamp - order_timestamp) / 60.0) AS avg_submit_minutes,
  AVG(EXTRACT(EPOCH FROM driverdone_timestamp - driverstarttheride_timestamp) / 60.0) AS`
Actual chart: type=`line` x=`hour` y=`avg_submit_minutes` series=`None`
Failed checks:
- `dimension_missing`: Missing dimensions: hour
- `filter_missing`: Expected filter {'field': 'status_order', 'operator': '=', 'value': 'done', 'value_any_of': [], 'value_contains': []}; actual filters=[]
- `sql_required_substring_missing`: Required SQL substring `status_order` missing.
- `sql_required_substring_missing`: Required SQL substring `driverarrived_timestamp` missing.
- `execution_required_column_missing`: Expected one of columns ['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_pickup_time', 'avg_accept_to_arrival_minutes']; actual columns=['avg_ride_minutes', 'avg_submit_minutes', 'hour']
- `chart_y_mismatch`: Chart y=avg_submit_minutes, acceptable=['avg_pickup_minutes', 'pickup_minutes', 'avg_time_to_arrival', 'avg_ride_minutes', 'ride_minutes', 'avg_accept_to_arrival_minutes', 'avg_start_to_done_minutes']

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
