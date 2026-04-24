<template>
  <div class="chat-result-table">
    <div class="chat-result-table__wrap">
      <table>
        <thead>
          <tr>
            <th v-for="column in columns" :key="column.name">
              <span>{{ column.name }}</span>
              <small>{{ column.type }}</small>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, rowIndex) in rows" :key="rowIndex">
            <td v-for="column in columns" :key="column.name">
              {{ formatValue(row[column.name]) }}
            </td>
          </tr>
        </tbody>
      </table>
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
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  height: 100%;
  width: 100%;
  max-width: 100%;
  overflow: hidden;
}

.chat-result-table__wrap {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: auto;
  border-radius: var(--radius-lg);
  border: 1px solid var(--line);
  background: var(--canvas);
}

table {
  min-width: 100%;
  width: max-content;
  border-collapse: collapse;
  font-family: var(--font-mono);
}

th,
td {
  white-space: nowrap;
  min-width: 140px;
}

th,
td {
  padding: 0.6rem 0.75rem;
  text-align: left;
  vertical-align: top;
}

th {
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
}

th span {
  display: block;
  color: var(--ink);
  font-size: 0.75rem;
}

th small {
  color: var(--muted);
  font-size: 0.68rem;
  font-weight: 600;
}

td {
  border-top: 1px solid var(--line);
  color: var(--ink);
  font-size: 0.8rem;
}

tr:hover td {
  background: rgba(255, 255, 255, 0.02);
}

.chat-result-table__note {
  margin: 0.55rem 0 0;
  color: var(--muted);
  font-size: 0.78rem;
}
</style>
