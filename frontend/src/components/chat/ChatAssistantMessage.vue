<template>
  <article class="chat-assistant-message">
    <header class="chat-assistant-message__header">
      <span class="chat-assistant-message__state" :class="`chat-assistant-message__state--${stateClass}`">
        {{ stateLabel }}
      </span>
    </header>

    <p class="chat-assistant-message__text">{{ displayText }}</p>

    <section v-if="hasSemanticSummary" class="chat-assistant-message__semantic">
      <button
        class="chat-assistant-message__semantic-head"
        type="button"
        @click="semanticOpen = !semanticOpen"
      >
        <span>Semantic summary</span>
        <svg
          class="chat-assistant-message__semantic-chevron"
          :class="{ 'chat-assistant-message__semantic-chevron--open': semanticOpen }"
          viewBox="0 0 16 16" width="12" height="12"
          fill="none" stroke="currentColor" stroke-width="1.8"
          stroke-linecap="round" stroke-linejoin="round"
        >
          <path d="M4 6l4 4 4-4"/>
        </svg>
      </button>
      <template v-if="semanticOpen">
      <div class="chat-assistant-message__chips">
        <span v-if="payload?.semantic_parse?.metric" class="chat-assistant-message__chip">
          Метрика: {{ payload.semantic_parse.metric }}
        </span>
        <span
          v-for="dimension in payload?.semantic_parse?.dimensions ?? []"
          :key="dimension"
          class="chat-assistant-message__chip"
        >
          Измерение: {{ dimension }}
        </span>
        <span
          v-for="table in payload?.semantic_parse?.candidate_tables ?? []"
          :key="table"
          class="chat-assistant-message__chip chat-assistant-message__chip--muted"
        >
          Таблица: {{ table }}
        </span>
      </div>
      <p
        v-for="note in payload?.semantic_parse?.notes ?? []"
        :key="note"
        class="chat-assistant-message__semantic-note"
      >
        {{ note }}
      </p>
      </template>
    </section>

    <section v-if="clarificationQuestion" class="chat-assistant-message__clarification">
      <p class="chat-assistant-message__clarification-text">{{ clarificationQuestion }}</p>
      <div v-if="clarificationOptions.length" class="chat-assistant-message__chips">
        <button
          v-for="option in clarificationOptions"
          :key="option.id"
          class="chat-assistant-message__btn"
          type="button"
          @click="emitClarification(option.id)"
        >
          {{ option.label }}
        </button>
      </div>
    </section>

    <section v-if="visibleActions.length" class="chat-assistant-message__actions">
      <button
        v-for="action in visibleActions"
        :key="action.type"
        class="chat-assistant-message__btn"
        :class="{ 'chat-assistant-message__btn--secondary': !action.primary }"
        :disabled="action.disabled"
        type="button"
        @click="handleAction(action.type)"
      >
        {{ action.label }}
      </button>

      <button
        v-if="payload?.mode_suggestion && payload.mode_suggestion_reason"
        class="chat-assistant-message__btn chat-assistant-message__btn--secondary"
        type="button"
        @click="$emit('switch-mode', payload.mode_suggestion)"
      >
        {{ payload.mode_suggestion === 'thinking' ? 'Thinking' : 'Fast' }}
      </button>
    </section>

    <section v-if="showSqlSection" class="chat-assistant-message__sql">
      <SQLCell :content="sqlCellContent" :collapsed="sqlCollapsed" />
    </section>

    <section v-if="hasReasoning" class="chat-assistant-message__reasoning">
      <button
        class="chat-assistant-message__reasoning-toggle"
        type="button"
        :aria-expanded="!reasoningCollapsed"
        @click="reasoningCollapsed = !reasoningCollapsed"
      >
        <span>Agent trace</span>
        <span aria-hidden="true">{{ reasoningCollapsed ? '▾' : '▴' }}</span>
      </button>
      <div v-show="!reasoningCollapsed" class="chat-assistant-message__reasoning-body">
        <p v-for="line in reasoningLines" :key="line">{{ line }}</p>
      </div>
    </section>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import SQLCell from '@/components/cells/SQLCell.vue';
import type {
  ApiChatAction,
  ApiChatMessageRead,
  ApiChatStructuredPayload,
  ApiQueryMode
} from '@/api/types';

const props = defineProps<{
  message: ApiChatMessageRead;
}>();

const emit = defineEmits<{
  (event: 'apply-sql', sql: string): void;
  (event: 'prepare-sql'): void;
  (event: 'clarification', payload: { clarificationId: string; optionId?: string | null; text?: string | null }): void;
  (event: 'run-prepared'): void;
  (event: 'show-chart-preview'): void;
  (event: 'switch-mode', mode: ApiQueryMode): void;
}>();

const payload = computed<ApiChatStructuredPayload | null>(() => props.message.structured_payload);
const sqlCollapsed = ref(false);
const reasoningCollapsed = ref(true);
const semanticOpen = ref(false);

watch(
  () => props.message.id,
  () => {
    sqlCollapsed.value = false;
    reasoningCollapsed.value = true;
  }
);

const displayText = computed(() => payload.value?.assistant_message || props.message.text);

const stateLabel = computed(() => {
  switch (payload.value?.state) {
    case 'CLARIFYING':
      return 'Нужно уточнение';
    case 'SQL_READY':
      return 'SQL готов';
    case 'ERROR':
      return 'Ошибка';
    default:
      return 'Подготовка';
  }
});

const stateClass = computed(() => {
  switch (payload.value?.state) {
    case 'CLARIFYING':
      return 'clarifying';
    case 'SQL_READY':
      return 'ready';
    case 'ERROR':
      return 'error';
    default:
      return 'drafting';
  }
});

