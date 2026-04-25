# Chat Text-to-SQL Eval: drivee_join_metrics_regression_20260425

- API: `http://127.0.0.1:8001/api`
- Started: `2026-04-25T05:11:41.075658+00:00`
- Duration: `449.136` sec
- Scores: overall `0.755`, understanding `0.800`, sql `0.710`, chart `1.000`

## Priority issues

### sql_required_substring_missing (16)
В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`
- `backend/app/agents/semantic.py`

Examples:
- `city_day_orders_online_time#step1`: Required SQL substring `join` missing.
- `city_day_avg_rides_per_active_driver#step1`: Required SQL substring `join` missing.
- `city_day_avg_rides_per_active_driver#step1`: Required SQL substring `distinct` missing.
- `city_day_avg_rides_per_active_driver#step1`: Required SQL substring `/` missing.
- `city_day_orders_and_driver_acceptance_share#step1`: Required SQL substring `join` missing.

### sql_table_missing (9)
SQL не использует ожидаемую таблицу или не делает нужный join.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/semantic.py`
- `backend/app/agents/sql_generation.py`

Examples:
- `city_day_orders_online_time#step1`: Required table `incity` missing; actual tables=['driver_detail']
- `city_day_avg_rides_per_active_driver#step1`: Required table `incity` missing; actual tables=['driver_detail']
- `city_day_orders_and_driver_acceptance_share#step1`: Required table `incity` missing; actual tables=['driver_detail']
- `city_day_orders_per_driver#step1`: Required table `incity` missing; actual tables=['driver_detail']
- `city_day_orders_and_avg_trip_duration#step1`: Required table `incity` missing; actual tables=['driver_detail']

### execution_required_column_missing (5)
Результат не содержит ожидаемых полей для таблицы/чарта.

Suggested files:
- `backend/app/agents/sql_generation.py`
- `backend/app/services/chat_execution_service.py`
- `backend/app/services/chart_data_adapter.py`

Examples:
- `city_day_orders_online_time#step1`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'total_online_seconds', 'total_orders']
- `city_day_orders_and_driver_acceptance_share#step1`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'driver_count', 'drivers_accepted', 'share_drivers_accepted', 'total_orders']
- `city_day_orders_and_avg_trip_duration#step1`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['avg_ride_minutes', 'city_id', 'day', 'total_orders']
- `city_day_orders_and_post_accept_cancels#step1`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'total_cancels_after_accept', 'total_orders']
- `city_day_driver_efficiency_orders_and_avg_rides#step1`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['avg_rides_per_driver', 'city_id', 'day', 'total_orders_accepted']

### clarification_unexpected (4)
Модель уходит в уточнение там, где ожидался прямой SQL-ответ.

Suggested files:
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/services/chat_sql_adapter.py`

Examples:
- `city_day_orders_drivers_total_rides#step1`: Expected a direct answer, but the system asked for clarification.
- `city_day_orders_online_time#step1`: Expected a direct answer, but the system asked for clarification.
- `city_day_orders_per_driver#step1`: Expected a direct answer, but the system asked for clarification.
- `city_day_orders_and_rides_time#step1`: Expected a direct answer, but the system asked for clarification.

### execution_failed (2)
SQL доехал до execution, но упал на реальной БД.

Suggested files:
- `backend/app/services/chat_execution_service.py`
- `backend/app/agents/validation.py`
- `backend/app/services/llm_service.py`
- `backend/app/agents/sql_generation.py`

