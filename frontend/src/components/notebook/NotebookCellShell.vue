<template>
  <article
    class="jcell"
    :class="{
      'jcell--selected': selected,
      'jcell--running': running,
      [`jcell--${cell.type}`]: true
    }"
  >
    <div class="jcell__gutter">
      <button class="jcell__run" type="button" :title="`Run ${cell.type}`">
        <svg v-if="!running" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M6 4.5v15l13-7.5z"/></svg>
        <svg v-else viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><rect x="6" y="5" width="4" height="14"/><rect x="14" y="5" width="4" height="14"/></svg>
      </button>
      <span class="jcell__index">[{{ cell.order }}]</span>
    </div>

    <div class="jcell__main">
      <header class="jcell__header">
        <span class="jcell__type">{{ cell.type.toUpperCase() }}</span>
        <span class="jcell__title">{{ cell.title }}</span>
        <span class="jcell__sep">·</span>
        <span class="jcell__agent">{{ cell.agent }}</span>
        <span class="jcell__confidence">{{ Math.round(cell.meta.confidence * 100) }}%</span>
      </header>

      <div class="jcell__body">
        <slot />
      </div>

      <p v-if="cell.subtitle" class="jcell__subtitle">{{ cell.subtitle }}</p>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { NotebookCell } from '@/types/app';

defineProps<{
  cell: NotebookCell;
  running: boolean;
  selected: boolean;
}>();
</script>

<style scoped lang="scss">
.jcell {
  position: relative;
  display: grid;
  grid-template-columns: 46px 1fr;
  gap: 0.6rem;
  padding: 0.6rem 0.75rem 0.75rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  transition: border-color 160ms ease, box-shadow 160ms ease, background 160ms ease;
  animation: cell-enter 240ms ease both;
}

.jcell:hover {
  border-color: var(--line-strong);
}

.jcell--selected {
  border-color: rgba(138, 180, 248, 0.45);
  box-shadow: 0 0 0 1px rgba(138, 180, 248, 0.18), var(--shadow-soft);
}

.jcell--running {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent-soft);
}

.jcell__gutter {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding-top: 0.3rem;
  color: var(--muted-2);
}

.jcell__run {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--ink);
  transition: background 140ms ease, color 140ms ease, transform 140ms ease;
}

.jcell__run:hover {
  background: var(--accent);
  color: #1a1d24;
}

.jcell--running .jcell__run {
  background: var(--accent);
  color: #1a1d24;
}

.jcell__index {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--muted-2);
}

.jcell__main {
  min-width: 0;
}

.jcell__header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-size: 0.76rem;
  color: var(--muted);
  flex-wrap: wrap;
}

.jcell__type {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  letter-spacing: 0.1em;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--muted);
}

.jcell--sql .jcell__type,
.jcell--prompt .jcell__type {
  color: var(--accent-strong);
  background: var(--accent-soft);
}

.jcell--table .jcell__type,
.jcell--chart .jcell__type {
  color: var(--link-strong);
  background: var(--link-soft);
}

.jcell--insight .jcell__type,
.jcell--clarification .jcell__type {
  color: var(--success);
  background: rgba(129, 201, 149, 0.14);
}

.jcell__title {
  color: var(--ink);
  font-weight: 500;
  font-size: 0.86rem;
}

.jcell__sep {
  color: var(--muted-2);
}

.jcell__confidence {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--muted);
}

.jcell__subtitle {
  margin: 0.55rem 0 0;
  color: var(--muted-2);
  font-size: 0.78rem;
}

.jcell__body :deep(p) {
  color: var(--ink);
  line-height: 1.55;
}

@keyframes cell-enter {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
