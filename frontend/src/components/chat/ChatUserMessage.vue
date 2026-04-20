<template>
  <article class="chat-user-message">
    <p>{{ message.text }}</p>
  </article>
</template>

<script setup lang="ts">
import type { ApiChatMessageRead } from '@/api/types';

defineProps<{
  message: ApiChatMessageRead;
}>();
</script>

<style scoped lang="scss">
.chat-user-message {
  display: flex;
  justify-content: flex-end;
}

.chat-user-message p {
  max-width: min(80%, 42rem);
  margin: 0;
  padding: 0.9rem 1rem;
  border-radius: 1rem 1rem 0.35rem 1rem;
  background: linear-gradient(180deg, rgba(138, 180, 248, 0.18), rgba(138, 180, 248, 0.1));
  border: 1px solid rgba(138, 180, 248, 0.18);
  color: var(--ink);
  line-height: 1.55;
  white-space: pre-wrap;
}
</style>

