# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-23T18:24:21.996159+00:00`
- Duration: `271.065` sec
- Scores: overall `0.840`, understanding `0.802`, sql `0.933`, chart `1.000`

## Priority issues

### sql_required_substring_missing (4)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `2026-04-14` missing.
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `status_order` missing.
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `driverarrived_timestamp` missing.
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `driverstarttheride_timestamp` missing.

### actions_missing (2)
Failure group: actions_missing

Suggested files:
- No file hints recorded.

Examples:
- `clarify_report_focus#step1`: Missing actions: create_sql.
- `hourly_followup_done_only_metrics#step1`: Missing actions: show_sql.

### clarification_options_missing (1)
Варианты уточнения слишком бедные, не schema-grounded или не покрывают нужные ответы.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/clarification.py`

Examples:
- `clarify_report_focus#step1`: Missing clarification option terms: создан, конвер

### clarification_question_terms_missing (1)
Уточняющий вопрос сформулирован слишком расплывчато или не попадает в нужную развилку.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/clarification.py`

Examples:
- `clarify_report_focus#step1`: Clarification question: Выберите интересующую метрику качества поездки:

### filter_missing (1)
Фильтр по строкам/срезу не дошёл до intent или SQL.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/agents/semantic.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Expected filter {'field': 'status_order', 'operator': '=', 'value': 'done', 'value_any_of': [], 'value_contains': []}; actual filters=[{'field': 'driverdone_timestamp', 'operator': 'is not null', 'value': None}]

### state_mismatch (1)
Failure group: state_mismatch

Suggested files:
- No file hints recorded.

Examples:
- `clarify_report_focus#step1`: Expected state CLARIFYING, got SQL_READY.

## Worst steps

### clarify_report_focus#step1 (0.429)
Prompt: За 14 апреля 2026 хочу понять, что именно лучше показать по качеству поездок. Дай понятный выбор из нескольких вариантов и не строй SQL, пока не выберу.
Actual clarification: True
Actual SQL: `SELECT
  DATE(order_timestamp) AS day,
  COUNT(*) AS total_orders,
  COUNT(*) FILTER(WHERE
    NOT driverdone_timestamp IS NULL) AS completed_orders,
  CAST((
    COUNT(*) FILTER(WHERE
      NOT driverdone_timestamp IS NULL)
  ) AS DOUBLE P`
Failed checks:
- `state_mismatch`: Expected state CLARIFYING, got SQL_READY.
- `actions_missing`: Missing actions: create_sql.
- `clarification_question_terms_missing`: Clarification question: Выберите интересующую метрику качества поездки:
- `clarification_options_missing`: Missing clarification option terms: создан, конвер

### hourly_followup_done_only_metrics#step2 (0.856)
Prompt: А теперь оставь только завершённые заказы и сравни по часам среднее время подачи и среднее время поездки.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  AVG(EXTRACT(EPOCH FROM (
    driveraccept_timestamp - order_timestamp
  )) / 60) AS avg_pickup_minutes,
  AVG(duration_in_seconds / 60.0) AS avg_ride_minutes
FROM train
WHERE
  NOT dri`
Actual chart: type=`line` x=`hour` y=`avg_pickup_minutes` series=`None`
Failed checks:
- `filter_missing`: Expected filter {'field': 'status_order', 'operator': '=', 'value': 'done', 'value_any_of': [], 'value_contains': []}; actual filters=[{'field': 'driverdone_timestamp', 'operator': 'is not null', 'value': None}]
- `sql_required_substring_missing`: Required SQL substring `2026-04-14` missing.
- `sql_required_substring_missing`: Required SQL substring `status_order` missing.
- `sql_required_substring_missing`: Required SQL substring `driverarrived_timestamp` missing.
- `sql_required_substring_missing`: Required SQL substring `driverstarttheride_timestamp` missing.

### hourly_followup_done_only_metrics#step1 (0.917)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов и количество завершённых поездок. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  COUNT(*) AS total_orders,
  COUNT(*) FILTER(WHERE
    NOT driverdone_timestamp IS NULL) AS completed_orders
FROM train
WHERE
  order_timestamp >= CAST('2026-04-14' AS DATE)
  AND order`
Actual chart: type=`line` x=`hour` y=`total_orders` series=`None`
Failed checks:
- `actions_missing`: Missing actions: show_sql.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
