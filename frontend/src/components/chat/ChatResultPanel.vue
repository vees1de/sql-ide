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
        <span v-if="execution" class="chat-result-panel__summary">{{ summary }}</span>
        <button
          v-if="execution && view === 'chart'"
          class="chat-result-panel__toggle-btn"
          type="button"
          @click="showInterpretation = !showInterpretation"
        >
          {{ showInterpretation ? 'Скрыть интерпретацию' : 'Показать интерпретацию' }}
        </button>
        <button
          v-if="execution && view === 'chart'"
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
          title="Сохранить как виджет"
          @click="showSaveModal = true"
        >
          Сохранить отчёт
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
      <ChatResultChart
        v-else
        :execution="execution"
        :show-interpretation="showInterpretation"
        :show-chart-header="showChartHeader"
      />
    </template>

    <div v-else class="chat-result-panel__empty">
      Результат появится после запуска SQL.
    </div>

    <SaveReportModal
      v-if="showSaveModal && execution && sqlText"
      :execution="execution"
      :sql-text="sqlText"
      :database-connection-id="databaseConnectionId"
      @close="showSaveModal = false"
      @saved="onSaved"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import ChatResultChart from '@/components/chat/ChatResultChart.vue';
import ChatResultTable from '@/components/chat/ChatResultTable.vue';
import SaveReportModal from '@/components/widgets/SaveReportModal.vue';
import type { ApiChatExecutionRead } from '@/api/types';

const props = defineProps<{
  execution: ApiChatExecutionRead | null;
  view: 'table' | 'chart';
  sqlText?: string | null;
  databaseConnectionId?: string | null;
}>();

defineEmits<{
  (event: 'change-view', value: 'table' | 'chart'): void;
}>();

const showSaveModal = ref(false);
const showInterpretation = ref(false);
const showChartHeader = ref(false);

const summary = computed(() => {
  if (!props.execution) {
    return '';
  }
  const columnCount = props.execution.columns?.length ?? 0;
  return `${props.execution.row_count} строк · ${columnCount} колонок · ${props.execution.execution_time_ms} мс`;
});

function onSaved(widgetId: string) {
  showSaveModal.value = false;
}

watch(
  () => props.execution?.id,
  () => {
    showInterpretation.value = false;
    showChartHeader.value = false;
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

.chat-result-panel__tab:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.chat-result-panel__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.chat-result-panel__summary {
  font-size: 0.72rem;
  color: var(--muted);
}

.chat-result-panel__save-btn {
  padding: 0 10px;
  min-height: 26px;
  border: 1px solid rgba(112, 59, 247, 0.6);
  border-radius: 8px;
  background: rgba(112, 59, 247, 0.12);
  color: rgba(180, 140, 255, 1);
  font-size: 0.72rem;
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    background: rgba(112, 59, 247, 0.22);
  }
}

.chat-result-panel__toggle-btn {
  padding: 0 10px;
  min-height: 26px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font-size: 0.72rem;
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    color: var(--ink-strong);
    border-color: rgba(112, 59, 247, 0.5);
    background: rgba(112, 59, 247, 0.12);
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

.chat-result-panel__error {
  border-style: solid;
  border-color: rgba(255, 107, 107, 0.6);
  background: rgba(255, 107, 107, 0.12);
  color: #ffb3b3;
}
</style>
