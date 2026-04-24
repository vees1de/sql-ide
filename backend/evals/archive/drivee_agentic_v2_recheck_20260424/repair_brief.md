# Chat Text-to-SQL Eval: drivee_agentic_chat_suite_v2

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-23T18:35:42.447928+00:00`
- Duration: `43.071` sec
- Scores: overall `0.918`, understanding `0.833`, sql `0.978`, chart `1.000`

## Priority issues

### actions_missing (2)
Failure group: actions_missing

Suggested files:
- No file hints recorded.

Examples:
- `hourly_completion_conversion#step1`: Missing actions: show_sql.
- `hourly_followup_done_only_metrics#step1`: Missing actions: show_sql.

### clarification_options_missing (1)
Варианты уточнения слишком бедные, не schema-grounded или не покрывают нужные ответы.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/clarification.py`

Examples:
- `clarify_report_focus#step1`: Missing clarification option terms: заверш, длитель, дистанц, отмен, прибыт

### filter_missing (1)
Фильтр по строкам/срезу не дошёл до intent или SQL.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/agents/semantic.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Expected filter {'field': 'status_order', 'operator': '=', 'value': 'done', 'value_any_of': [], 'value_contains': []}; actual filters=[{'field': 'driverdone_timestamp', 'operator': 'IS NOT NULL', 'value': None}, {'field': 'order_timestamp', 'operator': '=', 'value': '2026-04-14'}]

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
- `clarification_options_missing`: Missing clarification option terms: заверш, длитель, дистанц, отмен, прибыт

### hourly_completion_conversion#step1 (0.917)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  COUNT(*) AS total_orders,
  COUNT(CASE WHEN NOT driverdone_timestamp IS NULL THEN 1 END) AS completed_orders,
  CAST(COUNT(CASE WHEN NOT driverdone_timestamp IS NULL THEN 1 END) AS DEC`
Actual chart: type=`line` x=`hour` y=`total_orders` series=`None`
Failed checks:
- `actions_missing`: Missing actions: show_sql.

### hourly_followup_done_only_metrics#step1 (0.917)
Prompt: За 14 апреля 2026 покажи по часам количество созданных заказов и количество завершённых поездок. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  COUNT(*) AS total_orders,
  SUM(CASE WHEN NOT driverdone_timestamp IS NULL THEN 1 ELSE 0 END) AS completed_orders
FROM train
WHERE
  DATE(order_timestamp) = '2026-04-14'
GROUP BY
  hou`
Actual chart: type=`line` x=`hour` y=`total_orders` series=`None`
Failed checks:
- `actions_missing`: Missing actions: show_sql.

### hourly_followup_done_only_metrics#step2 (0.922)
Prompt: А теперь оставь только завершённые заказы и сравни по часам среднее время от принятия до прибытия и среднее время поездки от старта до завершения.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  AVG(
    CASE
      WHEN NOT driveraccept_timestamp IS NULL AND NOT driverarrived_timestamp IS NULL
      THEN EXTRACT(EPOCH FROM driverarrived_timestamp - driveraccept_timestamp)
    `
Actual chart: type=`line` x=`hour` y=`avg_accept_to_arrival_minutes` series=`None`
Failed checks:
- `filter_missing`: Expected filter {'field': 'status_order', 'operator': '=', 'value': 'done', 'value_any_of': [], 'value_contains': []}; actual filters=[{'field': 'driverdone_timestamp', 'operator': 'IS NOT NULL', 'value': None}, {'field': 'order_timestamp', 'operator': '=', 'value': '2026-04-14'}]
- `sql_required_substring_missing`: Required SQL substring `status_order` missing.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
