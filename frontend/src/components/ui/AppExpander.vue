<script setup lang="ts">
import { computed, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    items: unknown[];
    collapseAfter?: number;
    expandLabel?: string;
    collapseLabel?: string;
  }>(),
  {
    collapseAfter: 6,
    expandLabel: "Показать еще",
    collapseLabel: "Свернуть",
  },
);

const isExpanded = ref(false);

const isExpandable = computed(() => props.items.length > props.collapseAfter);
const hiddenCount = computed(() =>
  Math.max(props.items.length - props.collapseAfter, 0),
);
const visibleItems = computed(() =>
  isExpanded.value || !isExpandable.value
    ? props.items
    : props.items.slice(0, props.collapseAfter),
);
const buttonLabel = computed(() =>
  isExpanded.value
    ? props.collapseLabel
    : `${props.expandLabel} ${hiddenCount.value}`,
);

function toggle() {
  if (!isExpandable.value) return;
  isExpanded.value = !isExpanded.value;
}

watch(
  () => [props.items, props.items.length, props.collapseAfter],
  () => {
    isExpanded.value = false;
  },
);
</script>

<template>
  <div class="app-expander">
    <slot
      :expandable="isExpandable"
      :expanded="isExpanded"
      :hidden-count="hiddenCount"
      :items="visibleItems"
    />
    <button
      v-if="isExpandable"
      class="app-button app-button--ghost app-button--tiny app-expander__toggle"
      type="button"
      @click="toggle"
    >
      {{ buttonLabel }}
    </button>
  </div>
</template>

<style scoped lang="scss">
.app-expander {
  display: grid;
  gap: 0.75rem;
}

.app-expander__toggle {
  width: fit-content;
}
</style>
