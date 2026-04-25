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

                <!-- Как я понял запрос -->
                <div v-if="intentBlock(message)" class="r-block">
                  <p class="r-label">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><circle cx="6" cy="6" r="4.5" stroke="currentColor" stroke-width="1.2"/><path d="M6 4v2.5l1.5 1" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/></svg>
                    Как я понял запрос
                  </p>
                  <p class="r-lead">{{ intentBlock(message).summary }}</p>
                  <div v-if="intentBlock(message).tags.length" class="r-tags">
                    <span
                      v-for="tag in intentBlock(message).tags"
                      :key="tag.text"
                      class="r-tag"
                      :class="`r-tag--${tag.kind}`"
                    >{{ tag.text }}</span>
                  </div>
                </div>

                <!-- Почему выбраны таблицы и колонки -->
                <div v-if="tablesBlock(message).length" class="r-block">
                  <p class="r-label">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><rect x="1.5" y="2.5" width="9" height="7" rx="1" stroke="currentColor" stroke-width="1.2"/><path d="M1.5 5h9" stroke="currentColor" stroke-width="1.1"/><path d="M5 5v4.5" stroke="currentColor" stroke-width="1.1"/></svg>
                    Почему выбраны эти таблицы
                  </p>
                  <div class="r-table-list">
                    <div
                      v-for="row in tablesBlock(message)"
                      :key="row.table"
                      class="r-table-row"
                    >
                      <span class="r-table-name">{{ row.table }}</span>
                      <span class="r-table-reason">{{ row.reason }}</span>
                    </div>
                  </div>
                </div>

                <!-- Почему выбраны эти столбцы -->
                <div v-if="columnsBlock(message).length" class="r-block">
                  <p class="r-label">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M3 2h6v8H3z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><path d="M3 4.5h6M3 7h6" stroke="currentColor" stroke-width="1"/></svg>
                    Почему выбраны эти столбцы
                  </p>
                  <div class="r-col-list">
                    <div
                      v-for="col in columnsBlock(message)"
                      :key="col.term + col.match"
                      class="r-col-row"
                    >
                      <div class="r-col-header">
                        <span class="r-col-name">{{ col.match }}</span>
                        <span class="r-tag" :class="`r-tag--${col.kind}`">{{ col.kindLabel }}</span>
                        <span class="r-col-source">{{ col.sourceLabel }}</span>
                      </div>
                      <p v-if="col.note" class="r-col-note">{{ col.note }}</p>
                      <p v-else-if="col.term !== col.match" class="r-col-note">
                        Из запроса: <em>{{ col.term }}</em>
                      </p>
                    </div>
                  </div>
                </div>

                <!-- Как термины запроса легли на поля БД -->
                <div v-if="termsBlock(message).length" class="r-block">
                  <p class="r-label">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M2 6h8M7 3.5 9.5 6 7 8.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    Как слова запроса стали полями
                  </p>
                  <div class="r-term-list">
                    <div
                      v-for="t in termsBlock(message)"
                      :key="t.term"
                      class="r-term-row"
                    >
                      <span class="r-term-user">{{ t.term }}</span>
                      <svg class="r-term-arrow" width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M2 6h8M7 3.5 9.5 6 7 8.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                      <span class="r-term-match">{{ t.match }}</span>
                      <span class="r-term-kind r-tag" :class="`r-tag--${t.kind}`">{{ t.kindLabel }}</span>
                      <span v-if="t.note" class="r-term-note">{{ t.note }}</span>
                    </div>
                  </div>
                </div>

                <!-- Уверенность и фильтры -->
                <div v-if="metaBlock(message)" class="r-block r-block--meta">
                  <div v-if="metaBlock(message)!.confidence" class="r-confidence">
                    <span class="r-label r-label--inline">
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M6 1.5 7.2 4.4l3.1.3-2.2 2 .7 3L6 8.1l-2.8 1.6.7-3L1.7 4.7l3.1-.3Z" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/></svg>
                      Уверенность
                    </span>
                    <span class="r-confidence-bar">
                      <span class="r-confidence-fill" :class="`r-confidence-fill--${metaBlock(message)!.confidence}`" />
                    </span>
                    <span class="r-confidence-label" :class="`r-confidence-label--${metaBlock(message)!.confidence}`">
                      {{ { low: 'Низкая', medium: 'Средняя', high: 'Высокая' }[metaBlock(message)!.confidence] }}
                    </span>
                  </div>
                  <div v-if="metaBlock(message)!.filters.length" class="r-filters">
                    <span class="r-label r-label--inline">
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M1.5 3h9M3 6h6M4.5 9h3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
                      Фильтры
                    </span>
                    <span
                      v-for="f in metaBlock(message)!.filters"
                      :key="f"
                      class="r-tag r-tag--filter"
                    >{{ f }}</span>
                  </div>
                </div>

                <!-- Предупреждения -->
                <div v-if="warnings(message).length" class="r-block r-block--warnings">
                  <p class="r-label">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M6 1.5 11 10.5H1L6 1.5Z" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/><path d="M6 5v2.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><circle cx="6" cy="9" r="0.6" fill="currentColor"/></svg>
                    Обратите внимание
                  </p>
                  <div class="r-warning-list">
                    <span
                      v-for="w in warnings(message)"
                      :key="w"
                      class="r-warning"
                    >{{ w }}</span>
                  </div>
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
import { computed, nextTick, onMounted, ref, watch } from "vue";
import ChatAssistantMessage from "@/components/chat/ChatAssistantMessage.vue";
import ChatInput from "@/components/chat/ChatInput.vue";
import ChatUserMessage from "@/components/chat/ChatUserMessage.vue";
import type {
  ApiChatMessageRead,
  ApiChatStructuredPayload,
  ApiQueryMode,
} from "@/api/types";

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
    pendingUserMessage: "",
    queryMode: "fast",
    llmModelAlias: "gpt120",
    llmModelAliases: () => ["gpt120"],
  },
);

