<template>
  <div class="chat-result-table">
    <div class="chat-result-table__wrap">
      <div class="chat-result-table__track">
        <div class="chat-result-table__header">
          <div
            v-for="column in columns"
            :key="column.name"
            class="chat-result-table__cell chat-result-table__cell--head"
          >
            <span>{{ column.name }}</span>
            <small>{{ column.type }}</small>
          </div>
        </div>

        <div class="chat-result-table__body">
          <div v-for="(row, rowIndex) in rows" :key="rowIndex" class="chat-result-table__row">
            <div v-for="column in columns" :key="column.name" class="chat-result-table__cell">
              {{ formatValue(row[column.name]) }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <p v-if="truncated" class="chat-result-table__note">
      Показан только предпросмотр. Полный результат может быть больше.
    </p>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  columns: Array<{ name: string; type: string }>;
  rows: Array<Record<string, unknown>>;
  truncated: boolean;
}>();

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'number') {
    return Number.isInteger(value)
      ? value.toLocaleString('ru-RU')
      : value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
      return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' }).format(parsed);
    }
  }
  return String(value);
}
</script>

<style scoped lang="scss">
.chat-result-table {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.chat-result-table__wrap {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
  width: 100%;
  max-width: 100%;
  overflow: auto;
  border-radius: var(--radius-lg);
  border: 1px solid var(--line);
  background: var(--canvas);
}

.chat-result-table__track {
  display: inline-flex;
  flex-direction: column;
  min-width: 100%;
  width: max-content;
}

.chat-result-table__header,
.chat-result-table__row {
  display: flex;
  width: 100%;
  font-family: var(--font-mono);
}

.chat-result-table__body {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.chat-result-table__cell {
  flex: 0 0 180px;
  width: 180px;
  padding: 0.6rem 0.75rem;
  text-align: left;
  border-top: 1px solid var(--line);
  color: var(--ink);
  font-size: 0.8rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-result-table__cell--head {
  border-top: 0;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
}

.chat-result-table__cell--head span {
  display: block;
  color: var(--ink);
  font-size: 0.75rem;
}

.chat-result-table__cell--head small {
  color: var(--muted);
  font-size: 0.68rem;
  font-weight: 600;
}

.chat-result-table__row:hover .chat-result-table__cell {
  background: rgba(255, 255, 255, 0.02);
}

.chat-result-table__note {
  margin: 0.55rem 0 0;
  color: var(--muted);
  font-size: 0.78rem;
}
</style>
