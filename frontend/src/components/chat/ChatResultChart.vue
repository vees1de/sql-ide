<template>
  <div class="chat-result-chart">
    <div v-if="showInterpretation && interpretation" class="chat-result-chart__interpretation">
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
      <ChartCell :content="content" :show-header="showChartHeader" />
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
import { buildChartCellContentFromRecommendation } from '@/utils/chartPreview';

const props = defineProps<{
  execution: ApiChatExecutionRead | null;
  showInterpretation?: boolean;
  showChartHeader?: boolean;
}>();

const recommendation = computed(() => props.execution?.chart_recommendation ?? null);

const interpretation = computed(() => recommendation.value?.query_interpretation ?? null);

const primaryMetric = computed(() => interpretation.value?.metrics?.[0]?.name ?? null);

const recommendationReason = computed(() => recommendation.value?.reason ?? 'Рекомендованная визуализация');

const content = computed<ChartCellContent | null>(() => {
  return buildChartCellContentFromRecommendation(recommendation.value, props.execution);
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
