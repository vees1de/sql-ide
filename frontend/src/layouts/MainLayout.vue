<template>
  <div class="app-shell">
    <TopBar
      :banner="store.banner"
      :database="store.currentDatabase"
      :is-running="store.isRunning"
      :status-label="store.statusLabel"
      :workspace-name="store.workspace.name"
      @new-notebook="onNewNotebook"
      @run-all="store.runCurrentNotebook"
      @save-report="store.saveCurrentReport"
      @share="store.shareCurrentNotebook"
    />
    <div class="app-shell__main">
      <RouterView />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import TopBar from '@/components/layout/TopBar.vue';
import { useWorkspaceStore } from '@/stores/workspace';

const store = useWorkspaceStore();
const router = useRouter();

async function onNewNotebook() {
  try {
    const id = await store.createNotebook();
    if (id) {
      router.push({ name: 'notebook', params: { notebookId: id } });
    }
  } catch {
    /* banner in store */
  }
}
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
