<template>
  <main ref="canvasRef" class="notebook-canvas">
    <section class="notebook-header">
      <div class="notebook-header__identity">
        <div class="notebook-header__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        </div>
        <input
          :value="notebook.title"
          class="notebook-header__title"
          type="text"
          @change="onTitleChange"
        />
        <span class="notebook-header__db">· {{ databaseName }}</span>
      </div>

      <div class="notebook-header__meta">
        <span class="pill pill--ghost">{{ queryBlocks.length }} блоков</span>
        <span class="pill pill--ghost">{{ notebook.summary.lastRunLabel }}</span>
      </div>
    </section>

    <section class="notebook-toolbar">
      <button class="app-button" type="button" @click="$emit('create-input-cell', 'prompt')">
        + Prompt
      </button>
      <button class="app-button app-button--link" type="button" @click="$emit('create-input-cell', 'sql')">
        + SQL
      </button>
      <p>
        Notebook работает как Colab: блоки можно редактировать, запускать и переставлять drag-and-drop.
      </p>
    </section>

    <section v-if="queryBlocks.length" class="notebook-blocks">
      <template v-for="(block, index) in queryBlocks" :key="block.id">
        <button
          class="drop-slot"
          :class="{ 'drop-slot--active': activeDropIndex === index }"
          type="button"
          aria-hidden="true"
          tabindex="-1"
          @dragover.prevent="activeDropIndex = index"
          @drop.prevent="dropAt(index)"
        ></button>

        <NotebookQueryBlock
          :data-block-id="block.id"
          :block="block"
          :can-move-down="index < queryBlocks.length - 1"
          :can-move-up="index > 0"
          :clarification-answers="clarificationAnswers"
          :default-llm-model-alias="defaultLlmModelAlias"
          :llm-model-aliases="llmModelAliases"
          :running="runningCellIds.includes(block.inputCell.id)"
          :selected-cell-id="selectedCellId"
          @answer-clarification="onAnswerClarification"
          @drag-end="clearDragState"
          @drag-start="onDragStart"
          @format-sql-cell="onFormatSqlCell"
          @move-down="onMoveDown"
          @move-up="onMoveUp"
          @run-input-cell="onRunInputCell"
          @save-input-cell="onSaveInputCell"
          @set-input-model="onSetInputModel"
          @set-input-mode="onSetInputMode"
          @select-cell="$emit('select-cell', $event)"
        />
      </template>

      <button
        class="drop-slot"
        :class="{ 'drop-slot--active': activeDropIndex === queryBlocks.length }"
        type="button"
        aria-hidden="true"
        tabindex="-1"
        @dragover.prevent="activeDropIndex = queryBlocks.length"
        @drop.prevent="dropAt(queryBlocks.length)"
      ></button>
    </section>

    <section v-else class="notebook-empty">
      <span class="pill pill--accent">Empty notebook</span>
      <h3>Создайте первый блок</h3>
      <p>
        Начните с `prompt`-ячейки для NL→SQL или сразу добавьте SQL-блок и
        пишите запрос вручную.
      </p>
      <div class="notebook-empty__actions">
        <button class="app-button" type="button" @click="$emit('create-input-cell', 'prompt')">
          Добавить prompt
        </button>
        <button class="app-button app-button--link" type="button" @click="$emit('create-input-cell', 'sql')">
          Добавить SQL
        </button>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import NotebookQueryBlock from '@/components/notebook/NotebookQueryBlock.vue';
import type { Notebook, NotebookCell, NotebookQueryBlock as QueryBlock, QueryMode } from '@/types/app';

const props = defineProps<{
  clarificationAnswers: Record<string, string>;
  databaseName: string;
  defaultLlmModelAlias: string;
  llmModelAliases: string[];
  notebook: Notebook;
  runningCellIds: string[];
  selectedCellId: string;
}>();

const emit = defineEmits<{
  (event: 'answer-clarification', cellId: string, optionId: string): void;
  (event: 'create-input-cell', type: 'prompt' | 'sql'): void;
  (event: 'format-sql-cell', cellId: string, value: string): void;
  (event: 'move-input-cell', cellId: string, direction: 'up' | 'down'): void;
  (event: 'rename-notebook', title: string): void;
  (event: 'reorder-input-cells', orderedCellIds: string[]): void;
  (event: 'run-input-cell', cellId: string, value: string, mode: QueryMode, llmModelAlias?: string): void;
  (event: 'save-input-cell', cellId: string, value: string, mode?: QueryMode, llmModelAlias?: string): void;
  (event: 'set-input-model', cellId: string, llmModelAlias: string): void;
  (event: 'set-input-mode', cellId: string, mode: QueryMode): void;
  (event: 'select-cell', cellId: string): void;
}>();

const canvasRef = ref<HTMLElement | null>(null);
const draggingCellId = ref('');
const activeDropIndex = ref<number | null>(null);

function isInputCell(cell: NotebookCell) {
  return !cell.queryRunId && (cell.type === 'prompt' || cell.type === 'sql');
}

