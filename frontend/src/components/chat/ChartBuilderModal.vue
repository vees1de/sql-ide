<template>
  <Teleport to="body">
    <div class="chart-builder-backdrop" @click.self="$emit('close')">
      <div class="chart-builder">
        <div class="chart-builder__header">
          <div>
            <strong>Настроить график</strong>
            <p>Редактирование `ChartSpec` поверх текущего dataset без переписывания SQL.</p>
          </div>
          <button class="chart-builder__close" type="button" @click="$emit('close')">x</button>
        </div>

        <div class="chart-builder__body">
          <div class="chart-builder__form">
            <label class="chart-builder__field">
              <span>Тип графика</span>
              <select v-model="draft.chart_type">
                <option value="bar">Bar</option>
                <option value="line">Line</option>
                <option value="pie">Pie</option>
                <option value="metric_card">KPI</option>
                <option value="table">Только таблица</option>
              </select>
            </label>

            <label class="chart-builder__field">
              <span>Заголовок</span>
              <input v-model="draft.title" type="text" placeholder="Например, Выручка по месяцам" />
            </label>

            <label class="chart-builder__field">
              <span>X axis</span>
              <select v-model="draft.x_field" :disabled="draft.chart_type === 'metric_card' || draft.chart_type === 'table'">
                <option :value="null">Не выбрано</option>
                <option v-for="field in xOptions" :key="field" :value="field">{{ field }}</option>
              </select>
            </label>

            <label class="chart-builder__field">
              <span>Y axis</span>
              <select v-model="draft.y_field" :disabled="draft.chart_type === 'table'">
                <option :value="null">Не выбрано</option>
                <option v-for="field in yOptions" :key="field" :value="field">{{ field }}</option>
              </select>
            </label>

            <label class="chart-builder__field">
              <span>Series</span>
              <select
                v-model="draft.series_field"
                :disabled="draft.chart_type === 'metric_card' || draft.chart_type === 'pie' || draft.chart_type === 'table'"
              >
                <option :value="null">Нет</option>
                <option v-for="field in seriesOptions" :key="field" :value="field">{{ field }}</option>
              </select>
            </label>

            <label class="chart-builder__checkbox">
              <input
                v-model="draft.stacked"
                type="checkbox"
                :disabled="draft.chart_type !== 'bar' || !draft.series_field"
              />
              <span>Stacked</span>
            </label>
          </div>

          <div class="chart-builder__preview">
            <ChartCell v-if="previewContent" :content="previewContent" :show-header="true" />
            <div v-else class="chart-builder__empty">
              Выберите совместимые поля для превью или оставьте только таблицу.
            </div>
          </div>
        </div>

        <div class="chart-builder__footer">
          <button class="chart-builder__btn chart-builder__btn--ghost" type="button" @click="$emit('close')">
            Отмена
          </button>
          <button class="chart-builder__btn chart-builder__btn--primary" type="button" @click="applySpec">
            Применить
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue';
import type { ApiChatChartSpec, ApiChatExecutionRead } from '@/api/types';
import ChartCell from '@/components/cells/ChartCell.vue';
import { buildChartCellContentFromSpec, inferColumnKinds } from '@/utils/chartPreview';

const props = defineProps<{
  execution: ApiChatExecutionRead;
  initialSpec?: ApiChatChartSpec | null;
}>();

const emit = defineEmits<{
  (event: 'close'): void;
  (event: 'apply', spec: ApiChatChartSpec): void;
}>();

type DraftState = {
  chart_type: ApiChatChartSpec['chart_type'];
  title: string;
  x_field: string | null;
  y_field: string | null;
  series_field: string | null;
  stacked: boolean;
};

const draft = reactive<DraftState>(buildInitialDraft());

const kinds = computed(() =>
  inferColumnKinds(props.execution.columns ?? [], props.execution.rows_preview ?? [])
);

const xOptions = computed(() => {
  const preferred = [...kinds.value.temporal, ...kinds.value.categorical];
  return unique(preferred.length ? preferred : (props.execution.columns ?? []).map((column) => column.name));
});

const yOptions = computed(() => {
  const preferred = kinds.value.numeric;
  return unique(preferred.length ? preferred : (props.execution.columns ?? []).map((column) => column.name));
});

const seriesOptions = computed(() => unique(kinds.value.categorical.filter((field) => field !== draft.x_field)));

