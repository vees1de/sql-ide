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
  padding: 0.75rem 0.85rem;
  border-radius: 12px 12px 4px 12px;
  background: rgba(112, 59, 247, 0.22);
  border: 1px solid rgba(112, 59, 247, 0.65);
  color: var(--ink);
  line-height: 1.5;
  font-size: 0.86rem;
  white-space: pre-wrap;
}
</style>
