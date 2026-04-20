<template>
  <section class="chat-assistant">
    <header class="chat-assistant__head">
      <div>
        <p class="eyebrow">Диалог</p>
        <h2>Как я понял запрос</h2>
      </div>
      <div class="chat-assistant__status">
        <span class="pill pill--ghost">{{ messages.length }} сообщений</span>
        <span v-if="busy" class="pill pill--accent">Генерирую</span>
      </div>
    </header>

    <div ref="scrollRef" class="chat-assistant__feed">
      <template v-if="messages.length">
        <component
          :is="message.role === 'user' ? ChatUserMessage : ChatAssistantMessage"
          v-for="message in messages"
          :key="message.id"
          :auto-apply-sql="autoApplySql"
          :message="message"
          @apply-sql="$emit('apply-sql', $event)"
          @clarification="$emit('clarification', $event)"
        />
      </template>
      <div v-else class="chat-assistant__empty">
        <p class="chat-assistant__empty-title">Выберите базу данных и задайте вопрос.</p>
        <p class="chat-assistant__empty-text">
          Например: «сколько заказов было за последние 6 месяцев» или «выручка по месяцам за прошлый год».
        </p>
      </div>
    </div>

    <ChatInput
      v-model="draft"
      :busy="busy"
      placeholder="Спросите по-русски, что нужно посчитать"
      @send="submit"
    />
  </section>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue';
import ChatAssistantMessage from '@/components/chat/ChatAssistantMessage.vue';
import ChatInput from '@/components/chat/ChatInput.vue';
import ChatUserMessage from '@/components/chat/ChatUserMessage.vue';
import type { ApiChatMessageRead } from '@/api/types';

const props = defineProps<{
  messages: ApiChatMessageRead[];
  busy: boolean;
  autoApplySql: boolean;
}>();

const emit = defineEmits<{
  (event: 'send', text: string): void;
  (event: 'apply-sql', sql: string): void;
  (event: 'clarification', answer: string): void;
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
  emit('send', text);
  draft.value = '';
}
</script>

<style scoped lang="scss">
.chat-assistant {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 0.85rem;
  min-height: 0;
  height: 100%;
}

.chat-assistant__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.chat-assistant__head h2 {
  margin: 0.3rem 0 0;
  font-size: 1.05rem;
}

.chat-assistant__status {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.chat-assistant__feed {
  min-height: 0;
  overflow-y: auto;
  padding-right: 0.25rem;
  display: grid;
  gap: 0.85rem;
}

.chat-assistant__empty {
  padding: 1rem;
  border: 1px dashed var(--line);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.02);
}

.chat-assistant__empty-title {
  margin: 0;
  color: var(--ink);
  font-size: 0.92rem;
  font-weight: 600;
}

.chat-assistant__empty-text {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.55;
}
</style>

