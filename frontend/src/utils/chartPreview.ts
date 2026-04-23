import type {
  ApiChatChartSpec,
  ApiChatExecutionRead,
  ApiChatExecutionRecommendation
} from '@/api/types';
import type { ChartCellContent } from '@/types/app';

type ChartPayload = {
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

export function inferColumnKinds(
  columns: Array<{ name: string; type: string }>,
  rows: Array<Record<string, unknown>>
) {
  const numeric: string[] = [];
  const temporal: string[] = [];
  const categorical: string[] = [];

  for (const column of columns) {
    const name = column.name;
    const type = String(column.type ?? '').toLowerCase();
    const values = rows
      .map((row) => row[name])
      .filter((value) => value !== null && value !== undefined);

    if (looksTemporal(type, name, values)) {
      temporal.push(name);
      continue;
    }

    if (looksNumeric(type, name, values)) {
      numeric.push(name);
      continue;
    }

    categorical.push(name);
  }

  return { numeric, temporal, categorical };
}

export function buildChartCellContentFromRecommendation(
  recommendation: ApiChatExecutionRecommendation | null | undefined,
  execution: ApiChatExecutionRead | null
): ChartCellContent | null {
  if (!execution || execution.error_message || !recommendation) {
    return null;
  }

  if (recommendation.chart_spec) {
    return buildChartCellContentFromSpec(recommendation.chart_spec, execution, {
      fallbackReason: recommendation.reason,
      fallbackExplanation: recommendation.explanation ?? recommendation.reason
    });
  }

  if (recommendation.recommended_view !== 'chart') {
    return null;
  }

  return buildChartCellContentFromPayload(
    recommendation.data as ChartPayload | null | undefined,
    {
      chartType: recommendation.chart_type ?? 'bar',
      title: 'Рекомендованная визуализация',
      subtitle: recommendation.reason,
      explanation: recommendation.explanation ?? recommendation.reason,
      ruleId: recommendation.rule_id ?? undefined,
      confidence: recommendation.confidence ?? undefined,
      variant: recommendation.variant ?? undefined,
      valueFormat: recommendation.value_format ?? undefined
    },
    execution
  );
}

export function buildChartCellContentFromSpec(
  spec: ApiChatChartSpec | null | undefined,
  execution: ApiChatExecutionRead | null,
  fallback?: {
    fallbackReason?: string | null;
    fallbackExplanation?: string | null;
  }
): ChartCellContent | null {
  if (!execution || execution.error_message || !spec || spec.chart_type === 'table') {
    return null;
  }

  const meta = {
    chartType: spec.chart_type,
    title: spec.title || 'Визуализация',
    subtitle: spec.reason ?? fallback?.fallbackReason ?? 'Визуализация результата',
    explanation: spec.explanation ?? fallback?.fallbackExplanation ?? spec.reason ?? 'Визуализация результата',
    ruleId: spec.rule_id ?? undefined,
    confidence: spec.confidence ?? undefined,
    variant: spec.variant ?? undefined,
    valueFormat: spec.encoding.value_format ?? undefined
  } as const;

  if (spec.data) {
    return buildChartCellContentFromPayload(spec.data as ChartPayload, meta, execution);
  }

  const rows = execution.rows_preview ?? [];
  const columns = execution.columns ?? [];
  const xField = spec.encoding.x_field ?? null;
  const yField = spec.encoding.y_field ?? null;
  const seriesField = spec.encoding.series_field ?? null;

  if (spec.chart_type === 'metric_card') {
    const field = yField ?? inferColumnKinds(columns, rows).numeric[0] ?? null;
    const value = field ? firstNonNullValue(rows, field) : null;
    return {
      chartType: 'metric_card',
      title: meta.title,
      subtitle: meta.subtitle,
      explanation: meta.explanation,
      ruleId: meta.ruleId,
      confidence: meta.confidence,
      variant: meta.variant,
      valueFormat: meta.valueFormat,
      value: value ?? '—',
      metricLabel: field ?? 'Value'
    };
  }

  if (!xField || !yField) {
    return null;
  }

  if (spec.chart_type === 'pie') {
    const pieData = buildPieData(rows, xField, yField);
    return {
      chartType: 'pie',
      title: meta.title,
      subtitle: meta.subtitle,
      explanation: meta.explanation,
      ruleId: meta.ruleId,
      confidence: meta.confidence,
      variant: meta.variant,
      valueFormat: meta.valueFormat,
      pieData
    };
  }

  if (seriesField) {
    const multiSeries = buildMultiSeries(rows, xField, yField, seriesField);
    return {
      chartType: spec.chart_type === 'bar' ? 'bar' : 'line',
      title: meta.title,
      subtitle: meta.subtitle,
      explanation: meta.explanation,
      ruleId: meta.ruleId,
      confidence: meta.confidence,
      variant: meta.variant,
      valueFormat: meta.valueFormat,
      xAxis: multiSeries.xAxis,
      series: multiSeries.series,
      stacked: spec.variant === 'stacked'
    };
  }

  const singleSeries = buildSingleSeries(rows, xField, yField);
  return {
    chartType: spec.chart_type === 'bar' ? 'bar' : 'line',
    title: meta.title,
    subtitle: meta.subtitle,
    explanation: meta.explanation,
    ruleId: meta.ruleId,
    confidence: meta.confidence,
    variant: meta.variant,
    valueFormat: meta.valueFormat,
    xAxis: singleSeries.xAxis,
    series: [
      {
        name: yField,
        data: singleSeries.values
      }
    ],
    stacked: spec.variant === 'stacked'
  };
}

export function buildVisualizationConfigFromSpec(
  spec: ApiChatChartSpec | null | undefined
): Record<string, unknown> | null {
  if (!spec) {
    return null;
  }
  return {
    chart_spec: spec,
    chart_type: spec.chart_type,
    variant: spec.variant ?? null,
    x: spec.encoding.x_field ?? null,
    y: spec.encoding.y_field ?? null,
    series: spec.encoding.series_field ?? null,
    facet: spec.encoding.facet_field ?? null,
    normalize: spec.encoding.normalize ?? null,
    sort: spec.encoding.sort ?? null,
    value_format: spec.encoding.value_format ?? null
  };
}

function buildChartCellContentFromPayload(
  payload: ChartPayload | null | undefined,
  meta: {
    chartType: string;
    title: string;
    subtitle: string;
    explanation: string;
    ruleId?: string;
    confidence?: number;
    variant?: string;
    valueFormat?: string;
  },
  execution: ApiChatExecutionRead
): ChartCellContent | null {
  if (!payload) {
    return null;
  }

  if (payload.kind === 'kpi' || meta.chartType === 'metric_card') {
    return {
      chartType: 'metric_card',
      title: meta.title,
      subtitle: meta.subtitle,
      explanation: meta.explanation,
      ruleId: meta.ruleId,
      confidence: meta.confidence,
      variant: meta.variant,
      valueFormat: meta.valueFormat,
      value: payload.value ?? '—',
      metricLabel: payload.metricLabel ?? execution.chart_recommendation?.y ?? 'Value'
    };
  }

  if (payload.kind === 'pie' || meta.chartType === 'pie') {
    return {
      chartType: 'pie',
      title: meta.title,
      subtitle: meta.subtitle,
      explanation: meta.explanation,
      ruleId: meta.ruleId,
      confidence: meta.confidence,
      variant: meta.variant,
      valueFormat: meta.valueFormat,
      pieData:
        payload.slices?.map((slice, index) => ({
          name: String(slice.name ?? `Segment ${index + 1}`),
          value: toNumber(slice.value)
        })) ?? []
    };
  }

  if (payload.kind === 'multi_series') {
    const hasSeries = (payload.series ?? []).some(
      (series) => (series.data ?? []).length > 0 || Boolean(series.name)
    );

    if (!hasSeries) {
      return {
        chartType: meta.chartType === 'bar' ? 'bar' : 'line',
        title: meta.title,
        subtitle: meta.subtitle,
        explanation: meta.explanation,
        ruleId: meta.ruleId,
        confidence: meta.confidence,
        variant: meta.variant,
        valueFormat: meta.valueFormat,
        xAxis: (payload.x?.values ?? []).map((value) => String(value ?? '—')),
        series: [
          {
            name: String(payload.y?.field ?? execution.chart_recommendation?.y ?? 'Value'),
            data: (payload.y?.values ?? []).map((value) => toNumber(value))
          }
        ],
        stacked: Boolean(payload.stacked || payload.stackable)
      };
    }

    return {
      chartType: meta.chartType === 'bar' ? 'bar' : 'line',
      title: meta.title,
      subtitle: meta.subtitle,
      explanation: meta.explanation,
      ruleId: meta.ruleId,
      confidence: meta.confidence,
      variant: meta.variant,
      valueFormat: meta.valueFormat,
      xAxis: (payload.x?.values ?? []).map((value) => String(value ?? '—')),
      series:
        payload.series?.map((series) => ({
          name: String(series.name ?? 'Series'),
          data: (series.data ?? []).map((value) => toNumber(value))
        })) ?? [],
      stacked: Boolean(payload.stacked || payload.stackable)
    };
  }

  if (payload.kind === 'single_series') {
    return {
      chartType: meta.chartType === 'bar' ? 'bar' : 'line',
      title: meta.title,
      subtitle: meta.subtitle,
      explanation: meta.explanation,
      ruleId: meta.ruleId,
      confidence: meta.confidence,
      variant: meta.variant,
      valueFormat: meta.valueFormat,
      xAxis: (payload.x?.values ?? []).map((value) => String(value ?? '—')),
      series: [
        {
          name: String(payload.y?.field ?? execution.chart_recommendation?.y ?? 'Value'),
          data: (payload.y?.values ?? []).map((value) => toNumber(value))
        }
      ],
      stacked: Boolean(payload.stacked)
    };
  }

  return null;
}

function buildSingleSeries(rows: Array<Record<string, unknown>>, xField: string, yField: string) {
  const map = new Map<string, number>();
  const order: string[] = [];

  for (const row of rows) {
    const xValue = String(row[xField] ?? '—');
    if (!map.has(xValue)) {
      order.push(xValue);
      map.set(xValue, 0);
    }
    map.set(xValue, (map.get(xValue) ?? 0) + toNumber(row[yField]));
  }

  return {
    xAxis: order,
    values: order.map((key) => map.get(key) ?? 0)
  };
}

function buildMultiSeries(
  rows: Array<Record<string, unknown>>,
  xField: string,
  yField: string,
  seriesField: string
) {
  const xOrder: string[] = [];
  const seriesOrder: string[] = [];
  const matrix = new Map<string, number>();

  for (const row of rows) {
    const xValue = String(row[xField] ?? '—');
    const seriesValue = String(row[seriesField] ?? 'Series');
    const key = `${xValue}:::${seriesValue}`;

    if (!xOrder.includes(xValue)) {
      xOrder.push(xValue);
    }
    if (!seriesOrder.includes(seriesValue)) {
      seriesOrder.push(seriesValue);
    }

    matrix.set(key, (matrix.get(key) ?? 0) + toNumber(row[yField]));
  }

  return {
    xAxis: xOrder,
    series: seriesOrder.map((seriesName) => ({
      name: seriesName,
      data: xOrder.map((xValue) => matrix.get(`${xValue}:::${seriesName}`) ?? 0)
    }))
  };
}

function buildPieData(rows: Array<Record<string, unknown>>, xField: string, yField: string) {
  const aggregated = buildSingleSeries(rows, xField, yField);
  return aggregated.xAxis.map((name, index) => ({
    name,
    value: aggregated.values[index] ?? 0
  }));
}

function firstNonNullValue(rows: Array<Record<string, unknown>>, field: string) {
  for (const row of rows) {
    const value = row[field];
    if (value !== null && value !== undefined && value !== '') {
      return value;
    }
  }
  return null;
}

function looksNumeric(type: string, name: string, values: unknown[]) {
  if (/_id$/i.test(name)) {
    return false;
  }
  if (/(int|float|double|decimal|numeric|real|money|number)/.test(type)) {
    return true;
  }
  if (!values.length) {
    return false;
  }
  const numericCount = values.filter((value) => {
    if (typeof value === 'number') {
      return true;
    }
    const parsed = Number(String(value).replace(',', '.'));
    return Number.isFinite(parsed);
  }).length;
  return numericCount >= Math.max(1, Math.ceil(values.length * 0.7));
}

function looksTemporal(type: string, name: string, values: unknown[]) {
  if (/(date|time|timestamp)/.test(type) || /(date|time|month|day|week|year|_at)$/i.test(name)) {
    return true;
  }
  if (!values.length) {
    return false;
  }
  const temporalCount = values.filter((value) => {
    const text = String(value ?? '').trim();
    return /^\d{4}-\d{2}-\d{2}/.test(text) || !Number.isNaN(Date.parse(text));
  }).length;
  return temporalCount >= Math.max(1, Math.ceil(values.length * 0.6));
}

function toNumber(value: unknown) {
  if (typeof value === 'number') {
    return value;
  }
  const parsed = Number(String(value ?? '').replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : 0;
}
