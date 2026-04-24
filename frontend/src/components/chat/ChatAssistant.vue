<template>
  <section class="chat-assistant">
    <div ref="scrollRef" class="chat-assistant__feed">
      <template v-if="messages.length">
        <template
          v-for="message in messages"
          :key="message.id"
        >
          <ChatUserMessage
            v-if="message.role === 'user'"
            :message="message"
          />

          <div v-else class="chat-assistant__assistant-wrap">
            <section
              v-if="hasReasoning(message)"
              class="chat-assistant__reasoning-panel"
            >
              <button
                class="chat-assistant__reasoning-toggle"
                type="button"
                :aria-expanded="isReasoningOpen(message.id)"
                @click="toggleReasoning(message.id)"
              >
                <span>Показать процесс размышления</span>
                <span aria-hidden="true">
                  {{ isReasoningOpen(message.id) ? '▴' : '▾' }}
                </span>
              </button>

              <div v-show="isReasoningOpen(message.id)" class="chat-assistant__reasoning-body">
                <div v-if="hasUnderstanding(message)" class="chat-assistant__semantic-summary">
                  <p class="chat-assistant__semantic-title">Как я понял запрос</p>
                  <p v-if="understandingSummary(message)" class="chat-assistant__semantic-lead">
                    {{ understandingSummary(message) }}
                  </p>
                  <p v-if="taskSummary(message)" class="chat-assistant__semantic-task">
                    Задача: {{ taskSummary(message) }}
                  </p>

                  <p v-if="semanticIntentSummary(message)" class="chat-assistant__semantic-note">
                    {{ semanticIntentSummary(message) }}
                  </p>

                  <p class="chat-assistant__semantic-title">Semantic summary</p>
                  <div class="chat-assistant__chips">
                    <span
                      v-for="item in semanticSummaryItems(message)"
                      :key="item"
                      class="chat-assistant__chip"
                    >
                      {{ item }}
                    </span>
                  </div>
                  <p
                    v-for="note in semanticNotes(message)"
                    :key="note"
                    class="chat-assistant__semantic-note"
                  >
                    {{ note }}
                  </p>
                </div>

                <div v-if="reasoningLines(message).length" class="chat-assistant__reasoning-lines">
                  <p v-for="line in reasoningLines(message)" :key="line">{{ line }}</p>
                </div>

                <div v-if="warnings(message).length" class="sql-cell__warnings">
                  <span
                    v-for="warning in warnings(message)"
                    :key="warning"
                    class="pill pill--ghost"
                  >
                    {{ warning }}
                  </span>
                </div>
              </div>
            </section>

            <ChatAssistantMessage
              :message="message"
              @apply-sql="$emit('apply-sql', $event)"
              @explain-sql="$emit('explain-sql', $event)"
              @prepare-sql="$emit('prepare-sql')"
              @clarification="$emit('clarification', $event)"
              @run-prepared="$emit('run-prepared')"
              @show-chart-preview="$emit('show-chart-preview')"
              @switch-mode="$emit('set-query-mode', $event)"
            />
          </div>
        </template>
      </template>
      <div v-else-if="!busy" class="chat-assistant__empty">
        Чем я могу помочь?
      </div>
      <ChatUserMessage
        v-if="busy && pendingMessage"
        :message="pendingMessage"
      />
      <div v-if="busy" class="chat-assistant__loader">
        <span class="chat-assistant__dot" />
        <span class="chat-assistant__dot" />
        <span class="chat-assistant__dot" />
      </div>
    </div>

    <ChatInput
      v-model="draft"
      :busy="busy"
      :query-mode="queryMode"
      :model-alias="llmModelAlias"
      :model-aliases="llmModelAliases"
      placeholder="Чем я могу помочь?"
      @update:queryMode="$emit('set-query-mode', $event)"
      @update:modelAlias="$emit('set-llm-model-alias', $event)"
      @send="submit"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import ChatAssistantMessage from '@/components/chat/ChatAssistantMessage.vue';
import ChatInput from '@/components/chat/ChatInput.vue';
import ChatUserMessage from '@/components/chat/ChatUserMessage.vue';
import type { ApiChatMessageRead, ApiChatStructuredPayload, ApiQueryMode } from '@/api/types';

