Концепция
Что это за продукт

Это AI Analytics Notebook: среда, где пользователь работает не в формате “один вопрос — один ответ”, а в формате исследования данных шаг за шагом.

Пользователь открывает базу данных, создаёт ноутбук-сессию, пишет вопрос на естественном языке, а дальше LLM-агент:

понимает бизнес-смысл
строит SQL
выполняет запрос
визуализирует результат
пишет краткий вывод
сохраняет всё как последовательность ячеек, как в Colab

Итог: интерфейс похож на Google Colab, но вместо Python-кода пользователь пишет естественный язык, а внутри работают LLM-агенты и SQL.

Главная идея, которая выделяет вас

Большинство команд сделают:

поле ввода
LLM
SQL
таблицу

Вы делаете:

notebook-based workflow
многошаговую аналитику
агентную архитектуру
историю исследования
сохраняемые аналитические сценарии
explainability на каждом шаге

То есть не “чат к базе”, а:

Colab для бизнес-аналитики с LLM-агентами

Продуктовое позиционирование

Формулировка для презентации:

Мы создаём AI-first аналитическую среду в формате notebook, где non-tech пользователь может вести полноценное исследование данных на естественном языке, а LLM-агенты автоматически выполняют SQL, объясняют логику и сохраняют результаты как переиспользуемый сценарий.

Ещё короче:

Google Colab для бизнес-аналитики без SQL.

Как должен выглядеть интерфейс
Общий layout

Нужно взять за основу паттерн Google Colab / Jupyter Notebook / IDE.

Верхняя панель
название workspace
выбранная база данных
кнопка “New Notebook”
кнопка “Run all”
кнопка “Save report”
кнопка “Share”
индикатор текущего агента / статуса
Левая панель

Как sidebar в IDE:

Databases
Notebooks
Saved Reports
Query Templates
Business Dictionary
History

Это может выглядеть как explorer.

Пример дерева:

Databases
Sales DB
Marketing DB
Notebooks
Q1 Revenue Analysis
Regional Sales Deep Dive
Saved Reports
Weekly Sales Review
Templates
Revenue over time
Top products
Campaign performance
Центральная часть

Главная зона как в Colab:

блоки/ячейки
каждая ячейка — отдельный аналитический шаг

Типы ячеек:

Prompt cell
SQL cell
Result table cell
Chart cell
Insight/summary cell
Clarification cell
Правая панель

Inspector / Context / Agent Trace:

что понял агент
какие таблицы использовал
какой SQL сгенерировал
confidence
предупреждения
использованные бизнес-термины
Главная UX-модель

Пользователь работает не в чате, а в ноутбуке исследования.

Пример:

Ячейка 1

Текст:

Покажи выручку по месяцам за последние 6 месяцев

Система создаёт:

SQL cell
Result table cell
Chart cell
Insight cell
Ячейка 2

Пользователь пишет:

Теперь только по Москве

Агент использует контекст предыдущей ячейки и пересобирает анализ.

Ячейка 3

Пользователь:

Сравни с аналогичным периодом прошлого года

Система строит comparison analysis.

Ячейка 4

Пользователь:

Сделай выводы и сохрани как ежемесячный отчет

То есть пользователь ведёт исследование как notebook, а не просто кидает независимые запросы.

Почему формат Colab сильнее, чем обычный чат

Потому что он:

показывает ход мысли
создаёт артефакты
выглядит профессионально
даёт историю анализа
помогает повторять сценарии
отлично подходит для демо

Для жюри это выглядит как продукт, а не просто интерфейс к API.

Архитектура LLM-агентов

Лучше делать не “один большой агент”, а agent pipeline.

Базовая схема агентов

1. Intent Agent

Отвечает за понимание вопроса:

какая метрика
какой период
какие фильтры
какая группировка
нужно ли сравнение
есть ли неоднозначность

Выход:
structured intent JSON.

2. Semantic Mapping Agent

Преобразует бизнес-термины в сущности БД:

“выручка” → SUM(orders.revenue)
“регион” → customers.region
“реклама” → campaigns.source

Этот агент опирается на словарь и metadata.

3. SQL Generation Agent

На вход получает:

intent
schema
semantic layer
join rules
ограничения безопасности

На выход:

SQL
explanation
confidence 4. SQL Validation Agent

Проверяет:

только SELECT
только whitelist таблиц
запрет опасных операций
LIMIT / timeout
parse success
корректность join 5. Visualization Agent

Решает:

line chart
bar chart
pie
table

И формирует chart spec.

6. Insight Agent

Пишет краткий человеческий вывод:

рост / падение
аномалия
лидер / аутсайдер
сравнение периодов 7. Clarification Agent

Если запрос неясный, задаёт уточняющий вопрос:

“Под продажами вы имеете в виду выручку или количество заказов?”
“Какой период считать прошлым периодом?”
Как это объяснять просто

