<template>
  <article
    class="turn"
    :class="{ 'turn--running': running }"
  >
    <div
      v-if="turn.prompt"
      class="turn__row turn__row--prompt"
    >
      <div class="turn__avatar turn__avatar--prompt" aria-hidden="true">
        <span>Вы</span>
      </div>

      <div
        class="turn__prompt"
        :class="{ 'turn__prompt--selected': isPromptSelected }"
        @click="$emit('select-cell', turn.prompt.id)"
      >
        <div class="turn__head">
          <div>
            <p class="eyebrow">Запрос</p>
            <strong>Запрос на естественном языке</strong>
          </div>
          <span class="turn__index">[{{ turn.prompt.order }}]</span>
        </div>

        <PromptCell :content="promptContent(turn.prompt)" />
      </div>
    </div>

    <div
      v-if="hasResponse"
      class="turn__row turn__row--response"
    >
      <div class="turn__avatar turn__avatar--response" aria-hidden="true">
        <span>SQL</span>
      </div>

      <div
        class="turn__response"
        :class="{ 'turn__response--selected': isResponseSelected }"
      >
        <div class="turn__head">
          <div>
            <p class="eyebrow">Ответ</p>
            <strong>{{ responseTitle }}</strong>
          </div>
          <div class="turn__badges">
            <span v-if="rowCountLabel" class="pill pill--ghost">{{ rowCountLabel }}</span>
            <span class="pill" :class="hasResult ? 'pill--soft' : 'pill--accent'">
              {{ hasResult ? 'Выполнено' : 'Ждёт ввод' }}
            </span>
          </div>
        </div>

        <section
          v-if="turn.sqlCell"
          class="turn__section"
          :class="{ 'turn__section--selected': selectedCellId === turn.sqlCell.id }"
          @click="$emit('select-cell', turn.sqlCell.id)"
        >
          <div class="turn__section-label">SQL</div>
          <SQLCell :content="sqlContent(turn.sqlCell)" />
        </section>

        <section
          v-if="hasResultTabs"
          class="turn__section"
          :class="{ 'turn__section--selected': isResultSelected }"
        >
          <div class="turn__result-head">
            <div class="turn__section-label">Результат</div>
            <div class="turn__tabs" role="tablist" aria-label="Result view">
              <button
                v-if="turn.tableCell"
                class="turn__tab"
                :class="{ 'turn__tab--active': activeResultTab === 'table' }"
                type="button"
                role="tab"
                :aria-selected="activeResultTab === 'table'"
                @click="setResultTab('table')"
              >
                Таблица
              </button>
              <button
                v-if="turn.chartCell"
                class="turn__tab"
                :class="{ 'turn__tab--active': activeResultTab === 'chart' }"
                type="button"
                role="tab"
                :aria-selected="activeResultTab === 'chart'"
                @click="setResultTab('chart')"
              >
                График
              </button>
            </div>
          </div>

          <div
            class="turn__result-body"
            @click="selectActiveResultCell"
          >
            <TableCell
              v-if="activeResultTab === 'table' && turn.tableCell"
              :content="tableContent(turn.tableCell)"
            />
            <ChartCell
              v-else-if="activeResultTab === 'chart' && turn.chartCell"
              :content="chartContent(turn.chartCell)"
            />
          </div>
        </section>

        <section
          v-if="turn.clarificationCell"
          class="turn__section"
          :class="{ 'turn__section--selected': selectedCellId === turn.clarificationCell.id }"
          @click="$emit('select-cell', turn.clarificationCell.id)"
        >
          <div class="turn__section-label">Уточнение</div>
          <ClarificationCell
            :content="clarificationContent(turn.clarificationCell)"
            :selected-answer="clarificationAnswers[turn.clarificationCell.id]"
            @answer="$emit('answer-clarification', turn.clarificationCell.id, $event)"
          />
        </section>

        <section
          v-if="turn.insightCell"
          class="turn__section"
          :class="{ 'turn__section--selected': selectedCellId === turn.insightCell.id }"
          @click="$emit('select-cell', turn.insightCell.id)"
        >
          <div class="turn__section-label">Вывод</div>
          <InsightCell :content="insightContent(turn.insightCell)" />
        </section>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import ChartCell from '@/components/cells/ChartCell.vue';
import ClarificationCell from '@/components/cells/ClarificationCell.vue';
import InsightCell from '@/components/cells/InsightCell.vue';
import PromptCell from '@/components/cells/PromptCell.vue';
import SQLCell from '@/components/cells/SQLCell.vue';
import TableCell from '@/components/cells/TableCell.vue';
import type {
  ChartCellContent,
  ClarificationCellContent,
  InsightCellContent,
  NotebookCell,
  NotebookConversationTurn,
  PromptCellContent,
  SqlCellContent,
  TableCellContent
} from '@/types/app';

const props = defineProps<{
  clarificationAnswers: Record<string, string>;
  running: boolean;
  selectedCellId: string;
  turn: NotebookConversationTurn;
}>();

const emit = defineEmits<{
  (event: 'answer-clarification', cellId: string, optionId: string): void;
  (event: 'select-cell', cellId: string): void;
}>();

