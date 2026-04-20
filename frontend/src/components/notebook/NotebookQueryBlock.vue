<template>
  <article
    class="query-block"
    :class="{
      'query-block--selected': isInputSelected,
      'query-block--running': running,
      'query-block--sql': isSqlBlock
    }"
    draggable="true"
    @dragstart="onDragStart"
    @dragend="$emit('drag-end')"
  >
    <header class="query-block__header">
      <div class="query-block__identity">
        <button
          class="query-block__drag"
          type="button"
          title="Перетащить блок"
          aria-label="Перетащить блок"
        >
          <span></span>
          <span></span>
        </button>
        <span class="pill" :class="isSqlBlock ? 'pill--link' : 'pill--accent'">
          {{ isSqlBlock ? 'SQL' : 'Prompt' }}
        </span>
        <div>
          <strong>{{ blockTitle }}</strong>
          <p>{{ blockSubtitle }}</p>
        </div>
      </div>

      <div class="query-block__actions">
        <span v-if="rowCountLabel" class="pill pill--ghost">{{ rowCountLabel }}</span>
        <span v-if="executionTimeLabel" class="pill pill--ghost">{{ executionTimeLabel }}</span>
        <button
          class="app-button app-button--ghost app-button--tiny"
          type="button"
          :disabled="!canMoveUp"
          @click="$emit('move-up', block.inputCell.id)"
        >
          ↑
        </button>
        <button
          class="app-button app-button--ghost app-button--tiny"
          type="button"
          :disabled="!canMoveDown"
          @click="$emit('move-down', block.inputCell.id)"
        >
          ↓
        </button>
        <button
          v-if="isSqlBlock"
          class="app-button app-button--ghost app-button--tiny"
          type="button"
          @click="formatSql"
        >
          Format
        </button>
        <button
          class="app-button app-button--tiny"
          type="button"
          :disabled="running"
          @click="runCell"
        >
          {{ running ? 'Running…' : 'Run' }}
        </button>
      </div>
    </header>

    <div class="query-block__editor" @click="$emit('select-cell', block.inputCell.id)">
      <textarea
        :value="draftValue"
        class="query-block__textarea"
        :class="{ 'query-block__textarea--sql': isSqlBlock }"
        :placeholder="placeholder"
        :rows="editorRows"
        @input="onInput"
        @blur="saveCell"
        @keydown.enter.meta="runFromHotkey"
        @keydown.enter.ctrl="runFromHotkey"
      ></textarea>
      <div class="query-block__hint">
        <span>{{ helperText }}</span>
        <span>{{ block.inputCell.order }}</span>
      </div>
    </div>

    <section
      v-if="generatedSqlCell"
      class="query-block__section"
      :class="{ 'query-block__section--selected': selectedCellId === generatedSqlCell.id }"
      @click="$emit('select-cell', generatedSqlCell.id)"
    >
      <div class="query-block__section-label">Generated SQL</div>
      <SQLCell :content="sqlContent(generatedSqlCell)" />
    </section>

    <section
      v-if="hasResultTabs"
      class="query-block__section"
      :class="{ 'query-block__section--selected': isResultSelected }"
    >
      <div class="query-block__result-head">
        <div class="query-block__section-label">Result</div>
        <div class="query-block__tabs" role="tablist" aria-label="Result view">
          <button
            v-if="block.tableCell"
            class="query-block__tab"
            :class="{ 'query-block__tab--active': activeResultTab === 'table' }"
            type="button"
            @click="setResultTab('table')"
          >
            Таблица
          </button>
          <button
            v-if="block.chartCell"
            class="query-block__tab"
            :class="{ 'query-block__tab--active': activeResultTab === 'chart' }"
            type="button"
            @click="setResultTab('chart')"
          >
            График
          </button>
        </div>
      </div>

      <div class="query-block__result-body" @click="selectActiveResultCell">
        <TableCell
          v-if="activeResultTab === 'table' && block.tableCell"
          :content="tableContent(block.tableCell)"
        />
        <ChartCell
          v-else-if="activeResultTab === 'chart' && block.chartCell"
          :content="chartContent(block.chartCell)"
        />
      </div>
    </section>

    <section
      v-if="block.clarificationCell"
      class="query-block__section"
      :class="{ 'query-block__section--selected': selectedCellId === block.clarificationCell.id }"
      @click.self="$emit('select-cell', block.clarificationCell.id)"
    >
      <div class="query-block__section-label">Уточнение / Ошибка</div>
      <ClarificationCell
        :content="clarificationContent(block.clarificationCell)"
        :selected-answer="clarificationAnswers[block.clarificationCell.id]"
        @answer="$emit('answer-clarification', block.clarificationCell.id, $event)"
      />
    </section>

    <section
      v-if="block.insightCell"
      class="query-block__section"
      :class="{ 'query-block__section--selected': selectedCellId === block.insightCell.id }"
      @click="$emit('select-cell', block.insightCell.id)"
    >
      <div class="query-block__section-label">Вывод</div>
      <InsightCell :content="insightContent(block.insightCell)" />
    </section>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import ChartCell from '@/components/cells/ChartCell.vue';
