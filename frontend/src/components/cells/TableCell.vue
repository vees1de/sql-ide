<template>
  <div class="table-cell">
    <div class="table-cell__wrap">
      <table>
        <thead>
          <tr>
            <th
              v-for="column in content.columns"
              :key="column"
            >
              {{ column }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, rowIndex) in content.rows"
            :key="rowIndex"
          >
            <td
              v-for="column in content.columns"
              :key="column"
            >
              {{ formatValue(row[column]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p
      v-if="content.footnote"
      class="table-cell__footnote"
    >
      {{ content.footnote }}
    </p>
  </div>
</template>

<script setup lang="ts">
import type { TableCellContent } from '@/types/app';

defineProps<{
  content: TableCellContent;
}>();

function formatValue(value: string | number | undefined) {
  if (typeof value === 'number') {
    return Number.isInteger(value)
      ? value.toLocaleString('en-US')
      : value.toLocaleString('en-US', {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1
        });
  }

  return value ?? '—';
}
</script>

<style scoped lang="scss">
.table-cell__wrap {
  overflow-x: auto;
  border-radius: var(--radius);
  border: 1px solid var(--line);
  background: var(--canvas);
}

table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-mono);
}

th,
td {
  padding: 0.55rem 0.7rem;
  text-align: left;
}

th {
  color: var(--muted);
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid var(--line);
}

td {
  border-top: 1px solid var(--line);
  font-size: 0.82rem;
  color: var(--ink);
}

tr:hover td {
  background: rgba(255, 255, 255, 0.02);
}

.table-cell__footnote {
  margin: 0.55rem 0 0;
  color: var(--muted);
  font-size: 0.78rem;
}
</style>
