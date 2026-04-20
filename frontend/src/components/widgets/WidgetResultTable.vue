<template>
  <div class="widget-table">
    <div class="widget-table__scroll">
      <table class="widget-table__table">
        <thead>
          <tr>
            <th v-for="col in columns" :key="col.name" class="widget-table__th">{{ col.name }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in rows" :key="i" class="widget-table__tr">
            <td v-for="col in columns" :key="col.name" class="widget-table__td">
              {{ formatCell(row[col.name]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="truncated" class="widget-table__truncated">Показаны первые {{ rows.length }} строк</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  columns: Array<{ name: string; type: string }>;
  rows: Array<Record<string, unknown>>;
  truncated: boolean;
}>();

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '';
  return String(value);
}
</script>

<style scoped lang="scss">
.widget-table {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
  overflow: hidden;
}

.widget-table__scroll {
  overflow: auto;
  max-height: 400px;
}

.widget-table__table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.8rem;
}

.widget-table__th {
  background: var(--bg);
  color: var(--muted);
  font-weight: 600;
  font-size: 0.72rem;
  text-align: left;
  padding: 6px 10px;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
  position: sticky;
  top: 0;
}

.widget-table__tr:hover td { background: rgba(255,255,255,0.03); }

.widget-table__td {
  padding: 5px 10px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  color: var(--ink);
  white-space: nowrap;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.widget-table__truncated {
  font-size: 0.72rem;
  color: var(--muted);
  margin: 0;
}
</style>