const queryBlocks = computed<QueryBlock[]>(() => {
  const inputCells = props.notebook.cells
    .filter(isInputCell)
    .slice()
    .sort((left, right) => left.order - right.order);

  return inputCells.map((inputCell) => {
    const relatedCells = props.notebook.cells
      .filter(
        (cell) =>
          cell.id !== inputCell.id &&
          cell.sourceCellId === inputCell.id &&
          Boolean(cell.queryRunId)
      )
      .slice()
      .sort((left, right) => left.order - right.order);

    return {
      id: inputCell.id,
      inputCell,
      sqlCell: inputCell.type === 'prompt'
        ? relatedCells.find((cell) => cell.type === 'sql')
        : undefined,
      tableCell: relatedCells.find((cell) => cell.type === 'table'),
      chartCell: relatedCells.find((cell) => cell.type === 'chart'),
      insightCell: relatedCells.find((cell) => cell.type === 'insight'),
      clarificationCell: relatedCells.find((cell) => cell.type === 'clarification'),
      otherCells: relatedCells.filter(
        (cell) => !['sql', 'table', 'chart', 'insight', 'clarification'].includes(cell.type)
      )
    };
  });
});

function onTitleChange(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.value.trim()) {
    emit('rename-notebook', target.value.trim());
  }
}

function onAnswerClarification(cellId: string, optionId: string) {
  emit('answer-clarification', cellId, optionId);
}

function onDragStart(cellId: string) {
  draggingCellId.value = cellId;
}

function onSaveInputCell(cellId: string, value: string, mode?: QueryMode, llmModelAlias?: string) {
  emit('save-input-cell', cellId, value, mode, llmModelAlias);
}

function onRunInputCell(cellId: string, value: string, mode: QueryMode, llmModelAlias?: string) {
  emit('run-input-cell', cellId, value, mode, llmModelAlias);
}

function onFormatSqlCell(cellId: string, value: string) {
  emit('format-sql-cell', cellId, value);
}

function onMoveUp(cellId: string) {
  emit('move-input-cell', cellId, 'up');
}

function onMoveDown(cellId: string) {
  emit('move-input-cell', cellId, 'down');
}

function onSetInputMode(cellId: string, mode: QueryMode) {
  emit('set-input-mode', cellId, mode);
}

function onSetInputModel(cellId: string, llmModelAlias: string) {
  emit('set-input-model', cellId, llmModelAlias);
}

function clearDragState() {
  draggingCellId.value = '';
  activeDropIndex.value = null;
}

function dropAt(index: number) {
  if (!draggingCellId.value) {
    return;
  }

  const ordered = queryBlocks.value.map((block) => block.inputCell.id);
  const fromIndex = ordered.indexOf(draggingCellId.value);
  if (fromIndex < 0) {
    clearDragState();
    return;
  }

  const [moved] = ordered.splice(fromIndex, 1);
  const targetIndex = fromIndex < index ? index - 1 : index;
  ordered.splice(targetIndex, 0, moved);
  clearDragState();
  emit('reorder-input-cells', ordered);
}

watch(
  () => queryBlocks.value.map((block) => block.id).join(','),
  async () => {
    await nextTick();
    const lastBlock = queryBlocks.value[queryBlocks.value.length - 1];
    if (!lastBlock || !canvasRef.value) {
      return;
    }

    const element = canvasRef.value.querySelector<HTMLElement>(
      `[draggable="true"][data-block-id="${lastBlock.id}"]`
    );
    element?.scrollIntoView({
      behavior: 'smooth',
      block: 'end'
    });
  }
);
</script>

<style scoped lang="scss">
.notebook-canvas {
  height: 100%;
  overflow-y: auto;
  padding: 1rem 1.25rem 4rem;
  background: var(--canvas);
}

.notebook-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.25rem 0.25rem 0.9rem;
  margin-bottom: 0.9rem;
  border-bottom: 1px solid var(--line);
}

.notebook-header__identity {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  flex: 1;
}

.notebook-header__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 10px;
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.notebook-header__title {
  min-width: 0;
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--ink-strong);
  font-size: 1.2rem;
  font-weight: 700;
}

.notebook-header__db {
  color: var(--muted);
  white-space: nowrap;
}

.notebook-header__meta,
.notebook-empty__actions,
.notebook-toolbar {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.notebook-toolbar {
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(249, 171, 0, 0.08), rgba(138, 180, 248, 0.06));
}

.notebook-toolbar p {
  margin: 0;
  color: var(--muted);
  font-size: 0.84rem;
  line-height: 1.5;
}

.notebook-blocks {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.drop-slot {
  height: 12px;
  border: none;
  border-radius: 999px;
  background: transparent;
  transition: background 140ms ease, transform 140ms ease;
}

.drop-slot--active {
  background: var(--accent-soft);
  transform: scaleY(1.2);
}

.notebook-empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 1.4rem;
  border: 1px dashed var(--line-strong);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.02);
}

.notebook-empty h3,
.notebook-empty p {
  margin: 0;
}

.notebook-empty p {
  color: var(--muted);
  max-width: 42rem;
  line-height: 1.6;
}

@media (max-width: 760px) {
  .notebook-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
