import type {
  ApiCellRead,
  ApiDatabaseDescriptor,
  ApiDictionaryEntryRead,
  ApiNotebookDetail,
  ApiQueryRunRead,
  ApiQueryTemplate,
  ApiReportRead,
  ApiSchemaMetadataResponse,
  ApiWorkspaceRead
} from '@/api/types';
import type {
  ChartCellContent,
  ClarificationCellContent,
  DatabaseConnection,
  DictionaryTerm,
  HistoryItem,
  Notebook,
  NotebookCell,
  NotebookTraceStep,
  QueryMode,
  QueryTemplate,
  SavedReport,
  WorkspaceData
} from '@/types/app';

function formatRelativeTime(value: string) {
  const diffMs = Date.now() - new Date(value).getTime();
  const diffMinutes = Math.max(Math.round(diffMs / 60000), 0);

  if (diffMinutes < 1) {
    return 'Только что';
  }
  if (diffMinutes < 60) {
    return `${diffMinutes} мин назад`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} ч назад`;
  }

  const diffDays = Math.round(diffHours / 24);
  return `${diffDays} д назад`;
}

function formatClock(value: string) {
  return new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value));
}

function titleCase(input: string) {
  if (!input) {
    return '';
  }

  return input.charAt(0).toUpperCase() + input.slice(1);
}

function firstNumericValue(rows: Array<Record<string, unknown>>) {
  for (const row of rows) {
    for (const value of Object.values(row)) {
      const numeric = Number(String(value).replace(',', '.'));
      if (Number.isFinite(numeric)) {
        return numeric;
      }
    }
  }
  return undefined;
}

function normalizeQueryMode(value: unknown): QueryMode {
  return typeof value === 'string' && value.toLowerCase() === 'thinking' ? 'thinking' : 'fast';
}

function normalizeDisplayValue(value: unknown): string | number {
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value : Number(value.toFixed(2));
  }

  if (typeof value === 'string') {
    const asDate = Date.parse(value);
    if (!Number.isNaN(asDate) && /^\d{4}-\d{2}-\d{2}/.test(value)) {
      return new Intl.DateTimeFormat('ru-RU', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
      }).format(new Date(asDate));
    }
  }

  return String(value ?? '—');
}

function metricLabel(metric: unknown) {
  switch (metric) {
    case 'revenue':
      return 'выручка';
    case 'order_count':
      return 'количество заказов';
    case 'avg_order_value':
      return 'средний чек';
    default:
      return 'метрика';
  }
}

function buildSqlExplanation(run: ApiQueryRunRead | undefined) {
  if (!run) {
    return 'SQL будет показан после запуска аналитического шага.';
  }

  const dimensions = Array.isArray(run.explanation.dimensions)
    ? (run.explanation.dimensions as string[])
    : [];
  const filters = Array.isArray(run.explanation.filters)
    ? (run.explanation.filters as Array<{ field?: string; value?: string }>)
    : [];

  const dimensionText = dimensions.length
    ? ` с группировкой по ${dimensions.join(', ')}`
    : '';
  const filterText = filters.length
    ? ` и фильтрами ${filters.map((item) => `${item.field}: ${item.value}`).join(', ')}`
    : '';

  return `Агент посчитал ${metricLabel(run.explanation.metric)}${dimensionText}${filterText}.`;
}

function extractRunQueryMode(run: ApiQueryRunRead | undefined): QueryMode {
  const explanation = run?.explanation as { query_mode?: unknown } | undefined;
  const trace = run?.agent_trace as { query_mode?: unknown } | undefined;
  return normalizeQueryMode(explanation?.query_mode ?? trace?.query_mode);
}

function extractRunModelAlias(run: ApiQueryRunRead | undefined, fallbackAlias: string): string {
  const explanation = run?.explanation as { llm_model_alias?: unknown } | undefined;
  const trace = run?.agent_trace as { llm_model_alias?: unknown } | undefined;
  const raw = explanation?.llm_model_alias ?? trace?.llm_model_alias;
  return typeof raw === 'string' && raw.trim() ? raw.trim() : fallbackAlias;
}

function extractWarnings(run: ApiQueryRunRead | undefined, cell: ApiCellRead) {
  const validation = run?.agent_trace.validation as { warnings?: string[] } | undefined;
  const explanation = run?.explanation as { warnings?: string[] } | undefined;
  const contentWarnings = Array.isArray(cell.content.warnings)
    ? (cell.content.warnings as string[])
    : [];

  return [...(validation?.warnings ?? []), ...(explanation?.warnings ?? []), ...contentWarnings];
}

function extractTables(run: ApiQueryRunRead | undefined) {
  const validation = run?.agent_trace.validation as { tables?: string[] } | undefined;
  const semantic = run?.agent_trace.semantic_mapping as { tables?: string[] } | undefined;
  return [...new Set([...(validation?.tables ?? []), ...(semantic?.tables ?? [])])];
}

function extractBusinessTerms(run: ApiQueryRunRead | undefined) {
  const intent = run?.agent_trace.intent as {
    metric?: string;
    dimensions?: string[];
    filters?: Array<{ field?: string; value?: string }>;
  } | undefined;

  const terms = [
    intent?.metric,
    ...(intent?.dimensions ?? []),
    ...(intent?.filters ?? []).flatMap((item) =>
      [item.field, item.value].filter(Boolean) as string[]
    )
  ];

  return [...new Set(terms.filter(Boolean))];
}

function buildPromptMeta(run: ApiQueryRunRead | undefined, promptText: string) {
  return {
    confidence: run?.confidence ?? 0.72,
    executionTimeMs: run?.execution_time_ms,
    rowCount: run?.row_count,
    tablesUsed: extractTables(run),
    warnings: extractWarnings(
      run,
      {
        id: '',
        notebook_id: '',
        query_run_id: null,
        type: 'prompt',
        position: 0,
        content: {},
        created_at: '',
        updated_at: ''
      }
    ),
    businessTerms: extractBusinessTerms(run),
    summary: run
      ? `Prompt интерпретирован с confidence ${Math.round(run.confidence * 100)}%.`
      : `Notebook ждёт первый запрос: “${promptText}”.`
  };
}

function buildClarificationContent(cell: ApiCellRead): ClarificationCellContent {
  const rawOptions = Array.isArray(cell.content.options)
    ? (cell.content.options as unknown[])
    : [];
  const errors = Array.isArray(cell.content.errors)
    ? (cell.content.errors as string[])
    : [];
  const warnings = Array.isArray(cell.content.warnings)
    ? (cell.content.warnings as string[])
    : [];

  const options = rawOptions.length
    ? rawOptions.map((option, index) => {
        const label = String(option);
        return {
          id: `clarification-${index}`,
          label,
          detail: `Уточнить интерпретацию через вариант “${label}”.`
        };
      })
    : [...errors, ...warnings].map((message, index) => ({
        id: `issue-${index}`,
        label: errors[index] ? 'Validation issue' : 'Warning',
        detail: message
      }));

  return {
    question: String(cell.content.question ?? 'Требуется уточнение перед выполнением.'),
    options,
    recommended: options[0]?.id ?? 'clarification-0'
  };
}

function buildChartContent(cell: ApiCellRead): ChartCellContent {
  const chartSpec = (cell.content.chartSpec ?? {}) as {
    chart_type?: string;
    title?: string;
    explanation?: string;
    rule_id?: string;
    confidence?: number;
    variant?: string;
    data?: {
      kind?: string;
      x?: { field?: string | null; values?: unknown[]; type?: string | null };
      y?: { field?: string | null; values?: unknown[]; unit?: string | null };
      series?: Array<{ name?: string; data?: unknown[] }>;
      slices?: Array<{ name?: string; value?: unknown }>;
      value?: unknown;
      metricLabel?: string | null;
      stacked?: boolean;
      stackable?: boolean;
    };
    encoding?: {
      x_field?: string | null;
      y_field?: string | null;
      series_field?: string | null;
    };
    options?: {
      metricValue?: number | string | null;
    };
  };
  const rows = Array.isArray(cell.content.data)
    ? (cell.content.data as Array<Record<string, unknown>>)
    : [];
  const supportedType =
    chartSpec.chart_type === 'line' ||
    chartSpec.chart_type === 'bar' ||
    chartSpec.chart_type === 'pie' ||
    chartSpec.chart_type === 'metric_card'
      ? chartSpec.chart_type
      : 'bar';
  const subtitle = chartSpec.explanation ?? 'Сгенерировано агентом визуализации';
  const chartData = chartSpec.data;

  if (chartData?.kind === 'kpi' || supportedType === 'metric_card') {
    return {
      chartType: 'metric_card',
      title: chartSpec.title ?? 'Chart',
      subtitle,
      explanation: chartSpec.explanation,
      ruleId: chartSpec.rule_id,
      confidence: chartSpec.confidence,
      variant: chartSpec.variant,
      value: chartData?.value ?? chartSpec.options?.metricValue ?? firstNumericValue(rows) ?? '—',
      metricLabel: chartData?.metricLabel ?? chartSpec.encoding?.y_field ?? 'Value'
    };
  }

  if (chartData?.kind === 'pie' || supportedType === 'pie') {
    return {
      chartType: 'pie',
      title: chartSpec.title ?? 'Chart',
      subtitle,
      explanation: chartSpec.explanation,
      ruleId: chartSpec.rule_id,
      confidence: chartSpec.confidence,
      variant: chartSpec.variant,
      pieData: chartData?.slices
        ? chartData.slices.map((slice, index) => ({
            name: String(slice.name ?? `Segment ${index + 1}`),
            value: Number(slice.value ?? 0)
          }))
        : rows.map((row, index) => ({
            name: String(row[Object.keys(row)[0] ?? 'label'] ?? `Segment ${index + 1}`),
            value: Number(row[Object.keys(row)[1] ?? 'value'] ?? 0)
          }))
    };
  }

  if (chartData?.kind === 'multi_series') {
    return {
      chartType: supportedType === 'bar' ? 'bar' : 'line',
      title: chartSpec.title ?? 'Chart',
      subtitle,
      explanation: chartSpec.explanation,
      ruleId: chartSpec.rule_id,
      confidence: chartSpec.confidence,
      variant: chartSpec.variant,
      xAxis: Array.isArray(chartData.x?.values)
        ? chartData.x?.values.map((value) => String(value ?? '—'))
        : [],
      series: (chartData.series ?? []).map((series) => ({
        name: String(series.name ?? 'Series'),
        data: (series.data ?? []).map((value) => Number(value ?? 0))
      })),
      stacked: Boolean(chartData.stacked || chartData.stackable)
    };
  }

  if (chartData?.kind === 'single_series' || (supportedType === 'line' || supportedType === 'bar')) {
    return {
      chartType: supportedType,
      title: chartSpec.title ?? 'Chart',
      subtitle,
      explanation: chartSpec.explanation,
      ruleId: chartSpec.rule_id,
      confidence: chartSpec.confidence,
      variant: chartSpec.variant,
      xAxis: Array.isArray(chartData?.x?.values)
        ? chartData.x?.values.map((value) => String(value ?? '—'))
        : rows.map((row) => String(row[chartSpec.encoding?.x_field ?? ''] ?? '—')),
      series: [
        {
          name: titleCase(String(chartData?.y?.field ?? chartSpec.encoding?.y_field ?? 'value').replace(/_/g, ' ')),
          data: Array.isArray(chartData?.y?.values)
            ? chartData.y?.values.map((value) => Number(value ?? 0))
            : rows.map((row) => Number(row[chartSpec.encoding?.y_field ?? ''] ?? 0))
        }
      ],
      unit: chartData?.y?.unit ?? undefined
    };
  }

  const xField = chartSpec.encoding?.x_field ?? null;
  const yField = chartSpec.encoding?.y_field ?? null;
  const seriesField = chartSpec.encoding?.series_field ?? null;

  if (seriesField && xField && yField) {
    const xAxis = [...new Set(rows.map((row) => String(row[xField] ?? '—')))];
    const groups = [...new Set(rows.map((row) => String(row[seriesField] ?? 'Series')))];

    return {
      chartType: supportedType,
      title: chartSpec.title ?? 'Chart',
      subtitle,
      explanation: chartSpec.explanation,
      ruleId: chartSpec.rule_id,
      confidence: chartSpec.confidence,
      variant: chartSpec.variant,
      xAxis,
      series: groups.map((group) => ({
        name: group,
        data: xAxis.map((xValue) => {
          const point = rows.find(
            (row) =>
              String(row[xField] ?? '—') === xValue &&
              String(row[seriesField] ?? 'Series') === group
          );
          return Number(point?.[yField] ?? 0);
        })
      }))
    };
  }

  if (xField && yField) {
    return {
      chartType: supportedType,
      title: chartSpec.title ?? 'Chart',
      subtitle,
      explanation: chartSpec.explanation,
      ruleId: chartSpec.rule_id,
      confidence: chartSpec.confidence,
      variant: chartSpec.variant,
      xAxis: rows.map((row) => String(row[xField] ?? '—')),
      series: [
        {
          name: titleCase(String(yField).replace(/_/g, ' ')),
          data: rows.map((row) => Number(row[yField] ?? 0))
        }
      ]
    };
  }

  const value = rows[0] && chartSpec.encoding?.y_field ? Number(rows[0][chartSpec.encoding.y_field] ?? 0) : rows.length;
  return {
    chartType: supportedType === 'metric_card' ? 'metric_card' : 'bar',
    title: chartSpec.title ?? 'Chart',
    subtitle,
    explanation: chartSpec.explanation,
    ruleId: chartSpec.rule_id,
    confidence: chartSpec.confidence,
    variant: chartSpec.variant,
    xAxis: ['Result'],
    series: [
      {
        name: 'Result',
        data: [value]
      }
    ]
  };
}

function buildTrace(run: ApiQueryRunRead | undefined, notebookTitle: string, insightText?: string) {
  if (!run) {
    return [
      {
        agent: 'Intent Agent',
        purpose: 'Считать бизнес-запрос из notebook prompt.',
        output: `Notebook “${notebookTitle}” ждёт первый prompt.`,
        confidence: 0.7,
        latencyMs: 0
      }
    ] satisfies NotebookTraceStep[];
  }

  if (run.agent_trace.plan_source === 'manual_sql') {
    return [
      {
        agent: 'Manual SQL',
        purpose: 'Запуск редактируемой SQL-ячейки notebook.',
        output: run.sql.split('\n')[0] ?? 'Manual SQL execution',
        confidence: 1,
        latencyMs: Math.max(40, Math.round(run.execution_time_ms * 0.2))
      },
      {
        agent: 'SQL Validation Agent',
        purpose: 'Проверить single-statement, whitelist таблиц и LIMIT.',
        output:
          ((run.agent_trace.validation as { warnings?: string[] } | undefined)?.warnings ?? []).join(' ') ||
          'Validation passed with safe read-only execution.',
        confidence: 0.99,
        latencyMs: Math.max(35, Math.round(run.execution_time_ms * 0.08))
      }
    ] satisfies NotebookTraceStep[];
  }

  const intent = (run.agent_trace.intent ?? {}) as {
    metric?: string;
    dimensions?: string[];
    comparison?: string | null;
    filters?: Array<{ field?: string; value?: string }>;
  };
  const semantic = (run.agent_trace.semantic_mapping ?? {}) as {
    tables?: string[];
    metric_expression?: string;
    joins?: string[];
  };
  const validation = (run.agent_trace.validation ?? {}) as {
    warnings?: string[];
  };
  const chartSpec = (run.agent_trace.chart_spec ?? {}) as {
    chart_type?: string;
    explanation?: string;
    rule_id?: string;
    confidence?: number;
    variant?: string;
    encoding?: {
      x_field?: string | null;
      y_field?: string | null;
      series_field?: string | null;
    };
  };
  const clarification = run.agent_trace.clarification as
    | { question?: string; options?: string[] }
    | undefined;

  const steps: NotebookTraceStep[] = [
    {
      agent: 'Intent Agent',
      purpose: 'Разобрать метрику, период, фильтры и follow-up контекст.',
      output: `metric=${intent.metric ?? 'unknown'}; dimensions=${(intent.dimensions ?? []).join(', ') || 'none'}; comparison=${intent.comparison ?? 'none'}`,
      confidence: run.confidence,
      latencyMs: Math.max(90, Math.round(run.execution_time_ms * 0.15))
    }
  ];

  if (clarification?.question) {
    steps.push({
      agent: 'Clarification Agent',
      purpose: 'Снять неоднозначность до генерации SQL.',
      output: clarification.question,
      confidence: run.confidence,
      latencyMs: 45
    });
    return steps;
  }

  steps.push(
    {
      agent: 'Semantic Mapping Agent',
      purpose: 'Сопоставить бизнес-термины со схемой данных.',
      output: `${semantic.metric_expression ?? 'metric'} on ${(semantic.tables ?? []).join(', ') || 'orders'}`,
      confidence: Math.min(run.confidence + 0.02, 0.99),
      latencyMs: Math.max(60, Math.round(run.execution_time_ms * 0.08))
    },
    {
      agent: 'SQL Generation Agent',
      purpose: 'Собрать безопасный SELECT для аналитического шага.',
      output: run.sql.split('\n')[0] ?? 'Generated SQL query',
      confidence: Math.max(run.confidence - 0.02, 0.7),
      latencyMs: Math.max(80, Math.round(run.execution_time_ms * 0.22))
    },
    {
      agent: 'SQL Validation Agent',
      purpose: 'Проверить whitelist таблиц, LIMIT и guardrails.',
      output: validation.warnings?.length
        ? validation.warnings.join(' ')
        : 'Validation passed with safe read-only execution.',
      confidence: Math.min(run.confidence + 0.04, 0.99),
      latencyMs: Math.max(55, Math.round(run.execution_time_ms * 0.06))
    }
  );

  if (chartSpec.chart_type) {
    steps.push({
      agent: 'Chart Decision Engine',
      purpose: 'Выбрать тип визуализации по семантике и shape результата.',
      output: chartSpec.rule_id
        ? `${chartSpec.rule_id} · ${chartSpec.chart_type} (${chartSpec.variant ?? 'default'})`
        : `${chartSpec.chart_type} chart on ${chartSpec.encoding?.x_field ?? 'result'} / ${chartSpec.encoding?.y_field ?? 'metric'}`,
      confidence: typeof chartSpec.confidence === 'number' ? chartSpec.confidence : Math.max(run.confidence - 0.01, 0.7),
      latencyMs: 52
    });
  }

  if (insightText) {
    steps.push({
      agent: 'Insight Agent',
      purpose: 'Сформулировать вывод для бизнес-пользователя.',
      output: insightText,
      confidence: Math.max(run.confidence - 0.03, 0.68),
      latencyMs: 58
    });
  }

  return steps;
}

function mapCell(
  cell: ApiCellRead,
  run: ApiQueryRunRead | undefined,
  promptRun: ApiQueryRunRead | undefined,
  fallbackModelAlias: string
): NotebookCell {
  const effectiveRun = run ?? promptRun;
  const queryMode = normalizeQueryMode(
    cell.content.query_mode ?? cell.content.queryMode ?? extractRunQueryMode(effectiveRun)
  );
  const llmModelAlias =
    typeof cell.content.llm_model_alias === 'string'
      ? cell.content.llm_model_alias
      : typeof cell.content.llmModelAlias === 'string'
        ? cell.content.llmModelAlias
        : extractRunModelAlias(effectiveRun, fallbackModelAlias);
  const warnings = extractWarnings(effectiveRun, cell);
  const businessTerms = extractBusinessTerms(effectiveRun);
  const tablesUsed = extractTables(effectiveRun);
  const sourceCellId = effectiveRun?.prompt_cell_id ?? (cell.query_run_id ? null : cell.id);
  const runStatus = effectiveRun?.status ?? null;

  if (cell.type === 'prompt') {
    return {
      id: cell.id,
      type: 'prompt',
      order: cell.position,
      title: 'Prompt',
      subtitle: 'Natural language request',
      agent: 'Intent Agent',
      tone: 'accent',
      queryRunId: cell.query_run_id,
      sourceCellId: cell.id,
      runStatus,
      content: {
        prompt: String(cell.content.text ?? ''),
        queryMode,
        llmModelAlias,
        chips: businessTerms.slice(0, 3).map((term) => titleCase(term.replace(/_/g, ' '))),
        context: promptRun?.status ? [`Status: ${promptRun.status}`] : []
      },
      meta: buildPromptMeta(promptRun, String(cell.content.text ?? ''))
    };
  }

  if (cell.type === 'sql' && cell.query_run_id === null) {
    return {
      id: cell.id,
      type: 'sql',
      order: cell.position,
      title: 'SQL Block',
      subtitle: 'Editable query',
      agent: 'Manual SQL',
      tone: 'accent',
      queryRunId: cell.query_run_id,
      sourceCellId: cell.id,
      runStatus,
      content: {
        sql: String(cell.content.sql ?? promptRun?.sql ?? ''),
        explanation: promptRun
          ? 'Ручной SQL можно править, форматировать и запускать повторно.'
          : 'Вставьте SQL, затем отформатируйте или выполните блок.',
        mode: 'editable',
        queryMode,
        llmModelAlias,
        warnings
      },
      meta: {
        confidence: promptRun ? 1 : 0.92,
        executionTimeMs: promptRun?.execution_time_ms,
        rowCount: promptRun?.row_count,
        tablesUsed,
        warnings,
        businessTerms,
        summary: promptRun
          ? 'Последний ручной запуск сохранён как notebook block.'
          : 'Редактируемая SQL-ячейка в стиле notebook.'
      }
    };
  }

  if (cell.type === 'sql') {
    return {
      id: cell.id,
      type: 'sql',
      order: cell.position,
      title: 'SQL',
      subtitle: 'Generated query',
      agent: 'SQL Generation Agent',
      tone: 'neutral',
      queryRunId: cell.query_run_id,
      sourceCellId,
      runStatus,
      content: {
        sql: String(cell.content.sql ?? run?.sql ?? ''),
        explanation: buildSqlExplanation(run),
        mode: 'generated',
        queryMode,
        llmModelAlias,
        warnings
      },
      meta: {
        confidence: run?.confidence ?? 0.78,
        executionTimeMs: run?.execution_time_ms,
        rowCount: run?.row_count,
        tablesUsed,
        warnings,
        businessTerms,
        summary: 'SQL сгенерирован агентом и сохранён в notebook history.'
      }
    };
  }

  if (cell.type === 'table') {
    const columns = Array.isArray(cell.content.columns)
      ? (cell.content.columns as string[])
      : [];
    const rows = Array.isArray(cell.content.rows)
      ? (cell.content.rows as Array<Record<string, unknown>>)
      : [];

    return {
      id: cell.id,
      type: 'table',
      order: cell.position,
      title: 'Result',
      subtitle: 'Query output',
      agent: 'SQL Validation Agent',
      tone: 'neutral',
      queryRunId: cell.query_run_id,
      sourceCellId,
      runStatus,
      content: {
        columns,
        rows: rows.map((row) =>
          Object.fromEntries(
            Object.entries(row).map(([key, value]) => [key, normalizeDisplayValue(value)])
          )
        ),
        footnote: `Rows returned: ${run?.row_count ?? rows.length}`
      },
      meta: {
        confidence: run?.confidence ?? 0.82,
        executionTimeMs: run?.execution_time_ms,
        rowCount: run?.row_count,
        tablesUsed,
        warnings,
        businessTerms,
        summary: 'Результат запроса сохранён как отдельная табличная cell.'
      }
    };
  }

  if (cell.type === 'chart') {
    return {
      id: cell.id,
      type: 'chart',
      order: cell.position,
      title: 'Chart',
      subtitle: 'Visualization',
      agent: 'Visualization Agent',
      tone: 'accent',
      queryRunId: cell.query_run_id,
      sourceCellId,
      runStatus,
      content: buildChartContent(cell),
      meta: {
        confidence: run?.confidence ?? 0.8,
        executionTimeMs: run?.execution_time_ms,
        rowCount: run?.row_count,
        tablesUsed,
        warnings,
        businessTerms,
        summary: 'Chart spec подобран автоматически на основе структуры результата.'
      }
    };
  }

  if (cell.type === 'insight') {
    const text = String(cell.content.text ?? '');
    const sentences = text
      .split(/(?<=[.!?])\s+/)
      .map((item) => item.trim())
      .filter(Boolean);

    return {
      id: cell.id,
      type: 'insight',
      order: cell.position,
      title: 'Insight',
      subtitle: 'Business summary',
      agent: 'Insight Agent',
      tone: 'success',
      queryRunId: cell.query_run_id,
      sourceCellId,
      runStatus,
      content: {
        headline: sentences[0] ?? text ?? 'Insight generated.',
        bullets: sentences.length > 1 ? sentences.slice(1) : []
      },
      meta: {
        confidence: run?.confidence ?? 0.8,
        executionTimeMs: run?.execution_time_ms,
        rowCount: run?.row_count,
        tablesUsed,
        warnings,
        businessTerms,
        summary: 'Краткий вывод сохранён как explainability-слой для менеджера.'
      }
    };
  }

  return {
    id: cell.id,
    type: 'clarification',
    order: cell.position,
    title: run?.status === 'error' ? 'Validation' : 'Clarification',
    subtitle: run?.status === 'error' ? 'Guardrail response' : 'Agent asks for clarification',
    agent: run?.status === 'error' ? 'SQL Validation Agent' : 'Clarification Agent',
    tone: 'warning',
    queryRunId: cell.query_run_id,
    sourceCellId,
    runStatus,
    content: buildClarificationContent(cell),
    meta: {
      confidence: run?.confidence ?? 0.74,
      executionTimeMs: run?.execution_time_ms,
      rowCount: run?.row_count,
      tablesUsed,
      warnings,
      businessTerms,
      summary:
        run?.status === 'error'
          ? 'Запрос остановлен guardrail-слоем до исполнения.'
          : 'Агент запросил уточнение, чтобы не строить неверный SQL.'
    }
  };
}

function buildDatabaseConnections(
  databases: ApiDatabaseDescriptor[],
  schema: ApiSchemaMetadataResponse | null
): DatabaseConnection[] {
  return databases.map((database) => {
    const hostSegment = database.host
      ? `${database.host}${database.port ? `:${database.port}` : ''}`
      : '';
    const engineParts = [
      titleCase(database.dialect),
      hostSegment,
      database.database ?? undefined
    ].filter((part): part is string => Boolean(part));
    const tables =
      database.is_builtin || !database.table_count
        ? schema?.tables.length ?? database.table_count ?? 0
        : database.table_count;
    const status: DatabaseConnection['status'] =
      database.status === 'syncing' ? 'syncing' : 'connected';
    return {
      id: database.id,
      name: database.name,
      description: database.description,
      engine: engineParts.join(' · ') || titleCase(database.dialect),
      mode: database.read_only ? 'read-only' : 'read-write',
      tables,
      schemas: ['public'],
      status,
      knowledgeStatus: database.knowledge_status ?? 'not_scanned',
      lastScanAt: database.last_scan_at ?? undefined,
      isBuiltin: database.is_builtin,
      allowedTables: database.allowed_tables ?? null
    };
  });
}

function buildReports(reports: ApiReportRead[]): SavedReport[] {
  return reports.map((report) => ({
    id: report.id,
    title: report.title,
    notebookId: report.notebook_id,
    createdAt: report.created_at,
    schedule: report.schedule ?? undefined
  }));
}

function buildDictionary(entries: ApiDictionaryEntryRead[]): DictionaryTerm[] {
  return entries.map((entry) => ({
    id: entry.id,
    term: entry.term,
    synonyms: entry.synonyms,
    mappedExpression: entry.mapped_expression,
    description: entry.description
  }));
}

function buildTemplates(templates: ApiQueryTemplate[]): QueryTemplate[] {
  return templates.map((template) => ({
    id: template.id,
    title: template.title,
    description: template.prompt
  }));
}

function buildHistory(notebooks: Notebook[], reports: SavedReport[]): HistoryItem[] {
  const rawEvents = [
    ...reports.map((report) => ({
      id: `report-${report.id}`,
      label: `Saved report “${report.title}”`,
      createdAt: report.createdAt
    })),
    ...notebooks
      .filter((notebook) => notebook.cells.length > 0)
      .map((notebook) => ({
        id: `notebook-${notebook.id}`,
        label: `Ran notebook “${notebook.title}”`,
        createdAt: notebook.updatedAt
      }))
  ]
    .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
    .slice(0, 8);

  return rawEvents.map((event) => ({
    id: event.id,
    label: event.label,
    timestamp: formatClock(event.createdAt)
  }));
}

export function mapNotebookDetail(
  detail: ApiNotebookDetail,
  workspaceName: string,
  defaultModelAlias: string
): Notebook {
  const sortedCells = [...detail.cells].sort((left, right) => left.position - right.position);
  const sortedRuns = [...detail.query_runs].sort(
    (left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
  );
  const runById = new Map(sortedRuns.map((run) => [run.id, run]));
  const promptRunByCellId = new Map<string, ApiQueryRunRead>();

  for (const run of sortedRuns) {
    promptRunByCellId.set(run.prompt_cell_id, run);
  }

  const mappedCells = sortedCells.map((cell) =>
    mapCell(
      cell,
      cell.query_run_id ? runById.get(cell.query_run_id) : undefined,
      promptRunByCellId.get(cell.id),
      defaultModelAlias
    )
  );

  const latestRun = sortedRuns[sortedRuns.length - 1];
  const latestInsight = mappedCells
    .slice()
    .reverse()
    .find((cell) => cell.type === 'insight');

  return {
    id: detail.id,
    title: detail.title,
    databaseId: detail.database_id,
    createdAt: detail.created_at,
    updatedAt: detail.updated_at,
    status: detail.status === 'saved' ? 'saved' : 'draft',
    summary: {
      objective:
        latestRun?.prompt_text ??
        'Создайте prompt cell, чтобы запустить аналитическое исследование.',
      lastRunLabel: latestRun ? formatRelativeTime(latestRun.created_at) : 'Ещё не запускался',
      highlight:
        latestInsight?.type === 'insight'
          ? latestInsight.content.headline
          : latestRun?.error_message ?? 'Notebook готов к следующему аналитическому шагу.',
      owner: workspaceName
    },
    trace: buildTrace(
      latestRun,
      detail.title,
      latestInsight?.type === 'insight' ? latestInsight.content.headline : undefined
    ),
    cells: mappedCells
  };
}

export function buildWorkspaceData(params: {
  databases: ApiDatabaseDescriptor[];
  defaultModelAlias: string;
  dictionary: ApiDictionaryEntryRead[];
  notebookDetails: ApiNotebookDetail[];
  reports: ApiReportRead[];
  schema: ApiSchemaMetadataResponse | null;
  templates: ApiQueryTemplate[];
  workspace: ApiWorkspaceRead | null;
}): WorkspaceData {
  const notebooks = params.notebookDetails.map((detail) =>
    mapNotebookDetail(
      detail,
      params.workspace?.name ?? 'Workspace',
      params.defaultModelAlias
    )
  );
  const reports = buildReports(params.reports);

  return {
    id: params.workspace?.id ?? 'workspace',
    name: params.workspace?.name ?? 'Workspace',
    tagline: 'Notebook-first self-service analytics connected to a live backend',
    databases: buildDatabaseConnections(params.databases, params.schema),
    notebooks,
    reports,
    templates: buildTemplates(params.templates),
    dictionary: buildDictionary(params.dictionary),
    history: buildHistory(notebooks, reports)
  };
}
