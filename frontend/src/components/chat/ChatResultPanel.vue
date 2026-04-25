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

      <div class="chat-result-panel__actions">
        <span v-if="execution" class="chat-result-panel__summary">{{
          summary
        }}</span>
        <div v-if="execution && !execution.error_message" class="chat-result-panel__feedback">
          <button
            class="chat-result-panel__feedback-btn"
            :class="{ 'chat-result-panel__feedback-btn--active': feedbackSent === 'good' }"
            type="button"
            title="Хороший результат"
            @click="sendFeedback('good')"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 7.5h1.8V12H2V7.5ZM4.8 7 7.2 2c.9 0 1.6.7 1.6 1.6V5h2.8c.6 0 1 .5.9 1.1L11.8 10c-.1.5-.6.9-1.1.9H4.8V7Z" fill="currentColor"/>
            </svg>
          </button>
          <button
            class="chat-result-panel__feedback-btn chat-result-panel__feedback-btn--bad"
            :class="{ 'chat-result-panel__feedback-btn--active': feedbackSent === 'bad' }"
            type="button"
            title="Плохой результат"
            @click="sendFeedback('bad')"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M12 6.5h-1.8V2H12v4.5ZM9.2 7 6.8 12c-.9 0-1.6-.7-1.6-1.6V9H2.4C1.8 9 1.4 8.5 1.5 7.9L2.2 4c.1-.5.6-.9 1.1-.9h5.9V7Z" fill="currentColor"/>
            </svg>
          </button>
        </div>
        <button
          v-if="execution && view === 'chart' && !execution.error_message"
          class="chat-result-panel__toggle-btn"
          type="button"
          :disabled="chat.suggestingChart"
          @click="requestAiSuggestion"
        >
          {{ chat.suggestingChart ? "ИИ думает…" : "Предложить график с ИИ" }}
        </button>
        <button
          v-if="execution && view === 'chart' && !execution.error_message"
          class="chat-result-panel__toggle-btn"
          type="button"
          @click="showBuilder = true"
        >
          Настроить вручную
        </button>
        <button
          v-if="execution && view === 'chart' && currentInterpretation"
          class="chat-result-panel__toggle-btn"
          type="button"
          @click="showInterpretation = !showInterpretation"
        >
          {{
            showInterpretation
              ? "Скрыть интерпретацию"
              : "Показать интерпретацию"
          }}
        </button>
        <button
          v-if="execution && view === 'chart' && previewContent"
          class="chat-result-panel__toggle-btn"
          type="button"
          @click="showChartHeader = !showChartHeader"
        >
          {{ showChartHeader ? "Скрыть заголовок" : "Показать заголовок" }}
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

    <template v-else-if="execution">
      <ChatResultTable
        v-if="view === 'table'"
        :columns="execution.columns ?? []"
        :rows="execution.rows_preview ?? []"
        :truncated="Boolean(execution.rows_preview_truncated)"
      />

      <section v-else class="chat-result-panel__chart-view">
        <div
          v-if="showInterpretation && currentInterpretation"
          class="chat-result-panel__interpretation"
        >
          <strong>Как система поняла dataset</strong>
          <p>
            {{ currentInterpretation.short_explanation ?? currentSubtitle }}
          </p>
          <div class="chat-result-panel__chips">
            <span v-if="currentInterpretation.intent">{{
              currentInterpretation.intent
            }}</span>
            <span v-if="currentInterpretation.time_dimension"
              >X: {{ currentInterpretation.time_dimension }}</span
            >
            <span v-if="currentInterpretation.series_dimension"
              >Series: {{ currentInterpretation.series_dimension }}</span
            >
            <span v-if="primaryMetric">Metric: {{ primaryMetric }}</span>
          </div>
        </div>

        <ChartCell
          v-if="previewContent"
          :content="previewContent"
          :show-header="showChartHeader"
        />
        <div v-else class="chat-result-panel__empty">
          <p>{{ emptyChartMessage }}</p>
          <p class="chat-result-panel__empty-note">
            Попробуйте выбрать поля вручную или попросить ИИ предложить более
            подходящую визуализацию.
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
import { computed, ref, watch } from "vue";
import type { ApiChatChartSpec, ApiChatExecutionRead } from "@/api/types";
import ChartCell from "@/components/cells/ChartCell.vue";
import ChartBuilderModal from "@/components/chat/ChartBuilderModal.vue";
import ChatResultTable from "@/components/chat/ChatResultTable.vue";
import SaveReportModal from "@/components/widgets/SaveReportModal.vue";
import { useChatStore } from "@/stores/chat";
import { chatApi } from "@/api/chat";
import {
  buildChartCellContentFromRecommendation,
  buildChartCellContentFromSpec,
} from "@/utils/chartPreview";

const props = defineProps<{
  execution: ApiChatExecutionRead | null;
  view: "table" | "chart";
  sqlText?: string | null;
  databaseConnectionId?: string | null;
  sessionId?: string | null;
}>();

const emit = defineEmits<{
  (event: "change-view", value: "table" | "chart"): void;
}>();

const chat = useChatStore();
const showSaveModal = ref(false);
const feedbackSent = ref<'good' | 'bad' | null>(null);