const emit = defineEmits<{
  (event: "send", text: string, mode: ApiQueryMode): void;
  (event: "apply-sql", sql: string): void;
  (event: "explain-sql", sql: string): void;
  (event: "prepare-sql"): void;
  (
    event: "clarification",
    payload: {
      clarificationId: string;
      optionId?: string | null;
      text?: string | null;
    },
  ): void;
  (event: "run-prepared"): void;
  (event: "show-chart-preview"): void;
  (event: "set-query-mode", mode: ApiQueryMode): void;
  (event: "set-llm-model-alias", alias: string): void;
}>();

const draft = ref("");
const scrollRef = ref<HTMLElement | null>(null);
const openReasoning = ref<Record<string, boolean>>({});
const pendingMessage = computed<ApiChatMessageRead | null>(() => {
  const text = props.pendingUserMessage?.trim();
  if (!text) {
    return null;
  }

  return {
    id: "pending-user-message",
    session_id: "pending",
    role: "user",
    text,
    structured_payload: null,
    created_at: new Date().toISOString(),
  };
});

async function scrollToBottom() {
  await nextTick();
  scrollRef.value?.scrollTo({
    top: scrollRef.value.scrollHeight,
    behavior: "smooth",
  });
}

watch(
  () => props.messages.length,
  () => {
    void scrollToBottom();
  },
);

watch(
  () => props.busy,
  () => {
    void scrollToBottom();
  },
);

