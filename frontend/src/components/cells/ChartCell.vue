<template>
  <div class="chart-cell">
    <div class="chart-cell__head">
      <div>
        <strong>{{ content.title }}</strong>
        <p>{{ content.subtitle }}</p>
      </div>
    </div>

    <VChart
      class="chart-cell__plot"
      :option="chartOption"
      autoresize
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import VChart from 'vue-echarts';
import type { ChartCellContent } from '@/types/app';

const props = defineProps<{
  content: ChartCellContent;
}>();

const palette = computed(
  () => props.content.palette ?? ['#246bff', '#0f766e', '#f59e0b']
);

const chartOption = computed(() => {
  if (props.content.chartType === 'pie') {
    return {
      color: palette.value,
      tooltip: {
        trigger: 'item'
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
            formatter: '{b}: {d}%'
          },
          data: props.content.pieData ?? []
        }
      ]
    };
  }

  return {
    color: palette.value,
    tooltip: {
      trigger: 'axis'
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
        formatter: props.content.unit ? `{value} ${props.content.unit}` : '{value}'
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

.chart-cell__plot {
  width: 100%;
  height: 280px;
  padding: 0.5rem;
  background: var(--canvas);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

@media (max-width: 760px) {
  .chart-cell__plot {
    height: 220px;
  }
}
</style>
