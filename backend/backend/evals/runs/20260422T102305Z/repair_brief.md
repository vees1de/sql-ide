# Chat Text-to-SQL Eval: sakila_complex_chat_text_to_sql

- API: `http://localhost:8000/api`
- Started: `2026-04-22T10:23:05.106348+00:00`
- Duration: `56.607` sec
- Scores: overall `0.883`, understanding `0.750`, sql `0.886`, chart `1.000`

## Priority issues

### sql_required_substring_missing (3)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `monthly_revenue_timeseries#step1`: Required SQL substring `payment` missing.
- `monthly_revenue_timeseries#step1`: Required SQL substring `amount` missing.
- `weekly_rentals_and_revenue#step1`: Required SQL substring `2007` missing.

### clarification_unexpected (1)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `film_late_return_rate_by_rating#step1`: Expected a direct answer, but the system asked for clarification.

### execution_required_column_missing (1)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `monthly_revenue_timeseries#step1`: Expected one of columns ['payment_count', 'total_payments', 'count_payments', 'payments']; actual columns=['month', 'total_revenue']

### sql_table_missing (1)
SQL не использует ожидаемую таблицу или не делает нужный join.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/semantic.py`
- `backend/app/agents/sql_generation.py`

Examples:
- `monthly_revenue_timeseries#step1`: Required table `payment` missing; actual tables=['film']

## Worst steps

### film_late_return_rate_by_rating#step1 (0.683)
Prompt: По каждому рейтингу фильма (G, PG, PG-13, R, NC-17) посчитай долю прокатов, возвращённых позже срока (return_date > rental_date + rental_duration дней). Нужен bar chart.
Actual clarification: True
Actual SQL: `SELECT
  f.rating,
  COUNT(*) FILTER (WHERE r.return_date > r.rental_date + f.rental_duration * INTERVAL '1 day') AS late_rental_count,
  COUNT(*) AS total_rental_count,
  COUNT(*) FILTER (WHERE r.return_date > r.rental_date + f.rental_dura`
Actual chart: type=`bar` x=`rating` y=`late_return_rate` series=`rating`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.

### monthly_revenue_timeseries#step1 (0.879)
Prompt: Покажи помесячно общую выручку и количество платежей за весь период данных. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT
  DATE_TRUNC('MONTH', t0."last_update") AS month,
  SUM(t0."replacement_cost") AS total_revenue
FROM "film" AS t0
GROUP BY
  1
ORDER BY
  1
LIMIT 50`
Actual chart: type=`line` x=`month` y=`total_revenue` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `payment` missing.
- `sql_required_substring_missing`: Required SQL substring `amount` missing.
- `sql_table_missing`: Required table `payment` missing; actual tables=['film']
- `execution_required_column_missing`: Expected one of columns ['payment_count', 'total_payments', 'count_payments', 'payments']; actual columns=['month', 'total_revenue']

### weekly_rentals_and_revenue#step1 (0.970)
Prompt: Покажи понедельно количество аренд и выручку за февраль–май 2007 года. Нужен line chart.
Actual clarification: False
Actual SQL: `SELECT date_trunc('week', r.rental_date) AS week,
       COUNT(*) AS rental_count,
       SUM(p.amount) AS total_revenue
FROM rental r
JOIN payment p ON p.rental_id = r.rental_id
WHERE r.rental_date BETWEEN DATE '2005-01-01' AND DATE '2006-`
Actual chart: type=`line` x=`week` y=`rental_count` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `2007` missing.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