watch(
  () => props.pendingUserMessage,
  () => {
    void scrollToBottom();
  },
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
  const p = payloadOf(message);
  if (!p) return false;
  return Boolean(
    p.semantic_parse ||
    p.tables_used?.length ||
    p.confidence_level ||
    p.warnings?.length ||
    p.interpretation?.ambiguities?.length
  );
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

const KIND_LABELS: Record<string, string> = {
  metric: 'метрика',
  dimension: 'измерение',
  filter: 'фильтр',
  table: 'таблица',
  column: 'колонка',
  relationship: 'связь',
  term: 'термин'
};

function intentBlock(message: ApiChatMessageRead) {
  const semantic = payloadOf(message)?.semantic_parse;
  if (!semantic) return null;

  const summary = semantic.intent_summary ?? buildIntentSummary(semantic);
  if (!summary) return null;

  type Tag = { text: string; kind: string };
  const tags: Tag[] = [];
  if (semantic.metric) tags.push({ text: semantic.metric, kind: 'metric' });
  (semantic.dimensions ?? []).forEach(d => tags.push({ text: d, kind: 'dimension' }));
  if (semantic.date_range?.kind) tags.push({ text: semantic.date_range.kind, kind: 'date' });
  if (semantic.comparison) tags.push({ text: semantic.comparison, kind: 'comparison' });

  return { summary, tags };
}

function buildIntentSummary(semantic: NonNullable<ApiChatStructuredPayload['semantic_parse']>) {
  const parts: string[] = [];
  if (semantic.metric) parts.push(`метрика — ${semantic.metric}`);
  if (semantic.dimensions?.length) parts.push(`группировка по ${semantic.dimensions.join(', ')}`);
  if (semantic.date_range?.kind) parts.push(`период ${semantic.date_range.kind}`);
  if (semantic.comparison) parts.push(`сравнение ${semantic.comparison}`);
  return parts.length ? parts.join('; ') : null;
}

function tablesBlock(message: ApiChatMessageRead) {
  return payloadOf(message)?.tables_used ?? [];
}

const SOURCE_LABELS: Record<string, string> = {
  semantic_catalog: 'семантика',
  schema: 'схема БД',
  dictionary: 'словарь',
  user_input: 'из запроса',
  unknown: ''
};

const COLUMN_KINDS = new Set(['column', 'metric', 'dimension']);

function columnsBlock(message: ApiChatMessageRead) {
  const terms = payloadOf(message)?.semantic_parse?.resolved_terms ?? [];
  return terms
    .filter(t => COLUMN_KINDS.has(t.kind) && t.match)
    .map(t => ({
      term: t.term,
      match: t.match!,
      kind: t.kind,
      kindLabel: KIND_LABELS[t.kind] ?? t.kind,
      sourceLabel: SOURCE_LABELS[t.source] ?? '',
      note: t.note ?? null
    }));
}

function termsBlock(message: ApiChatMessageRead) {
  const terms = payloadOf(message)?.semantic_parse?.resolved_terms ?? [];
  return terms
    .filter(t => !COLUMN_KINDS.has(t.kind))
    .map(t => ({
      term: t.term,
      match: t.match || t.term,
      kind: t.kind,
      kindLabel: KIND_LABELS[t.kind] ?? t.kind,
      note: t.note ?? null
    }));
}

function metaBlock(message: ApiChatMessageRead) {
  const p = payloadOf(message);
  if (!p) return null;
  const filters = (p.semantic_parse?.filters ?? []).map(
    f => `${f.field} ${f.operator} ${String(f.value)}`
  );
  const confidence = p.confidence_level ?? null;
  if (!confidence && !filters.length) return null;
  return { confidence, filters };
}

function warnings(message: ApiChatMessageRead) {
  const payload = payloadOf(message);
  return [
    ...(payload?.warnings ?? []),
    ...(payload?.interpretation?.ambiguities ?? []).map(
      item => `Неоднозначность: ${item.replaceAll('_', ' ')}`
    )
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
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 2px;
  scrollbar-width: thin;
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
  color: var(--muted-2);
  font-size: 0.78rem;
  cursor: pointer;
}

.chat-assistant__reasoning-toggle:hover {
  color: var(--ink);
}

/* ── Reasoning body ─────────────────────────────────────── */
.chat-assistant__reasoning-body {
  display: grid;
  gap: 1px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--line);
  background: #1a1a1a;
}

.r-block {
  display: grid;
  gap: 8px;
  padding: 10px 12px;
  background: #262626;
}

.r-block + .r-block {
  border-top: 1px solid var(--line);
}

.r-block--meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.r-block--warnings {
  background: rgba(255, 184, 77, 0.05);
  border-top-color: rgba(255, 184, 77, 0.15) !important;
}

/* labels */
.r-label {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--muted-2);
  font-size: 0.69rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;

  svg { opacity: 0.6; flex-shrink: 0; }
}

.r-label--inline {
  font-size: 0.69rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted-2);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  svg { opacity: 0.6; }
}

/* intent lead text */
.r-lead {
  margin: 0;
  color: var(--ink);
  font-size: 0.82rem;
  line-height: 1.5;
}

