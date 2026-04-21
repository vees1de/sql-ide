<template>
  <div class="sql-cell">
    <div v-if="content.warnings?.length" class="sql-cell__warnings">
      <span
        v-for="warning in content.warnings"
        :key="warning"
        class="pill pill--ghost"
      >
        {{ warning }}
      </span>
    </div>

    <pre v-if="!collapsed"><code v-html="highlightedSql"></code></pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { SqlCellContent } from '@/types/app';

const props = defineProps<{
  content: SqlCellContent;
  collapsed?: boolean;
}>();

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

const highlightedSql = computed(() => {
  const escaped = escapeHtml(props.content.sql ?? '');
  return escaped
    .replace(
      /\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|WITH|AS|LEFT JOIN|RIGHT JOIN|INNER JOIN|FULL JOIN|JOIN|ON|AND|OR|CASE|WHEN|THEN|ELSE|END|UNION|ALL|DESC|ASC)\b/gi,
      '<span class="sql-keyword">$1</span>'
    )
    .replace(/('[^']*')/g, '<span class="sql-string">$1</span>')
    .replace(/\b(\d+(\.\d+)?)\b/g, '<span class="sql-number">$1</span>');
});
</script>

<style scoped lang="scss">
.sql-cell__toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.7rem;
  margin-bottom: 0.55rem;
}

.sql-cell__toolbar p {
  margin: 0;
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1.5;
}

.sql-cell__warnings {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 0.55rem;
}

pre {
  margin: 0;
  padding: 0.75rem 0.9rem;
  overflow-x: auto;
  border-radius: var(--radius);
  background: var(--canvas);
  border: 1px solid var(--line);
  color: #d7dfe9;
  font-family: var(--font-mono);
  font-size: 0.82rem;
  line-height: 1.6;
}

:deep(.sql-keyword) {
  color: #fbbc04;
  font-weight: 700;
}

:deep(.sql-string) {
  color: #81c995;
}

:deep(.sql-number) {
  color: #8ab4f8;
}

</style>
