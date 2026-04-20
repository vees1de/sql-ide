<template>
  <section class="chat-result-panel">
    <header class="chat-result-panel__head">
      <div>
        <p class="eyebrow">Результат</p>
        <h2>Таблица или график</h2>
      </div>
      <div class="chat-result-panel__meta">
        <span v-if="execution" class="pill pill--ghost">{{ summary }}</span>
        <span v-if="execution?.rows_preview_truncated" class="pill pill--accent">Предпросмотр</span>
      </div>
    </header>

    <div v-if="execution?.error_message" class="chat-result-panel__error">
      <p class="chat-result-panel__error-title">Ошибка выполнения</p>
      <p class="chat-result-panel__error-body">{{ execution.error_message }}</p>
    </div>

    <template v-else-if="execution">
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
          :disabled="execution.chart_recommendation?.recommended_view !== 'chart'"
          @click="$emit('change-view', 'chart')"
        >
          График
        </button>
      </div>

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
      <p>Запустите SQL вручную, чтобы увидеть результат здесь.</p>
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
  return `${props.execution.row_count} строк, ${columnCount} колонок, ${props.execution.execution_time_ms} ms`;
});
</script>

<style scoped lang="scss">
.chat-result-panel {
  display: grid;
  gap: 0.85rem;
  min-height: 0;
}

.chat-result-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.chat-result-panel__head h2 {
  margin: 0.3rem 0 0;
  font-size: 1.05rem;
}

.chat-result-panel__meta,
.chat-result-panel__tabs {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.chat-result-panel__tabs {
  padding: 0.18rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.02);
}

.chat-result-panel__tab {
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.42rem 0.78rem;
}

.chat-result-panel__tab--active {
  color: var(--ink-strong);
  background: rgba(249, 171, 0, 0.14);
}

.chat-result-panel__tab:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.chat-result-panel__empty,
.chat-result-panel__error {
  display: grid;
  gap: 0.35rem;
  padding: 0.95rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.02);
}

.chat-result-panel__error {
  border-color: rgba(242, 139, 130, 0.35);
  background: rgba(242, 139, 130, 0.08);
}

.chat-result-panel__error-title {
  margin: 0;
  color: var(--danger);
  font-size: 0.84rem;
  font-weight: 700;
}

.chat-result-panel__error-body,
.chat-result-panel__empty p {
  margin: 0;
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1.55;
}
</style>

