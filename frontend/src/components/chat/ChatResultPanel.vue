<template>
  <section class="chat-result-panel">
    <div class="chat-result-panel__toolbar">
      <div class="chat-result-panel__tabs">
        <button
          class="chat-result-panel__tab"
          :class="{ 'chat-result-panel__tab--active': view === 'table' }"
          type="button"
          @click="$emit('change-view', 'table')"
        >
          Таблица
        </button>
        <button
          class="chat-result-panel__tab"
          :class="{ 'chat-result-panel__tab--active': view === 'chart' }"
          type="button"
          @click="$emit('change-view', 'chart')"
        >
          График
        </button>
      </div>

      <div v-if="execution" class="chat-result-panel__meta">
        <span class="chat-result-panel__summary">{{ summary }}</span>
        <span v-if="execution?.dataset" class="chat-result-panel__dataset">
          dataset: {{ execution.dataset.dataset_id }}
        </span>
      </div>

      <div class="chat-result-panel__actions">
        <button
          v-if="execution && view === 'chart' && !execution.error_message"
          class="chat-result-panel__ai-suggest-btn"
          type="button"
          :disabled="chat.suggestingChart"
          :title="chat.suggestingChart ? 'ИИ думает…' : 'Предложить график с ИИ'"
          @click="requestAiSuggestion"
        >
          <svg
            v-if="!chat.suggestingChart"
            class="chat-result-panel__ai-icon"
            width="15"
            height="15"
            viewBox="0 0 15 15"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="ai-star-grad" x1="0" y1="0" x2="15" y2="15" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stop-color="#a78bfa"/>
                <stop offset="50%" stop-color="#818cf8"/>
                <stop offset="100%" stop-color="#38bdf8"/>
              </linearGradient>
            </defs>
            <!-- large center star -->
            <path d="M7.5 1 L8.3 5.5 L12.5 5.5 L9.2 8.1 L10.3 12.5 L7.5 10 L4.7 12.5 L5.8 8.1 L2.5 5.5 L6.7 5.5 Z" fill="url(#ai-star-grad)"/>
            <!-- small top-right sparkle -->
            <path d="M12 1 L12.4 2.6 L14 3 L12.4 3.4 L12 5 L11.6 3.4 L10 3 L11.6 2.6 Z" fill="url(#ai-star-grad)" opacity="0.85"/>
            <!-- small bottom-left sparkle -->
            <path d="M3 10 L3.3 11.3 L4.5 11.5 L3.3 11.7 L3 13 L2.7 11.7 L1.5 11.5 L2.7 11.3 Z" fill="url(#ai-star-grad)" opacity="0.7"/>
          </svg>
          <span v-if="chat.suggestingChart" class="chat-result-panel__ai-pulse"/>
        </button>
        <button
          v-if="execution && view === 'chart' && !execution.error_message"
          class="chat-result-panel__icon-btn"
          type="button"
          title="Настроить вручную"
          @click="showBuilder = true"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path fill-rule="evenodd" clip-rule="evenodd" d="M7 4.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5ZM5.5 7a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0Z" fill="currentColor"/>
            <path fill-rule="evenodd" clip-rule="evenodd" d="M7 1a.75.75 0 0 1 .75.75v.42a4.52 4.52 0 0 1 1.27.527l.298-.298a.75.75 0 1 1 1.06 1.06l-.297.299c.228.394.397.826.527 1.27h.42a.75.75 0 0 1 0 1.5h-.42a4.52 4.52 0 0 1-.527 1.27l.297.298a.75.75 0 1 1-1.06 1.06l-.298-.297a4.52 4.52 0 0 1-1.27.527v.42a.75.75 0 0 1-1.5 0v-.42a4.52 4.52 0 0 1-1.27-.527l-.298.297a.75.75 0 1 1-1.06-1.06l.297-.298A4.52 4.52 0 0 1 2.67 7.75H2.25a.75.75 0 0 1 0-1.5h.42c.13-.444.299-.876.527-1.27l-.297-.298a.75.75 0 1 1 1.06-1.06l.298.298A4.52 4.52 0 0 1 5.528 3.17V2.75A.75.75 0 0 1 7 1Z" fill="currentColor"/>
          </svg>
        </button>
        <button
          v-if="execution && view === 'chart' && currentInterpretation"
          class="chat-result-panel__icon-btn"
          type="button"
          :title="showInterpretation ? 'Скрыть интерпретацию' : 'Показать интерпретацию'"
          @click="showInterpretation = !showInterpretation"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.2"/>
            <path d="M7 9.5V7.25C6.17 7.08 5.5 6.36 5.5 5.5a1.5 1.5 0 0 1 3 0c0 .56-.31 1.05-.77 1.31" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            <circle cx="7" cy="10.75" r="0.6" fill="currentColor"/>
          </svg>
        </button>
        <button
          v-if="execution && view === 'chart' && previewContent"
          class="chat-result-panel__toggle-btn"
          type="button"
          @click="showChartHeader = !showChartHeader"
        >
          {{ showChartHeader ? 'Скрыть заголовок' : 'Показать заголовок' }}
        </button>
        <button
          v-if="execution && !execution.error_message && sqlText"
          class="chat-result-panel__save-btn"
          type="button"
          @click="showSaveModal = true"
        >
          Сохранить график
        </button>
      </div>
    </div>

    <div v-if="execution?.error_message" class="chat-result-panel__error">
      {{ execution.error_message }}
    </div>

    <div v-else-if="execution?.analysis_message" class="chat-result-panel__analysis">
      {{ execution.analysis_message }}
    </div>

    <template v-else-if="execution">
      <ChatResultTable
        v-if="view === 'table'"
        :columns="execution.columns ?? []"
        :rows="execution.rows_preview ?? []"
        :truncated="Boolean(execution.rows_preview_truncated)"
      />

      <section v-else class="chat-result-panel__chart-view">
        <div class="chat-result-panel__section-head">
          <div>
            <strong>Визуализация</strong>
            <p>{{ visualizationLead }}</p>
          </div>

          <div v-if="sourceOptions.length" class="chat-result-panel__source-switcher">
            <button
              v-for="option in sourceOptions"
              :key="option.key"
              class="chat-result-panel__source-btn"
              :class="{ 'chat-result-panel__source-btn--active': activeSource === option.key }"
              type="button"
              @click="activeSource = option.key"
            >
              {{ option.label }}
            </button>
          </div>
        </div>

        <div v-if="showInterpretation && currentInterpretation" class="chat-result-panel__interpretation">
          <strong>Как система поняла dataset</strong>
          <p>{{ currentInterpretation.short_explanation ?? currentSubtitle }}</p>
          <div class="chat-result-panel__chips">
            <span v-if="currentInterpretation.intent">{{ currentInterpretation.intent }}</span>
            <span v-if="currentInterpretation.time_dimension">X: {{ currentInterpretation.time_dimension }}</span>
            <span v-if="currentInterpretation.series_dimension">Series: {{ currentInterpretation.series_dimension }}</span>
            <span v-if="primaryMetric">Metric: {{ primaryMetric }}</span>
          </div>
        </div>

        <ChartCell v-if="previewContent" :content="previewContent" :show-header="showChartHeader" />
        <div v-else class="chat-result-panel__empty">
          <p>{{ emptyChartMessage }}</p>
          <p class="chat-result-panel__empty-note">
            Попробуйте выбрать поля вручную или попросить ИИ предложить более подходящую визуализацию.
          </p>
        </div>
      </section>
    </template>

    <div v-else class="chat-result-panel__empty">
      Результат появится после запуска SQL.
    </div>

    <SaveReportModal
      v-if="showSaveModal && execution && sqlText"
      :execution="execution"
      :sql-text="sqlText"
      :database-connection-id="databaseConnectionId"
      :chart-spec="currentChartSpec"
      @close="showSaveModal = false"
      @saved="showSaveModal = false"
    />

    <ChartBuilderModal
      v-if="showBuilder && execution"
      :execution="execution"
      :initial-spec="currentChartSpec ?? defaultChartSpec"
      @close="showBuilder = false"
      @apply="applyManualSpec"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { ApiChatChartSpec, ApiChatExecutionRead } from '@/api/types';
