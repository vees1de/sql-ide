# Chat Text-to-SQL Eval: dvdrental_complex_chat_text_to_sql

- API: `http://127.0.0.1:8001/api`
- Started: `2026-04-23T02:04:49.997122+00:00`
- Duration: `104.769` sec
- Scores: overall `0.182`, understanding `0.333`, sql `0.212`, chart `0.000`

## Priority issues

### chart_missing (3)
Chart recommendation отсутствует или не может быть построен.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `daily_store_revenue_march_2007#step1`: Chart cannot be evaluated without execution payload.
- `top_categories_revenue_april_2007#step1`: Chart cannot be evaluated without execution payload.
- `weekly_late_return_rate_august_2005#step1`: Chart recommendation is missing.

### clarification_unexpected (2)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `daily_store_revenue_march_2007#step1`: Expected a direct answer, but the system asked for clarification.
- `top_categories_revenue_april_2007#step1`: Expected a direct answer, but the system asked for clarification.

### execution_missing (2)
Тестер не получил execution payload, хотя он нужен для проверки результата.

Suggested files:
- `backend/app/api/routes/chat.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `daily_store_revenue_march_2007#step1`: Execution payload is missing.
- `top_categories_revenue_april_2007#step1`: Execution payload is missing.

### sql_missing (2)
SQL вообще не был сгенерирован там, где ожидался ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/services/chat_sql_adapter.py`
- `backend/app/services/analytics_agent_service.py`

Examples:
- `daily_store_revenue_march_2007#step1`: SQL draft is empty.
- `top_categories_revenue_april_2007#step1`: SQL draft is empty.

### sql_table_missing (2)
SQL не использует ожидаемую таблицу или не делает нужный join.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/semantic.py`
- `backend/app/agents/sql_generation.py`

Examples:
- `weekly_late_return_rate_august_2005#step1`: Required table `film` missing; actual tables=['rental']
- `weekly_late_return_rate_august_2005#step1`: Required table `inventory` missing; actual tables=['rental']

### execution_failed (1)
SQL доехал до execution, но упал на реальной БД.

Suggested files:
- `backend/app/services/chat_execution_service.py`
- `backend/app/agents/validation.py`
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`

Examples:
- `weekly_late_return_rate_august_2005#step1`: Execution failed; error=(psycopg2.errors.UndefinedColumn) column r.rental_duration does not exist
LINE 8:       WHEN r.return_date > r.rental_date + r.rental_duration...
                                                   ^

[SQL: SELECT
  CAST(DATE_TRUNC('WEEK', r.rental_date) AS DATE) AS week,
  AVG((
    CAST(r.return_date AS DATE) - CAST(r.rental_date AS DATE)
  )) AS avg_rental_days,
  CAST(SUM(
    CASE
      WHEN r.return_date > r.rental_date + r.rental_duration * INTERVAL '1 DAY'
      THEN 1
      ELSE 0
    END
  ) AS DOUBLE PRECISION) / NULLIF(COUNT(*), 0) AS overdue_rate
FROM rental AS r
WHERE
  r.rental_date >= CAST('2005-08-01' AS DATE)
  AND r.rental_date < CAST('2005-09-01' AS DATE)
  AND NOT r.return_date IS NULL
GROUP BY
  week
ORDER BY
  week
LIMIT 50]
(Background on this error at: https://sqlalche.me/e/20/f405)

## Worst steps

### daily_store_revenue_march_2007#step1 (0.000)
Prompt: За март 2007 покажи по дням выручку и количество платежей по магазинам. Нужен line chart.
Actual clarification: True
Actual SQL: ``
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_missing`: SQL draft is empty.
- `execution_missing`: Execution payload is missing.
- `chart_missing`: Chart cannot be evaluated without execution payload.

### top_categories_revenue_april_2007#step1 (0.000)
Prompt: За апрель 2007 найди топ-10 категорий фильмов по выручке и количеству платежей. Нужен bar chart.
Actual clarification: True
Actual SQL: ``
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_missing`: SQL draft is empty.
- `execution_missing`: Execution payload is missing.
- `chart_missing`: Chart cannot be evaluated without execution payload.

### weekly_late_return_rate_august_2005#step1 (0.545)
Prompt: За август 2005 покажи по неделям среднее фактическое число дней аренды и долю просроченных возвратов. Считать аренду просроченной, если return_date > rental_date + rental_duration дней. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  CAST(DATE_TRUNC('WEEK', r.rental_date) AS DATE) AS week,
  AVG((
    CAST(r.return_date AS DATE) - CAST(r.rental_date AS DATE)
  )) AS avg_rental_days,
  CAST(SUM(
    CASE
      WHEN r.return_date > r.rental_date + r.rental_durati`
Failed checks:
- `sql_table_missing`: Required table `film` missing; actual tables=['rental']
- `sql_table_missing`: Required table `inventory` missing; actual tables=['rental']
- `execution_failed`: Execution failed; error=(psycopg2.errors.UndefinedColumn) column r.rental_duration does not exist
LINE 8:       WHEN r.return_date > r.rental_date + r.rental_duration...
                                                   ^

[SQL: SELECT
  CAST(DATE_TRUNC('WEEK', r.rental_date) AS DATE) AS week,
  AVG((
    CAST(r.return_date AS DATE) - CAST(r.rental_date AS DATE)
  )) AS avg_rental_days,
  CAST(SUM(
    CASE
      WHEN r.return_date > r.rental_date + r.rental_duration * INTERVAL '1 DAY'
      THEN 1
      ELSE 0
    END
  ) AS DOUBLE PRECISION) / NULLIF(COUNT(*), 0) AS overdue_rate
FROM rental AS r
WHERE
  r.rental_date >= CAST('2005-08-01' AS DATE)
  AND r.rental_date < CAST('2005-09-01' AS DATE)
  AND NOT r.return_date IS NULL
GROUP BY
  week
ORDER BY
  week
LIMIT 50]
(Background on this error at: https://sqlalche.me/e/20/f405)
- `chart_missing`: Chart recommendation is missing.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
