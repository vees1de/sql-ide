<template>
  <div class="insight-cell">
    <p class="insight-cell__headline">{{ content.headline }}</p>

    <ul class="insight-cell__list">
      <li
        v-for="bullet in content.bullets"
        :key="bullet"
      >
        {{ bullet }}
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { InsightCellContent } from '@/types/app';

defineProps<{
  content: InsightCellContent;
}>();
</script>

<style scoped lang="scss">
.insight-cell__headline {
  margin: 0;
  color: var(--ink);
  font-size: 0.95rem;
  line-height: 1.55;
}

.insight-cell__list {
  margin: 0.55rem 0 0;
  padding-left: 1.1rem;
  color: var(--muted);
  font-size: 0.85rem;
  line-height: 1.55;
}
</style>
