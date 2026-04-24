# Eval Guide

Этот гайд описывает, как прогонять `chat -> SQL -> execute -> chart` eval suite, как читать артефакты и как дебажить flaky кейсы, где система иногда уходит в кларификацию вместо прямого SQL-ответа.

## Что именно проверяет eval

Harness вызывает реальный `/api/chat` pipeline и отдельно оценивает:

- `understanding`
- `sql`
- `chart`

Эти три bucket'а считаются так:

- `understanding`:
  - совпал ли ожидаемый режим ответа: прямой ответ, clarification, SQL-ready
  - сохранён ли follow-up контекст из предыдущего сообщения
  - попали ли нужные intent-фильтры, dimensions и date range
  - были ли clarification-вопросы достаточно конкретными и schema-grounded
  - предложены ли понятные варианты ответа, если нужен выбор
- `sql`:
  - SQL ли вообще был сгенерирован
  - парсится ли он
  - есть ли ожидаемые таблицы, колонки и критичные паттерны
  - не потерялись ли важные predicate'ы и group by-структура
- `chart`:
  - соответствует ли chart recommendation фактическому result shape
  - совпадают ли x/y/series с ожидаемой аналитической осью

`overall` считается как среднее по применимым bucket'ам. Если bucket не участвует в шаге, он не должен тянуть итог вниз.

### Что считается правильным промптом

Метрика промпта в этом suite не равна буквальному совпадению строки. Мы считаем промпт правильным, если система:

- поняла бизнес-намерение
- не потеряла контекст предыдущего сообщения
- задаёт уточнение только когда оно реально нужно
- предлагает понятные варианты выбора, если запрос неоднозначный
- сохраняет семантически эквивалентные фильтры и агрегации

Примеры семантически эквивалентных совпадений:

- `done` и `completed`
- `hour` и `hour_of_day`
- `avg_pickup_minutes` и `avg_accept_to_arrival_minutes`
- `total_orders` и `created_orders`

При необходимости он также вызывает `/execute`, чтобы проверить фактический result shape и `chart_recommendation`.

Артефакты каждого прогона:

- `results.json`
- `summary.json`
- `failing_steps.json`
- `repair_brief.md`

Они складываются в `backend/evals/runs/<run_name>/`.

## Быстрый запуск

Из директории `backend`:

```bash
.venv/bin/python scripts/eval_chat_text_to_sql.py \
  --cases evals/drivee_complex_suite.json \
  --api-base http://127.0.0.1:8000/api \
  --output-dir evals/runs/drivee_manual_run
```

Полезные флаги:

- `--query-mode thinking`
- `--model-alias gpt120`
- `--database-id <db_id>`
- `--with-judge`
- `--fail-under 0.85`

Посмотреть все параметры:

```bash
cd backend
.venv/bin/python scripts/eval_chat_text_to_sql.py --help
```

## Рекомендуемый цикл работы

1. Прогнать suite против локального backend.
2. Открыть `summary.json` и `repair_brief.md`.
3. Исправить самый частый или самый дорогой класс ошибок.
4. Перезапустить backend на новой версии кода.
5. Прогнать тот же suite повторно.
6. Сравнить новый `summary.json` с предыдущим.

Если SQL и charts уже зелёные, а `understanding` падает, почти всегда проблема в одном из трёх мест:

- лишняя кларификация
- нестабильный LLM planning path
- fallback после невалидного плана или validation failure

## Как читать результаты

`summary.json` нужен для общей картины:

- `overall`
- `understanding`
- `sql`
- `chart`
- top issue counts

`repair_brief.md` нужен для приоритизации:

- какой failure class остался
- на каком шаге он воспроизводится
- какой SQL или clarification реально вернулся
- какие файлы стоит смотреть в первую очередь

`failing_steps.json` нужен для точечного воспроизведения:

- исходный prompt
- ожидаемое поведение
- фактический payload

## Когда suite падает на clarification

Если один и тот же prompt иногда отвечает SQL, а иногда возвращает:

```text
How should the result be grouped?
```

это обычно не бизнес-логика, а нестабильность LLM path:

- transient failure планирования
- невалидный SQL после plan
- fallback в rule-based clarification path

В такой ситуации сначала нужно проверить не suite, а живой `chat` API.

## Точечная проверка одного prompt через chat API

