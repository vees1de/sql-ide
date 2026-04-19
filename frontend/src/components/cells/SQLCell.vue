<template>
  <div class="sql-cell">
    <div class="sql-cell__toolbar">
      <p>{{ content.explanation }}</p>
      <button
        class="app-button app-button--ghost app-button--tiny"
        type="button"
        @click="collapsed = !collapsed"
      >
        {{ collapsed ? 'Показать SQL' : 'Скрыть SQL' }}
      </button>
    </div>

    <pre v-if="!collapsed"><code>{{ content.sql }}</code></pre>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import type { SqlCellContent } from '@/types/app';

defineProps<{
  content: SqlCellContent;
}>();

const collapsed = ref(false);
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

@media (max-width: 640px) {
  .sql-cell__toolbar {
    flex-direction: column;
  }
}
</style>
