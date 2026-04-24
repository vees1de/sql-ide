<template>
  <div class="widget-chart">
    <div v-if="!chartContent" class="widget-chart__empty">
      Недостаточно данных для графика.
    </div>
    <ChartCell v-else :content="chartContent" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import ChartCell from '@/components/cells/ChartCell.vue';
import type { ChartCellContent } from '@/types/app';
import type { ApiChatChartSpec, ApiChatExecutionRead, ApiWidgetRunRead, ApiVisualizationType } from '@/api/types';
import { buildChartCellContentFromSpec } from '@/utils/chartPreview';

const props = defineProps<{
  run: ApiWidgetRunRead;
  vizType: ApiVisualizationType;
  vizConfig: Record<string, unknown> | null | undefined;
  chartSpec?: ApiChatChartSpec | null;
}>();

const chartContent = computed<ChartCellContent | null>(() => {
  if (props.chartSpec) {
    const adaptedExecution = {
      columns: props.run.columns ?? [],
      rows_preview: props.run.rows_preview ?? [],
      rows_preview_truncated: props.run.rows_preview_truncated,
      row_count: props.run.row_count,
      execution_time_ms: props.run.execution_time_ms,
      error_message: props.run.status === 'error' ? props.run.error_text : null,
      sql_text: '',
      session_id: '',
      id: '',
      dataset: null,
      chart_recommendation: null,
      created_at: props.run.started_at
    } as unknown as ApiChatExecutionRead;

    return buildChartCellContentFromSpec(props.chartSpec, adaptedExecution);
  }

  const rows = props.run.rows_preview;
  const columns = props.run.columns;
  if (!rows || !columns || rows.length === 0) return null;

  const cfg = props.vizConfig ?? {};
  const xField = (cfg.x as string) ?? columns[0]?.name ?? '';
  const yField = (cfg.y as string) ?? columns[1]?.name ?? columns[0]?.name ?? '';
  const chartType: 'line' | 'bar' | 'pie' =
    props.vizType === 'pie' ? 'pie' :
    props.vizType === 'line' || props.vizType === 'area' ? 'line' : 'bar';

  if (chartType === 'pie') {
    return {
      chartType: 'pie',
      title: '',
      pieData: rows.map((row) => ({
        name: String(row[xField] ?? ''),
        value: Number(row[yField] ?? 0),
      })),
    };
  }

  const xAxis = rows.map((row) => String(row[xField] ?? ''));
  const data = rows.map((row) => Number(row[yField] ?? 0));

  return {
    chartType,
    title: '',
    xAxis,
    series: [{ name: yField, data }],
  };
});
</script>

<style scoped lang="scss">
.widget-chart {
  flex: 1;
  min-height: 220px;
  display: flex;
  flex-direction: column;
}

.widget-chart__empty {
  color: var(--muted);
  font-size: 0.85rem;
  text-align: center;
  padding: 24px 0;
}
</style>
