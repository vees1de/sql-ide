<template>
  <div class="prompt-cell">
    <p class="prompt-cell__text">{{ content.prompt }}</p>

    <div
      v-if="content.chips?.length"
      class="prompt-cell__chips"
    >
      <span
        v-for="chip in content.chips"
        :key="chip"
        class="tag-chip tag-chip--accent"
      >
        {{ chip }}
      </span>
    </div>

    <ul
      v-if="content.context?.length"
      class="prompt-cell__context"
    >
      <li
        v-for="item in content.context"
        :key="item"
      >
        {{ item }}
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { PromptCellContent } from '@/types/app';

defineProps<{
  content: PromptCellContent;
}>();
</script>

<style scoped lang="scss">
.prompt-cell__text {
  margin: 0;
  color: var(--ink);
  font-size: 0.98rem;
  line-height: 1.6;
}

.prompt-cell__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.7rem;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  background: var(--link-soft);
  color: var(--link-strong);
  font-size: 0.76rem;
}

.prompt-cell__context {
  margin: 0.7rem 0 0;
  padding-left: 1.1rem;
  color: var(--muted);
  font-size: 0.85rem;
  line-height: 1.5;
}
</style>