const clarificationQuestion = computed(
  () => payload.value?.clarification?.question || payload.value?.clarification_question || null
);

const clarificationId = computed(
  () => payload.value?.clarification?.clarification_id || 'clarification:pending'
);

const clarificationOptions = computed(
  () => payload.value?.clarification?.options || payload.value?.clarification_options || []
);

const visibleActions = computed<ApiChatAction[]>(() => payload.value?.actions ?? []);

const hasSemanticSummary = computed(() => {
  const semantic = payload.value?.semantic_parse;
  return Boolean(
    semantic &&
    (semantic.metric ||
      semantic.dimensions.length ||
      semantic.candidate_tables.length ||
      semantic.notes.length)
  );
});

const warnings = computed(() => [
  ...(payload.value?.warnings ?? []),
  ...(payload.value?.interpretation.ambiguities ?? []).map((item) => `Неоднозначность: ${item.replaceAll('_', ' ')}`)
]);

const showSqlSection = computed(() => Boolean(payload.value?.sql));
const hasReasoning = computed(() => reasoningLines.value.length > 0);

const reasoningLines = computed(() => {
  const lines: string[] = [];
  if (payload.value?.confidence_level) {
    lines.push(`Уверенность SQL: ${payload.value.confidence_level}`);
  }
  if (payload.value?.tables_used?.length) {
    lines.push(`Таблицы: ${payload.value.tables_used.map((item) => item.table).join(', ')}`);
  }
  if (payload.value?.semantic_parse?.unresolved_terms?.length) {
    lines.push(
      `Требуют уточнения: ${payload.value.semantic_parse.unresolved_terms.map((item) => item.term).join(', ')}`
    );
  }
  if (payload.value?.debug_trace?.length) {
    lines.push(...payload.value.debug_trace.map((item) => `${item.stage}: ${item.detail}`));
  }
  if (warnings.value.length) {
    lines.push(`Предупреждения: ${warnings.value.join('; ')}`);
  }
  return lines;
});

const sqlCellContent = computed(() => ({
  sql: payload.value?.sql ?? '',
  explanation: '',
  warnings: warnings.value
}));

function emitClarification(optionId: string) {
  emit('clarification', {
    clarificationId: clarificationId.value,
    optionId
  });
}

function handleAction(type: ApiChatAction['type']) {
  switch (type) {
    case 'create_sql':
      if (payload.value?.sql) {
        emit('apply-sql', payload.value.sql);
      } else {
        emit('prepare-sql');
      }
      break;
    case 'show_sql':
      sqlCollapsed.value = !sqlCollapsed.value;
      break;
    case 'show_run_button':
      emit('run-prepared');
      break;
    case 'show_chart_preview':
      emit('show-chart-preview');
      break;
    case 'save_report':
      emit('show-chart-preview');
      break;
  }
}
</script>

<style scoped lang="scss">
.chat-assistant-message {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.16);
  display: grid;
  gap: 10px;
}

.chat-assistant-message__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chat-assistant-message__state {
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--line);
  display: inline-flex;
  align-items: center;
  font-size: 0.72rem;
  color: var(--muted);
}

.chat-assistant-message__state--clarifying {
  border-color: rgba(255, 184, 77, 0.55);
  background: rgba(255, 184, 77, 0.12);
  color: #ffd79a;
}

.chat-assistant-message__state--ready {
  border-color: rgba(67, 176, 42, 0.55);
  background: rgba(67, 176, 42, 0.14);
  color: #c4f0b8;
}

.chat-assistant-message__state--error {
  border-color: rgba(255, 107, 107, 0.55);
  background: rgba(255, 107, 107, 0.14);
  color: #ffb3b3;
}

.chat-assistant-message__state--drafting {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
}

.chat-assistant-message__text,
.chat-assistant-message__clarification-text,
.chat-assistant-message__semantic-note,
.chat-assistant-message__reasoning-body p {
  margin: 0;
  color: var(--ink);
  font-size: 0.84rem;
  line-height: 1.5;
  white-space: pre-wrap;
}

.chat-assistant-message__semantic,
.chat-assistant-message__clarification,
.chat-assistant-message__reasoning {
  min-width: 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.03);
  display: grid;
  gap: 8px;
}

.chat-assistant-message__semantic-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  width: 100%;
  border: none;
  background: none;
  padding: 0;
  cursor: pointer;
  color: var(--muted);
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  text-align: left;
}

.chat-assistant-message__semantic-chevron {
  flex-shrink: 0;
  transition: transform 180ms ease;
  color: var(--muted);
}

.chat-assistant-message__semantic-chevron--open {
  transform: rotate(180deg);
}

.chat-assistant-message__chips,
.chat-assistant-message__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chat-assistant-message__chip {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(112, 59, 247, 0.16);
  color: var(--ink-strong);
  font-size: 0.72rem;
}

.chat-assistant-message__chip--muted {
  background: rgba(255, 255, 255, 0.06);
  color: var(--muted);
}

.chat-assistant-message__btn {
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(112, 59, 247, 0.18);
  color: var(--ink-strong);
  font-size: 0.74rem;
}

.chat-assistant-message__btn--secondary {
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
}

.chat-assistant-message__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-assistant-message__reasoning-toggle {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--ink);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0;
  cursor: pointer;
}

.chat-assistant-message__reasoning-body {
  display: grid;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
}

.chat-assistant-message__reasoning-body p {
  min-width: 0;
  overflow-wrap: break-word;
  word-break: break-word;
}
</style>