import ChartCell from '@/components/cells/ChartCell.vue';
import ChartBuilderModal from '@/components/chat/ChartBuilderModal.vue';
import ChatResultTable from '@/components/chat/ChatResultTable.vue';
import SaveReportModal from '@/components/widgets/SaveReportModal.vue';
import { useChatStore } from '@/stores/chat';
import {
  buildChartCellContentFromRecommendation,
  buildChartCellContentFromSpec
} from '@/utils/chartPreview';

const props = defineProps<{
  execution: ApiChatExecutionRead | null;
  view: 'table' | 'chart';
  sqlText?: string | null;
  databaseConnectionId?: string | null;
}>();

const emit = defineEmits<{
  (event: 'change-view', value: 'table' | 'chart'): void;
}>();

const chat = useChatStore();
const showSaveModal = ref(false);
const showInterpretation = ref(false);
const showChartHeader = ref(true);
const showBuilder = ref(false);
const activeSource = ref<'heuristic' | 'ai' | 'manual'>('heuristic');
const manualChartSpec = ref<ApiChatChartSpec | null>(null);

const recommendation = computed(() => props.execution?.chart_recommendation ?? null);
const defaultChartSpec = computed(() => recommendation.value?.chart_spec ?? null);
const aiChartSpec = computed(() => recommendation.value?.ai_chart_spec ?? null);