const props = withDefaults(
  defineProps<{
    messages: ApiChatMessageRead[];
    busy: boolean;
    pendingUserMessage?: string;
    queryMode?: ApiQueryMode;
    llmModelAlias?: string;
    llmModelAliases?: string[];
  }>(),
  {
    pendingUserMessage: '',
    queryMode: 'fast',
    llmModelAlias: 'gpt120',
    llmModelAliases: () => ['gpt120']
  }
);

const emit = defineEmits<{
  (event: 'send', text: string, mode: ApiQueryMode): void;
  (event: 'apply-sql', sql: string): void;
  (event: 'explain-sql', sql: string): void;
  (event: 'prepare-sql'): void;
  (event: 'clarification', payload: { clarificationId: string; optionId?: string | null; text?: string | null }): void;
  (event: 'run-prepared'): void;
  (event: 'show-chart-preview'): void;
  (event: 'set-query-mode', mode: ApiQueryMode): void;
  (event: 'set-llm-model-alias', alias: string): void;
}>();

const draft = ref('');
const scrollRef = ref<HTMLElement | null>(null);
const openReasoning = ref<Record<string, boolean>>({});
const pendingMessage = computed<ApiChatMessageRead | null>(() => {
  const text = props.pendingUserMessage?.trim();
  if (!text) {
    return null;
  }

  return {
    id: 'pending-user-message',
    session_id: 'pending',
    role: 'user',
    text,
    structured_payload: null,
    created_at: new Date().toISOString()
  };
});

async function scrollToBottom() {
  await nextTick();
  scrollRef.value?.scrollTo({
    top: scrollRef.value.scrollHeight,
    behavior: 'smooth'
  });
}

watch(
  () => props.messages.length,
  () => {
    void scrollToBottom();
  }
);

watch(
  () => props.busy,
  () => {
    void scrollToBottom();
  }
);

watch(
  () => props.pendingUserMessage,
  () => {
    void scrollToBottom();
  }
);

onMounted(() => {
  void scrollToBottom();
});

function submit() {
  const text = draft.value.trim();
  if (!text) {
    return;
  }
  emit('send', text, props.queryMode);
  draft.value = '';
}

function payloadOf(message: ApiChatMessageRead): ApiChatStructuredPayload | null {
  return message.structured_payload;
}

function hasReasoning(message: ApiChatMessageRead) {
  return (
    reasoningLines(message).length > 0 ||
    semanticSummaryItems(message).length > 0 ||
    Boolean(understandingSummary(message) || taskSummary(message) || semanticIntentSummary(message)) ||
    warnings(message).length > 0
  );
}

function hasUnderstanding(message: ApiChatMessageRead) {
  return Boolean(understandingSummary(message) || taskSummary(message) || semanticIntentSummary(message));
}

function isReasoningOpen(messageId: string) {
  return Boolean(openReasoning.value[messageId]);
}

function toggleReasoning(messageId: string) {
  openReasoning.value = {
    ...openReasoning.value,
    [messageId]: !openReasoning.value[messageId]
  };
}

function reasoningLines(message: ApiChatMessageRead) {
  const payload = payloadOf(message);
  const lines: string[] = [];
  if (!payload) {
    return lines;
  }
  if (payload.confidence_level) {
    lines.push(`Уверенность SQL: ${payload.confidence_level}`);
  }
  if (payload.tables_used?.length) {
    lines.push(`Таблицы: ${payload.tables_used.map((item) => item.table).join(', ')}`);
  }
  if (payload.semantic_parse?.unresolved_terms?.length) {
    lines.push(
      `Требуют уточнения: ${payload.semantic_parse.unresolved_terms.map((item) => item.term).join(', ')}`
    );
  }
  if (payload.debug_trace?.length) {
    lines.push(...payload.debug_trace.map((item) => `${item.stage}: ${item.detail}`));
  }
  return lines;
}

function semanticSummaryItems(message: ApiChatMessageRead) {
  const payload = payloadOf(message);
  const semantic = payload?.semantic_parse;
  if (!semantic) {
    return [];
  }

  return [
    semantic.metric ? `Метрика: ${semantic.metric}` : '',
    ...(semantic.dimensions ?? []).map((dimension) => `Измерение: ${dimension}`),
    ...(semantic.candidate_tables ?? []).map((table) => `Таблица: ${table}`)
  ].filter(Boolean);
}

function semanticIntentSummary(message: ApiChatMessageRead) {
  return payloadOf(message)?.semantic_parse?.intent_summary ?? null;
}

