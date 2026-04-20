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
          :disabled="execution?.chart_recommendation?.recommended_view !== 'chart'"
          @click="$emit('change-view', 'chart')"
        >
          График
        </button>
      </div>

      <span v-if="execution" class="chat-result-panel__summary">{{ summary }}</span>
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
      />
    </template>

    <div v-else class="chat-result-panel__empty">
      Результат появится после запуска SQL.
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import ChatResultChart from '@/components/chat/ChatResultChart.vue';
import ChatResultTable from '@/components/chat/ChatResultTable.vue';
import type { ApiChatExecutionRead } from '@/api/types';

const props = defineProps<{
  execution: ApiChatExecutionRead | null;
  view: 'table' | 'chart';
}>();

defineEmits<{
  (event: 'change-view', value: 'table' | 'chart'): void;
}>();

const summary = computed(() => {
  if (!props.execution) {
    return '';
  }
  const columnCount = props.execution.columns?.length ?? 0;
  return `${props.execution.row_count} строк · ${columnCount} колонок · ${props.execution.execution_time_ms} ms`;
});
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

.chat-result-panel__summary {
  font-size: 0.72rem;
  color: var(--muted);
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
