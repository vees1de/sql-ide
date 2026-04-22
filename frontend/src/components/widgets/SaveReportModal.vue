<template>
  <Teleport to="body">
    <div class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal">
        <div class="modal__header">
          <span class="modal__title">Сохранить отчёт</span>
          <button class="modal__close" type="button" @click="$emit('close')">✕</button>
        </div>

        <div class="modal__body">
          <div class="form-field">
            <label class="form-field__label">Название *</label>
            <input
              v-model="title"
              class="form-field__input"
              type="text"
              placeholder="Выручка по месяцам"
              autofocus
            />
          </div>

          <div class="form-field">
            <label class="form-field__label">Описание</label>
            <textarea
              v-model="description"
              class="form-field__input form-field__input--textarea"
              placeholder="Краткое описание отчёта (опционально)"
              rows="2"
            />
          </div>

          <div class="form-field">
            <label class="form-field__label">Тип визуализации</label>
            <div class="viz-picker">
              <button
                v-for="option in vizOptions"
                :key="option.value"
                type="button"
                class="viz-picker__btn"
                :class="{ 'viz-picker__btn--active': vizType === option.value }"
                @click="vizType = option.value"
              >
                {{ option.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="modal__footer">
          <button class="btn btn--ghost" type="button" @click="$emit('close')">Отмена</button>
          <button
            class="btn btn--primary"
            type="button"
            :disabled="!title.trim() || saving"
            @click="submit"
          >
            {{ saving ? 'Сохраняем…' : 'Сохранить' }}
          </button>
        </div>

        <p v-if="errorMsg" class="modal__error">{{ errorMsg }}</p>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useWidgetsStore } from '@/stores/widgets';
import type { ApiChatExecutionRead, ApiVisualizationType } from '@/api/types';

const props = defineProps<{
  execution: ApiChatExecutionRead;
  sqlText: string;
  databaseConnectionId?: string | null;
}>();

const emit = defineEmits<{
  (event: 'close'): void;
  (event: 'saved', widgetId: string): void;
}>();

const widgetsStore = useWidgetsStore();
const router = useRouter();

const title = ref('');
const description = ref('');
const vizType = ref<ApiVisualizationType>(
  props.execution.chart_recommendation?.recommended_view === 'chart'
    ? (props.execution.chart_recommendation?.chart_type as ApiVisualizationType) ?? 'bar'
    : 'table'
);
const saving = ref(false);
const errorMsg = ref<string | null>(null);

const vizOptions: { value: ApiVisualizationType; label: string }[] = [
  { value: 'table', label: 'Таблица' },
  { value: 'bar', label: 'Столбчатая' },
  { value: 'line', label: 'Линейная' },
  { value: 'area', label: 'Областная' },
  { value: 'pie', label: 'Круговая' },
  { value: 'metric', label: 'Метрика' },
];

async function submit() {
  if (!title.value.trim()) return;
  saving.value = true;
  errorMsg.value = null;
  try {
    const rec = props.execution.chart_recommendation;
    const vizConfig = rec
      ? { x: rec.x, y: rec.y, series: rec.series, chart_type: rec.chart_type }
      : null;

    const widget = await widgetsStore.createWidget({
      title: title.value.trim(),
      description: description.value.trim() || null,
      source_type: 'text_to_sql',
      sql_text: props.sqlText,
      visualization_type: vizType.value,
      visualization_config: vizConfig ?? undefined,
      database_connection_id: props.databaseConnectionId ?? null,
    });
    await router.push(`/widget/${widget.id}`);
    emit('saved', widget.id);
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : 'Ошибка при сохранении.';
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
  width: 440px;
  max-width: calc(100vw - 32px);
  display: flex;
  flex-direction: column;
  gap: 0;
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
  &:hover { background: var(--line); }
}

.modal__body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
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

.form-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.form-field__label {
  font-size: 0.75rem;
  color: var(--muted);
  font-weight: 500;
}

.form-field__input {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--ink);
  font-size: 0.85rem;
  padding: 7px 10px;
  outline: none;
  width: 100%;
  box-sizing: border-box;

  &:focus {
    border-color: rgba(112, 59, 247, 0.7);
  }
}

.form-field__input--textarea {
  resize: vertical;
  font-family: inherit;
}

.viz-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.viz-picker__btn {
  padding: 4px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font-size: 0.78rem;
  cursor: pointer;

  &:hover { border-color: rgba(112, 59, 247, 0.5); color: var(--ink); }
}

.viz-picker__btn--active {
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.18);
  color: var(--ink-strong);
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

  &:disabled { opacity: 0.45; cursor: not-allowed; }
}

.btn--primary {
  background: rgba(112, 59, 247, 0.85);
  border-color: transparent;
  color: #fff;
  font-weight: 600;

  &:not(:disabled):hover { background: rgba(112, 59, 247, 1); }
}

.btn--ghost {
  &:hover { background: var(--line); }
}
</style>
