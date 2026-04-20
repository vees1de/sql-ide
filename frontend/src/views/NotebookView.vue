<template>
  <div class="notebook-page">
    <Splitpanes class="workspace-panes" :horizontal="isCompact">
      <Pane :size="isCompact ? 30 : 22" min-size="16">
        <ExplorerSidebar
          :active-database-id="store.currentDatabase.id"
          :selected-notebook-id="store.selectedNotebookId"
          :workspace="store.workspace"
          @open-notebook="openNotebook"
          @add-database="showAddDatabase = true"
          @create-notebook="handleCreateNotebook"
          @delete-database="onDeleteDatabase"
          @delete-notebook="onDeleteNotebook"
        />
      </Pane>

      <Pane :min-size="50">
        <NotebookCanvas
          v-if="store.currentNotebook"
          :clarification-answers="store.clarificationAnswers"
          :database-name="store.currentDatabase.name"
          :notebook="store.currentNotebook"
          :running-cell-ids="store.runningCellIds"
          :selected-cell-id="store.selectedCellId"
          @answer-clarification="store.answerClarification"
          @create-input-cell="store.createInputCell"
          @format-sql-cell="store.formatSqlCell"
          @move-input-cell="store.moveInputCell"
          @rename-notebook="store.renameCurrentNotebook"
          @reorder-input-cells="store.reorderInputCells"
          @run-input-cell="store.runCell"
          @save-input-cell="store.saveInputCell"
          @select-cell="store.selectCell"
        />
        <div v-else class="empty-canvas">
          <div class="empty-canvas__card">
            <p class="eyebrow">Workspace</p>
            <h2>Выберите или создайте notebook</h2>
            <p class="empty-canvas__hint">
              В левой панели — подключённые базы данных. Раскройте папку и
              откройте чат, либо подключите новую БД.
            </p>
            <button
              class="app-button"
              type="button"
              @click="showAddDatabase = true"
            >
              Добавить базу данных
            </button>
          </div>
        </div>
      </Pane>
    </Splitpanes>

    <AddDatabaseModal
      v-if="showAddDatabase"
      @close="showAddDatabase = false"
      @submit="onSubmitDatabase"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AddDatabaseModal from "@/components/layout/AddDatabaseModal.vue";
import ExplorerSidebar from "@/components/layout/ExplorerSidebar.vue";
import NotebookCanvas from "@/components/notebook/NotebookCanvas.vue";
import { useWorkspaceStore } from "@/stores/workspace";

const store = useWorkspaceStore();
const route = useRoute();
const router = useRouter();
const isCompact = ref(false);
const showAddDatabase = ref(false);

function syncCompactMode() {
  isCompact.value = window.innerWidth < 900;
}

async function syncNotebookFromRoute(
  notebookId: string | string[] | undefined,
) {
  const id = Array.isArray(notebookId) ? notebookId[0] : notebookId;
  await store.ensureInitialized(id);
  const exists = store.workspace.notebooks.some(
    (notebook) => notebook.id === id,
  );

  if (!id) {
    const fallback = store.workspace.notebooks[0]?.id;
    if (fallback) {
      router.replace({ name: 'notebook', params: { notebookId: fallback } });
    }
    return;
  }

  if (!exists) {
    const fallback = store.workspace.notebooks[0]?.id;
    if (fallback) {
      router.replace({ name: 'notebook', params: { notebookId: fallback } });
    }
    return;
  }

  if (store.selectedNotebookId !== id) {
    await store.selectNotebook(id);
  }
}

function openNotebook(notebookId: string) {
  router.push({ name: 'notebook', params: { notebookId } });
}

async function handleCreateNotebook(databaseId?: string) {
  const id = await store.createNotebook(databaseId);
  router.push({ name: 'notebook', params: { notebookId: id } });
}

async function onSubmitDatabase(payload: {
  name: string;
  engine: string;
  host: string;
  port: string;
  database: string;
  user: string;
  password: string;
  tables: number;
  importSchemaToDictionary: boolean;
  allowedTables: string[] | null;
}) {
  try {
    await store.connectDatabase({
      name: payload.name,
      engine: payload.engine,
      host: payload.host,
      port: payload.port,
      database: payload.database,
      user: payload.user,
      password: payload.password,
      tables: payload.tables,
      importSchemaToDictionary: payload.importSchemaToDictionary,
      allowedTables: payload.allowedTables
    });
    showAddDatabase.value = false;
  } catch {
    // banner already surfaces the error; keep modal open for retry
  }
}

async function onDeleteDatabase(databaseId: string) {
  if (!window.confirm('Удалить эту базу данных? Notebooks, привязанные к ней, останутся.')) {
    return;
  }
  try {
    await store.deleteDatabase(databaseId);
  } catch {
    // banner already surfaces the error
  }
}

async function onDeleteNotebook(notebookId: string) {
  if (!window.confirm('Удалить этот notebook? Все ячейки и история будут стёрты.')) {
    return;
  }
  try {
    const fallbackId = await store.deleteNotebook(notebookId);
    if (fallbackId) {
      router.replace({ name: 'notebook', params: { notebookId: fallbackId } });
    } else {
      router.replace({ name: 'chat' });
    }
  } catch {
    // banner already surfaces the error
  }
}

watch(
  () => ({ name: route.name, notebookId: route.params.notebookId }),
  async ({ name, notebookId }) => {
    await store.ensureInitialized();
    if (notebookId) {
      await syncNotebookFromRoute(notebookId);
    } else if (name === 'chat' || name === 'colab') {
      const first = store.workspace.notebooks[0]?.id;
      if (first && store.selectedNotebookId !== first) {
        await store.selectNotebook(first);
      }
    }
  },
  { immediate: true, deep: true }
);

onMounted(() => {
  syncCompactMode();
  window.addEventListener("resize", syncCompactMode);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", syncCompactMode);
});
</script>

<style scoped lang="scss">
.notebook-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}

.workspace-panes {
  flex: 1;
  min-height: 0;
}

:deep(.splitpanes__pane) {
  background: transparent;
}

:deep(.splitpanes__splitter) {
  background: transparent;
  position: relative;
  width: 6px;
}

:deep(.splitpanes__splitter::before) {
  content: "";
  position: absolute;
  inset: 0 calc(50% - 1px);
  background: var(--line);
}

:deep(.splitpanes__splitter:hover::before) {
  background: var(--line-strong);
}

:deep(.splitpanes--horizontal > .splitpanes__splitter) {
  height: 6px;
  width: auto;
}

:deep(.splitpanes--horizontal > .splitpanes__splitter::before) {
  inset: calc(50% - 1px) 0;
}

.empty-canvas {
  height: 100%;
  display: grid;
  place-items: center;
  padding: 2rem;
}

.empty-canvas__card {
  max-width: 420px;
  padding: 1.5rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  text-align: center;
}

.empty-canvas__card h2 {
  margin: 0.3rem 0 0.5rem;
  color: var(--ink-strong);
  font-size: 1.2rem;
}

.empty-canvas__hint {
  margin: 0 0 1rem;
  color: var(--muted);
  font-size: 0.88rem;
  line-height: 1.5;
}
</style>
