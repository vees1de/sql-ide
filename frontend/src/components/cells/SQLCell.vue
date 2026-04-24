<template>
  <div class="sql-cell">
    <div v-if="hasHeader" class="sql-cell__toolbar">
      <p v-if="content.explanation" class="sql-cell__explanation">
        {{ content.explanation }}
      </p>
      <div class="sql-cell__actions">
        <button
          v-if="showRunButton"
          class="sql-cell__run-btn"
          type="button"
          title="Запустить SQL"
          aria-label="Запустить SQL"
          @click="$emit('run')"
        >
          <v-icon name="md-playarrow" style="font-size: 13px" />
          <span>Запустить</span>
        </button>
        <button
          v-if="showToggleSqlButton"
          class="sql-cell__action-btn"
          type="button"
          :title="collapsed ? 'Показать SQL' : 'Скрыть SQL'"
          :aria-label="collapsed ? 'Показать SQL' : 'Скрыть SQL'"
          @click="$emit('toggle-sql')"
        >
          <v-icon name="md-code" style="font-size: 14px" />
        </button>
        <button
          v-if="showExplainButton"
          class="sql-cell__action-btn sql-cell__action-btn--explain"
          type="button"
          :disabled="busy"
          aria-label="Объяснить SQL"
          title="Объяснить SQL"
          @click="$emit('explain')"
        >
          <span class="sql-cell__help-tooltip">ИИ объяснит, почему выбраны таблицы и колонки</span>
          ?
        </button>
        <button
          v-if="showCopyButton"
          class="sql-cell__action-btn"
          type="button"
          title="Скопировать SQL код"
          aria-label="Скопировать SQL код"
          @click="$emit('copy')"
        >
          <v-icon name="md-contentcopy" style="font-size: 14px" />
        </button>
      </div>
    </div>

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
  busy?: boolean;
  showExplainButton?: boolean;
  showCopyButton?: boolean;
  showToggleSqlButton?: boolean;
  showRunButton?: boolean;
}>();

defineEmits<{
  (event: 'explain'): void;
  (event: 'copy'): void;
  (event: 'toggle-sql'): void;
  (event: 'run'): void;
}>();

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

const hasHeader = computed(() => Boolean(props.content.explanation || props.showExplainButton || props.showCopyButton || props.showToggleSqlButton || props.showRunButton));

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

.sql-cell__actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: auto;
}

.sql-cell__run-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 12px 0 9px;
  border-radius: 999px;
  border: 1px solid rgba(112, 59, 247, 0.7);
  background: linear-gradient(180deg, rgba(112, 59, 247, 0.34), rgba(112, 59, 247, 0.2));
  color: #efe9ff;
  font-size: 0.76rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    background 160ms ease,
    box-shadow 160ms ease;

  &:hover:not(:disabled) {
    border-color: rgba(164, 126, 255, 0.92);
    background: linear-gradient(180deg, rgba(112, 59, 247, 0.46), rgba(112, 59, 247, 0.3));
    box-shadow: 0 4px 16px rgba(112, 59, 247, 0.28);
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.sql-cell__action-btn {
  position: relative;
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  padding: 0;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
  color: var(--muted);
  font-size: 1rem;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    color 160ms ease,
    border-color 160ms ease,
    background 160ms ease;
}

.sql-cell__action-btn:hover:not(:disabled),
.sql-cell__action-btn:focus-visible:not(:disabled) {
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.55);
  background: rgba(112, 59, 247, 0.12);
}

.sql-cell__action-btn--explain {
  border-color: rgba(112, 59, 247, 0.7);
  background: linear-gradient(180deg, rgba(112, 59, 247, 0.34), rgba(112, 59, 247, 0.2));
  color: #efe9ff;
  box-shadow: 0 8px 24px rgba(112, 59, 247, 0.18);
  animation: sql-cell-float 3.2s ease-in-out infinite;
}

.sql-cell__action-btn--explain:hover:not(:disabled),
.sql-cell__action-btn--explain:focus-visible:not(:disabled) {
  border-color: rgba(164, 126, 255, 0.92);
  background: linear-gradient(180deg, rgba(112, 59, 247, 0.42), rgba(112, 59, 247, 0.26));
}

.sql-cell__action-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  animation: none;
}

.sql-cell__help-tooltip {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  min-width: 240px;
  padding: 8px 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(8, 12, 20, 0.96);
  color: var(--ink);
  font-size: 0.76rem;
  line-height: 1.35;
  white-space: normal;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px);
  transition:
    opacity 160ms ease,
    transform 160ms ease;
  z-index: 10;
}

.sql-cell__action-btn:hover .sql-cell__help-tooltip,
.sql-cell__action-btn:focus-visible .sql-cell__help-tooltip {
  opacity: 1;
  transform: translateY(0);
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