function understandingSummary(message: ApiChatMessageRead) {
  const payload = payloadOf(message);
  const semantic = payload?.semantic_parse;
  if (!semantic) {
    return null;
  }

  const parts: string[] = [];
  if (semantic.metric) {
    parts.push(`метрика ${semantic.metric}`);
  }
  if (semantic.dimensions?.length) {
    parts.push(`группировка по ${semantic.dimensions.join(', ')}`);
  }
  if (semantic.date_range?.kind) {
    parts.push(`период ${semantic.date_range.kind}`);
  }
  if (semantic.comparison) {
    parts.push(`сравнение ${semantic.comparison}`);
  }

  return parts.length ? parts.join(', ') : null;
}

function taskSummary(message: ApiChatMessageRead) {
  const payload = payloadOf(message);
  const semantic = payload?.semantic_parse;
  if (!semantic) {
    return null;
  }

  const parts: string[] = ['построить SQL-запрос'];
  if (semantic.metric) {
    parts.push(`по метрике ${semantic.metric}`);
  }
  if (semantic.dimensions?.length) {
    parts.push(`с группировкой по ${semantic.dimensions.join(', ')}`);
  }
  if (semantic.filters?.length) {
    parts.push(
      `с фильтрами ${semantic.filters
        .map((item) => `${item.field} ${item.operator} ${String(item.value)}`)
        .join('; ')}`
    );
  }
  if (semantic.date_range?.kind) {
    parts.push(`за период ${semantic.date_range.kind}`);
  }
  if (semantic.comparison) {
    parts.push(`и сравнением ${semantic.comparison}`);
  }

  return parts.join(' ');
}

function semanticNotes(message: ApiChatMessageRead) {
  return payloadOf(message)?.semantic_parse?.notes ?? [];
}

function warnings(message: ApiChatMessageRead) {
  const payload = payloadOf(message);
  return [
    ...(payload?.warnings ?? []),
    ...(payload?.interpretation.ambiguities ?? []).map((item) => `Неоднозначность: ${item.replaceAll('_', ' ')}`)
  ];
}
</script>

<style scoped lang="scss">
.chat-assistant {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  height: 100%;
}

.chat-assistant__feed {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 2px;
}

.chat-assistant__assistant-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-assistant__reasoning-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0;
  border: 0;
  background: transparent;
}

.chat-assistant__reasoning-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: flex-start;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 0.78rem;
  cursor: pointer;
}

.chat-assistant__reasoning-toggle:hover {
  color: var(--ink);
}

.chat-assistant__reasoning-body {
  display: grid;
  gap: 10px;
  padding-left: 2px;
}

.chat-assistant__semantic-summary {
  display: grid;
  gap: 8px;
}

.chat-assistant__semantic-title {
  margin: 0;
  color: var(--muted);
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.chat-assistant__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.chat-assistant__chip {
  display: inline-flex;
  align-items: center;
  padding: 0.28rem 0.55rem;
  border-radius: 999px;
  background: rgba(36, 107, 255, 0.08);
  color: var(--ink);
  font-size: 0.72rem;
  font-weight: 600;
}

.chat-assistant__semantic-note,
.chat-assistant__semantic-lead,
.chat-assistant__semantic-task,
.chat-assistant__reasoning-lines p {
  margin: 0;
  color: var(--muted);
  font-size: 0.78rem;
  line-height: 1.45;
}

.chat-assistant__semantic-lead,
.chat-assistant__semantic-task {
  color: var(--ink);
}

.chat-assistant__semantic-task {
  font-weight: 600;
}

.chat-assistant__reasoning-lines {
  display: grid;
  gap: 4px;
}

.sql-cell__warnings {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.sql-cell__warnings .pill {
  background: rgba(255, 255, 255, 0.04);
}

.chat-assistant__empty {
  border: 1px dashed var(--line);
  border-radius: var(--radius-lg);
  min-height: 120px;
  display: grid;
  place-items: center;
  color: var(--muted);
  font-size: 0.82rem;
}

.chat-assistant__loader {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 2px;
}

.chat-assistant__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--muted);
  animation: chat-dot-bounce 1.2s infinite ease-in-out;
}

.chat-assistant__dot:nth-child(1) { animation-delay: 0s; }
.chat-assistant__dot:nth-child(2) { animation-delay: 0.2s; }
.chat-assistant__dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes chat-dot-bounce {
  0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
  40%            { opacity: 1;    transform: translateY(-4px); }
}
</style>