async function sendFeedback(value: 'good' | 'bad') {
  if (!props.execution || !props.sessionId) return;
  feedbackSent.value = value;
  try {
    await chatApi.sendFeedback(props.sessionId, props.execution.id, value);
  } catch {
    feedbackSent.value = null;
  }
}
const showInterpretation = ref(false);
const showChartHeader = ref(true);
const showBuilder = ref(false);
const activeSource = ref<"heuristic" | "ai" | "manual">("heuristic");
const manualChartSpec = ref<ApiChatChartSpec | null>(null);

const recommendation = computed(
  () => props.execution?.chart_recommendation ?? null,
);
const defaultChartSpec = computed(
  () => recommendation.value?.chart_spec ?? null,
);
const aiChartSpec = computed(() => recommendation.value?.ai_chart_spec ?? null);

const currentChartSpec = computed<ApiChatChartSpec | null>(() => {
  if (activeSource.value === "manual" && manualChartSpec.value) {
    return manualChartSpec.value;
  }
  if (activeSource.value === "ai" && aiChartSpec.value) {
    return aiChartSpec.value;
  }
  return defaultChartSpec.value;
});

const previewContent = computed(() => {
  if (!props.execution) {
    return null;
  }
  if (activeSource.value === "manual" && manualChartSpec.value) {
    return buildChartCellContentFromSpec(
      manualChartSpec.value,
      props.execution,
    );
  }
  if (activeSource.value === "ai" && aiChartSpec.value) {
    return buildChartCellContentFromSpec(aiChartSpec.value, props.execution);
  }
  return buildChartCellContentFromRecommendation(
    recommendation.value,
    props.execution,
  );
});

const currentInterpretation = computed(
  () =>
    currentChartSpec.value?.query_interpretation ??
    recommendation.value?.query_interpretation ??
    null,
);

const primaryMetric = computed(
  () => currentInterpretation.value?.metrics?.[0]?.name ?? null,
);

const currentSubtitle = computed(
  () =>
    currentChartSpec.value?.reason ??
    recommendation.value?.reason ??
    "Визуализация результата",
);

const summary = computed(() => {
  if (!props.execution) {
    return "";
  }
  const columnCount = props.execution.columns?.length ?? 0;
  return `${props.execution.row_count} строк · ${columnCount} колонок · ${props.execution.execution_time_ms} мс`;
});

const emptyChartMessage = computed(() => {
  if (activeSource.value === "manual") {
    return "Текущий ручной ChartSpec не даёт корректного превью.";
  }
  if (
    activeSource.value === "ai" &&
    aiChartSpec.value?.chart_type === "table"
  ) {
    return (
      aiChartSpec.value.reason ??
      "ИИ посчитал, что результат лучше оставить таблицей."
    );
  }
  if (recommendation.value?.recommended_view !== "chart") {
    return (
      recommendation.value?.reason ??
      "Автоматическая визуализация не построена."
    );
  }
  return "Для этого результата график не построен.";
});

async function requestAiSuggestion() {
  try {
    await chat.suggestChart("best_chart");
    activeSource.value = "ai";
    emit("change-view", "chart");
  } catch {
    // Store already exposes the error state.
  }
}

function applyManualSpec(spec: ApiChatChartSpec) {
  manualChartSpec.value = spec;
  activeSource.value = "manual";
  showBuilder.value = false;
  emit("change-view", "chart");
}

watch(
  () => props.execution?.id,
  () => {
    manualChartSpec.value = null;
    activeSource.value = "heuristic";
    showInterpretation.value = false;
    showChartHeader.value = true;
    showBuilder.value = false;
    feedbackSent.value = null;
  },
);
</script>

<style scoped lang="scss">
.chat-result-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  min-width: 0;
  color: var(--canvas);
}

.chat-result-panel > :deep(*) {
  min-width: 0;
}

.chat-result-panel :deep(.chat-result-table) {
  flex: 1 1 auto;
  min-height: 0;
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
}

.chat-result-panel__toggle-btn,
.chat-result-panel__save-btn {
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

.chat-result-panel__toggle-btn:hover {
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.5);
  background: rgba(112, 59, 247, 0.12);
}

.chat-result-panel__save-btn {
  border: 1px solid rgba(112, 59, 247, 0.6);
  background: rgba(112, 59, 247, 0.12);
  color: #262626;
}

.chat-result-panel__chart-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
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

.chat-result-panel__feedback {
  display: inline-flex;
  gap: 4px;
}

.chat-result-panel__feedback-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: color 140ms ease, border-color 140ms ease, background 140ms ease;

  &:hover {
    color: var(--ink-strong);
    border-color: rgba(112, 59, 247, 0.45);
    background: rgba(112, 59, 247, 0.1);
  }

  &--active {
    color: #a0f0a0;
    border-color: rgba(80, 200, 80, 0.6);
    background: rgba(80, 200, 80, 0.12);
  }

  &--bad.chat-result-panel__feedback-btn--active {
    color: #ffb3b3;
    border-color: rgba(255, 80, 80, 0.6);
    background: rgba(255, 80, 80, 0.12);
  }
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
