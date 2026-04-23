<template>
  <section class="chat-assistant">
    <div ref="scrollRef" class="chat-assistant__feed">
      <template v-if="messages.length">
        <component
          :is="message.role === 'user' ? ChatUserMessage : ChatAssistantMessage"
          v-for="message in messages"
          :key="message.id"
          :message="message"
          @apply-sql="$emit('apply-sql', $event)"
          @prepare-sql="$emit('prepare-sql')"
          @clarification="$emit('clarification', $event)"
          @run-prepared="$emit('run-prepared')"
          @show-chart-preview="$emit('show-chart-preview')"
          @switch-mode="$emit('set-query-mode', $event)"
        />
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
import type { ApiChatMessageRead, ApiQueryMode } from '@/api/types';

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
  (event: 'prepare-sql'): void;
  (event: 'clarification', payload: { clarificationId: string; optionId?: string | null; text?: string | null }): void;
  (event: 'run-prepared'): void;
  (event: 'show-chart-preview'): void;
  (event: 'set-query-mode', mode: ApiQueryMode): void;
  (event: 'set-llm-model-alias', alias: string): void;
}>();

const draft = ref('');
const scrollRef = ref<HTMLElement | null>(null);
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