import ClarificationCell from '@/components/cells/ClarificationCell.vue';
import InsightCell from '@/components/cells/InsightCell.vue';
import SQLCell from '@/components/cells/SQLCell.vue';
import TableCell from '@/components/cells/TableCell.vue';
import type {
  ChartCellContent,
  ClarificationCellContent,
  InsightCellContent,
  NotebookCell,
  NotebookQueryBlock,
  SqlCellContent,
  TableCellContent
} from '@/types/app';

const props = defineProps<{
  block: NotebookQueryBlock;
  canMoveDown: boolean;
  canMoveUp: boolean;
  clarificationAnswers: Record<string, string>;
  running: boolean;
  selectedCellId: string;
}>();

const emit = defineEmits<{
  (event: 'answer-clarification', cellId: string, optionId: string): void;
  (event: 'drag-end'): void;
  (event: 'drag-start', cellId: string): void;
  (event: 'format-sql-cell', cellId: string, value: string): void;
  (event: 'move-down', cellId: string): void;
  (event: 'move-up', cellId: string): void;
  (event: 'run-input-cell', cellId: string, value: string): void;
  (event: 'save-input-cell', cellId: string, value: string): void;
  (event: 'select-cell', cellId: string): void;
}>();

const activeResultTab = ref<'table' | 'chart'>('table');
const draftValue = ref('');
const dirty = ref(false);

const isSqlBlock = computed(() => props.block.inputCell.type === 'sql');
const generatedSqlCell = computed(() => (isSqlBlock.value ? undefined : props.block.sqlCell));
const isInputSelected = computed(() => props.selectedCellId === props.block.inputCell.id);
const isResultSelected = computed(
  () =>
    props.selectedCellId === props.block.tableCell?.id ||
    props.selectedCellId === props.block.chartCell?.id
);
const hasResultTabs = computed(() => Boolean(props.block.tableCell || props.block.chartCell));

const blockTitle = computed(() =>
  isSqlBlock.value ? 'Редактируемый SQL-блок' : 'Prompt → SQL block'
);

const blockSubtitle = computed(() =>
  isSqlBlock.value
    ? 'Как в Colab: правка, форматирование и запуск из одной ячейки'
    : 'Редактируйте запрос на естественном языке и перезапускайте блок'
);

const placeholder = computed(() =>
  isSqlBlock.value
    ? 'SELECT region, SUM(revenue) AS revenue\nFROM orders\nGROUP BY region\nORDER BY revenue DESC'
    : 'Например: Покажи выручку по регионам за текущий квартал'
);

const helperText = computed(() =>
  isSqlBlock.value ? 'Cmd/Ctrl + Enter запускает SQL' : 'Cmd/Ctrl + Enter запускает prompt'
);

const rowCountLabel = computed(() => {
  const rowCount =
    props.block.tableCell?.meta.rowCount ??
    props.block.chartCell?.meta.rowCount ??
    props.block.inputCell.meta.rowCount;

  return typeof rowCount === 'number' ? `${rowCount} строк` : null;
});

const executionTimeLabel = computed(() => {
  const executionMs =
    props.block.tableCell?.meta.executionTimeMs ??
    props.block.chartCell?.meta.executionTimeMs ??
    props.block.inputCell.meta.executionTimeMs;

  return typeof executionMs === 'number' && executionMs > 0 ? `${executionMs} ms` : null;
});

const editorRows = computed(() => {
  const lineCount = Math.max(draftValue.value.split('\n').length, isSqlBlock.value ? 6 : 3);
  return Math.min(lineCount + 1, 18);
});

function extractInputValue(cell: NotebookCell) {
  if (cell.type === 'sql') {
    return (cell.content as SqlCellContent).sql ?? '';
  }
  return String((cell.content as { prompt?: string }).prompt ?? '');
}

function syncDraftFromCell() {
  if (!dirty.value) {
    draftValue.value = extractInputValue(props.block.inputCell);
  }
}

function onInput(event: Event) {
  const target = event.target as HTMLTextAreaElement;
  draftValue.value = target.value;
  dirty.value = true;
}

function saveCell() {
  if (!dirty.value) {
    return;
  }
  dirty.value = false;
  emit('save-input-cell', props.block.inputCell.id, draftValue.value);
}

function runCell() {
  dirty.value = false;
  emit('run-input-cell', props.block.inputCell.id, draftValue.value);
}

function runFromHotkey(event: KeyboardEvent) {
  event.preventDefault();
  runCell();
}

function formatSql() {
  dirty.value = false;
  emit('format-sql-cell', props.block.inputCell.id, draftValue.value);
}