Можно сказать так:

Мы разбили работу LLM на несколько специализированных агентов, чтобы повысить точность, прозрачность и безопасность. Один агент понимает намерение пользователя, второй сопоставляет термины со схемой данных, третий пишет SQL, четвёртый валидирует запрос, пятый подбирает визуализацию и шестой формулирует вывод.

Это звучит очень сильно для техжюри.

Полная архитектура приложения

1. Frontend layer

Интерфейс ноутбука:

notebook editor
cell renderer
sidebar explorer
result viewer
chart viewer
agent trace panel
saved notebooks/reports 2. Backend API layer

Сервисы:

notebook service
query orchestration service
report service
metadata service
auth/session service 3. Agent orchestration layer
Intent Agent
Semantic Agent
SQL Agent
Validation Agent
Visualization Agent
Insight Agent
Clarification Agent 4. Data access layer
read-only analytical DB connection
semantic dictionary storage
notebook storage
report storage
query history storage 5. Safety layer
SQL parser
whitelist policy
rate limit
timeout
row limit
audit logs
Какой должен быть flow запроса
Шаг 1

Пользователь пишет prompt в notebook cell.

Шаг 2

Intent Agent превращает запрос в структуру.

Пример:

{
"metric": "revenue",
"dimensions": ["month"],
"filters": [{"field": "city", "value": "Moscow"}],
"comparison": "previous_year",
"visualization_preference": "line"
}
Шаг 3

Semantic Agent сопоставляет intent со схемой.

Шаг 4

SQL Agent создаёт SQL.

Шаг 5

Validation Agent проверяет SQL.

Шаг 6

SQL исполняется.

Шаг 7

Visualization Agent подбирает формат вывода.

Шаг 8

Insight Agent генерирует summary.

Шаг 9

Все результаты рендерятся как набор notebook cells.

Какие сущности нужны в системе
Workspace

Пространство работы пользователя.

{
id: string,
name: string,
databases: string[]
}
Notebook

Аналитическая тетрадь.

{
id: string,
title: string,
databaseId: string,
createdAt: string,
updatedAt: string,
status: 'draft' | 'saved'
}
Cell

Базовая единица интерфейса.

{
id: string,
notebookId: string,
type: 'prompt' | 'sql' | 'table' | 'chart' | 'insight' | 'clarification',
order: number,
content: any,
createdAt: string
}
Query Run

Результат выполнения одного аналитического шага.

{
id: string,
notebookId: string,
promptCellId: string,
sql: string,
explanation: object,
confidence: number,
executionTimeMs: number,
rowCount: number,
status: 'success' | 'error' | 'clarification_required'
}
Saved Report

Сохранённая аналитика.

{
id: string,
title: string,
notebookId: string,
createdAt: string,
schedule?: string
}
Semantic Dictionary

Бизнес-словарь.

{
id: string,
term: string,
synonyms: string[],
mappedExpression: string,
description: string
}
Какой стек брать

С вашим пожеланием:

Frontend
Vue 3
Pinia
Vue Router
SCSS
Monaco Editor или CodeMirror для notebook cells
ECharts для визуализаций
Splitpanes / resizable layout library
Почему так

Vue + Pinia хорошо подходят для notebook UI:

удобно держать дерево слева
удобно управлять ячейками
удобно строить editor-like интерфейс
Backend
Python
FastAPI
Pydantic
SQLAlchemy
Pandas
LLM / agents
OpenAI compatible API / любая сильная instruct-модель
structured JSON output
агентная оркестрация руками или через лёгкий orchestration layer
DB
PostgreSQL
read-only user для аналитической БД
отдельная сервисная БД для notebooks/reports/history
SQL safety
sqlglot
кастомные validator rules
Async / jobs
Celery / RQ — не обязательно для MVP
можно обойтись sync execution
Как должен выглядеть notebook UI
Типы ячеек
Prompt cell

Выглядит как markdown/code cell input.
Пользователь пишет естественный язык.

SQL cell

Показывает SQL в стиле code cell.
Можно свернуть/развернуть.

Result table cell

Отображает таблицу.

Chart cell

Отображает график.

Insight cell

Показывает краткий вывод агента.

Clarification cell

Если вопрос неоднозначен — показывает варианты выбора.

Пример notebook-сценария
Cell 1 — Prompt

“Покажи выручку по месяцам за последние 6 месяцев”

Cell 2 — SQL
SELECT DATE_TRUNC('month', order_date) AS month,
SUM(revenue) AS total_revenue
FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '6 months'
GROUP BY 1
ORDER BY 1;
Cell 3 — Chart

Line chart

Cell 4 — Insight

“Выручка росла 4 месяца подряд, максимум достигнут в марте.”

Cell 5 — Prompt

“Теперь разбей по регионам”

Cell 6 — SQL

Новый запрос уже с контекстом

Что должно выглядеть “как Google Colab”

