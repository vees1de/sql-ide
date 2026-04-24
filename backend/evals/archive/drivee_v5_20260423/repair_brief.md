# Chat Text-to-SQL Eval: drivee_complex_chat_text_to_sql

- API: `http://127.0.0.1:8001/api`
- Started: `2026-04-23T00:11:24.633012+00:00`
- Duration: `142.292` sec
- Scores: overall `0.889`, understanding `0.667`, sql `1.000`, chart `1.000`

## Priority issues

### clarification_unexpected (1)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `hourly_pickup_vs_ride_duration#step1`: Expected a direct answer, but the system asked for clarification.

## Worst steps

### hourly_pickup_vs_ride_duration#step1 (0.667)
Prompt: За 14 апреля 2026 сравни по часам среднее время подачи от принятия водителем до прибытия и среднее время поездки от старта до завершения только для завершённых заказов. Нужен line chart.
Actual clarification: True
Actual SQL: `SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  AVG(EXTRACT(EPOCH FROM (
    driverarrived_timestamp - driveraccept_timestamp
  )) / 60) AS avg_pickup_minutes,
  AVG(
    EXTRACT(EPOCH FROM (
      driverdone_timestamp - driverstart`
Actual chart: type=`line` x=`hour` y=`avg_pickup_minutes` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
