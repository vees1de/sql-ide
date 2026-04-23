# Chat Text-to-SQL Eval: dvdrental_complex_chat_text_to_sql

- API: `http://127.0.0.1:8001/api`
- Started: `2026-04-23T02:16:37.088131+00:00`
- Duration: `163.414` sec
- Scores: overall `0.235`, understanding `0.000`, sql `0.429`, chart `0.278`

## Priority issues

### sql_required_substring_missing (5)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `daily_store_revenue_march_2007#step1`: Required SQL substring `2007-03` missing.
- `daily_store_revenue_march_2007#step1`: Required SQL substring `payment_date` missing.
- `top_categories_revenue_april_2007#step1`: Required SQL substring `2007-04` missing.
- `top_categories_revenue_april_2007#step1`: Required SQL substring `payment` missing.
- `top_categories_revenue_april_2007#step1`: Required SQL substring `category` missing.

### execution_required_column_missing (4)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `daily_store_revenue_march_2007#step1`: Expected one of columns ['day']; actual columns=['payment_count', 'total_revenue', 'year']
- `daily_store_revenue_march_2007#step1`: Expected one of columns ['store_id']; actual columns=['payment_count', 'total_revenue', 'year']
- `top_categories_revenue_april_2007#step1`: Expected one of columns ['category']; actual columns=['film_count', 'rating', 'total_revenue']
- `top_categories_revenue_april_2007#step1`: Expected one of columns ['payment_count']; actual columns=['film_count', 'rating', 'total_revenue']

### clarification_unexpected (3)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `daily_store_revenue_march_2007#step1`: Expected a direct answer, but the system asked for clarification.
- `top_categories_revenue_april_2007#step1`: Expected a direct answer, but the system asked for clarification.
- `weekly_late_return_rate_august_2005#step1`: Expected a direct answer, but the system asked for clarification.

### chart_x_mismatch (2)
Неверно выбрана ось X.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `daily_store_revenue_march_2007#step1`: Chart x=year, acceptable=['day']
- `top_categories_revenue_april_2007#step1`: Chart x=rating, acceptable=['category']

### chart_missing (1)
Chart recommendation отсутствует или не может быть построен.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `weekly_late_return_rate_august_2005#step1`: Chart cannot be evaluated without execution payload.

### chart_series_mismatch (1)
Серия/legend выбрана неверно либо потеряна.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `daily_store_revenue_march_2007#step1`: Chart series=∅, acceptable=['store_id']

### chart_type_mismatch (1)
Выбран неподходящий тип графика.

Suggested files:
- `backend/app/services/chart_decision_service.py`
- `backend/app/services/chart_data_adapter.py`
- `backend/app/services/llm_service.py`

Examples:
- `top_categories_revenue_april_2007#step1`: Chart type=table, acceptable=['bar']

### execution_missing (1)
Тестер не получил execution payload, хотя он нужен для проверки результата.

Suggested files:
- `backend/app/api/routes/chat.py`
- `backend/app/services/chat_execution_service.py`

Examples:
- `weekly_late_return_rate_august_2005#step1`: Execution payload is missing.

## Worst steps

### weekly_late_return_rate_august_2005#step1 (0.000)
Prompt: За август 2005 покажи по неделям среднее фактическое число дней аренды и долю просроченных возвратов. Считать аренду просроченной, если return_date > rental_date + rental_duration дней. Нужен line chart.
Actual clarification: True
Actual SQL: ``
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_missing`: SQL draft is empty.
- `execution_missing`: Execution payload is missing.
- `chart_missing`: Chart cannot be evaluated without execution payload.

### top_categories_revenue_april_2007#step1 (0.302)
Prompt: За апрель 2007 найди топ-10 категорий фильмов по выручке и количеству платежей. Нужен bar chart.
Actual clarification: True
Actual SQL: `SELECT
  f.rating,
  SUM(f.replacement_cost) AS total_revenue,
  COUNT(*) AS film_count
FROM film AS f
WHERE
  f.release_year = 2006
GROUP BY
  f.rating
ORDER BY
  total_revenue DESC NULLS LAST
LIMIT 10`
Actual chart: type=`table` x=`rating` y=`total_revenue` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `2007-04` missing.
- `sql_required_substring_missing`: Required SQL substring `payment` missing.
- `sql_required_substring_missing`: Required SQL substring `category` missing.
- `sql_table_missing`: Required table `payment` missing; actual tables=['film']
- `execution_required_column_missing`: Expected one of columns ['category']; actual columns=['film_count', 'rating', 'total_revenue']

### daily_store_revenue_march_2007#step1 (0.405)
Prompt: За март 2007 покажи по дням выручку и количество платежей по магазинам. Нужен line chart.
Actual clarification: True
Actual SQL: `SELECT
  f.release_year AS year,
  SUM(f.rental_rate) AS total_revenue,
  COUNT(*) AS payment_count
FROM film AS f
GROUP BY
  f.release_year
ORDER BY
  f.release_year
LIMIT 50`
Actual chart: type=`line` x=`year` y=`total_revenue` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `2007-03` missing.
- `sql_required_substring_missing`: Required SQL substring `payment_date` missing.
- `execution_required_column_missing`: Expected one of columns ['day']; actual columns=['payment_count', 'total_revenue', 'year']
- `execution_required_column_missing`: Expected one of columns ['store_id']; actual columns=['payment_count', 'total_revenue', 'year']
- `chart_x_mismatch`: Chart x=year, acceptable=['day']

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
