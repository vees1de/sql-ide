<template>
  <div class="chat-result-table">
    <div class="chat-result-table__wrap">
      <table>
        <thead>
          <tr>
            <th v-for="column in columns" :key="column.name">
              <button
                class="chat-result-table__sort-btn"
                type="button"
                :aria-label="sortAriaLabel(column.name)"
                @click="toggleSort(column.name)"
              >
                <span>{{ column.name }}</span>
                <small>{{ column.type }}</small>
                <strong
                  class="chat-result-table__sort-indicator"
                  :class="{
                    'chat-result-table__sort-indicator--active':
                      sortColumn === column.name,
                  }"
                  aria-hidden="true"
                >
                  {{
                    sortColumn === column.name
                      ? sortDirection === 'asc'
                        ? '↑'
                        : '↓'
                      : '↕'
                  }}
                </strong>
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, rowIndex) in sortedRows" :key="rowIndex">
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
import { computed, ref, watch } from 'vue';

const props = defineProps<{
  columns: Array<{ name: string; type: string }>;
  rows: Array<Record<string, unknown>>;
  truncated: boolean;
}>();

const sortColumn = ref<string | null>(null);
const sortDirection = ref<'asc' | 'desc'>('asc');

const sortedRows = computed(() => {
  if (!sortColumn.value) {
    return props.rows;
  }

  const columnName = sortColumn.value;
  const direction = sortDirection.value === 'asc' ? 1 : -1;

  return [...props.rows].sort((leftRow, rightRow) => {
    const left = normalizeSortValue(leftRow[columnName]);
    const right = normalizeSortValue(rightRow[columnName]);

    if (left.rank !== right.rank) {
      return (left.rank - right.rank) * direction;
    }

    if (left.value < right.value) {
      return -1 * direction;
    }
    if (left.value > right.value) {
      return 1 * direction;
    }
    return 0;
  });
});

watch(
  () => [props.columns, props.rows],
  () => {
    sortColumn.value = null;
    sortDirection.value = 'asc';
  }
);

function toggleSort(columnName: string) {
  if (sortColumn.value !== columnName) {
    sortColumn.value = columnName;
    sortDirection.value = 'asc';
    return;
  }

  sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
}

function sortAriaLabel(columnName: string) {
  if (sortColumn.value !== columnName) {
    return `Сортировать по колонке ${columnName} по возрастанию`;
  }

  return sortDirection.value === 'asc'
    ? `Сейчас сортировка по колонке ${columnName} по возрастанию. Нажмите для сортировки по убыванию`
    : `Сейчас сортировка по колонке ${columnName} по убыванию. Нажмите для сортировки по возрастанию`;
}

function normalizeSortValue(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return { rank: 2, value: '' };
  }

  if (typeof value === 'number') {
    return { rank: 0, value };
  }

  if (typeof value === 'boolean') {
    return { rank: 0, value: Number(value) };
  }

  if (value instanceof Date) {
    return { rank: 0, value: value.getTime() };
  }

  if (typeof value === 'string') {
    const trimmed = value.trim();
    const numeric = Number(trimmed);
    if (trimmed && Number.isFinite(numeric)) {
      return { rank: 0, value: numeric };
    }

    const timestamp = Date.parse(trimmed);
    if (!Number.isNaN(timestamp) && /^\d{4}-\d{2}-\d{2}/.test(trimmed)) {
      return { rank: 0, value: timestamp };
    }

    return { rank: 1, value: trimmed.toLocaleLowerCase('ru-RU') };
  }

  return { rank: 1, value: String(value).toLocaleLowerCase('ru-RU') };
}

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

.chat-result-table__sort-btn {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas:
    "name indicator"
    "type indicator";
  gap: 2px 8px;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  color: inherit;
  cursor: pointer;
}

.chat-result-table__sort-btn span {
  grid-area: name;
  display: block;
  color: var(--ink);
  font-size: 0.75rem;
}

.chat-result-table__sort-btn small {
  grid-area: type;
  color: var(--muted);
  font-size: 0.68rem;
  font-weight: 600;
}

.chat-result-table__sort-indicator {
  grid-area: indicator;
  align-self: center;
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1;
  transition: color 160ms ease;
}

.chat-result-table__sort-indicator--active,
.chat-result-table__sort-btn:hover .chat-result-table__sort-indicator,
.chat-result-table__sort-btn:focus-visible .chat-result-table__sort-indicator {
  color: var(--ink);
}

.chat-result-table__sort-btn:focus-visible {
  outline: 2px solid rgba(255, 255, 255, 0.18);
  outline-offset: 3px;
  border-radius: 8px;
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
