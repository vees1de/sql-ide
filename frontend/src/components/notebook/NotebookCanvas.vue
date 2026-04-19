<template>
  <main
    ref="canvasRef"
    class="notebook-canvas"
  >
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
        <span class="pill pill--ghost">{{ conversationTurns.length }} запросов</span>
        <span class="pill pill--ghost">{{ notebook.summary.lastRunLabel }}</span>
      </div>
    </section>

    <section class="notebook-stream">
      <div
        v-if="conversationTurns.length === 0"
        class="notebook-empty"
      >
        <span class="pill pill--accent">Empty notebook</span>
        <p>
          Введите запрос ниже. Notebook покажет prompt пользователя, затем
          сгенерированный SQL и результат с переключением между таблицей и
          графиком.
        </p>
      </div>

      <div
        v-for="turn in conversationTurns"
        :key="turn.id"
        class="notebook-stream__turn"
        :data-turn-id="turn.id"
      >
        <NotebookTurn
          :clarification-answers="clarificationAnswers"
          :running="isRunning && turn.cellIds.includes(selectedCellId)"
          :selected-cell-id="selectedCellId"
          :turn="turn"
          @answer-clarification="onAnswerClarification"
          @select-cell="$emit('select-cell', $event)"
        />
      </div>
    </section>

    <section class="composer">
      <div class="composer__inner">
        <div class="composer__gutter">
          <button
            class="composer__run"
            type="button"
            :disabled="!canSubmitPrompt || isSubmittingPrompt"
            @click="$emit('submit-prompt')"
            :title="isSubmittingPrompt ? 'Running…' : 'Run prompt'"
          >
            <svg v-if="!isSubmittingPrompt" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M6 4.5v15l13-7.5z"/></svg>
            <span v-else class="composer__spinner" aria-hidden="true"></span>
          </button>
          <span class="composer__label">prompt</span>
        </div>

        <textarea
          :value="draftPrompt"
          class="composer__input"
          rows="2"
          placeholder="Например: Покажи выручку по регионам за текущий квартал"
          @input="onDraftInput"
          @keydown.enter.meta="onEnterSubmit"
          @keydown.enter.ctrl="onEnterSubmit"
        ></textarea>
      </div>
      <div class="composer__hint">
        <span>⌘/Ctrl + Enter чтобы запустить</span>
        <span>{{ conversationTurns.length }} запросов в notebook</span>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import NotebookTurn from '@/components/notebook/NotebookTurn.vue';
import type {
  Notebook,
  NotebookCell,
  NotebookConversationTurn
} from '@/types/app';

const props = defineProps<{
  canSubmitPrompt: boolean;
  clarificationAnswers: Record<string, string>;
  databaseName: string;
  draftPrompt: string;
  isRunning: boolean;
  isSubmittingPrompt: boolean;
  notebook: Notebook;
  selectedCellId: string;
  visibleCells: NotebookCell[];
}>();

const emit = defineEmits<{
  (event: 'answer-clarification', cellId: string, optionId: string): void;
  (event: 'rename-notebook', title: string): void;
  (event: 'select-cell', cellId: string): void;
  (event: 'submit-prompt'): void;
  (event: 'update-draft-prompt', value: string): void;
}>();

const canvasRef = ref<HTMLElement | null>(null);
const conversationTurns = computed(() => groupCellsIntoTurns(props.visibleCells));

function onTitleChange(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.value.trim()) {
    emit('rename-notebook', target.value.trim());
  }
}

function onDraftInput(event: Event) {
  const target = event.target as HTMLTextAreaElement;
  emit('update-draft-prompt', target.value);
}

function onEnterSubmit(event: KeyboardEvent) {
  if (props.canSubmitPrompt && !props.isSubmittingPrompt) {
    event.preventDefault();
    emit('submit-prompt');
  }
}

function onAnswerClarification(cellId: string, optionId: string) {
  emit('answer-clarification', cellId, optionId);
}

function createTurn(id: string, order: number): NotebookConversationTurn {
  return {
    id,
    order,
    cellIds: [],
    prompt: null,
    otherCells: []
  };
}

