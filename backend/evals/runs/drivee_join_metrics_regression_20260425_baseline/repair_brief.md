# Chat Text-to-SQL Eval: drivee_join_metrics_regression_20260425

- API: `http://127.0.0.1:8001/api`
- Started: `2026-04-25T04:49:58.112212+00:00`
- Duration: `365.963` sec
- Scores: overall `0.654`, understanding `0.500`, sql `0.807`, chart `1.000`

## Priority issues

### clarification_unexpected (10)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `city_day_orders_drivers_total_rides#step1`: Expected a direct answer, but the system asked for clarification.
- `city_day_orders_online_time#step1`: Expected a direct answer, but the system asked for clarification.
- `city_day_avg_rides_per_active_driver#step1`: Expected a direct answer, but the system asked for clarification.
- `city_day_orders_and_driver_acceptance_share#step1`: Expected a direct answer, but the system asked for clarification.
- `city_day_orders_per_driver#step1`: Expected a direct answer, but the system asked for clarification.

### sql_required_substring_missing (10)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `city_day_orders_online_time#step1`: Required SQL substring `join` missing.
- `city_day_avg_rides_per_active_driver#step1`: Required SQL substring `join` missing.
- `city_day_orders_per_driver#step1`: Required SQL substring `join` missing.
- `city_day_orders_and_avg_trip_duration#step1`: Required SQL substring `join` missing.
- `city_day_orders_and_avg_trip_duration#step1`: Required SQL substring `avg(` missing.

### sql_table_missing (8)
SQL не использует ожидаемую таблицу или не делает нужный join.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/semantic.py`
- `backend/app/agents/sql_generation.py`

Examples:
- `city_day_orders_online_time#step1`: Required table `incity` missing; actual tables=['driver_detail']
- `city_day_avg_rides_per_active_driver#step1`: Required table `incity` missing; actual tables=['driver_detail']
- `city_day_orders_per_driver#step1`: Required table `incity` missing; actual tables=['driver_detail']
- `city_day_orders_and_avg_trip_duration#step1`: Required table `incity` missing; actual tables=['driver_detail']
- `city_day_orders_and_rides_time#step1`: Required table `incity` missing; actual tables=['driver_detail']

### execution_required_column_missing (7)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `city_day_orders_drivers_total_rides#step1`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'driver_count', 'total_orders', 'total_rides']
- `city_day_orders_online_time#step1`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'total_online_seconds', 'total_orders']
- `city_day_orders_and_driver_acceptance_share#step1`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'driver_acceptance_share', 'total_orders']
- `city_day_orders_and_avg_trip_duration#step1`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['avg_ride_minutes', 'city_id', 'day', 'total_orders']
- `city_day_orders_and_rides_time#step1`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'total_orders', 'total_ride_seconds']

## Worst steps

### city_day_orders_and_avg_trip_duration#step1 (0.558)
Prompt: Для каждого города и дня покажи общее количество заказов и среднее время поездки у водителей, которые их выполняли.
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
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['avg_ride_minutes', 'city_id', 'day', 'total_orders']

### city_day_orders_and_rides_time#step1 (0.625)
Prompt: Хочу понять загрузку водителей: по каждому дню и городу покажи, сколько заказов было и сколько времени водители провели в поездках.
Actual clarification: True
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  SUM(dd.orders) AS total_orders,
  SUM(dd.rides_time_sum_seconds) AS total_ride_seconds
FROM driver_detail AS dd
WHERE
  dd.tender_date_part >= CAST('2024-12-06' AS DATE)
  AND dd.tender_d`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'total_orders', 'total_ride_seconds']

### city_day_orders_and_post_accept_cancels#step1 (0.625)
Prompt: Покажи по дням и городам, сколько заказов сделали водители и сколько у них было отмен после принятия заказа.
Actual clarification: True
Actual SQL: `SELECT
  tender_date_part AS day,
  city_id,
  SUM(orders) AS total_orders,
  SUM(client_cancel_after_accept) AS total_client_cancel_after_accept
FROM driver_detail
WHERE
  tender_date_part BETWEEN CAST('2026-04-18' AS DATE) AND CAST('2026-`
Actual chart: type=`line` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'total_client_cancel_after_accept', 'total_orders']

