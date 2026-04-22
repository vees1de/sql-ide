<template>
  <div class="app-shell">
    <div class="app-shell__main">
      <RouterView v-slot="{ Component, route }">
        <div :key="route.fullPath" class="app-shell__route">
          <component :is="Component" />
        </div>
      </RouterView>
    </div>
  </div>
</template>

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

.app-shell__route {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
}

:global(html[data-view-transition-scope='page']) .app-shell__route {
  view-transition-name: app-route-content;
}

:global(html[data-view-transition-scope='section']) .app-shell__route {
  view-transition-name: none;
}
</style>
