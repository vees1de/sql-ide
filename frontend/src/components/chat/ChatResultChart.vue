<template>
  <div class="chat-result-chart">
    <div v-if="interpretation" class="chat-result-chart__interpretation">
      <strong>Как я понял запрос</strong>
      <p>{{ interpretation.short_explanation ?? recommendationReason }}</p>
      <div class="chat-result-chart__chips">
        <span v-if="interpretation.intent">{{ interpretation.intent }}</span>
        <span v-if="interpretation.time_dimension">X: {{ interpretation.time_dimension }}</span>
        <span v-if="interpretation.series_dimension">Series: {{ interpretation.series_dimension }}</span>
        <span v-if="primaryMetric">Metric: {{ primaryMetric }}</span>
      </div>
      <p v-if="interpretation.assumptions?.length" class="chat-result-chart__meta">
        Допущения: {{ interpretation.assumptions.join('; ') }}
      </p>
      <p v-if="interpretation.ambiguities?.length" class="chat-result-chart__meta">
        Неоднозначности: {{ interpretation.ambiguities.join('; ') }}
      </p>
    </div>
    <div v-if="content" class="chat-result-chart__chart">
      <ChartCell :content="content" />
    </div>
    <div v-else class="chat-result-chart__empty">
      <p>{{ emptyMessage }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import ChartCell from '@/components/cells/ChartCell.vue';
import type { ChartCellContent } from '@/types/app';
import type { ApiChatExecutionRead } from '@/api/types';

const props = defineProps<{
  execution: ApiChatExecutionRead | null;
}>();

const recommendation = computed(() => props.execution?.chart_recommendation ?? null);

const interpretation = computed(() => recommendation.value?.query_interpretation ?? null);

const primaryMetric = computed(() => interpretation.value?.metrics?.[0]?.name ?? null);

const recommendationReason = computed(() => recommendation.value?.reason ?? 'Рекомендованная визуализация');

const content = computed<ChartCellContent | null>(() => {
  const execution = props.execution;
  if (!execution || execution.error_message) {
    return null;
  }

  const recommendation = execution.chart_recommendation;
  if (!recommendation || recommendation.recommended_view !== 'chart') {
    return null;
  }

  const chartData = recommendation.data as
    | {
        kind?: string;
        x?: { field?: string | null; values?: unknown[]; type?: string | null };
        y?: { field?: string | null; values?: unknown[]; unit?: string | null };
        series?: Array<{ name?: string; data?: unknown[] }>;
        slices?: Array<{ name?: string; value?: unknown }>;
        value?: unknown;
        metricLabel?: string | null;
        stacked?: boolean;
        stackable?: boolean;
      }
    | undefined;

  if (chartData?.kind === 'kpi' || recommendation.chart_type === 'metric_card') {
    return {
      chartType: 'metric_card',
      title: recommendation.reason,
      subtitle: recommendation.explanation ?? recommendation.reason,
      explanation: recommendation.explanation ?? recommendation.reason,
      ruleId: recommendation.rule_id ?? undefined,
      confidence: recommendation.confidence ?? undefined,
      variant: recommendation.variant ?? undefined,
      valueFormat: recommendation.value_format ?? undefined,
      value: chartData?.value ?? '—',
      metricLabel: chartData?.metricLabel ?? recommendation.y ?? 'Value'
    };
  }

  if (chartData?.kind === 'pie' || recommendation.chart_type === 'pie') {
    return {
      chartType: 'pie',
      title: 'Структура результата',
      subtitle: recommendation.reason,
      explanation: recommendation.explanation ?? recommendation.reason,
      ruleId: recommendation.rule_id ?? undefined,
      confidence: recommendation.confidence ?? undefined,
      variant: recommendation.variant ?? undefined,
      valueFormat: recommendation.value_format ?? undefined,
      pieData: chartData?.slices?.map((slice, index) => ({
        name: String(slice.name ?? `Segment ${index + 1}`),
        value: Number(slice.value ?? 0)
      })) ?? fallbackPieData(execution.rows_preview ?? [])
    };
  }

  if (chartData?.kind === 'multi_series') {
    return {
      chartType: recommendation.chart_type === 'bar' ? 'bar' : 'line',
      title: 'Рекомендованная визуализация',
      subtitle: recommendation.reason,
      explanation: recommendation.explanation ?? recommendation.reason,
      ruleId: recommendation.rule_id ?? undefined,
      confidence: recommendation.confidence ?? undefined,
      variant: recommendation.variant ?? undefined,
      valueFormat: recommendation.value_format ?? undefined,
      xAxis: (chartData.x?.values ?? []).map((value) => String(value ?? '—')),
      series: (chartData.series ?? []).map((series) => ({
        name: String(series.name ?? 'Series'),
        data: (series.data ?? []).map((value) => Number(value ?? 0))
      })),
      stacked: Boolean(chartData.stacked || chartData.stackable)
    };
  }

  if (chartData?.kind === 'single_series') {
    return {
      chartType: recommendation.chart_type === 'bar' ? 'bar' : 'line',
      title: 'Рекомендованная визуализация',
      subtitle: recommendation.reason,
      explanation: recommendation.explanation ?? recommendation.reason,
      ruleId: recommendation.rule_id ?? undefined,
      confidence: recommendation.confidence ?? undefined,
      variant: recommendation.variant ?? undefined,
      valueFormat: recommendation.value_format ?? undefined,
      xAxis: (chartData.x?.values ?? []).map((value) => String(value ?? '—')),
      series: [
        {
          name: String(chartData.y?.field ?? recommendation.y ?? 'Value'),
          data: (chartData.y?.values ?? []).map((value) => Number(value ?? 0))
        }
      ]
    };
  }

  const rows = execution.rows_preview ?? [];
  const xField = recommendation.x ?? Object.keys(rows[0] ?? {})[0] ?? '';
  const yField = recommendation.y ?? Object.keys(rows[0] ?? {})[1] ?? '';

  if (recommendation.series) {
    const xValues = [...new Set(rows.map((row) => String(row[xField] ?? '—')))];
    const seriesValues = [...new Set(rows.map((row) => String(row[recommendation.series!] ?? 'Series')))];
    return {
      chartType: recommendation.chart_type === 'line' ? 'line' : 'bar',
      title: 'Рекомендованная визуализация',
      subtitle: recommendation.reason,
      explanation: recommendation.explanation ?? recommendation.reason,
      ruleId: recommendation.rule_id ?? undefined,
      confidence: recommendation.confidence ?? undefined,
      variant: recommendation.variant ?? undefined,
      valueFormat: recommendation.value_format ?? undefined,
      xAxis: xValues,
      series: seriesValues.map((seriesName) => ({
        name: seriesName,
        data: xValues.map((xValue) => sumMatchingRows(rows, xField, recommendation.series!, xValue, seriesName, yField))
      }))
    };
  }

  return {
    chartType: recommendation.chart_type === 'line' ? 'line' : 'bar',
    title: 'Рекомендованная визуализация',
    subtitle: recommendation.reason,
    explanation: recommendation.explanation ?? recommendation.reason,
    ruleId: recommendation.rule_id ?? undefined,
    confidence: recommendation.confidence ?? undefined,
    variant: recommendation.variant ?? undefined,
    valueFormat: recommendation.value_format ?? undefined,
    xAxis: rows.map((row) => String(row[xField] ?? '—')),
    series: [
      {
        name: String(yField),
        data: rows.map((row) => Number(row[yField] ?? 0))
      }
    ]
  };
});

const emptyMessage = computed(() => {
  const execution = props.execution;
  if (!execution) {
    return 'Для этого результата график не рекомендован.';
  }

  const recommendation = execution.chart_recommendation;
  if (!recommendation) {
    return 'Для этого результата график не рекомендован.';
  }

  if (recommendation.recommended_view !== 'chart') {
    return recommendation.reason;
  }

  if (execution.error_message) {
    return execution.error_message;
  }

  return 'Для этого результата график не рекомендован.';
});

function fallbackPieData(rows: Array<Record<string, unknown>>) {
  return rows.map((row, index) => ({
    name: String(row[Object.keys(row)[0] ?? `label-${index}`] ?? `Segment ${index + 1}`),
    value: Number(row[Object.keys(row)[1] ?? 'value'] ?? 0)
  }));
}

function sumMatchingRows(
  rows: Array<Record<string, unknown>>,
  xField: string,
  seriesField: string,
  xValue: string,
  seriesValue: string,
  yField: string
) {
  return rows
    .filter(
      (row) =>
        String(row[xField] ?? '—') === xValue &&
        String(row[seriesField] ?? '—') === seriesValue
    )
    .reduce((sum, row) => sum + toNumber(row[yField]), 0);
}

function toNumber(value: unknown) {
  if (typeof value === 'number') {
    return value;
  }
  const parsed = Number(String(value).replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : 0;
}
</script>

<style scoped lang="scss">
.chat-result-chart__empty {
  display: grid;
  place-items: center;
  min-height: 16rem;
  padding: 1rem;
  border: 1px dashed var(--line);
  border-radius: var(--radius-lg);
  color: var(--muted);
  background: rgba(255, 255, 255, 0.02);
}

.chat-result-chart__chart :deep(.chart-cell__plot) {
  height: 100%;
  min-height: 18rem;
}

.chat-result-chart__interpretation {
  margin-bottom: 0.85rem;
  padding: 0.9rem 1rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: rgba(15, 23, 42, 0.03);
}

.chat-result-chart__interpretation strong {
  display: block;
  margin-bottom: 0.3rem;
  font-size: 0.88rem;
  color: var(--ink);
}

.chat-result-chart__interpretation p {
  margin: 0;
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.45;
}

.chat-result-chart__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0.6rem 0 0.4rem;
}

.chat-result-chart__chips span {
  display: inline-flex;
  align-items: center;
  padding: 0.28rem 0.55rem;
  border-radius: 999px;
  background: rgba(36, 107, 255, 0.08);
  color: var(--ink);
  font-size: 0.72rem;
  font-weight: 600;
}

.chat-result-chart__meta + .chat-result-chart__meta {
  margin-top: 0.3rem;
}
</style>
