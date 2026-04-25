# Chat Text-to-SQL Eval: drivee_join_easy_suite_20260425

- API: `http://127.0.0.1:8001/api`
- Started: `2026-04-25T05:43:04.227610+00:00`
- Duration: `127.45` sec
- Scores: overall `0.669`, understanding `0.500`, sql `0.838`, chart `1.000`

## Priority issues

### sql_required_substring_missing (6)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `orders_and_online_time_by_city_day#step1`: Required SQL substring `join` missing.
- `orders_and_avg_duration_by_city_day#step1`: Required SQL substring `join` missing.
- `orders_and_avg_duration_by_city_day#step1`: Required SQL substring `avg(` missing.
- `orders_and_avg_duration_by_city_day#step1`: Required SQL substring `duration_in_seconds` missing.
- `orders_per_driver_by_city_day#step1`: Required SQL substring `join` missing.

### clarification_unexpected (5)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `orders_and_rides_by_city_day#step1`: Expected a direct answer, but the system asked for clarification.
- `orders_and_online_time_by_city_day#step1`: Expected a direct answer, but the system asked for clarification.
- `orders_and_avg_duration_by_city_day#step1`: Expected a direct answer, but the system asked for clarification.
- `orders_per_driver_by_city_day#step1`: Expected a direct answer, but the system asked for clarification.
- `orders_and_accept_cancels_by_city_day#step1`: Expected a direct answer, but the system asked for clarification.

### sql_table_missing (4)
SQL не использует ожидаемую таблицу или не делает нужный join.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/semantic.py`
- `backend/app/agents/sql_generation.py`

Examples:
- `orders_and_online_time_by_city_day#step1`: Required table `incity` missing; actual tables=['driver_detail']
- `orders_and_avg_duration_by_city_day#step1`: Required table `incity` missing; actual tables=['driver_detail']
- `orders_per_driver_by_city_day#step1`: Required table `incity` missing; actual tables=['driver_detail']
- `orders_and_accept_cancels_by_city_day#step1`: Required table `incity` missing; actual tables=['driver_detail']

## Worst steps

### orders_and_avg_duration_by_city_day#step1 (0.596)
Prompt: Покажи по дням и городам количество заказов и среднюю длительность поездки.
Actual clarification: True
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  SUM(dd.orders) AS total_orders,
  (
    SUM(dd.rides_time_sum_seconds) / NULLIF(SUM(dd.rides_count), 0) / 60.0
  ) AS avg_ride_minutes
FROM driver_detail AS dd
WHERE
  dd.tender_date_part`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_required_substring_missing`: Required SQL substring `avg(` missing.
- `sql_required_substring_missing`: Required SQL substring `duration_in_seconds` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']

### orders_and_online_time_by_city_day#step1 (0.667)
Prompt: Покажи по дням и городам количество заказов и общее онлайн-время водителей.
Actual clarification: True
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  SUM(dd.orders) AS total_orders,
  SUM(dd.online_time_sum_seconds) AS total_online_seconds
FROM driver_detail AS dd
WHERE
  dd.tender_date_part >= CAST('2024-12-06' AS DATE)
  AND dd.tende`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']

### orders_per_driver_by_city_day#step1 (0.667)
Prompt: Покажи по дням и городам, сколько заказов приходится на одного водителя.
Actual clarification: True
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  SUM(dd.orders) AS total_orders,
  COUNT(DISTINCT dd.driver_id) AS driver_count,
  CAST(SUM(dd.orders) AS DECIMAL) / NULLIF(COUNT(DISTINCT dd.driver_id), 0) AS avg_orders_per_driver
FROM d`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']

### orders_and_accept_cancels_by_city_day#step1 (0.667)
Prompt: Покажи по дням и городам количество заказов и количество отмен после принятия заказа.
Actual clarification: True
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  SUM(dd.orders) AS total_orders,
  SUM(dd.client_cancel_after_accept) AS total_client_cancel_after_accept
FROM driver_detail AS dd
WHERE
  dd.tender_date_part >= CAST('2024-12-06' AS DATE)`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']

### orders_and_rides_by_city_day#step1 (0.750)
Prompt: Покажи по дням и городам количество заказов и количество поездок водителей.
Actual clarification: True
Actual SQL: `SELECT
  i.city_id,
  DATE(i.order_timestamp) AS day,
  COUNT(DISTINCT i.order_id) AS total_orders,
  SUM(dd.rides_count) AS total_rides
FROM incity AS i
LEFT JOIN driver_detail AS dd
  ON i.driver_id = dd.driver_id AND DATE(i.order_timesta`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