Важно не копировать буквально, а взять паттерны.

Нужно повторить ощущения:
рабочая тетрадь
ячейки
запуск ячейки
история выполнения
последовательность шагов
автосохранение
возможность переименовать notebook
аккуратный минималистичный layout
панель файлов/ноутбуков слева
Что можно адаптировать:
кнопка Run cell
Run all
статус выполнения
collapsible outputs
outputs под ячейкой
sticky toolbar
Что надо сделать, чтобы это выглядело дорого

1. У каждой ячейки должны быть действия
   Run
   Edit
   Duplicate
   Delete
   Save as report step
2. Должна быть хорошая визуальная иерархия
   input cell
   generated sql
   result
   explanation
3. Должен быть trace агента

Небольшой блок:

Intent parsed
Semantic mapping applied
SQL validated
Visualization selected

Это очень усиливает ощущение “умной платформы”.

Pinia stores
useWorkspaceStore
список баз
список notebooks
выбранная база
выбранный notebook
sidebar tree
useNotebookStore
notebook metadata
cells
cell order
active cell
run status
useAgentStore
agent trace
current stage
confidence
warnings
clarification state
useResultStore
rows
chart specs
sql text
insights
execution stats
useReportsStore
saved reports
templates
scheduling options
Компоненты frontend
Layout
AppShell
TopToolbar
SidebarExplorer
NotebookCanvas
InspectorPanel
Notebook
NotebookCell
PromptCell
SQLCell
ChartCell
TableCell
InsightCell
ClarificationCell
CellToolbar
Data / agent
AgentTracePanel
ConfidenceBadge
ExecutionStats
SemanticMappingView
QueryExplanationCard
Sidebar
DatabaseTree
NotebookList
ReportList
TemplateList
Самая сильная продуктовая фича

Сделайте непрерывный аналитический контекст между ячейками.

То есть каждая новая prompt cell может ссылаться на предыдущие результаты.

Примеры:

“Теперь только топ-5”
“Сравни с прошлым кварталом”
“Добавь разбивку по каналу”
“Сделай график вместо таблицы”

Это производит гораздо более сильное впечатление, чем обычный чат.

Какие функции входят в MVP
Обязательные
Выбор базы данных
Создание notebook
Prompt cell на естественном языке
Генерация SQL
Выполнение запроса
Рендер таблицы
Рендер графика
Insight summary
Сохранение notebook
Сохранение отчёта
Очень желательные
История ячеек
Контекст между запросами
Explainability panel
Confidence score
Clarification flow
Бонус
Templates
Re-run notebook
Scheduled report
Share notebook
Business term dictionary
Как выиграть на архитектуре

На защите упор надо делать на 4 вещи:

1. Agent specialization

Не один агент, а набор маленьких ролей.

2. Notebook UX

Решение похоже на рабочую среду, а не на чат.

3. Explainability

Каждый ответ прозрачен и проверяем.

4. Reusability

Ноутбук и отчёты можно сохранять и запускать заново.

Как презентовать это жюри

Формулировка:

Обычные NL2SQL-решения отвечают на один вопрос. Мы предлагаем notebook-подход: пользователь строит последовательное исследование данных, а LLM-агенты ведут его через понимание вопроса, генерацию SQL, проверку, визуализацию и интерпретацию. Это делает решение ближе к реальному рабочему инструменту, а не просто к демо-боту.

План реализации по этапам
Этап 1. Основа
поднять frontend shell
sidebar
notebook canvas
prompt cells
backend /query
Этап 2. Agent pipeline
intent parser
semantic mapper
sql generator
validator
result formatter
Этап 3. Notebook rendering
sql cell
table cell
chart cell
insight cell
Этап 4. Persistence
save notebook
load notebook
save report
history
Этап 5. Differentiators
context memory
clarification
confidence
templates
agent trace
Как может называться продукт

Несколько сильных вариантов:

Insight Notebook
DataColab
QueryLab
BizNotebook
Analytics Copilot Notebook
InsightFlow
SQLless Notebook
Agentic BI Notebook

Из них для хакатона я бы выбрал что-то вроде:
Insight Notebook
или
QueryLab

Короткая итоговая формулировка плана
Идея

Создать notebook-платформу для self-service аналитики, визуально и по UX похожую на Google Colab, где пользователь задаёт вопросы на естественном языке, а система с помощью набора LLM-агентов преобразует их в SQL, выполняет запросы, строит визуализацию и сохраняет исследование в виде последовательности ячеек.

Архитектура
Vue 3 + Pinia + SCSS frontend
notebook-style UI
FastAPI backend
PostgreSQL
LLM agent pipeline: Intent → Semantic Mapping → SQL → Validation → Visualization → Insight
saved notebooks, reports, history, business dictionary
Ключевое отличие

Не чат с SQL, а полноценная аналитическая notebook-среда для бизнеса.