function attachCellToTurn(turn: NotebookConversationTurn, cell: NotebookCell) {
  turn.cellIds.push(cell.id);

  if (cell.type === 'prompt') {
    turn.prompt = cell;
    return;
  }

  if (cell.type === 'sql' && !turn.sqlCell) {
    turn.sqlCell = cell;
    return;
  }

  if (cell.type === 'table' && !turn.tableCell) {
    turn.tableCell = cell;
    return;
  }

  if (cell.type === 'chart' && !turn.chartCell) {
    turn.chartCell = cell;
    return;
  }

  if (cell.type === 'insight' && !turn.insightCell) {
    turn.insightCell = cell;
    return;
  }

  if (cell.type === 'clarification' && !turn.clarificationCell) {
    turn.clarificationCell = cell;
    return;
  }

  turn.otherCells.push(cell);
}

function groupCellsIntoTurns(cells: NotebookCell[]): NotebookConversationTurn[] {
  const turns: NotebookConversationTurn[] = [];
  let currentTurn: NotebookConversationTurn | null = null;

  for (const cell of cells) {
    if (cell.type === 'prompt') {
      currentTurn = createTurn(cell.id, cell.order);
      attachCellToTurn(currentTurn, cell);
      turns.push(currentTurn);
      continue;
    }

    if (!currentTurn) {
      currentTurn = createTurn(`system-${cell.id}`, cell.order);
      turns.push(currentTurn);
    }

    attachCellToTurn(currentTurn, cell);
  }

  return turns;
}

watch(
  () => conversationTurns.value.map((turn) => turn.id).join(','),
  async () => {
    await nextTick();
    const lastTurn = conversationTurns.value[conversationTurns.value.length - 1];
    if (!lastTurn || !canvasRef.value) {
      return;
    }

    const element = canvasRef.value.querySelector<HTMLElement>(
      `[data-turn-id="${lastTurn.id}"]`
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
  padding: 1rem 1.25rem 7rem;
  background: var(--canvas);
  position: relative;
}

.notebook-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.25rem 0.25rem 0.9rem;
  margin-bottom: 0.75rem;
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
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.notebook-header__title {
  flex: 1;
  min-width: 0;
  padding: 0.25rem 0.35rem;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-strong);
  font-size: 1.05rem;
  font-weight: 600;
}

.notebook-header__title:hover {
  border-color: var(--line-strong);
}

.notebook-header__title:focus {
  outline: none;
  border-color: var(--link);
  background: var(--bg-elev);
}

.notebook-header__db {
  color: var(--muted);
  font-size: 0.82rem;
  white-space: nowrap;
}

.notebook-header__meta {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
}

.notebook-stream {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  max-width: 1100px;
  margin: 0 auto;
}

.notebook-stream__turn {
  width: 100%;
}

.notebook-empty {
  padding: 1rem 1.1rem;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--muted);
}

.notebook-empty p {
  margin: 0.5rem 0 0;
  font-size: 0.88rem;
  line-height: 1.55;
}

.composer {
  position: sticky;
  bottom: 1rem;
  margin: 1.2rem auto 0;
  max-width: 1100px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-hover);
  overflow: hidden;
  backdrop-filter: blur(8px);
}

.composer__inner {
  display: grid;
  grid-template-columns: 66px 1fr;
  gap: 0.5rem;
  padding: 0.6rem 0.7rem 0.5rem;
  align-items: flex-start;
}

.composer__gutter {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  padding-top: 0.25rem;
}

.composer__run {
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 999px;
  background: var(--accent);
  color: #1a1d24;
  transition: background 140ms ease, transform 140ms ease;
}

.composer__run:hover:not(:disabled) {
  background: var(--accent-strong);
}

.composer__run:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.composer__label {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--muted-2);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.composer__spinner {
  width: 14px;
  height: 14px;
  border-radius: 999px;
  border: 2px solid rgba(26, 29, 36, 0.25);
  border-top-color: #1a1d24;
  animation: spin 700ms linear infinite;
}

.composer__input {
  width: 100%;
  padding: 0.6rem 0.7rem;
  background: var(--canvas);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  color: var(--ink);
  font-family: var(--font-mono);
  font-size: 0.88rem;
  line-height: 1.55;
  resize: vertical;
  min-height: 2.6rem;
}

.composer__input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.composer__input::placeholder {
  color: var(--muted-2);
  font-family: inherit;
}

.composer__hint {
  display: flex;
  justify-content: space-between;
  padding: 0.3rem 0.8rem 0.5rem 4.8rem;
  color: var(--muted-2);
  font-size: 0.72rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 760px) {
  .notebook-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .composer__hint {
    padding-left: 0.8rem;
  }
}
</style>