const activeResultTab = ref<'table' | 'chart'>('table');

const responseCellIds = computed(() =>
  props.turn.cellIds.filter((cellId) => cellId !== props.turn.prompt?.id)
);

const isPromptSelected = computed(
  () => props.turn.prompt?.id === props.selectedCellId
);

const isResponseSelected = computed(() =>
  responseCellIds.value.includes(props.selectedCellId)
);

const isResultSelected = computed(
  () =>
    props.selectedCellId === props.turn.tableCell?.id ||
    props.selectedCellId === props.turn.chartCell?.id
);

const hasResult = computed(
  () => Boolean(props.turn.tableCell || props.turn.chartCell)
);

const hasResponse = computed(
  () =>
    Boolean(
      props.turn.sqlCell ||
        props.turn.tableCell ||
        props.turn.chartCell ||
        props.turn.insightCell ||
        props.turn.clarificationCell ||
        props.turn.otherCells.length
    )
);

const hasResultTabs = computed(
  () => Boolean(props.turn.tableCell || props.turn.chartCell)
);

const responseTitle = computed(() => {
  if (props.turn.clarificationCell && !hasResult.value && !props.turn.sqlCell) {
    return 'Нужно уточнение перед SQL'
  }

  return 'Сгенерированный SQL и результат'
});

const rowCountLabel = computed(() => {
  const meta =
    props.turn.tableCell?.meta ??
    props.turn.chartCell?.meta ??
    props.turn.sqlCell?.meta;

  if (typeof meta?.rowCount === 'number') {
    return `${meta.rowCount} строк`;
  }

  return null;
});

function setDefaultResultTab() {
  if (props.turn.tableCell) {
    activeResultTab.value = 'table';
    return;
  }
  if (props.turn.chartCell) {
    activeResultTab.value = 'chart';
  }
}

function setResultTab(tab: 'table' | 'chart') {
  activeResultTab.value = tab;

  if (tab === 'table' && props.turn.tableCell) {
    emit('select-cell', props.turn.tableCell.id);
    return;
  }

  if (tab === 'chart' && props.turn.chartCell) {
    emit('select-cell', props.turn.chartCell.id);
  }
}

function selectActiveResultCell() {
  if (activeResultTab.value === 'table' && props.turn.tableCell) {
    emit('select-cell', props.turn.tableCell.id);
    return;
  }

  if (activeResultTab.value === 'chart' && props.turn.chartCell) {
    emit('select-cell', props.turn.chartCell.id);
  }
}

function promptContent(cell: NotebookCell) {
  return cell.content as PromptCellContent;
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
  () => `${props.turn.id}:${Boolean(props.turn.tableCell)}:${Boolean(props.turn.chartCell)}`,
  () => {
    setDefaultResultTab();
  },
  { immediate: true }
);
</script>

<style scoped lang="scss">
.turn {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.turn__row {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 0.9rem;
  align-items: flex-start;
}

.turn__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  min-height: 42px;
  border-radius: 14px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.turn__avatar--prompt {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.turn__avatar--response {
  background: var(--link-soft);
  color: var(--link-strong);
}

.turn__prompt,
.turn__response {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 18px;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

.turn__prompt {
  padding: 1rem 1.05rem;
  background: linear-gradient(180deg, rgba(249, 171, 0, 0.12), rgba(249, 171, 0, 0.06));
  cursor: pointer;
}

.turn__response {
  padding: 1rem 1.05rem;
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.turn__prompt:hover,
.turn__response:hover {
  border-color: var(--line-strong);
}

.turn__prompt--selected,
.turn__response--selected,
.turn__section--selected {
  border-color: rgba(138, 180, 248, 0.45);
  box-shadow: 0 0 0 1px rgba(138, 180, 248, 0.18);
}

.turn--running .turn__response {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent-soft), var(--shadow-soft);
}

.turn__head,
.turn__result-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.85rem;
}

.turn__head strong {
  display: block;
  margin-top: 0.15rem;
  color: var(--ink-strong);
  font-size: 0.98rem;
}

.turn__badges {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.turn__index {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  color: var(--muted);
}

.turn__section {
  margin-top: 0.95rem;
  padding-top: 0.95rem;
  border-top: 1px solid var(--line);
  border-radius: 14px;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

.turn__section--selected {
  padding: 0.95rem 0.8rem 0 0.8rem;
  margin: 0.95rem -0.8rem 0;
  border-top-color: transparent;
}

.turn__section-label {
  margin-bottom: 0.6rem;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 0.74rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.turn__tabs {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.22rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--bg-elev);
}

.turn__tab {
  min-height: 2rem;
  padding: 0.35rem 0.8rem;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 600;
}

.turn__tab--active {
  background: var(--link-soft);
  color: var(--link-strong);
}

.turn__result-body {
  margin-top: 0.75rem;
  cursor: pointer;
}

@media (max-width: 760px) {
  .turn__row {
    grid-template-columns: 1fr;
    gap: 0.55rem;
  }

  .turn__avatar {
    width: auto;
    min-height: 2rem;
    padding: 0 0.75rem;
    justify-self: start;
  }

  .turn__head,
  .turn__result-head {
    flex-direction: column;
  }
}
</style>