function onDragStart(event: DragEvent) {
  event.dataTransfer?.setData('text/plain', props.block.inputCell.id);
  event.dataTransfer?.setDragImage(event.currentTarget as HTMLElement, 24, 24);
  emit('drag-start', props.block.inputCell.id);
}

function setDefaultResultTab() {
  if (props.block.tableCell) {
    activeResultTab.value = 'table';
    return;
  }
  if (props.block.chartCell) {
    activeResultTab.value = 'chart';
  }
}

function setResultTab(tab: 'table' | 'chart') {
  activeResultTab.value = tab;
  if (tab === 'table' && props.block.tableCell) {
    emit('select-cell', props.block.tableCell.id);
    return;
  }
  if (tab === 'chart' && props.block.chartCell) {
    emit('select-cell', props.block.chartCell.id);
  }
}

function selectActiveResultCell() {
  if (activeResultTab.value === 'table' && props.block.tableCell) {
    emit('select-cell', props.block.tableCell.id);
    return;
  }
  if (activeResultTab.value === 'chart' && props.block.chartCell) {
    emit('select-cell', props.block.chartCell.id);
  }
}

function sqlContent(cell: NotebookCell) {
  return cell.content as SqlCellContent;
}

function tableContent(cell: NotebookCell) {
  return cell.content as TableCellContent;
}

function chartContent(cell: NotebookCell) {
  return cell.content as ChartCellContent;
}

function clarificationContent(cell: NotebookCell) {
  return cell.content as ClarificationCellContent;
}

function insightContent(cell: NotebookCell) {
  return cell.content as InsightCellContent;
}

watch(
  () => [props.block.inputCell.id, extractInputValue(props.block.inputCell)],
  () => {
    syncDraftFromCell();
  },
  { immediate: true }
);

watch(
  () => `${props.block.id}:${Boolean(props.block.tableCell)}:${Boolean(props.block.chartCell)}`,
  () => {
    setDefaultResultTab();
  },
  { immediate: true }
);
</script>

<style scoped lang="scss">
.query-block {
  border: 1px solid var(--line);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0.015));
  box-shadow: var(--shadow-soft);
  padding: 1rem 1.05rem;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

.query-block:hover {
  border-color: var(--line-strong);
}

.query-block--selected {
  border-color: rgba(138, 180, 248, 0.45);
  box-shadow: 0 0 0 1px rgba(138, 180, 248, 0.18), var(--shadow-soft);
}

.query-block--running {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent-soft), var(--shadow-soft);
}

.query-block__header,
.query-block__result-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.9rem;
}

.query-block__identity {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  min-width: 0;
}

.query-block__identity strong {
  display: block;
  color: var(--ink-strong);
  font-size: 0.95rem;
}

.query-block__identity p {
  margin: 0.2rem 0 0;
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.45;
}

.query-block__drag {
  display: inline-flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.18rem;
  width: 2rem;
  min-height: 2rem;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: transparent;
  color: var(--muted);
  cursor: grab;
}

.query-block__drag span {
  display: block;
  width: 0.9rem;
  height: 2px;
  margin: 0 auto;
  border-radius: 999px;
  background: currentColor;
}

.query-block__actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.query-block__editor {
  margin-top: 0.95rem;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(18, 20, 27, 0.72);
  overflow: hidden;
}

.query-block__textarea {
  width: 100%;
  border: none;
  resize: vertical;
  padding: 0.95rem 1rem 0.8rem;
  background: transparent;
  color: var(--ink);
  font-size: 0.92rem;
  line-height: 1.65;
  outline: none;
}

.query-block__textarea--sql {
  font-family: var(--font-mono);
  font-size: 0.84rem;
  line-height: 1.7;
}

.query-block__hint {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.65rem 1rem 0.8rem;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.74rem;
  font-family: var(--font-mono);
}

.query-block__section {
  margin-top: 0.95rem;
  padding-top: 0.95rem;
  border-top: 1px solid var(--line);
  border-radius: 14px;
}

.query-block__section--selected {
  padding: 0.95rem 0.8rem 0 0.8rem;
  margin: 0.95rem -0.8rem 0;
  border-top-color: transparent;
  box-shadow: 0 0 0 1px rgba(138, 180, 248, 0.18);
}

.query-block__section-label {
  margin-bottom: 0.6rem;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 0.74rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.query-block__tabs {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.22rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--bg-elev);
}

.query-block__tab {
  min-height: 2rem;
  padding: 0.35rem 0.8rem;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 600;
}

.query-block__tab--active {
  background: var(--link-soft);
  color: var(--link-strong);
}

.query-block__result-body {
  margin-top: 0.75rem;
  cursor: pointer;
}

@media (max-width: 760px) {
  .query-block__header,
  .query-block__result-head {
    flex-direction: column;
  }

  .query-block__actions {
    justify-content: flex-start;
  }
}
</style>
