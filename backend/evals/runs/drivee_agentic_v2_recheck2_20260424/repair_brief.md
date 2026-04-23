# Chat Text-to-SQL Eval: drivee_agentic_chat_suite_v2

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-23T18:37:21.521586+00:00`
- Duration: `57.47` sec
- Scores: overall `0.951`, understanding `0.933`, sql `0.978`, chart `1.000`

## Priority issues

### clarification_options_missing (1)
Варианты уточнения слишком бедные, не schema-grounded или не покрывают нужные ответы.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/clarification.py`

Examples:
- `clarify_report_focus#step1`: Missing clarification option terms: дистанц

### filter_missing (1)
Фильтр по строкам/срезу не дошёл до intent или SQL.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/agents/semantic.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Expected filter {'field': 'status_order', 'operator': '=', 'value': 'done', 'value_any_of': [], 'value_contains': []}; actual filters=[{'field': 'order_timestamp', 'operator': '=', 'value': '2026-04-14'}, {'field': 'driverdone_timestamp', 'operator': 'IS NOT NULL', 'value': None}, {'field': 'driveraccept_timestamp', 'operator': 'IS NOT NULL', 'value': None}, {'field': 'driverarrived_timestamp', 'operator': 'IS NOT NULL', 'value': None}, {'field': 'driverstarttheride_timestamp', 'operator': 'IS NOT NULL', 'value': None}]

### sql_required_substring_missing (1)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `status_order` missing.

## Worst steps

### clarify_report_focus#step1 (0.833)
Prompt: За 14 апреля 2026 хочу понять, что именно лучше показать по качеству поездок. Дай понятный выбор из нескольких вариантов и не строй SQL, пока не выберу.
Actual clarification: True
Actual SQL: ``
Failed checks:
- `clarification_options_missing`: Missing clarification option terms: дистанц

### hourly_followup_done_only_metrics#step2 (0.922)
Prompt: А теперь оставь только завершённые заказы и сравни по часам среднее время от принятия до прибытия и среднее время поездки от старта до завершения.
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
- `filter_missing`: Expected filter {'field': 'status_order', 'operator': '=', 'value': 'done', 'value_any_of': [], 'value_contains': []}; actual filters=[{'field': 'order_timestamp', 'operator': '=', 'value': '2026-04-14'}, {'field': 'driverdone_timestamp', 'operator': 'IS NOT NULL', 'value': None}, {'field': 'driveraccept_timestamp', 'operator': 'IS NOT NULL', 'value': None}, {'field': 'driverarrived_timestamp', 'operator': 'IS NOT NULL', 'value': None}, {'field': 'driverstarttheride_timestamp', 'operator': 'IS NOT NULL', 'value': None}]
- `sql_required_substring_missing`: Required SQL substring `status_order` missing.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
