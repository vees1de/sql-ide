# Chat Text-to-SQL Eval: drivee_agentic_chat_suite_v2

- API: `http://127.0.0.1:8000/api`
- Started: `2026-04-23T18:38:48.193577+00:00`
- Duration: `62.648` sec
- Scores: overall `0.991`, understanding `1.000`, sql `0.956`, chart `1.000`

## Priority issues

### sql_required_substring_missing (2)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `2026-04-14` missing.
- `hourly_followup_done_only_metrics#step2`: Required SQL substring `status_order` missing.

## Worst steps

### hourly_followup_done_only_metrics#step2 (0.956)
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
- `sql_required_substring_missing`: Required SQL substring `2026-04-14` missing.
- `sql_required_substring_missing`: Required SQL substring `status_order` missing.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
