<template>
  <article class="chat-assistant-message">
    <p v-if="primaryText" class="chat-assistant-message__text">{{ primaryText }}</p>

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

    <section
      v-if="visibleActions.length || (payload?.mode_suggestion && payload.mode_suggestion_reason)"
      class="chat-assistant-message__actions"
    >
      <button
        v-for="action in visibleActions"
        :key="action.type"
        class="chat-assistant-message__icon-btn"
        :disabled="action.disabled"
        type="button"
        @click="handleAction(action.type)"
      >
        <svg
          v-if="action.type === 'create_sql'"
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M7 2.5v9M2.5 7h9"
            stroke="currentColor"
            stroke-width="1.4"
            stroke-linecap="round"
          />
        </svg>
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
      <SQLCell
        :content="sqlCellContent"
        :collapsed="sqlCollapsed"
        :busy="false"
        :show-explain-button="Boolean(payload?.sql)"
        :show-copy-button="Boolean(payload?.sql)"
        :show-toggle-sql-button="hasToggleSqlAction"
        :show-run-button="hasRunAction"
        @explain="emitExplain"
        @copy="copySql"
        @toggle-sql="sqlCollapsed = !sqlCollapsed"
        @run="emit('run-prepared')"
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

const clarificationQuestion = computed(
  () => payload.value?.clarification?.question || payload.value?.clarification_question || null
);

const primaryText = computed(() => {
  const messageText = displayText.value?.trim() ?? '';
  const questionText = clarificationQuestion.value?.trim() ?? '';

  if (!questionText) {
    return messageText;
  }
  if (!messageText || messageText === questionText) {
    return questionText;
  }
  return `${messageText}\n\n${questionText}`;
});

const clarificationId = computed(
  () => payload.value?.clarification?.clarification_id || 'clarification:pending'
);

const clarificationOptions = computed(
  () => payload.value?.clarification?.options || payload.value?.clarification_options || []
);

const HIDDEN_ACTION_TYPES = new Set(['show_sql', 'save_report', 'show_chart_preview', 'show_run_button']);
const visibleActions = computed<ApiChatAction[]>(() =>
  (payload.value?.actions ?? []).filter(a => !HIDDEN_ACTION_TYPES.has(a.type))
);
const hasToggleSqlAction = computed(() =>
  Boolean(payload.value?.actions?.some(a => a.type === 'show_sql'))
);
const hasRunAction = computed(() =>
  Boolean(payload.value?.actions?.some(a => a.type === 'show_run_button' && !a.disabled))
);

const warnings = computed(() => [
  ...(payload.value?.warnings ?? []),
  ...(payload.value?.interpretation.ambiguities ?? []).map((item) => `Неоднозначность: ${item.replaceAll('_', ' ')}`)
]);

const showSqlSection = computed(() => Boolean(payload.value?.sql));

const sqlCellContent = computed(() => ({
  sql: payload.value?.sql ?? '',
  explanation: '',
  warnings: warnings.value
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
  }
}
</script>

<style scoped lang="scss">
.chat-assistant-message {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.16);
  display: grid;
  gap: 10px;
}

.chat-assistant-message__text {
  margin: 0;
  color: var(--ink);
  font-size: 0.84rem;
  line-height: 1.5;
  white-space: pre-wrap;
}

.chat-assistant-message__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chat-assistant-message__actions {
  display: none;
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
</style>
