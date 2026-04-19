<template>
  <div class="clarification-cell">
    <p class="clarification-cell__question">{{ content.question }}</p>

    <div class="clarification-cell__options">
      <button
        v-for="option in content.options"
        :key="option.id"
        class="clarification-option"
        :class="{
          'clarification-option--active': selectedAnswer === option.id,
          'clarification-option--recommended': content.recommended === option.id
        }"
        type="button"
        @click.stop="$emit('answer', option.id)"
      >
        <div class="clarification-option__head">
          <strong>{{ option.label }}</strong>
          <span v-if="content.recommended === option.id">Recommended</span>
        </div>
        <p>{{ option.detail }}</p>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ClarificationCellContent } from '@/types/app';

defineProps<{
  content: ClarificationCellContent;
  selectedAnswer?: string;
}>();

defineEmits<{
  (event: 'answer', optionId: string): void;
}>();
</script>

<style scoped lang="scss">
.clarification-cell__question {
  margin: 0 0 0.65rem;
  color: var(--ink);
  font-size: 0.92rem;
  line-height: 1.55;
}

.clarification-cell__options {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.55rem;
}

.clarification-option {
  padding: 0.65rem 0.7rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--canvas);
  color: var(--ink);
  text-align: left;
  transition: border-color 160ms ease, background 160ms ease;
}

.clarification-option:hover {
  border-color: var(--link-strong);
}

.clarification-option--active {
  border-color: var(--link);
  background: var(--link-soft);
}

.clarification-option--recommended .clarification-option__head span {
  color: var(--accent-strong);
}

.clarification-option__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}

.clarification-option__head strong {
  font-size: 0.85rem;
  color: var(--ink);
}

.clarification-option__head span,
.clarification-option p {
  color: var(--muted);
  font-size: 0.78rem;
}

.clarification-option p {
  margin: 0.35rem 0 0;
  line-height: 1.45;
}
</style>
