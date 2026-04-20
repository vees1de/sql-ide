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

  const rows = execution.rows_preview ?? [];
  if (!rows.length || !recommendation.x || !recommendation.y) {
    return null;
  }

  const title = recommendation.chart_type === 'pie'
    ? 'Структура результата'
    : 'Рекомендованная визуализация';

  if (recommendation.chart_type === 'pie') {
    return {
      chartType: 'pie',
      title,
      subtitle: recommendation.reason,
      pieData: rows.map((row, index) => ({
        name: String(row[recommendation.x ?? Object.keys(row)[0] ?? `label-${index}`] ?? `Сегмент ${index + 1}`),
        value: toNumber(row[recommendation.y ?? 'value'])
      }))
    };
  }

  const xValues = uniqueValues(rows, recommendation.x);
  if (recommendation.chart_type === 'stacked_bar' && recommendation.series) {
    const seriesValues = uniqueValues(rows, recommendation.series);
    return {
      chartType: 'bar',
      stacked: true,
      title,
      subtitle: recommendation.reason,
      xAxis: xValues,
      series: seriesValues.map((seriesName) => ({
        name: seriesName,
        data: xValues.map((xValue) => sumMatchingRows(rows, recommendation.x!, recommendation.series!, xValue, seriesName, recommendation.y!))
      }))
    };
  }

  if (recommendation.series) {
    const seriesValues = uniqueValues(rows, recommendation.series);
    return {
      chartType: recommendation.chart_type === 'line' ? 'line' : 'bar',
      title,
      subtitle: recommendation.reason,
      xAxis: xValues,
      series: seriesValues.map((seriesName) => ({
        name: seriesName,
        data: xValues.map((xValue) => sumMatchingRows(rows, recommendation.x!, recommendation.series!, xValue, seriesName, recommendation.y!))
      }))
    };
  }

  return {
    chartType: recommendation.chart_type === 'line' ? 'line' : 'bar',
    title,
    subtitle: recommendation.reason,
    xAxis: xValues,
    series: [
      {
        name: recommendation.y,
        data: xValues.map((xValue) => sumRowValue(rows, recommendation.x!, xValue, recommendation.y!))
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

function uniqueValues(rows: Array<Record<string, unknown>>, field: string) {
  return [...new Set(rows.map((row) => String(row[field] ?? '—')))];
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

function sumRowValue(rows: Array<Record<string, unknown>>, xField: string, xValue: string, yField: string) {
  return rows
    .filter((row) => String(row[xField] ?? '—') === xValue)
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