Examples:
- `city_day_orders_drivers_total_rides#step1`: Execution failed; error=3 validation errors for MultiSeriesChartPayload
series.0.name
  Input should be a valid string [type=string_type, input_value=60, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
series.1.name
  Input should be a valid string [type=string_type, input_value=50, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
series.2.name
  Input should be a valid string [type=string_type, input_value=76, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
- `city_day_orders_and_rides_time#step1`: Execution failed; error=3 validation errors for MultiSeriesChartPayload
series.0.name
  Input should be a valid string [type=string_type, input_value=60, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
series.1.name
  Input should be a valid string [type=string_type, input_value=50, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
series.2.name
  Input should be a valid string [type=string_type, input_value=76, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type

## Worst steps

### city_day_orders_and_rides_time#step1 (0.464)
Prompt: Хочу понять загрузку водителей: по каждому дню и городу покажи, сколько заказов было и сколько времени водители провели в поездках.
Actual clarification: True
Actual SQL: `SELECT
  dd.tender_date_part AS day,
  dd.city_id,
  SUM(dd.orders) AS orders,
  SUM(dd.rides_time_sum_seconds) AS ride_time_seconds
FROM driver_detail AS dd
WHERE
  dd.tender_date_part >= CAST('2026-03-26' AS DATE)
  AND dd.tender_date_par`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']
- `execution_failed`: Execution failed; error=3 validation errors for MultiSeriesChartPayload
series.0.name
  Input should be a valid string [type=string_type, input_value=60, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
series.1.name
  Input should be a valid string [type=string_type, input_value=50, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
series.2.name
  Input should be a valid string [type=string_type, input_value=76, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type

### city_day_orders_online_time#step1 (0.635)
Prompt: Хочу видеть по дням и городам, сколько заказов было сделано и сколько времени водители суммарно были онлайн.
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
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'total_online_seconds', 'total_orders']

### city_day_orders_drivers_total_rides#step1 (0.659)
Prompt: Покажи по каждому городу и дню, сколько было заказов и сколько водителей их выполняли, а также сколько всего поездок у этих водителей.
Actual clarification: True
Actual SQL: `SELECT
  inc.city_id,
  DATE(inc.order_timestamp) AS day,
  COUNT(*) AS total_orders,
  COUNT(DISTINCT inc.driver_id) AS driver_count,
  COALESCE(SUM(dd.rides_count), 0) AS total_rides
FROM incity AS inc
LEFT JOIN driver_detail AS dd
  ON d`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `execution_failed`: Execution failed; error=3 validation errors for MultiSeriesChartPayload
series.0.name
  Input should be a valid string [type=string_type, input_value=60, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
series.1.name
  Input should be a valid string [type=string_type, input_value=50, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
series.2.name
  Input should be a valid string [type=string_type, input_value=76, input_type=int]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type

### city_day_orders_per_driver#step1 (0.673)
Prompt: Покажи по городам и дням, сколько заказов пришлось на одного водителя.
Actual clarification: True
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  SUM(dd.orders) AS total_orders,
  COUNT(DISTINCT dd.driver_id) AS driver_count,
  CAST(SUM(dd.orders) AS DECIMAL) / NULLIF(COUNT(DISTINCT dd.driver_id), 0) AS orders_per_driver
FROM drive`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `clarification_unexpected`: Expected a direct answer, but the system asked for clarification.
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']

### city_day_orders_and_avg_trip_duration#step1 (0.808)
Prompt: Для каждого города и дня покажи общее количество заказов и среднее время поездки у водителей, которые их выполняли.
Actual clarification: False
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  SUM(dd.orders) AS total_orders,
  CAST((
    SUM(dd.rides_time_sum_seconds) / NULLIF(SUM(dd.rides_count), 0)
  ) / 60 AS DECIMAL(10, 2)) AS avg_ride_minutes
FROM driver_detail AS dd
GROUP`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_required_substring_missing`: Required SQL substring `avg(` missing.
- `sql_required_substring_missing`: Required SQL substring `duration_in_seconds` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['avg_ride_minutes', 'city_id', 'day', 'total_orders']

### city_day_driver_efficiency_orders_and_avg_rides#step1 (0.822)
Prompt: Покажи по дням и городам эффективность водителей: сколько заказов они выполняли и сколько поездок в среднем приходилось на одного водителя.
Actual clarification: False
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  SUM(dd.orders_cnt_accepted) AS total_orders_accepted,
  AVG(dd.rides_count) AS avg_rides_per_driver
FROM driver_detail AS dd
GROUP BY
  dd.city_id,
  dd.tender_date_part
ORDER BY
  dd.cit`
Actual chart: type=`table` x=`day` y=`total_orders_accepted` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_required_substring_missing`: Required SQL substring `distinct` missing.
- `sql_required_substring_missing`: Required SQL substring `/` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['avg_rides_per_driver', 'city_id', 'day', 'total_orders_accepted']

### city_day_avg_rides_per_active_driver#step1 (0.846)
Prompt: Покажи по каждому городу среднее количество поездок на одного водителя среди тех, кто выполнял заказы в этот день.
Actual clarification: False
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  AVG(dd.rides_count) AS avg_rides_per_driver
FROM driver_detail AS dd
WHERE
  dd.orders > 0
GROUP BY
  dd.city_id,
  dd.tender_date_part
ORDER BY
  dd.city_id,
  dd.tender_date_part
LIMIT `
Actual chart: type=`table` x=`day` y=`avg_rides_per_driver` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_required_substring_missing`: Required SQL substring `distinct` missing.
- `sql_required_substring_missing`: Required SQL substring `/` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']

### city_day_orders_and_post_accept_cancels#step1 (0.875)
Prompt: Покажи по дням и городам, сколько заказов сделали водители и сколько у них было отмен после принятия заказа.
Actual clarification: False
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  SUM(dd.orders) AS total_orders,
  SUM(dd.client_cancel_after_accept) AS total_cancels_after_accept
FROM driver_detail AS dd
GROUP BY
  dd.city_id,
  dd.tender_date_part
ORDER BY
  dd.city`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'total_cancels_after_accept', 'total_orders']

### city_day_orders_and_driver_acceptance_share#step1 (0.885)
Prompt: По каждому дню и городу покажи количество заказов и долю водителей, которые приняли заказы.
Actual clarification: False
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  SUM(dd.orders) AS total_orders,
  COUNT(*) AS driver_count,
  COUNT(*) FILTER(WHERE
    dd.orders_cnt_accepted > 0) AS drivers_accepted,
  CAST((
    COUNT(*) FILTER(WHERE
      dd.orders`
Actual chart: type=`table` x=`day` y=`total_orders` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']
- `execution_required_column_missing`: Expected one of columns ['orders_count', 'order_count', 'cnt_orders', 'count_order_id']; actual columns=['city_id', 'day', 'driver_count', 'drivers_accepted', 'share_drivers_accepted', 'total_orders']

### city_day_avg_orders_per_driver_and_online_time#step1 (0.885)
Prompt: По каждому городу и дню покажи среднее количество заказов на водителя и их общее онлайн-время.
Actual clarification: False
Actual SQL: `SELECT
  dd.city_id,
  dd.tender_date_part AS day,
  AVG(dd.orders) AS avg_orders_per_driver,
  SUM(dd.online_time_sum_seconds) AS total_online_time_seconds
FROM driver_detail AS dd
GROUP BY
  dd.city_id,
  dd.tender_date_part
ORDER BY
  dd`
Actual chart: type=`table` x=`day` y=`avg_orders_per_driver` series=`None`
Failed checks:
- `sql_required_substring_missing`: Required SQL substring `join` missing.
- `sql_required_substring_missing`: Required SQL substring `/` missing.
- `sql_table_missing`: Required table `incity` missing; actual tables=['driver_detail']

## Agent loop

1. Fix the highest-frequency issue cluster first.
2. Re-run this suite with the same model/mode.
3. Compare `summary.json` and `failing_steps.json` against the previous run.
4. Stop only when the same failure stops reproducing across the targeted cases.
