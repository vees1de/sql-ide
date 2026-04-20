<template>
  <div class="app-shell">
    <div class="app-shell__main">
      <RouterView />
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
</style>
