<template>
  <div class="chat-result-chart">
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
</style>
