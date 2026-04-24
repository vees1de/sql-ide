<template>
  <Teleport to="body">
    <div class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal">
        <div class="modal__header">
          <span class="modal__title">Add Widget</span>
          <button class="modal__close" type="button" @click="$emit('close')">✕</button>
        </div>

        <div class="modal__body">
          <input
            v-model="search"
            class="modal__search"
            type="text"
            placeholder="Search widgets..."
          />

          <div v-if="widgetsStore.loading" class="modal__list">
            <div
              v-for="item in 5"
              :key="`widget-modal-skeleton-${item}`"
              class="modal__list-item modal__list-item--skeleton"
            >
              <AppSkeleton class="modal__list-title-skeleton" height="0.82rem" radius="6px" />
              <AppSkeleton width="68px" height="1rem" radius="999px" />
            </div>
          </div>

          <div v-else-if="!filteredWidgets.length" class="modal__hint">
            No available widgets
          </div>

          <div v-else class="modal__list">
            <button
              v-for="widget in filteredWidgets"
              :key="widget.id"
              class="modal__list-item"
              :class="{ 'modal__list-item--selected': selectedId === widget.id }"
              type="button"
              @click="selectedId = widget.id"
            >
              <span>{{ widget.title }}</span>
              <span class="modal__viz-badge">
                {{ translateVisualizationType(widget.visualization_type) }}
              </span>
            </button>
          </div>
        </div>

        <div class="modal__footer">
          <button class="btn btn--ghost" type="button" @click="$emit('close')">
            Cancel
          </button>
          <button
            class="btn btn--primary"
            type="button"
            :disabled="!selectedId || saving"
            @click="submit"
          >
            {{ saving ? '...' : 'Add' }}
          </button>
        </div>

        <p v-if="errorMsg" class="modal__error">{{ errorMsg }}</p>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import AppSkeleton from '@/components/ui/AppSkeleton.vue';
import { useDashboardsStore } from '@/stores/dashboards';
import { useWidgetsStore } from '@/stores/widgets';

const props = defineProps<{
  dashboardId: string;
  alreadyAddedIds: string[];
}>();

const emit = defineEmits<{
  (event: 'close'): void;
  (event: 'added'): void;
}>();

const widgetsStore = useWidgetsStore();
const dashboardsStore = useDashboardsStore();

const search = ref('');
const selectedId = ref<string | null>(null);
const saving = ref(false);
const errorMsg = ref<string | null>(null);

const filteredWidgets = computed(() =>
  widgetsStore.widgets
    .filter((w) => !props.alreadyAddedIds.includes(w.id))
    .filter((w) => w.title.toLowerCase().includes(search.value.toLowerCase())),
);

function translateVisualizationType(value: string) {
  switch (value) {
    case 'table':
      return 'Table';
    case 'bar':
      return 'Bar';
    case 'line':
      return 'Line';
    case 'area':
      return 'Area';
    case 'pie':
      return 'Pie';
    case 'metric':
      return 'Metric';
    default:
      return value;
  }
}

async function submit() {
  if (!selectedId.value) return;
  saving.value = true;
  errorMsg.value = null;
  try {
    await dashboardsStore.addWidget(props.dashboardId, { widget_id: selectedId.value });
    emit('added');
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : 'Something went wrong.';
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  void widgetsStore.loadWidgets();
});
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
  max-height: 360px;
  overflow-y: auto;
}

.modal__search {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--ink);
  font-size: 0.82rem;
  padding: 6px 10px;
  width: 100%;
  box-sizing: border-box;
  outline: none;

  &:focus {
    border-color: rgba(112, 59, 247, 0.6);
  }
}

.modal__hint {
  color: var(--muted);
  font-size: 0.82rem;
  text-align: center;
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
  font-size: 0.82rem;
  padding: 7px 12px;
  text-align: left;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;

  &:hover {
    border-color: rgba(112, 59, 247, 0.4);
  }

  &--selected {
    border-color: rgba(112, 59, 247, 0.8);
    background: rgba(112, 59, 247, 0.1);
  }
}

.modal__list-item--skeleton {
  pointer-events: none;
}

.modal__list-title-skeleton {
  flex: 1;
}

.modal__viz-badge {
  font-size: 0.68rem;
  color: var(--muted);
  background: var(--line);
  padding: 1px 5px;
  border-radius: 4px;
  flex-shrink: 0;
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