const currentChartSpec = computed<ApiChatChartSpec | null>(() => {
  if (activeSource.value === 'manual' && manualChartSpec.value) {
    return manualChartSpec.value;
  }
  if (activeSource.value === 'ai' && aiChartSpec.value) {
    return aiChartSpec.value;
  }
  return defaultChartSpec.value;
});

const previewContent = computed(() => {
  if (!props.execution) {
    return null;
  }
  if (activeSource.value === 'manual' && manualChartSpec.value) {
    return buildChartCellContentFromSpec(manualChartSpec.value, props.execution);
  }
  if (activeSource.value === 'ai' && aiChartSpec.value) {
    return buildChartCellContentFromSpec(aiChartSpec.value, props.execution);
  }
  return buildChartCellContentFromRecommendation(recommendation.value, props.execution);
});

const currentInterpretation = computed(
  () => currentChartSpec.value?.query_interpretation ?? recommendation.value?.query_interpretation ?? null
);

const primaryMetric = computed(() => currentInterpretation.value?.metrics?.[0]?.name ?? null);

const sourceOptions = computed(() => {
  const options: Array<{ key: 'heuristic' | 'ai' | 'manual'; label: string }> = [];
  if (defaultChartSpec.value || recommendation.value) {
    options.push({ key: 'heuristic', label: 'Эвристика' });
  }
  if (aiChartSpec.value) {
    options.push({ key: 'ai', label: 'AI suggestion' });
  }
  if (manualChartSpec.value) {
    options.push({ key: 'manual', label: 'Ручная' });
  }
  return options;
});

const currentSubtitle = computed(
  () => currentChartSpec.value?.reason ?? recommendation.value?.reason ?? 'Визуализация результата'
);

const summary = computed(() => {
  if (!props.execution) {
    return '';
  }
  const columnCount = props.execution.columns?.length ?? 0;
  return `${props.execution.row_count} строк · ${columnCount} колонок · ${props.execution.execution_time_ms} мс`;
});

const visualizationLead = computed(() => {
  if (activeSource.value === 'manual') {
    return 'Текущий preview собран из вручную отредактированного ChartSpec.';
  }
  if (activeSource.value === 'ai' && aiChartSpec.value) {
    return 'AI-контур предложил альтернативную визуализацию поверх готового dataset.';
  }
  return 'Сначала строится deterministic chart по shape результата, без участия LLM.';
});

const emptyChartMessage = computed(() => {
  if (activeSource.value === 'manual') {
    return 'Текущий ручной ChartSpec не даёт корректного превью.';
  }
  if (activeSource.value === 'ai' && aiChartSpec.value?.chart_type === 'table') {
    return aiChartSpec.value.reason ?? 'ИИ посчитал, что результат лучше оставить таблицей.';
  }
  if (recommendation.value?.recommended_view !== 'chart') {
    return recommendation.value?.reason ?? 'Автоматическая визуализация не построена.';
  }
  return 'Для этого результата график не построен.';
});

async function requestAiSuggestion() {
  try {
    await chat.suggestChart('best_chart');
    activeSource.value = 'ai';
    emit('change-view', 'chart');
  } catch {
    // Store already exposes the error state.
  }
}

function applyManualSpec(spec: ApiChatChartSpec) {
  manualChartSpec.value = spec;
  activeSource.value = 'manual';
  showBuilder.value = false;
  emit('change-view', 'chart');
}

watch(
  () => props.execution?.id,
  () => {
    manualChartSpec.value = null;
    activeSource.value = 'heuristic';
    showInterpretation.value = false;
    showChartHeader.value = true;
    showBuilder.value = false;
  }
);
</script>

<style scoped lang="scss">
.chat-result-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  min-width: 0;
}

