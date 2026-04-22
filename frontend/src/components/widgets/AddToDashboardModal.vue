<template>
  <Teleport to="body">
    <div class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal">
        <div class="modal__header">
          <span class="modal__title">Add To Dashboard</span>
          <button class="modal__close" type="button" @click="$emit('close')">
            вњ•
          </button>
        </div>

        <div class="modal__body">
          <div v-if="dashboardsStore.loading" class="modal__list">
            <div
              v-for="item in 4"
              :key="`dashboard-modal-skeleton-${item}`"
              class="modal__list-item modal__list-item--skeleton"
            >
              <AppSkeleton height="0.85rem" width="62%" radius="6px" />
            </div>
          </div>

          <template v-else>
            <div v-if="dashboardsStore.dashboards.length" class="modal__list">
              <button
                v-for="dashboard in dashboardsStore.dashboards"
                :key="dashboard.id"
                class="modal__list-item"
                :class="{
                  'modal__list-item--selected': selectedId === dashboard.id,
                }"
                type="button"
                @click="selectedId = dashboard.id"
              >
                {{ dashboard.title }}
              </button>
            </div>
            <p v-else class="modal__hint">You don't have any dashboards yet.</p>

            <div class="modal__or">or</div>

            <div class="modal__new-dashboard">
              <input
                v-model="newTitle"
                class="modal__input"
                type="text"
                placeholder="Create a new dashboard..."
                @focus="selectedId = null"
              />
            </div>
          </template>
        </div>

        <div class="modal__footer">
          <button class="btn btn--ghost" type="button" @click="$emit('close')">
            Cancel
          </button>
          <button
            class="btn btn--primary"
            type="button"
            :disabled="(!selectedId && !newTitle.trim()) || saving"
            @click="submit"
          >
            {{ saving ? "..." : "Add" }}
          </button>
        </div>

        <p v-if="errorMsg" class="modal__error">{{ errorMsg }}</p>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import AppSkeleton from "@/components/ui/AppSkeleton.vue";
import { useDashboardsStore } from "@/stores/dashboards";

const props = defineProps<{
  widgetId: string;
}>();

const emit = defineEmits<{
  (event: "close"): void;
}>();

const router = useRouter();
const dashboardsStore = useDashboardsStore();

const selectedId = ref<string | null>(null);
const newTitle = ref("");
const saving = ref(false);
const errorMsg = ref<string | null>(null);

onMounted(() => {
  void dashboardsStore.loadDashboards();
});

async function submit() {
  saving.value = true;
  errorMsg.value = null;
  try {
    let dashboardId = selectedId.value;

    if (!dashboardId && newTitle.value.trim()) {
      const created = await dashboardsStore.createDashboard({
        title: newTitle.value.trim(),
        widgets: [{ widget_id: props.widgetId }],
      });
      dashboardId = created.id;
      emit("close");
      void router.push(`/dashboards/${dashboardId}`);
      return;
    }

    if (dashboardId) {
      await dashboardsStore.addWidget(dashboardId, {
        widget_id: props.widgetId,
      });
      emit("close");
      void router.push(`/dashboards/${dashboardId}`);
    }
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : "Something went wrong.";
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped lang="scss">
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  width: 380px;
  max-width: calc(100vw - 32px);
  display: flex;
  flex-direction: column;
}

.modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  border-bottom: 1px solid var(--line);
}

.modal__title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--ink-strong);
}

.modal__close {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.9rem;
  padding: 2px 6px;
  border-radius: 4px;

  &:hover {
    background: var(--line);
  }
}

.modal__body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 320px;
  overflow-y: auto;
}

.modal__hint {
  color: var(--muted);
  font-size: 0.82rem;
  margin: 0;
}

.modal__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.modal__list-item {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--ink);
  font-size: 0.85rem;
  padding: 8px 12px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s;

  &:hover {
    border-color: rgba(112, 59, 247, 0.5);
  }

  &--selected {
    border-color: rgba(112, 59, 247, 0.8);
    background: rgba(112, 59, 247, 0.1);
  }
}

.modal__list-item--skeleton {
  pointer-events: none;
}

.modal__or {
  text-align: center;
  font-size: 0.72rem;
  color: var(--muted);
  position: relative;

  &::before,
  &::after {
    content: "";
    position: absolute;
    top: 50%;
    width: 38%;
    height: 1px;
    background: var(--line);
  }

  &::before {
    left: 0;
  }

  &::after {
    right: 0;
  }
}

.modal__input {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--ink);
  font-size: 0.85rem;
  padding: 7px 10px;
  width: 100%;
  box-sizing: border-box;
  outline: none;

  &:focus {
    border-color: rgba(112, 59, 247, 0.7);
  }
}

.modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 16px 14px;
  border-top: 1px solid var(--line);
}

.modal__error {
  padding: 0 16px 12px;
  color: #ff7070;
  font-size: 0.78rem;
}

.btn {
  min-height: 32px;
  padding: 0 14px;
  border-radius: 8px;
  font-size: 0.82rem;
  cursor: pointer;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.btn--primary {
  background: rgba(112, 59, 247, 0.85);
  border-color: transparent;
  color: #fff;
  font-weight: 600;

  &:not(:disabled):hover {
    background: rgba(112, 59, 247, 1);
  }
}

.btn--ghost:hover {
  background: var(--line);
}
</style>