/* tags */
.r-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.r-tag {
  display: inline-flex;
  align-items: center;
  padding: 0.22rem 0.55rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.06);
  color: var(--ink);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.r-tag--metric    { background: rgba(112, 59, 247, 0.16); border-color: rgba(112, 59, 247, 0.3); color: #d4bfff; }
.r-tag--dimension { background: rgba(36, 107, 255, 0.12); border-color: rgba(36, 107, 255, 0.25); color: #a8c4ff; }
.r-tag--date      { background: rgba(67, 176, 42, 0.1);   border-color: rgba(67, 176, 42, 0.25);  color: #b8f0a8; }
.r-tag--comparison{ background: rgba(255, 184, 77, 0.1);  border-color: rgba(255, 184, 77, 0.25); color: #ffd79a; }
.r-tag--filter    { background: rgba(255, 107, 107, 0.1); border-color: rgba(255, 107, 107, 0.22); color: #ffb3b3; }
.r-tag--column    { background: rgba(0, 196, 180, 0.1);   border-color: rgba(0, 196, 180, 0.22);  color: #9ef0e8; }
.r-tag--table     { background: rgba(255, 140, 0, 0.1);   border-color: rgba(255, 140, 0, 0.22);  color: #ffc87a; }

/* tables */
.r-table-list {
  display: grid;
  gap: 5px;
}

.r-table-row {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: baseline;
  gap: 8px;
}

.r-table-name {
  font-size: 0.76rem;
  font-weight: 700;
  font-family: var(--font-mono);
  color: #ffc87a;
  white-space: nowrap;
}

.r-table-reason {
  font-size: 0.78rem;
  color: var(--muted-2);
  line-height: 1.4;
}

/* columns */
.r-col-list {
  display: grid;
  gap: 6px;
}

.r-col-row {
  display: grid;
  gap: 3px;
  padding: 6px 8px;
  border-radius: 7px;
  background: rgba(0, 196, 180, 0.06);
  border: 1px solid rgba(0, 196, 180, 0.14);
}

.r-col-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.r-col-name {
  font-size: 0.78rem;
  font-weight: 700;
  font-family: var(--font-mono);
  color: #9ef0e8;
}

.r-col-source {
  font-size: 0.68rem;
  color: var(--muted-2);
  margin-left: auto;
}

.r-col-note {
  margin: 0;
  font-size: 0.74rem;
  color: var(--muted-2);
  line-height: 1.4;

  em {
    color: var(--ink);
    font-style: italic;
  }
}

/* terms */
.r-term-list {
  display: grid;
  gap: 5px;
}

.r-term-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.r-term-user {
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--ink);
  font-style: italic;
}

.r-term-arrow {
  color: var(--muted-2);
  opacity: 0.5;
  flex-shrink: 0;
}

.r-term-match {
  font-size: 0.76rem;
  font-weight: 700;
  font-family: var(--font-mono);
  color: #9ef0e8;
}

.r-term-note {
  font-size: 0.72rem;
  color: var(--muted-2);
}

/* confidence */
.r-confidence {
  display: flex;
  align-items: center;
  gap: 8px;
}

.r-confidence-bar {
  width: 56px;
  height: 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
  flex-shrink: 0;
}

.r-confidence-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--muted);
}
.r-confidence-fill--low    { width: 33%; background: #ff6b6b; }
.r-confidence-fill--medium { width: 66%; background: #ffb84d; }
.r-confidence-fill--high   { width: 100%; background: #43b02a; }

.r-confidence-label {
  font-size: 0.72rem;
  font-weight: 600;
}
.r-confidence-label--low    { color: #ff9898; }
.r-confidence-label--medium { color: #ffd79a; }
.r-confidence-label--high   { color: #b8f0a8; }

/* filters */
.r-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

/* warnings */
.r-warning-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.r-warning {
  font-size: 0.78rem;
  color: #ffd79a;
  line-height: 1.4;
  padding-left: 12px;
  position: relative;

  &::before {
    content: '·';
    position: absolute;
    left: 3px;
    color: #ffb84d;
  }
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

.chat-assistant__dot:nth-child(1) {
  animation-delay: 0s;
}
.chat-assistant__dot:nth-child(2) {
  animation-delay: 0.2s;
}
.chat-assistant__dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes chat-dot-bounce {
  0%,
  80%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-4px);
  }
}
</style>
