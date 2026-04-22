<template>
  <component
    :is="as"
    class="app-skeleton"
    :class="{ 'app-skeleton--inline': inline }"
    :style="skeletonStyle"
    aria-hidden="true"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    as?: string;
    width?: string;
    height?: string;
    radius?: string;
    inline?: boolean;
  }>(),
  {
    as: 'span',
    width: '100%',
    height: '1rem',
    radius: '10px',
    inline: false,
  },
);

const skeletonStyle = computed(() => ({
  width: props.width,
  height: props.height,
  borderRadius: props.radius,
}));
</script>

<style scoped lang="scss">
.app-skeleton {
  position: relative;
  display: block;
  overflow: hidden;
  background: linear-gradient(
    90deg,
    var(--skeleton-base) 0%,
    var(--skeleton-base) 28%,
    var(--skeleton-mid) 48%,
    var(--skeleton-base) 68%,
    var(--skeleton-base) 100%
  );
  background-size: 220% 100%;
  animation: app-skeleton-shimmer 1.5s ease-in-out infinite;
}

.app-skeleton--inline {
  display: inline-block;
  vertical-align: middle;
}

@keyframes app-skeleton-shimmer {
  from {
    background-position: 100% 0;
  }

  to {
    background-position: -120% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .app-skeleton {
    animation: none;
  }
}
</style>
