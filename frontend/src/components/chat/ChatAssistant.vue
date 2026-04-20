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
          @clarification="$emit('clarification', $event)"
          @switch-mode="$emit('set-query-mode', $event)"
        />
      </template>
      <div v-else class="chat-assistant__empty">
        Чем я могу помочь?
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
import { nextTick, onMounted, ref, watch } from 'vue';
import ChatAssistantMessage from '@/components/chat/ChatAssistantMessage.vue';
import ChatInput from '@/components/chat/ChatInput.vue';
import ChatUserMessage from '@/components/chat/ChatUserMessage.vue';
import type { ApiChatMessageRead, ApiQueryMode } from '@/api/types';

const props = withDefaults(
  defineProps<{
    messages: ApiChatMessageRead[];
    busy: boolean;
    queryMode?: ApiQueryMode;
    llmModelAlias?: string;
    llmModelAliases?: string[];
  }>(),
  {
    queryMode: 'fast',
    llmModelAlias: 'gpt120',
    llmModelAliases: () => ['gpt120']
  }
);

const emit = defineEmits<{
  (event: 'send', text: string, mode: ApiQueryMode): void;
  (event: 'apply-sql', sql: string): void;
  (event: 'clarification', answer: string): void;
  (event: 'set-query-mode', mode: ApiQueryMode): void;
  (event: 'set-llm-model-alias', alias: string): void;
}>();

const draft = ref('');
const scrollRef = ref<HTMLElement | null>(null);

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
</style>