Ниже скрипт, который создаёт чистую сессию и отправляет один и тот же prompt несколько раз.

```bash
cd backend && .venv/bin/python - <<'PY'
import json
import urllib.request

BASE = 'http://127.0.0.1:8000/api'
DB_ID = '30a98b573aef4c069fd14d129e21f82b'
PROMPT = 'За 14 апреля 2026 сравни по часам среднее время подачи от принятия водителем до прибытия и среднее время поездки от старта до завершения только для завершённых заказов. Нужен line chart.'

def req(method, path, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode('utf-8'))

results = []
for i in range(5):
    session = req('POST', f'/chat/databases/{DB_ID}/sessions', {'title': f'debug flake {i}'})
    result = req('POST', f"/chat/sessions/{session['id']}/messages", {
        'text': PROMPT,
        'query_mode': 'thinking',
        'llm_model_alias': 'gpt120',
    })
    payload = result['assistant_message']['structured_payload']
    results.append({
        'i': i + 1,
        'needs_clarification': payload.get('needs_clarification'),
        'question': payload.get('clarification_question'),
        'has_sql': bool(payload.get('sql')),
    })

print(json.dumps(results, ensure_ascii=False, indent=2))
PY
```

Если ответы флапают между `clarification` и `sql`, проблема находится в orchestration path, а не в конкретном wording prompt.

## Edge cases и сложные кейсы

При расширении metrics полезно держать отдельные тесты на такие сценарии:

- прямой вопрос о колонке с предложением выгрузить таблицу
- ambiguity-first запрос с 3-5 вариантами ответа
- follow-up, который должен наследовать метрику, фильтр и группировку
- семантически эквивалентные фильтры, например `done` vs `completed`
- сложный временной запрос, где SQL может быть выражен по-разному, но смысл одинаковый

Если такой кейс падает, сначала проверьте:

1. не слишком ли literal сейчас проверка
2. не потерялся ли контекст чата
3. не требует ли suite отдельного semantic alias
4. не нужно ли ослабить SQL-substring check до более семантического сигнала

## Как проверять новую версию кода, не ломая основной backend

Удобнее поднимать отдельный backend-процесс на другом порту, например `8001`.

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
```

После этого можно:

1. проверить flaky prompt на `8001`
2. запустить весь suite против `8001`
3. не трогать основной процесс на `8000`

Пример полного прогона:

```bash
cd backend
.venv/bin/python scripts/eval_chat_text_to_sql.py \
  --cases evals/drivee_complex_suite.json \
  --api-base http://127.0.0.1:8001/api \
  --output-dir evals/runs/drivee_retry_check
```

## Что делать, если проблема выглядит как transient LLM failure

Симптомы:

- тот же prompt иногда даёт SQL, иногда clarification
- одиночный ручной вызов может проходить, а suite иногда падает
- SQL correctness уже высокая, но `understanding` проседает

Типовой фикс:

- добавить retry на `thinking` planning path до fallback
- не уходить в default clarification после первого неудачного плана
- логировать причину fallback в payload trace

После такого фикса нужно проверить две вещи:

1. flaky prompt стабилизировался на нескольких чистых сессиях
2. полный suite не деградировал по latency и итоговым score

## Минимальный чек-лист перед merge

- problematic prompt стабильно отвечает одинаково на 5+ чистых сессиях
- `summary.json` улучшился или не ухудшился
- не появилось новых `sql_required_substring_missing`
- не появилось новых chart regressions
- `repair_brief.md` показывает новый, а не старый failure cluster

## Где смотреть код при проблемах

- `backend/app/services/chat_sql_adapter.py`
- `backend/app/services/llm_service.py`
- `backend/app/agents/intent.py`
- `backend/app/agents/semantic.py`
- `backend/app/agents/validation.py`
- `backend/app/services/chart_decision_service.py`
- `backend/app/evals/chat_text_to_sql_eval.py`

## Практическое правило

Если `sql` и `chart` уже зелёные, а падает только `understanding`, не надо сразу переписывать prompt. Сначала проверьте:

- был ли прямой LLM plan
- прошёл ли он validation
- не сработал ли fallback path
- нет ли transient flakiness на чистых сессиях

Это быстрее и обычно точнее, чем повторная ручная настройка prompt.
