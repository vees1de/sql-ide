import type { WorkspaceData } from '@/types/app';

export const workspaceData: WorkspaceData = {
  id: 'aurora-workspace',
  name: 'Aurora Analytics Lab',
  tagline: 'Notebook-first self-service analytics for business teams',
  databases: [
    {
      id: 'sales-db',
      name: 'Sales DB',
      engine: 'PostgreSQL',
      mode: 'read-only',
      tables: 36,
      schemas: ['public', 'mart'],
      status: 'connected'
    },
    {
      id: 'marketing-db',
      name: 'Marketing DB',
      engine: 'PostgreSQL',
      mode: 'read-only',
      tables: 18,
      schemas: ['campaigns', 'attribution'],
      status: 'connected'
    },
    {
      id: 'finance-db',
      name: 'Finance Snapshot',
      engine: 'PostgreSQL',
      mode: 'read-only',
      tables: 12,
      schemas: ['finance'],
      status: 'syncing'
    }
  ],
  notebooks: [
    {
      id: 'q1-revenue-analysis',
      title: 'Q1 Revenue Analysis',
      databaseId: 'sales-db',
      createdAt: '2026-04-19T08:15:00.000Z',
      updatedAt: '2026-04-19T11:37:00.000Z',
      status: 'draft',
      summary: {
        objective:
          'Понять динамику выручки за полгода, выделить Москву и сравнить период с прошлым годом.',
        lastRunLabel: '2 min ago',
        highlight: 'Revenue peaked in March after four consecutive months of growth.',
        owner: 'Growth Team'
      },
      trace: [
        {
          agent: 'Intent Agent',
          purpose: 'Разобрать метрику, период и аналитический сценарий.',
          output: 'metric=revenue; dimensions=month; filters=none; comparison=none',
          confidence: 0.94,
          latencyMs: 240
        },
        {
          agent: 'Semantic Mapping Agent',
          purpose: 'Связать бизнес-термины со схемой sales mart.',
          output: 'revenue -> fact_orders.net_revenue; month -> date_trunc(order_date)',
          confidence: 0.92,
          latencyMs: 180
        },
        {
          agent: 'SQL Generation Agent',
          purpose: 'Сгенерировать SQL и CTE-структуру для помесячной аналитики.',
          output: 'Generated 3 safe SELECT statements with explicit grouping.',
          confidence: 0.89,
          latencyMs: 315
        },
        {
          agent: 'SQL Validation Agent',
          purpose: 'Проверить join policy, LIMIT, read-only restrictions.',
          output: 'Whitelist passed; no mutating statements detected.',
          confidence: 0.97,
          latencyMs: 120
        },
        {
          agent: 'Visualization Agent',
          purpose: 'Выбрать line/bar chart для сравнения трендов.',
          output: 'Line chart for trend, grouped bar for YoY comparison.',
          confidence: 0.91,
          latencyMs: 105
        },
        {
          agent: 'Insight Agent',
          purpose: 'Сформулировать краткий вывод для менеджера.',
          output: 'Moscow outperformed total trend after January slowdown.',
          confidence: 0.86,
          latencyMs: 160
        }
      ],
      cells: [
        {
          id: 'q1-prompt-1',
          type: 'prompt',
          order: 1,
          title: 'Prompt',
          subtitle: 'Natural language request',
          agent: 'Intent Agent',
          tone: 'accent',
          content: {
            prompt: 'Покажи выручку по месяцам за последние 6 месяцев.',
            chips: ['Revenue', '6 months', 'Monthly trend'],
            context: ['Workspace memory enabled', 'Default currency: RUB']
          },
          meta: {
            confidence: 0.94,
            tablesUsed: ['mart.fact_orders', 'mart.dim_calendar'],
            warnings: [],
            businessTerms: ['выручка', 'месяц', 'последние 6 месяцев'],
            summary: 'Запрос трактован как trend analysis без фильтров.',
            executionTimeMs: 84
          }
        },
        {
          id: 'q1-sql-1',
          type: 'sql',
          order: 2,
          title: 'SQL',
          subtitle: 'Generated query',
          agent: 'SQL Generation Agent',
          tone: 'neutral',
          content: {
            sql: `SELECT
  DATE_TRUNC('month', o.order_date) AS month,
  ROUND(SUM(o.net_revenue), 2) AS total_revenue
FROM mart.fact_orders AS o
WHERE o.order_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
GROUP BY 1
ORDER BY 1;`,
            explanation:
              'Агент берёт чистую выручку из fact_orders, агрегирует по месяцам и ограничивает окно последними шестью месяцами.'
          },
          meta: {
            confidence: 0.89,
            executionTimeMs: 132,
            rowCount: 6,
            tablesUsed: ['mart.fact_orders'],
            warnings: ['Read-only query', 'Time window snapped to calendar month'],
            businessTerms: ['net_revenue', 'order_date'],
            summary: 'SQL построен без joins, поэтому риск неоднозначности низкий.'
          }
        },
        {
          id: 'q1-table-1',
          type: 'table',
          order: 3,
          title: 'Result',
          subtitle: 'Monthly revenue snapshot',
          agent: 'SQL Validation Agent',
          tone: 'neutral',
          content: {
            columns: ['Month', 'Revenue, RUB mln', 'MoM'],
            rows: [
              { Month: 'Nov 2025', 'Revenue, RUB mln': 11.8, MoM: '+2.3%' },
              { Month: 'Dec 2025', 'Revenue, RUB mln': 12.1, MoM: '+2.5%' },
              { Month: 'Jan 2026', 'Revenue, RUB mln': 11.4, MoM: '-5.8%' },
              { Month: 'Feb 2026', 'Revenue, RUB mln': 13.3, MoM: '+16.7%' },
              { Month: 'Mar 2026', 'Revenue, RUB mln': 14.2, MoM: '+6.8%' },
              { Month: 'Apr 2026', 'Revenue, RUB mln': 13.9, MoM: '-2.1%' }
            ],
            footnote: 'Rows limited to 6 because the notebook uses a fixed monthly window.'
          },
          meta: {
            confidence: 0.97,
            executionTimeMs: 210,
            rowCount: 6,
            tablesUsed: ['mart.fact_orders'],
            warnings: [],
            businessTerms: ['month', 'mom'],
            summary: 'Validation passed, returned six aggregated rows.'
          }
        },
        {
          id: 'q1-chart-1',
          type: 'chart',
          order: 4,
          title: 'Chart',
          subtitle: 'Trend visualization',
          agent: 'Visualization Agent',
          tone: 'accent',
          content: {
            chartType: 'line',
            title: 'Revenue trend',
            subtitle: 'Last 6 calendar months',
            xAxis: ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr'],
            series: [
              {
                name: 'Revenue',
                data: [11.8, 12.1, 11.4, 13.3, 14.2, 13.9]
              }
            ],
            unit: 'RUB mln',
            palette: ['#246bff']
          },
          meta: {
            confidence: 0.91,
            tablesUsed: ['mart.fact_orders'],
            warnings: [],
            businessTerms: ['trend', 'line chart'],
            summary: 'Для непрерывной временной оси выбран line chart.'
          }
        },
        {
          id: 'q1-insight-1',
          type: 'insight',
          order: 5,
          title: 'Insight',
          subtitle: 'Manager-facing conclusion',
          agent: 'Insight Agent',
          tone: 'success',
          content: {
            headline: 'Выручка росла четыре месяца подряд после январской просадки.',
            bullets: [
              'Пик достигнут в марте: 14.2 млн RUB.',
              'В апреле видна небольшая коррекция, но уровень остаётся выше зимнего базиса.',
              'Тренд выглядит устойчивым для запуска регионального среза.'
            ]
          },
          meta: {
            confidence: 0.86,
            tablesUsed: ['mart.fact_orders'],
            warnings: [],
            businessTerms: ['просадка', 'устойчивый тренд'],
            summary: 'Инсайт делает акцент на динамике, а не на абсолютном объёме.'
          }
        },
        {
          id: 'q1-prompt-2',
          type: 'prompt',
          order: 6,
          title: 'Prompt',
          subtitle: 'Context-aware follow-up',
          agent: 'Intent Agent',
          tone: 'accent',
          content: {
            prompt: 'Теперь только по Москве.',
            chips: ['Filter: Moscow', 'Reuse previous metric'],
            context: ['Inherited context from previous cell', 'Same 6-month window']
          },
          meta: {
            confidence: 0.93,
            tablesUsed: ['mart.fact_orders', 'mart.dim_city'],
            warnings: [],
            businessTerms: ['Москва', 'фильтр по городу'],
            summary: 'Контекст предыдущей ячейки сохранён, меняется только geographic filter.'
          }
        },
        {
          id: 'q1-sql-2',
          type: 'sql',
          order: 7,
          title: 'SQL',
          subtitle: 'Filtered query',
          agent: 'SQL Generation Agent',
          tone: 'neutral',
          content: {
            sql: `SELECT
  DATE_TRUNC('month', o.order_date) AS month,
  ROUND(SUM(o.net_revenue), 2) AS total_revenue
FROM mart.fact_orders AS o
JOIN mart.dim_city AS c
  ON c.city_id = o.city_id
WHERE c.city_name = 'Moscow'
  AND o.order_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
GROUP BY 1
ORDER BY 1;`,
            explanation:
              'SQL reuse-ит предыдущую агрегацию и добавляет lookup по dim_city для точного city filter.'
          },
          meta: {
            confidence: 0.9,
            executionTimeMs: 186,
            rowCount: 6,
            tablesUsed: ['mart.fact_orders', 'mart.dim_city'],
            warnings: ['City filter normalized from "Москва" to canonical value "Moscow"'],
            businessTerms: ['city_name', 'Moscow'],
            summary: 'Добавлен безопасный join по surrogate key с dimension table.'
          }
        },
        {
          id: 'q1-chart-2',
          type: 'chart',
          order: 8,
          title: 'Chart',
          subtitle: 'Regional slice',
          agent: 'Visualization Agent',
          tone: 'accent',
          content: {
            chartType: 'line',
            title: 'Moscow revenue',
            subtitle: 'Compared with total trend from notebook context',
            xAxis: ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr'],
            series: [
              {
                name: 'Moscow',
                data: [3.2, 3.5, 3.1, 4.0, 4.4, 4.3]
              },
              {
                name: 'All regions',
                data: [11.8, 12.1, 11.4, 13.3, 14.2, 13.9]
              }
            ],
            unit: 'RUB mln',
            palette: ['#246bff', '#7b879c']
          },
          meta: {
            confidence: 0.88,
            tablesUsed: ['mart.fact_orders', 'mart.dim_city'],
            warnings: [],
            businessTerms: ['regional share', 'context comparison'],
            summary: 'Визуализация добавляет общий тренд как reference series.'
          }
        },
        {
          id: 'q1-insight-2',
          type: 'insight',
          order: 9,
          title: 'Insight',
          subtitle: 'Regional interpretation',
          agent: 'Insight Agent',
          tone: 'success',
          content: {
            headline: 'Москва ускорилась сильнее общего тренда после январского провала.',
            bullets: [
              'Доля Москвы выросла с 27% в январе до 31% в марте.',
              'Апрельская коррекция практически не затронула столичный сегмент.',
              'Именно Москва даёт основной вклад в мартовский пик.'
            ]
          },
          meta: {
            confidence: 0.85,
            tablesUsed: ['mart.fact_orders', 'mart.dim_city'],
            warnings: [],
            businessTerms: ['доля Москвы', 'вклад в пик'],
            summary: 'Фокус смещён на contribution analysis, а не только на абсолютные значения.'
          }
        },
        {
          id: 'q1-prompt-3',
          type: 'prompt',
          order: 10,
          title: 'Prompt',
          subtitle: 'Comparison request',
          agent: 'Intent Agent',
          tone: 'accent',
          content: {
            prompt: 'Сравни с аналогичным периодом прошлого года.',
            chips: ['YoY comparison', 'Same months'],
            context: ['Moscow filter inherited', 'Comparison mode enabled']
          },
          meta: {
            confidence: 0.91,
            tablesUsed: ['mart.fact_orders', 'mart.dim_city'],
            warnings: [],
            businessTerms: ['аналогичный период', 'прошлый год'],
            summary: 'Система распознала year-over-year comparison на той же витрине.'
          }
        },
        {
          id: 'q1-sql-3',
          type: 'sql',
          order: 11,
          title: 'SQL',
          subtitle: 'YoY comparison query',
          agent: 'SQL Generation Agent',
          tone: 'neutral',
          content: {
            sql: `WITH monthly AS (
  SELECT
    DATE_TRUNC('month', o.order_date) AS month_start,
    EXTRACT(YEAR FROM o.order_date) AS year_num,
    ROUND(SUM(o.net_revenue), 2) AS total_revenue
  FROM mart.fact_orders AS o
  JOIN mart.dim_city AS c
    ON c.city_id = o.city_id
  WHERE c.city_name = 'Moscow'
    AND o.order_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '17 months'
  GROUP BY 1, 2
)
SELECT
  TO_CHAR(month_start, 'Mon') AS month,
  MAX(CASE WHEN year_num = 2025 THEN total_revenue END) AS revenue_2025,
  MAX(CASE WHEN year_num = 2026 THEN total_revenue END) AS revenue_2026
FROM monthly
WHERE month_start >= DATE '2025-11-01'
GROUP BY 1, month_start
ORDER BY month_start;`,
            explanation:
              'Запрос строит CTE с двумя годами и затем разворачивает их в формат для grouped comparison.'
          },
          meta: {
            confidence: 0.87,
            executionTimeMs: 241,
            rowCount: 6,
            tablesUsed: ['mart.fact_orders', 'mart.dim_city'],
            warnings: ['Comparison window uses fixed Nov-Apr period for both years'],
            businessTerms: ['yoy', 'comparison window'],
            summary: 'Для сравнения выбрана wide-table форма, удобная для графика и инсайта.'
          }
        },
        {
          id: 'q1-table-2',
          type: 'table',
          order: 12,
          title: 'Result',
          subtitle: 'Year-over-year snapshot',
          agent: 'SQL Validation Agent',
          tone: 'neutral',
          content: {
            columns: ['Month', '2025, RUB mln', '2026, RUB mln', 'YoY'],
            rows: [
              { Month: 'Nov', '2025, RUB mln': 2.8, '2026, RUB mln': 3.2, YoY: '+14%' },
              { Month: 'Dec', '2025, RUB mln': 3.1, '2026, RUB mln': 3.5, YoY: '+13%' },
              { Month: 'Jan', '2025, RUB mln': 2.9, '2026, RUB mln': 3.1, YoY: '+7%' },
              { Month: 'Feb', '2025, RUB mln': 3.3, '2026, RUB mln': 4.0, YoY: '+21%' },
              { Month: 'Mar', '2025, RUB mln': 3.6, '2026, RUB mln': 4.4, YoY: '+22%' },
              { Month: 'Apr', '2025, RUB mln': 3.8, '2026, RUB mln': 4.3, YoY: '+13%' }
            ],
            footnote: 'YoY calculated on the Moscow-only slice.'
          },
          meta: {
            confidence: 0.96,
            executionTimeMs: 255,
            rowCount: 6,
            tablesUsed: ['mart.fact_orders', 'mart.dim_city'],
            warnings: [],
            businessTerms: ['yoy', 'Moscow-only'],
            summary: 'Каждый месяц 2026 выше соответствующего месяца 2025.'
          }
        },
        {
          id: 'q1-chart-3',
          type: 'chart',
          order: 13,
          title: 'Chart',
          subtitle: 'Grouped comparison',
          agent: 'Visualization Agent',
          tone: 'accent',
          content: {
            chartType: 'bar',
            title: 'Moscow YoY revenue',
            subtitle: 'Same months, previous year vs current year',
            xAxis: ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr'],
            series: [
              {
                name: '2025',
                data: [2.8, 3.1, 2.9, 3.3, 3.6, 3.8]
              },
              {
                name: '2026',
                data: [3.2, 3.5, 3.1, 4.0, 4.4, 4.3]
              }
            ],
            unit: 'RUB mln',
            palette: ['#98a2b3', '#246bff']
          },
          meta: {
            confidence: 0.9,
            tablesUsed: ['mart.fact_orders', 'mart.dim_city'],
            warnings: [],
            businessTerms: ['grouped comparison', 'year-over-year'],
            summary: 'Bar chart выбран для прямого сравнения пар месяцев.'
          }
        },
        {
          id: 'q1-insight-3',
          type: 'insight',
          order: 14,
          title: 'Insight',
          subtitle: 'Final conclusion',
          agent: 'Insight Agent',
          tone: 'success',
          content: {
            headline: 'Москва опережает прошлый год по выручке во всех шести месяцах.',
            bullets: [
              'Максимальный YoY lift приходится на февраль и март: +21% и +22%.',
              'Даже январь выше прошлогоднего уровня, что снижает риск ложного сезонного сигнала.',
              'Этот сценарий уже готов к сохранению как ежемесячный отчёт.'
            ]
          },
          meta: {
            confidence: 0.88,
            tablesUsed: ['mart.fact_orders', 'mart.dim_city'],
            warnings: [],
            businessTerms: ['lift', 'seasonality'],
            summary: 'Итоговый вывод оформлен в report-ready формате.'
          }
        }
      ]
    },
    {
      id: 'campaign-performance',
      title: 'Campaign Performance',
      databaseId: 'marketing-db',
      createdAt: '2026-04-18T12:10:00.000Z',
      updatedAt: '2026-04-19T10:02:00.000Z',
      status: 'saved',
      summary: {
        objective:
          'Разобрать эффективность последней кампании и показать, как продукт обрабатывает неоднозначный бизнес-запрос.',
        lastRunLabel: '15 min ago',
        highlight: 'Clarification reduces ambiguity before SQL is generated.',
        owner: 'Performance Marketing'
      },
      trace: [
        {
          agent: 'Intent Agent',
          purpose: 'Понять, что пользователь имеет в виду под "продажами и рекламой".',
          output: 'Ambiguity detected: revenue vs orders vs CAC.',
          confidence: 0.79,
          latencyMs: 210
        },
        {
          agent: 'Clarification Agent',
          purpose: 'Уточнить, какая метрика нужна бизнесу.',
          output: 'Suggested three metric interpretations with one recommended option.',
          confidence: 0.93,
          latencyMs: 96
        },
        {
          agent: 'Semantic Mapping Agent',
          purpose: 'Сопоставить chosen metric со схемой marketing mart.',
          output: 'CAC -> spend / acquired_customers; channel -> campaigns.channel_name',
          confidence: 0.9,
          latencyMs: 140
        },
        {
          agent: 'SQL Generation Agent',
          purpose: 'Сформировать агрегированный SQL по каналам.',
          output: 'Safe SELECT with joins to spend and attribution tables.',
          confidence: 0.87,
          latencyMs: 290
        },
        {
          agent: 'Visualization Agent',
          purpose: 'Выбрать chart для channel comparison.',
          output: 'Horizontal bar chart for scanability across 5 channels.',
          confidence: 0.9,
          latencyMs: 102
        },
        {
          agent: 'Insight Agent',
          purpose: 'Сформулировать вывод по эффективности каналов.',
          output: 'Paid social is over-spending relative to acquired customers.',
          confidence: 0.84,
          latencyMs: 135
        }
      ],
      cells: [
        {
          id: 'cp-prompt-1',
          type: 'prompt',
          order: 1,
          title: 'Prompt',
          subtitle: 'Ambiguous business language',
          agent: 'Intent Agent',
          tone: 'accent',
          content: {
            prompt: 'Покажи продажи и рекламу по последней кампании.',
            chips: ['Ambiguous metric', 'Campaign analysis'],
            context: ['Marketing workspace', 'Latest campaign focus']
          },
          meta: {
            confidence: 0.79,
            tablesUsed: ['campaigns.fact_spend', 'campaigns.fact_conversions'],
            warnings: ['The word "sales" can map to revenue, orders, or acquired customers'],
            businessTerms: ['продажи', 'реклама', 'последняя кампания'],
            summary: 'Запрос требует уточнения до генерации SQL.'
          }
        },
        {
          id: 'cp-clarification-1',
          type: 'clarification',
          order: 2,
          title: 'Clarification',
          subtitle: 'Agent asks for metric disambiguation',
          agent: 'Clarification Agent',
          tone: 'warning',
          content: {
            question: 'Под продажами в контексте кампании что вы хотите увидеть?',
            recommended: 'cac',
            options: [
              {
                id: 'cac',
                label: 'CAC по каналам',
                detail: 'Стоимость привлечения одного клиента по каждому маркетинговому каналу.'
              },
              {
                id: 'orders',
                label: 'Количество заказов',
                detail: 'Сколько заказов атрибутировано кампании по каналам.'
              },
              {
                id: 'revenue',
                label: 'Выручка',
                detail: 'Какая выручка связана с кампанией и через какие каналы она пришла.'
              }
            ]
          },
          meta: {
            confidence: 0.93,
            tablesUsed: ['campaigns.fact_spend', 'campaigns.fact_conversions'],
            warnings: ['Clarification required before query execution'],
            businessTerms: ['cac', 'orders', 'revenue'],
            summary: 'Clarification cell снижает риск неверной интерпретации.'
          }
        },
        {
          id: 'cp-sql-1',
          type: 'sql',
          order: 3,
          title: 'SQL',
          subtitle: 'Chosen metric query',
          agent: 'SQL Generation Agent',
          tone: 'neutral',
          content: {
            sql: `SELECT
  ch.channel_name,
  ROUND(SUM(s.spend_rub) / NULLIF(SUM(c.acquired_customers), 0), 2) AS cac_rub
FROM campaigns.fact_spend AS s
JOIN campaigns.fact_conversions AS c
  ON c.campaign_id = s.campaign_id
 AND c.channel_id = s.channel_id
JOIN campaigns.dim_channel AS ch
  ON ch.channel_id = s.channel_id
WHERE s.campaign_id = 'CMP_2026_SPRING'
GROUP BY 1
ORDER BY 2 ASC;`,
            explanation:
              'После уточнения агент строит CAC как spend / acquired_customers по каждому каналу последней кампании.'
          },
          meta: {
            confidence: 0.87,
            executionTimeMs: 201,
            rowCount: 5,
            tablesUsed: [
              'campaigns.fact_spend',
              'campaigns.fact_conversions',
              'campaigns.dim_channel'
            ],
            warnings: [],
            businessTerms: ['cac', 'campaign_id'],
            summary: 'Метрика уже не двусмысленна, SQL строится стабильно.'
          }
        },
        {
          id: 'cp-table-1',
          type: 'table',
          order: 4,
          title: 'Result',
          subtitle: 'CAC by channel',
          agent: 'SQL Validation Agent',
          tone: 'neutral',
          content: {
            columns: ['Channel', 'CAC, RUB'],
            rows: [
              { Channel: 'Organic search', 'CAC, RUB': 740 },
              { Channel: 'Email', 'CAC, RUB': 960 },
              { Channel: 'Paid search', 'CAC, RUB': 1280 },
              { Channel: 'Influencers', 'CAC, RUB': 1710 },
              { Channel: 'Paid social', 'CAC, RUB': 2260 }
            ],
            footnote: 'Lower CAC is better for this comparison.'
          },
          meta: {
            confidence: 0.95,
            executionTimeMs: 219,
            rowCount: 5,
            tablesUsed: ['campaigns.fact_spend', 'campaigns.fact_conversions'],
            warnings: [],
            businessTerms: ['lower is better'],
            summary: 'Результат сразу пригоден для channel ranking.'
          }
        },
        {
          id: 'cp-chart-1',
          type: 'chart',
          order: 5,
          title: 'Chart',
          subtitle: 'Channel comparison',
          agent: 'Visualization Agent',
          tone: 'accent',
          content: {
            chartType: 'bar',
            title: 'Campaign CAC by channel',
            subtitle: 'Latest campaign only',
            xAxis: ['Organic', 'Email', 'Paid Search', 'Influencers', 'Paid Social'],
            series: [
              {
                name: 'CAC',
                data: [740, 960, 1280, 1710, 2260]
              }
            ],
            unit: 'RUB',
            palette: ['#1d4ed8']
          },
          meta: {
            confidence: 0.9,
            tablesUsed: ['campaigns.fact_spend', 'campaigns.fact_conversions'],
            warnings: [],
            businessTerms: ['channel ranking'],
            summary: 'Single-series bar chart ускоряет сравнение эффективности.'
          }
        },
        {
          id: 'cp-insight-1',
          type: 'insight',
          order: 6,
          title: 'Insight',
          subtitle: 'Budget implication',
          agent: 'Insight Agent',
          tone: 'success',
          content: {
            headline: 'Paid social заметно проигрывает остальным каналам по стоимости привлечения.',
            bullets: [
              'Organic search и Email дают самый дешёвый acquisition.',
              'Paid social почти в 3 раза дороже organic search.',
              'Есть смысл пересмотреть allocation до следующего flight.'
            ]
          },
          meta: {
            confidence: 0.84,
            tablesUsed: ['campaigns.fact_spend', 'campaigns.fact_conversions'],
            warnings: [],
            businessTerms: ['allocation', 'acquisition'],
            summary: 'Инсайт переводит таблицу в конкретное budget decision.'
          }
        }
      ]
    },
    {
      id: 'regional-sales-deep-dive',
      title: 'Regional Sales Deep Dive',
      databaseId: 'sales-db',
      createdAt: '2026-04-16T09:40:00.000Z',
      updatedAt: '2026-04-19T09:10:00.000Z',
      status: 'saved',
      summary: {
        objective: 'Сравнить регионы по вкладу в выручку и быстро найти лидеров.',
        lastRunLabel: '1 hour ago',
        highlight: 'Ural region is closing the gap with Moscow and St. Petersburg.',
        owner: 'Regional Ops'
      },
      trace: [
        {
          agent: 'Intent Agent',
          purpose: 'Выделить метрику revenue и breakdown by region.',
          output: 'metric=revenue; dimension=region; ranking=descending',
          confidence: 0.92,
          latencyMs: 170
        },
        {
          agent: 'Semantic Mapping Agent',
          purpose: 'Сопоставить регион и revenue со схемой marts.',
          output: 'region -> dim_region.region_name; revenue -> fact_orders.net_revenue',
          confidence: 0.91,
          latencyMs: 141
        },
        {
          agent: 'SQL Generation Agent',
          purpose: 'Сгенерировать safe ranking query.',
          output: 'SELECT with aggregation, ordering and LIMIT 8',
          confidence: 0.88,
          latencyMs: 220
        },
        {
          agent: 'Visualization Agent',
          purpose: 'Выбрать visual for region ranking.',
          output: 'Bar chart with descending order for rapid scan.',
          confidence: 0.9,
          latencyMs: 88
        },
        {
          agent: 'Insight Agent',
          purpose: 'Сделать вывод по региональным лидерам.',
          output: 'Top 3 regions contribute more than half of revenue.',
          confidence: 0.83,
          latencyMs: 120
        }
      ],
      cells: [
        {
          id: 'rs-prompt-1',
          type: 'prompt',
          order: 1,
          title: 'Prompt',
          subtitle: 'Regional ranking request',
          agent: 'Intent Agent',
          tone: 'accent',
          content: {
            prompt: 'Покажи топ регионов по выручке за текущий квартал.',
            chips: ['Revenue', 'Current quarter', 'Ranking'],
            context: ['Quarter-to-date mode']
          },
          meta: {
            confidence: 0.92,
            tablesUsed: ['mart.fact_orders', 'mart.dim_region'],
            warnings: [],
            businessTerms: ['топ регионов', 'текущий квартал'],
            summary: 'Запрос распознан как ranked table plus bar chart.'
          }
        },
        {
          id: 'rs-sql-1',
          type: 'sql',
          order: 2,
          title: 'SQL',
          subtitle: 'Ranking query',
          agent: 'SQL Generation Agent',
          tone: 'neutral',
          content: {
            sql: `SELECT
  r.region_name,
  ROUND(SUM(o.net_revenue), 2) AS total_revenue
FROM mart.fact_orders AS o
JOIN mart.dim_region AS r
  ON r.region_id = o.region_id
WHERE DATE_TRUNC('quarter', o.order_date) = DATE_TRUNC('quarter', CURRENT_DATE)
GROUP BY 1
ORDER BY 2 DESC
LIMIT 8;`,
            explanation:
              'Агент строит ранжирование по выручке квартал-к-дате и ограничивает результат восемью регионами.'
          },
          meta: {
            confidence: 0.88,
            executionTimeMs: 172,
            rowCount: 8,
            tablesUsed: ['mart.fact_orders', 'mart.dim_region'],
            warnings: [],
            businessTerms: ['quarter-to-date', 'ranking'],
            summary: 'Запрос оптимизирован под быстрый leaderboard.'
          }
        },
        {
          id: 'rs-table-1',
          type: 'table',
          order: 3,
          title: 'Result',
          subtitle: 'Top regions',
          agent: 'SQL Validation Agent',
          tone: 'neutral',
          content: {
            columns: ['Region', 'Revenue, RUB mln'],
            rows: [
              { Region: 'Moscow', 'Revenue, RUB mln': 18.4 },
              { Region: 'St. Petersburg', 'Revenue, RUB mln': 12.2 },
              { Region: 'Ural', 'Revenue, RUB mln': 10.7 },
              { Region: 'South', 'Revenue, RUB mln': 9.6 },
              { Region: 'Siberia', 'Revenue, RUB mln': 8.9 },
              { Region: 'Volga', 'Revenue, RUB mln': 8.1 },
              { Region: 'Far East', 'Revenue, RUB mln': 6.8 },
              { Region: 'North-West', 'Revenue, RUB mln': 6.4 }
            ]
          },
          meta: {
            confidence: 0.96,
            executionTimeMs: 184,
            rowCount: 8,
            tablesUsed: ['mart.fact_orders', 'mart.dim_region'],
            warnings: [],
            businessTerms: ['leaderboard'],
            summary: 'Топ-3 региона формируют основной объём квартальной выручки.'
          }
        },
        {
          id: 'rs-chart-1',
          type: 'chart',
          order: 4,
          title: 'Chart',
          subtitle: 'Descending leaderboard',
          agent: 'Visualization Agent',
          tone: 'accent',
          content: {
            chartType: 'bar',
            title: 'Revenue by region',
            subtitle: 'Current quarter',
            xAxis: ['Moscow', 'St. Pete', 'Ural', 'South', 'Siberia', 'Volga', 'Far East', 'NW'],
            series: [
              {
                name: 'Revenue',
                data: [18.4, 12.2, 10.7, 9.6, 8.9, 8.1, 6.8, 6.4]
              }
            ],
            unit: 'RUB mln',
            palette: ['#0f766e']
          },
          meta: {
            confidence: 0.9,
            tablesUsed: ['mart.fact_orders', 'mart.dim_region'],
            warnings: [],
            businessTerms: ['descending ranking'],
            summary: 'Bar chart даёт максимально быстрый scan top regions.'
          }
        },
        {
          id: 'rs-insight-1',
          type: 'insight',
          order: 5,
          title: 'Insight',
          subtitle: 'Regional narrative',
          agent: 'Insight Agent',
          tone: 'success',
          content: {
            headline: 'Урал уже почти догнал Санкт-Петербург и выглядит самым сильным регионом вне столиц.',
            bullets: [
              'Топ-3 региона обеспечивают более 50% квартальной выручки.',
              'Ural и South формируют основную зону роста.',
              'Far East и North-West остаются кандидатами на точечное усиление.'
            ]
          },
          meta: {
            confidence: 0.83,
            tablesUsed: ['mart.fact_orders', 'mart.dim_region'],
            warnings: [],
            businessTerms: ['зона роста', 'точечное усиление'],
            summary: 'Инсайт годится для региональной оперативки и weekly review.'
          }
        }
      ]
    }
  ],
  reports: [
    {
      id: 'report-weekly-sales',
      title: 'Weekly Sales Review',
      notebookId: 'regional-sales-deep-dive',
      createdAt: '2026-04-19T07:10:00.000Z',
      schedule: 'Every Monday, 09:00'
    },
    {
      id: 'report-monthly-moscow',
      title: 'Moscow Revenue Snapshot',
      notebookId: 'q1-revenue-analysis',
      createdAt: '2026-04-18T16:45:00.000Z',
      schedule: 'First day of month, 10:00'
    }
  ],
  templates: [
    {
      id: 'template-revenue-over-time',
      title: 'Revenue over time',
      description: 'Помесячная динамика выручки с quick insights.'
    },
    {
      id: 'template-top-products',
      title: 'Top products',
      description: 'Ranking of products with revenue and quantity sold.'
    },
    {
      id: 'template-campaign-performance',
      title: 'Campaign performance',
      description: 'Spend, CAC and attributed revenue by channel.'
    }
  ],
  dictionary: [
    {
      id: 'dict-revenue',
      term: 'Выручка',
      synonyms: ['продажи', 'revenue', 'оборот'],
      mappedExpression: 'SUM(mart.fact_orders.net_revenue)',
      description: 'Чистая выручка после возвратов и скидок.'
    },
    {
      id: 'dict-cac',
      term: 'CAC',
      synonyms: ['стоимость привлечения', 'acquisition cost'],
      mappedExpression: 'SUM(spend_rub) / SUM(acquired_customers)',
      description: 'Стоимость привлечения одного клиента.'
    },
    {
      id: 'dict-region',
      term: 'Регион',
      synonyms: ['area', 'territory'],
      mappedExpression: 'mart.dim_region.region_name',
      description: 'Нормализованное название региона продажи.'
    }
  ],
  history: [
    {
      id: 'history-1',
      label: 'Saved “Moscow Revenue Snapshot” report',
      timestamp: '11:42'
    },
    {
      id: 'history-2',
      label: 'Ran notebook “Campaign Performance”',
      timestamp: '10:02'
    },
    {
      id: 'history-3',
      label: 'Updated business term “CAC”',
      timestamp: '09:37'
    }
  ]
};