.chat-result-panel > :deep(*) {
  min-width: 0;
}

.chat-result-panel :deep(.chat-result-table) {
  min-width: 0;
}

.chat-result-panel__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.chat-result-panel__tabs {
  display: inline-flex;
  gap: 6px;
  flex-shrink: 0;
}

.chat-result-panel__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.chat-result-panel__tab {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: transparent;
  color: var(--muted);
  font-size: 0.78rem;
}

.chat-result-panel__tab--active {
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.2);
}

.chat-result-panel__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.chat-result-panel__summary,
.chat-result-panel__dataset {
  font-size: 0.72rem;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-result-panel__toggle-btn,
.chat-result-panel__save-btn,
.chat-result-panel__source-btn {
  padding: 0 10px;
  min-height: 26px;
  border-radius: 8px;
  font-size: 0.72rem;
  cursor: pointer;
  white-space: nowrap;
}

.chat-result-panel__toggle-btn {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
}

.chat-result-panel__toggle-btn:hover,
.chat-result-panel__source-btn:hover {
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.5);
  background: rgba(112, 59, 247, 0.12);
}

.chat-result-panel__icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.chat-result-panel__icon-btn:hover {
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.5);
  background: rgba(112, 59, 247, 0.12);
}

.chat-result-panel__ai-suggest-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, transform 0.1s;
  position: relative;
}

.chat-result-panel__ai-suggest-btn:hover {
  background: rgba(129, 140, 248, 0.12);
  border-color: rgba(129, 140, 248, 0.4);
  transform: scale(1.1);
}

.chat-result-panel__ai-suggest-btn:disabled {
  cursor: default;
  opacity: 0.6;
  transform: none;
}

.chat-result-panel__ai-icon {
  display: block;
  filter: drop-shadow(0 0 3px rgba(167, 139, 250, 0.5));
  transition: filter 0.15s;
}

.chat-result-panel__ai-suggest-btn:hover .chat-result-panel__ai-icon {
  filter: drop-shadow(0 0 6px rgba(56, 189, 248, 0.6));
}

.chat-result-panel__ai-pulse {
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #a78bfa, #38bdf8);
  animation: ai-pulse 0.9s ease-in-out infinite alternate;
}

@keyframes ai-pulse {
  from { transform: scale(0.7); opacity: 0.5; }
  to   { transform: scale(1.2); opacity: 1; }
}

.chat-result-panel__save-btn {
  border: 1px solid rgba(112, 59, 247, 0.6);
  background: rgba(112, 59, 247, 0.12);
  color: rgba(180, 140, 255, 1);
}

.chat-result-panel__chart-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  overflow: auto;
}

.chat-result-panel__section-head {
  display: none;
}

.chat-result-panel__section-head strong {
  display: block;
  color: var(--ink-strong);
  font-size: 0.88rem;
}

.chat-result-panel__section-head p {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 0.76rem;
}

.chat-result-panel__source-switcher {
  display: inline-flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chat-result-panel__source-btn {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
}

.chat-result-panel__source-btn--active {
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.7);
  background: rgba(112, 59, 247, 0.16);
}

.chat-result-panel__interpretation {
  padding: 0.9rem 1rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: rgba(15, 23, 42, 0.03);
}

.chat-result-panel__interpretation strong {
  display: block;
  margin-bottom: 0.3rem;
  font-size: 0.88rem;
  color: var(--ink);
}

.chat-result-panel__interpretation p {
  margin: 0;
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.45;
}

.chat-result-panel__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0.6rem 0 0.2rem;
}

.chat-result-panel__chips span {
  display: inline-flex;
  align-items: center;
  padding: 0.28rem 0.55rem;
  border-radius: 999px;
  background: rgba(36, 107, 255, 0.08);
  color: var(--ink);
  font-size: 0.72rem;
  font-weight: 600;
}

.chat-result-panel__empty,
.chat-result-panel__error {
  border: 1px dashed var(--line);
  border-radius: var(--radius-lg);
  padding: 12px;
  color: var(--muted);
  font-size: 0.82rem;
  display: grid;
  align-content: center;
}

.chat-result-panel__empty-note {
  margin-top: 6px;
  font-size: 0.76rem;
}

.chat-result-panel__error {
  border-style: solid;
  border-color: rgba(255, 107, 107, 0.6);
  background: rgba(255, 107, 107, 0.12);
  color: #ffb3b3;
}
</style>
