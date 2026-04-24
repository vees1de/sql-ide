# Техническое описание text-to-SQL пайплайна

Этот файл описывает, как в этом репозитории работает поток `non-tech text classification -> SQL -> dataset`, и фиксирует два сложных реальных примера с пользовательским запросом, формой backend-пейлоада и итоговым SQL/результатом выполнения.

## Архитектура

Основные файлы:

- [backend/app/api/routes/chat.py](/Users/vees1de/repos/sql-ide/backend/app/api/routes/chat.py)
- [backend/app/services/chat_sql_adapter.py](/Users/vees1de/repos/sql-ide/backend/app/services/chat_sql_adapter.py)
- [backend/app/services/llm_service.py](/Users/vees1de/repos/sql-ide/backend/app/services/llm_service.py)
- [backend/app/services/chat_execution_service.py](/Users/vees1de/repos/sql-ide/backend/app/services/chat_execution_service.py)
- [backend/app/agents/intent.py](/Users/vees1de/repos/sql-ide/backend/app/agents/intent.py)
- [backend/app/agents/semantic.py](/Users/vees1de/repos/sql-ide/backend/app/agents/semantic.py)
- [backend/app/agents/sql_generation.py](/Users/vees1de/repos/sql-ide/backend/app/agents/sql_generation.py)
- [backend/app/agents/validation.py](/Users/vees1de/repos/sql-ide/backend/app/agents/validation.py)

На высоком уровне система работает так:

1. Фронтенд отправляет сообщение пользователя в `POST /chat/sessions/{session_id}/messages`.
2. `chat.py` вызывает `ChatSqlAdapter.generate_response(...)`.
3. Адаптер загружает:
   - сессию,
   - previous intent из `session.last_intent_json`,
   - недавнюю историю сообщений,
   - dictionary entries,
   - semantic/catalog context, если он доступен.
4. В режиме `thinking` адаптер сначала пытается путь LLM-планирования через `LLMService.plan_query(...)`.
5. У LLM запрашивается один JSON-объект с полями:
   - `state`,
   - `assistant_message`,
   - `semantic_parse`,
   - `actions`,
   - `intent`,
   - `semantics`,
   - `sql`,
   - `warnings`.
6. Если ответ — это уточнение, адаптер сохраняет:
   - сообщение пользователя,
   - сообщение-уточнение ассистента,
   - structured payload,
   - `current_sql_draft = null`.
7. Если SQL готов, адаптер сохраняет draft SQL в сессии и возвращает structured payload с действиями вроде `show_run_button`, `show_sql`, `show_chart_preview`.
8. Когда пользователь запускает SQL, `ChatExecutionService.execute(...)` валидирует запрос, делает dry run, исполняет его, сериализует строки и создаёт dataset из результата.
9. Если выполнение падает или возвращает 0 строк, сервис может вызвать `LLMService.repair_sql(...)` и повторить попытку.
10. Рекомендация графика строится после выполнения и сохраняется вместе с execution record.

## Что сохраняется

Система хранит два слоя истории:

- История диалога в `ChatMessageModel`.
- История выполнения в `QueryExecutionModel` и записях dataset.

Ключевые точки сохранения:

- `ChatService.append_message(...)` сохраняет сырой user/assistant text плюс `structured_payload`.
- `ChatService.update_session_fields(...)` сохраняет last intent, SQL draft и last executed SQL.
- `ChatExecutionService.execute(...)` сохраняет:
  - выполненный SQL,
  - schema колонок,
  - preview rows,
  - количество строк,
  - время выполнения,
  - JSON рекомендации графика,
  - связанный dataset.

## Что реально получает LLM

Пейлоад запроса, который собирается в `LLMService.plan_query(...)`, содержит:

- `today`
- `dialect`
- `schema`
- `semantic_catalog`
- `semantic_contract`
- `semantic_notes`
- `previous_intent`
- `history_text`
- `alias_contract`
- `available_tools`
- `user_prompt`

Точный system prompt и JSON-конверт собираются в:

- [backend/app/services/llm_service.py](/Users/vees1de/repos/sql-ide/backend/app/services/llm_service.py)

Промпт намеренно жёсткий:

- вернуть ровно один JSON object,
- не генерировать write queries,
- предпочитать explicit joins и explicit aliases,
- использовать semantic catalog и schema truth как source of truth,
- уточнять, когда термин ambiguous,
- держать clarification options schema-grounded.

## Формат логов в этом файле

Для каждого примера ниже я сохраняю:

- user input,
- backend interpretation,
- LLM-facing request shape,
- assistant output,
- final SQL,
- execution result.

Примеры взяты из:

- [backend/evals/runs/drivee_agentic_v2_recheck3_20260424/results.json](/Users/vees1de/repos/sql-ide/backend/evals/runs/drivee_agentic_v2_recheck3_20260424/results.json)

## Пример 1: Созданные заказы, завершённые заказы и completion rate по часам

### Ввод пользователя

```text
За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart.
```

### Уточнение от пользователя

Система прогнала одно уточняющее сообщение:

```text
Hour
```

Это follow-up selection, который использовал eval harness для выбора часового grain.

### Форма backend-запроса

LLM planning request собирается так:

```json
{
  "today": "2026-04-24",
  "dialect": "postgresql",
  "schema": "<сводка схемы, сформированная на backend>",
  "semantic_catalog": "<semantic catalog, если доступен>",
  "semantic_contract": "<semantic contract, если доступен>",
  "semantic_notes": [],
  "previous_intent": null,
  "history_text": "",
  "alias_contract": "<ссылка на alias contract>",
  "available_tools": [],
  "user_prompt": "За 14 апреля 2026 покажи по часам количество созданных заказов, количество завершённых поездок и конверсию в завершение. Нужен line chart."
}
```

В реальном runtime это оборачивается в OpenAI chat payload так:

```json
[
  { "role": "system", "content": "<жёсткий planning system prompt>" },
  { "role": "user", "content": "<JSON-документ выше>" }
]
```

### Ответ ассистента

Результат eval показывает, что ассистент вернул SQL-ready payload и включил действия для просмотра/запуска SQL.

### Итоговый SQL

```sql
SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  COUNT(*) AS total_orders,
  COUNT(CASE WHEN NOT driverdone_timestamp IS NULL THEN 1 END) AS completed_orders,
  CAST(COUNT(CASE WHEN NOT driverdone_timestamp IS NULL THEN 1 END) AS DOUBLE PRECISION) / NULLIF(COUNT(*), 0) AS completion_rate
FROM train
WHERE
  DATE(order_timestamp) = '2026-04-14'
GROUP BY
  hour
ORDER BY
  hour
LIMIT 50
```

### Результат выполнения

Колонки:

- `hour`
- `total_orders`
- `completed_orders`
- `completion_rate`

Preview rows содержат hourly aggregates для `2026-04-14`, например:

- `2026-04-14T00:00:00.000` -> `18 / 5 / 0.2777777778`
- `2026-04-14T07:00:00.000` -> `140 / 65 / 0.4642857143`

Рекомендация графика в этом прогоне была `line` с:

- x-axis: `hour`
- y-axis: `completion_rate` или count-series

## Пример 2: Среднее время прибытия и длительность поездки по часам для завершённых заказов

### Ввод пользователя

```text
А теперь оставь только завершённые заказы и сравни по часам среднее время от принятия до прибытия и среднее время поездки от старта до завершения.
```

### Форма backend-запроса

У этого запроса такая же форма, но адаптер ещё несёт состояние предыдущего диалога, потому что это follow-up.

Важные поля:

- `history_text` содержит недавние user/assistant turns.
- `previous_intent` хранит предыдущий metric/dimension context.
- `user_prompt` — это новое follow-up сообщение.

### Ответ ассистента

Результат выполнения показывает, что ассистент собрал SQL-ready ответ с двумя метриками и без уточнения.

### Итоговый SQL

```sql
SELECT
  DATE_TRUNC('HOUR', order_timestamp) AS hour,
  AVG(EXTRACT(EPOCH FROM (
    driverarrived_timestamp - driveraccept_timestamp
  )) / 60) AS avg_accept_to_arrival_minutes,
  AVG(
    EXTRACT(EPOCH FROM (
      driverdone_timestamp - driverstarttheride_timestamp
    )) / 60
  ) AS avg_start_to_done_minutes
FROM train
WHERE
  NOT driverdone_timestamp IS NULL
  AND NOT driveraccept_timestamp IS NULL
  AND NOT driverarrived_timestamp IS NULL
  AND NOT driverstarttheride_timestamp IS NULL
GROUP BY
  hour
ORDER BY
  hour ASC
LIMIT 50
```

### Результат выполнения

Колонки:

- `hour`
- `avg_accept_to_arrival_minutes`
- `avg_start_to_done_minutes`

Preview rows показывают почасовые значения, например:

- `2025-01-02T14:00:00.000` -> `1.8166666667 / 2827.7166666667`
- `2025-01-03T08:00:00.000` -> `2.0633333333 / 3.11`

Этот запрос хорошо показывает, что система сохраняет контекст между follow-up-ответами:

- the time grain remains hourly,
- the completed-order filter is enforced via non-null timestamps,
- both requested metrics are translated into explicit SQL aggregates.

## Интерпретация пайплайна

Фактически это не просто классификация. Это staged semantic compiler:

- text -> intent,
- intent -> semantic mapping,
- semantic mapping -> SQL,
- SQL -> validation,
- validation -> execution,
- execution -> dataset and chart.

Ключевое отличие от типового NL2SQL demo в том, что этот репозиторий ещё хранит:

- conversation memory,
- clarification state,
- semantic catalog / contract grounding,
- SQL draft versioning,
- post-execution dataset materialization.

## Где смотреть сырой артефакт

Если нужен полный run artifact для примеров выше, открой:

- [backend/evals/runs/drivee_agentic_v2_recheck3_20260424/results.json](/Users/vees1de/repos/sql-ide/backend/evals/runs/drivee_agentic_v2_recheck3_20260424/results.json)
- [backend/evals/runs/drivee_agentic_v2_recheck3_20260424/summary.json](/Users/vees1de/repos/sql-ide/backend/evals/runs/drivee_agentic_v2_recheck3_20260424/summary.json)

Если хочешь расширить это живыми wire logs API, лучшее место для этого:

- `LLMService._chat_json(...)`
- `LLMService._chat_json_with_tools(...)`
- `ChatSqlAdapter._persist_result(...)`
- `ChatExecutionService.execute(...)`
