<template>
  <div class="app-shell">
    <div class="app-shell__main">
      <RouterView />
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, watch } from 'vue';
import { useRoute } from 'vue-router';

type ViewTransition = {
  finished: Promise<void>;
};

type ViewTransitionStarter = (
  updateCallback: () => void | Promise<void>,
) => ViewTransition;

const route = useRoute();
const documentWithTransition = document as Document & {
  startViewTransition?: ViewTransitionStarter;
};
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

let isFirstRouteRender = true;
let activeTransition: Promise<void> | null = null;

watch(
  () => route.path,
  (nextPath, previousPath) => {
    if (isFirstRouteRender) {
      isFirstRouteRender = false;
      return;
    }

    if (nextPath === previousPath) {
      return;
    }

    const startViewTransition =
      documentWithTransition.startViewTransition?.bind(documentWithTransition);

    if (!startViewTransition) {
      return;
    }

    if (prefersReducedMotion.matches) {
      return;
    }

    if (activeTransition) {
      return;
    }

    const transition = startViewTransition(async () => {
      await nextTick();
    });

    activeTransition = transition.finished
      .catch(() => undefined)
      .finally(() => {
        activeTransition = null;
      });
  },
  { flush: 'sync' },
);
</script>

<style scoped lang="scss">
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg);
}

.app-shell__main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
