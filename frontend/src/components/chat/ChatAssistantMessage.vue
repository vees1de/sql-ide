<template>
  <article class="chat-assistant-message">
    <header class="chat-assistant-message__header">
      <span class="chat-assistant-message__state" :class="`chat-assistant-message__state--${stateClass}`">
        {{ stateLabel }}
      </span>
    </header>

    <p class="chat-assistant-message__text">{{ displayText }}</p>

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

    <section
      v-if="visibleActions.length || (payload?.mode_suggestion && payload.mode_suggestion_reason)"
      class="chat-assistant-message__actions"
    >
      <button
        v-for="action in visibleActions"
        :key="action.type"
        class="chat-assistant-message__icon-btn"
        :class="{ 'chat-assistant-message__icon-btn--primary': action.primary }"
        :disabled="action.disabled"
        type="button"
        :title="action.label"
        :aria-label="action.label"
        @click="handleAction(action.type)"
      >
        <svg v-if="action.type === 'show_run_button'" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path d="M4.5 3.3v7.4L10.8 7 4.5 3.3Z" fill="currentColor"/>
        </svg>
        <svg v-else-if="action.type === 'create_sql'" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path d="M7 2.2v9.6M2.2 7h9.6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
        </svg>
      </button>

      <button
        v-if="payload?.mode_suggestion && payload.mode_suggestion_reason"
        class="chat-assistant-message__icon-btn"
        type="button"
        :title="payload.mode_suggestion === 'thinking' ? 'Thinking' : 'Fast'"
        :aria-label="payload.mode_suggestion === 'thinking' ? 'Thinking' : 'Fast'"
        @click="$emit('switch-mode', payload.mode_suggestion)"
      >
        <svg v-if="payload.mode_suggestion === 'thinking'" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path d="M6.2 1.8a4.2 4.2 0 1 0 3.4 7.1h1.9l-.7 1.6-1.8.3" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M5.7 4.2h2.6M5.7 6h1.8" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
        </svg>
        <svg v-else width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path d="M7 2.2v9.6M2.2 7h9.6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
        </svg>
      </button>
    </section>

    <section v-if="showSqlSection" class="chat-assistant-message__sql">
      <SQLCell
        :content="sqlCellContent"
        :collapsed="sqlCollapsed"
        :busy="false"
        :show-explain-button="Boolean(payload?.sql)"
        :show-copy-button="Boolean(payload?.sql)"
        :show-toggle-sql-button="hasToggleSqlAction"
        @explain="emitExplain"
        @copy="copySql"
        @toggle-sql="sqlCollapsed = !sqlCollapsed"
      />
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
  (event: 'explain-sql', sql: string): void;
  (event: 'run-prepared'): void;
  (event: 'show-chart-preview'): void;
  (event: 'switch-mode', mode: ApiQueryMode): void;
}>();

const payload = computed<ApiChatStructuredPayload | null>(() => props.message.structured_payload);
const sqlCollapsed = ref(false);

watch(
  () => props.message.id,
  () => {
    sqlCollapsed.value = false;
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

const HIDDEN_ACTION_TYPES = new Set(['show_sql', 'save_report', 'show_chart_preview']);
const visibleActions = computed<ApiChatAction[]>(() =>
  (payload.value?.actions ?? []).filter(a => !HIDDEN_ACTION_TYPES.has(a.type))
);
const hasToggleSqlAction = computed(() =>
  Boolean(payload.value?.actions?.some(a => a.type === 'show_sql'))
);

const showSqlSection = computed(() => Boolean(payload.value?.sql));

const sqlCellContent = computed(() => ({
  sql: payload.value?.sql ?? '',
  explanation: '',
  warnings: []
}));

async function copySql() {
  const sql = payload.value?.sql?.trim();
  if (!sql) {
    return;
  }
  try {
    await navigator.clipboard.writeText(sql);
  } catch {
    /* ignore clipboard failures */
  }
}

function emitClarification(optionId: string) {
  emit('clarification', {
    clarificationId: clarificationId.value,
    optionId
  });
}

function emitExplain() {
  const sql = payload.value?.sql?.trim();
  if (!sql) {
    return;
  }
  emit('explain-sql', sql);
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
    case 'show_run_button':
      emit('run-prepared');
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
.chat-assistant-message__clarification-text {
  margin: 0;
  color: var(--ink);
  font-size: 0.84rem;
  line-height: 1.5;
  white-space: pre-wrap;
}

.chat-assistant-message__clarification {
  min-width: 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.03);
  display: grid;
  gap: 8px;
}

.chat-assistant-message__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chat-assistant-message__btn {
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid rgba(112, 59, 247, 0.22);
  border-radius: 999px;
  background: rgba(112, 59, 247, 0.14);
  color: var(--ink-strong);
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  transition:
    transform 120ms ease,
    border-color 160ms ease,
    background 160ms ease,
    color 160ms ease,
    box-shadow 160ms ease;
}

.chat-assistant-message__btn:hover:not(:disabled),
.chat-assistant-message__btn:focus-visible:not(:disabled) {
  border-color: rgba(112, 59, 247, 0.45);
  background: rgba(112, 59, 247, 0.22);
  color: #fff;
  box-shadow: 0 0 0 3px rgba(112, 59, 247, 0.14);
  outline: none;
  transform: translateY(-1px);
}

.chat-assistant-message__btn:active:not(:disabled) {
  transform: translateY(0);
  background: rgba(112, 59, 247, 0.18);
}

.chat-assistant-message__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}

.chat-assistant-message__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chat-assistant-message__icon-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--muted);
  cursor: pointer;
  transition:
    color 160ms ease,
    border-color 160ms ease,
    background 160ms ease;
}

.chat-assistant-message__icon-btn:hover:not(:disabled),
.chat-assistant-message__icon-btn:focus-visible:not(:disabled) {
  color: var(--ink-strong);
  border-color: rgba(112, 59, 247, 0.55);
  background: rgba(112, 59, 247, 0.12);
}

.chat-assistant-message__icon-btn--primary {
  color: #efe9ff;
  border-color: rgba(112, 59, 247, 0.7);
  background: rgba(112, 59, 247, 0.22);
}

.chat-assistant-message__icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
