<template>
  <div class="chart-cell">
    <div v-if="content.chartType === 'metric_card'" class="chart-cell__metric">
      <div class="chart-cell__metric-value">{{ formatValue(content.value, content.valueFormat) }}</div>
      <div class="chart-cell__metric-label">{{ content.metricLabel ?? 'Value' }}</div>
      <p v-if="content.explanation" class="chart-cell__metric-note">
        {{ content.explanation }}
      </p>
    </div>

    <VChart v-else class="chart-cell__plot" :option="chartOption" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import VChart from 'vue-echarts';
import type { ChartCellContent } from '@/types/app';

const props = defineProps<{
  content: ChartCellContent;
  showHeader?: boolean;
}>();

const palette = computed(
  () => props.content.palette ?? ['#246bff', '#0f766e', '#f59e0b']
);

const confidenceLabel = computed(() => {
  if (typeof props.content.confidence !== 'number') {
    return 'n/a';
  }
  return `${Math.round(props.content.confidence * 100)}%`;
});

function formatValue(value: unknown, valueFormat?: string) {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'string' && !Number.isFinite(Number(value))) {
    return value;
  }
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return String(value);
  }
  switch (valueFormat) {
    case 'percent':
      return new Intl.NumberFormat('ru-RU', {
        style: 'percent',
        maximumFractionDigits: 1
      }).format(numericValue > 1 ? numericValue / 100 : numericValue);
    case 'compact':
      return new Intl.NumberFormat('ru-RU', {
        notation: 'compact',
        maximumFractionDigits: 1
      }).format(numericValue);
    case 'integer':
      return new Intl.NumberFormat('ru-RU', {
        maximumFractionDigits: 0
      }).format(numericValue);
    case 'currency':
      return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        maximumFractionDigits: 0
      }).format(numericValue);
    default:
      return new Intl.NumberFormat('ru-RU', {
        maximumFractionDigits: Math.abs(numericValue) >= 100 ? 0 : 2
      }).format(numericValue);
  }
}

const chartOption = computed(() => {
  if (props.content.chartType === 'pie') {
    return {
      color: palette.value,
      tooltip: {
        trigger: 'item',
        valueFormatter: (value: number) => formatValue(value, props.content.valueFormat)
      },
      legend: {
        bottom: 0,
        icon: 'circle'
      },
      series: [
        {
          type: 'pie',
          radius: ['46%', '72%'],
          itemStyle: {
            borderRadius: 10,
            borderColor: '#ffffff',
            borderWidth: 3
          },
          label: {
            formatter: ({ name, value }: { name: string; value: number }) =>
              `${name}: ${formatValue(value, props.content.valueFormat)}`
          },
          data: props.content.pieData ?? []
        }
      ]
    };
  }

  return {
    color: palette.value,
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: number) => formatValue(value, props.content.valueFormat)
    },
    legend: {
      top: 0,
      icon: 'roundRect'
    },
    grid: {
      top: 44,
      left: 20,
      right: 18,
      bottom: 24,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: props.content.xAxis ?? [],
      axisLine: {
        lineStyle: {
          color: 'rgba(15, 23, 42, 0.16)'
        }
      },
      axisLabel: {
        color: '#51607a'
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#51607a',
        formatter: (value: number) => {
          const formatted = formatValue(value, props.content.valueFormat);
          return props.content.unit ? `${formatted} ${props.content.unit}` : formatted;
        }
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(15, 23, 42, 0.08)'
        }
      }
    },
    series: (props.content.series ?? []).map((series) => ({
      ...series,
      type: props.content.chartType,
      stack: props.content.stacked ? 'total' : undefined,
      smooth: props.content.chartType === 'line',
      symbolSize: props.content.chartType === 'line' ? 9 : undefined,
      barMaxWidth: props.content.chartType === 'bar' ? 30 : undefined,
      areaStyle:
        props.content.chartType === 'line'
          ? {
              opacity: 0.08
            }
          : undefined
    }))
  };
});
</script>

<style scoped lang="scss">
.chart-cell__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.55rem;
}

.chart-cell__head strong {
  display: block;
  font-size: 0.9rem;
  color: var(--ink);
}

.chart-cell__head p {
  margin: 0.2rem 0 0;
  color: var(--muted);
  font-size: 0.78rem;
}

.chart-cell__pill {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(36, 107, 255, 0.18);
  background: rgba(36, 107, 255, 0.08);
  color: var(--ink);
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
}

.chart-cell__plot {
  width: 100%;
  height: 280px;
  padding: 0.5rem;
  background: var(--canvas);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.chart-cell__metric {
  display: grid;
  place-items: center;
  min-height: 280px;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background:
    radial-gradient(circle at top, rgba(36, 107, 255, 0.08), transparent 42%),
    var(--canvas);
  text-align: center;
}

.chart-cell__metric-value {
  font-size: clamp(2.6rem, 8vw, 4.2rem);
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--ink);
  line-height: 1;
}

.chart-cell__metric-label {
  margin-top: 0.4rem;
  font-size: 0.92rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.chart-cell__metric-note {
  max-width: 26rem;
  margin: 0.9rem auto 0;
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.45;
}

@media (max-width: 760px) {
  .chart-cell__plot {
    height: 220px;
  }

  .chart-cell__metric {
    min-height: 220px;
  }
}
</style>