const previewSpec = computed<ApiChatChartSpec>(() => ({
  chart_type: draft.chart_type,
  title: draft.title.trim() || 'Пользовательская визуализация',
  encoding: {
    x_field: draft.chart_type === 'metric_card' || draft.chart_type === 'table' ? null : draft.x_field,
    y_field: draft.chart_type === 'table' ? null : draft.y_field,
    series_field:
      draft.chart_type === 'metric_card' || draft.chart_type === 'pie' || draft.chart_type === 'table'
        ? null
        : draft.series_field,
    facet_field: null,
    sort: null,
    normalize: null,
    value_format: null
  },
  options: {
    source: 'manual'
  },
  variant: resolveVariant(draft.chart_type, draft.series_field, draft.stacked),
  explanation: 'Ручная настройка поверх результата SQL.',
  reason: 'Пользователь изменил конфигурацию визуализации.',
  rule_id: 'MANUAL_SPEC',
  confidence: 1
}));

const previewContent = computed(() => buildChartCellContentFromSpec(previewSpec.value, props.execution));

watch(
  () => props.initialSpec,
  () => {
    Object.assign(draft, buildInitialDraft());
  }
);

function buildInitialDraft(): DraftState {
  const columns = props.execution.columns ?? [];
  const rows = props.execution.rows_preview ?? [];
  const inferred = inferColumnKinds(columns, rows);
  const initial = props.initialSpec;

  return {
    chart_type: initial?.chart_type ?? 'bar',
    title: initial?.title ?? 'Пользовательская визуализация',
    x_field:
      initial?.encoding.x_field ??
      inferred.temporal[0] ??
      inferred.categorical[0] ??
      columns[0]?.name ??
      null,
    y_field: initial?.encoding.y_field ?? inferred.numeric[0] ?? columns[1]?.name ?? null,
    series_field: initial?.encoding.series_field ?? null,
    stacked: initial?.variant === 'stacked'
  };
}

function resolveVariant(chartType: ApiChatChartSpec['chart_type'], seriesField: string | null, stacked: boolean) {
  if (chartType === 'table') {
    return 'table_only';
  }
  if (chartType === 'metric_card') {
    return 'single_value';
  }
  if (chartType === 'pie') {
    return 'share';
  }
  if (chartType === 'bar') {
    if (stacked && seriesField) {
      return 'stacked';
    }
    return seriesField ? 'grouped' : 'single_series';
  }
  return seriesField ? 'multi_series' : 'single_series';
}

function applySpec() {
  emit('apply', previewSpec.value);
}

function unique(values: string[]) {
  return [...new Set(values.filter(Boolean))];
}
</script>

<style scoped lang="scss">
.chart-builder-backdrop {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(6, 10, 18, 0.62);
  z-index: 1000;
}

.chart-builder {
  width: min(1080px, calc(100vw - 40px));
  max-height: calc(100vh - 40px);
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--surface);
  overflow: hidden;
}

.chart-builder__header,
.chart-builder__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--line);
}

.chart-builder__footer {
  justify-content: flex-end;
  border-top: 1px solid var(--line);
  border-bottom: 0;
}

.chart-builder__header strong {
  display: block;
  color: var(--ink-strong);
  font-size: 0.96rem;
}

.chart-builder__header p {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 0.78rem;
}

.chart-builder__body {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 18px;
  padding: 18px;
  min-height: 0;
  overflow: auto;
}

.chart-builder__form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chart-builder__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chart-builder__field span,
.chart-builder__checkbox span {
  color: var(--muted);
  font-size: 0.76rem;
  font-weight: 600;
}

.chart-builder__field input,
.chart-builder__field select {
  min-height: 38px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--canvas);
  color: var(--ink);
  padding: 0 12px;
  font-size: 0.84rem;
  outline: none;
}

.chart-builder__checkbox {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
}

.chart-builder__preview {
  min-width: 0;
}

.chart-builder__preview :deep(.chart-cell__plot),
.chart-builder__preview :deep(.chart-cell__metric) {
  min-height: 360px;
  height: 360px;
}

.chart-builder__empty {
  min-height: 360px;
  border: 1px dashed var(--line);
  border-radius: 16px;
  display: grid;
  place-items: center;
  color: var(--muted);
  background: rgba(255, 255, 255, 0.02);
  text-align: center;
  padding: 20px;
}

.chart-builder__close,
.chart-builder__btn {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
}

.chart-builder__btn--primary {
  border-color: rgba(112, 59, 247, 0.65);
  background: rgba(112, 59, 247, 0.16);
}
</style>