### city_day_orders_online_time#step1 (0.635)
Prompt: Хочу видеть по дням и городам, сколько заказов было сделано и сколько времени водители суммарно были онлайн.
Actual clarification: True
Actual SQL: `SELECT
  city_id,
  tender_date_part AS day,
  SUM(orders) AS total_orders,
  SUM(online_time_sum_seconds) AS total_online_seconds
FROM driver_detail
GROUP BY
  city_id,
  tender_date_part
ORDER BY
  city_id,
  day
LIMIT 50`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'total_online_seconds', 'total_orders']

### city_day_driver_efficiency_orders_and_avg_rides#step1 (0.643)
Prompt: Покажи по дням и городам эффективность водителей: сколько заказов они выполняли и сколько поездок в среднем приходилось на одного водителя.
Actual clarification: True
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  SUM(dd.orders) AS total_orders,
  SUM(dd.rides_count) / NULLIF(COUNT(DISTINCT dd.driver_id), 0) AS avg_rides_per_driver
FROM driver_detail AS dd
WHERE
  dd.tender_date_part >= CAST('2024-`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['avg_rides_per_driver', 'city_id', 'day', 'total_orders']

### city_day_avg_rides_per_active_driver#step1 (0.673)
Prompt: Покажи по каждому городу среднее количество поездок на одного водителя среди тех, кто выполнял заказы в этот день.
Actual clarification: True
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  CAST(SUM(dd.rides_count) AS DECIMAL) / NULLIF(COUNT(DISTINCT dd.driver_id), 0) AS avg_rides_per_driver
FROM driver_detail AS dd
WHERE
  dd.orders > 0
  AND dd.tender_date_part >= CAST('20`
Actual chart: type=`table` x=`day` y=`avg_rides_per_driver` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']

### city_day_orders_per_driver#step1 (0.673)
Prompt: Покажи по городам и дням, сколько заказов пришлось на одного водителя.
Actual clarification: True
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  CAST(SUM(dd.orders) AS DECIMAL) / NULLIF(COUNT(DISTINCT dd.driver_id), 0) AS orders_per_driver
FROM driver_detail AS dd
WHERE
  dd.tender_date_part >= CAST('2024-10-23' AS DATE)
  AND dd.`
Actual chart: type=`table` x=`day` y=`orders_per_driver` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']

### city_day_avg_orders_per_driver_and_online_time#step1 (0.673)
Prompt: По каждому городу и дню покажи среднее количество заказов на водителя и их общее онлайн-время.
Actual clarification: True
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  CAST(SUM(dd.orders) AS DECIMAL) / NULLIF(COUNT(DISTINCT dd.driver_id), 0) AS avg_orders_per_driver,
  SUM(dd.online_time_sum_seconds) AS total_online_seconds
FROM driver_detail AS dd
WHER`
Actual chart: type=`table` x=`day` y=`avg_orders_per_driver` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']

### city_day_orders_and_driver_acceptance_share#step1 (0.712)
Prompt: По каждому дню и городу покажи количество заказов и долю водителей, которые приняли заказы.
Actual clarification: True
Actual SQL: `SELECT
  i.city_id,
  DATE(i.order_timestamp) AS day,
  COUNT(DISTINCT i.order_id) AS total_orders,
  CAST(COUNT(DISTINCT CASE WHEN dd.orders_cnt_accepted > 0 THEN dd.driver_id END) AS DECIMAL) / NULLIF(COUNT(DISTINCT dd.driver_id), 0) AS d`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'driver_acceptance_share', 'total_orders']

### city_day_orders_drivers_total_rides#step1 (0.721)
Prompt: Покажи по каждому городу и дню, сколько было заказов и сколько водителей их выполняли, а также сколько всего поездок у этих водителей.
Actual clarification: True
Actual SQL: `SELECT
  i.city_id,
  DATE(i.order_timestamp) AS day,
  COUNT(DISTINCT i.order_id) AS total_orders,
  COUNT(DISTINCT i.driver_id) AS driver_count,
  SUM(dd.rides_count) AS total_rides
FROM incity AS i
LEFT JOIN driver_detail AS dd
  ON i.dr`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'driver_count', 'total_orders', 'total_rides']

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
