# Chat Text-to-SQL Eval: drivee_agentic_chat_suite

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-23T18:24:21.996132+00:00`
- Duration: `271.065` sec
- Scores: overall `0.891`, understanding `0.771`, sql `0.950`, chart `1.000`

## Priority issues

### actions_missing (3)
Failure group: actions_missing

Suggested files:
- No file hints recorded.

Examples:
- `top_drivers_non_completion_rate#step1`: Missing actions: show_run_button, show_sql.
- `hourly_followup_done_only_metrics#step1`: Missing actions: show_sql.
- `hourly_followup_done_only_metrics#step2`: Missing actions: show_run_button, show_sql.

### sql_required_substring_missing (3)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `status_order` missing.
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `driverarrived_timestamp` missing.
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `driverstarttheride_timestamp` missing.

### clarification_options_missing (1)
Варианты уточнения слишком бедные, не schema-grounded или не покрывают нужные ответы.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/clarification.py`

Examples:
- `clarify_report_focus#step1`: Missing clarification option terms: дистанц

### dimension_missing (1)
LLM потеряла нужную группировку или не сохранила контекст follow-up запроса.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/agents/semantic.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Missing dimensions: hour

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

### hourly_followup_done_only_metrics#step2 (0.767)
Prompt: А теперь оставь только завершённые заказы и сравни по часам среднее время подачи и среднее время поездки.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  AVG(EXTRACT(EPOCH FROM driveraccept_timestamp - order_timestamp)) / 60.0 AS avg_time_to_accept_minutes,
  AVG(duration_in_seconds) / 60.0 AS avg_ride_duration_minutes
FROM train
WHERE
`
Actual chart: type=`line` x=`hour` y=`avg_ride_duration_minutes` series=`None`
Failed checks:
- `actions_missing`: Missing actions: show_run_button, show_sql.
- `dimension_missing`: Missing dimensions: hour
- `filter_missing`: Expected filter {'field': 'status_order', 'operator': '=', 'value': 'done', 'value_any_of': [], 'value_contains': []}; actual filters=[]
- `sql_required_substring_missing`: Required SQL substring `status_order` missing.
- `sql_required_substring_missing`: Required SQL substring `driverarrived_timestamp` missing.
- `sql_required_substring_missing`: Required SQL substring `driverstarttheride_timestamp` missing.

### clarify_report_focus#step1 (0.857)
Prompt: За 14 апреля 2026 хочу понять, что именно лучше показать по качеству поездок. Дай понятный выбор из нескольких вариантов и не строй SQL, пока не выберу.
Actual clarification: True
Actual SQL: ``
Failed checks:
- `clarification_options_missing`: Missing clarification option terms: дистанц

### top_drivers_non_completion_rate#step1 (0.917)
Prompt: За 14 апреля 2026 найди топ-10 водителей с самой высокой долей принятых, но не завершённых поездок среди всех принятых ими заказов. Учитывай только водителей минимум с 20 принятыми заказами. Нужен bar chart.
Actual clarification: False
Actual SQL: `SELECT
  driver_id,
  COUNT(*) FILTER(WHERE
    NOT driveraccept_timestamp IS NULL) AS accepted_count,
  COUNT(*) FILTER(WHERE
    NOT driveraccept_timestamp IS NULL AND driverdone_timestamp IS NULL) AS not_completed_count,
  CAST((
    COU`
Actual chart: type=`bar` x=`driver_id` y=`not_completed_share` series=`None`
Failed checks:
- `actions_missing`: Missing actions: show_run_button, show_sql.

### hourly_followup_done_only_metrics#step1 (0.917)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов и количество завершённых поездок. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  COUNT(*) AS total_orders,
  COUNT(CASE WHEN NOT driverdone_timestamp IS NULL THEN 1 END) AS completed_rides
FROM train
WHERE
  DATE(order_timestamp) = CAST('2026-04-14' AS DATE)
GROUP `
Actual chart: type=`line` x=`hour` y=`total_orders` series=`None`
Failed checks:
- `actions_missing`: Missing actions: show_sql.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
