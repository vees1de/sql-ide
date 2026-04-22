<template>
  <aside class="inspector">
    <section class="inspector__section">
      <div class="inspector__section-head">
        <div>
          <p class="eyebrow">Ноутбук</p>
          <h2>{{ notebook.title }}</h2>
        </div>
        <span class="pill pill--soft">{{ notebook.status === 'saved' ? 'Сохранён' : 'Черновик' }}</span>
      </div>

      <p class="inspector__lede">{{ notebook.summary.objective }}</p>

      <div class="inspector__stats">
        <div>
          <span>Владелец</span>
          <strong>{{ notebook.summary.owner }}</strong>
        </div>
        <div>
          <span>Последний запуск</span>
          <strong>{{ notebook.summary.lastRunLabel }}</strong>
        </div>
        <div>
          <span>БД</span>
          <strong>{{ database.name }}</strong>
        </div>
      </div>
    </section>

    <section class="inspector__section">
      <div class="inspector__section-head">
        <div>
          <p class="eyebrow">Выбранная ячейка</p>
          <h3>{{ selectedCell?.title ?? 'Ячейка не выбрана' }}</h3>
        </div>
        <span
          v-if="selectedCell"
          class="confidence-pill"
          :class="{ 'confidence-pill--running': isRunning }"
        >
          {{ Math.round(selectedCell.meta.confidence * 100) }}%
        </span>
      </div>

      <p class="inspector__summary">
        {{
          selectedCell?.meta.summary ??
          'Новый ноутбук появится здесь после первого запроса и завершения серверной обработки.'
        }}
      </p>

      <div class="inspector__block">
        <span class="inspector__label">Использованные таблицы</span>
        <div class="tag-list">
          <span
            v-for="table in selectedCell?.meta.tablesUsed ?? []"
            :key="table"
            class="tag-chip"
          >
            {{ table }}
          </span>
          <span
            v-if="!(selectedCell?.meta.tablesUsed.length)"
            class="tag-chip"
          >
            Ждём запрос.
          </span>
        </div>
      </div>

      <div class="inspector__block">
        <span class="inspector__label">Бизнес-термины</span>
        <div class="tag-list">
          <span
            v-for="term in selectedCell?.meta.businessTerms ?? []"
            :key="term"
            class="tag-chip tag-chip--accent"
          >
            {{ term }}
          </span>
          <span
            v-if="!(selectedCell?.meta.businessTerms.length)"
            class="tag-chip tag-chip--accent"
          >
            Терминов пока нет.
          </span>
        </div>
      </div>

      <div
        v-if="selectedCell?.meta.warnings.length"
        class="inspector__warning"
      >
        <span class="inspector__label">Предупреждения</span>
        <ul>
          <li
            v-for="warning in selectedCell?.meta.warnings ?? []"
            :key="warning"
          >
            {{ warning }}
          </li>
        </ul>
      </div>
    </section>

    <section class="inspector__section">
      <div class="inspector__section-head">
        <div>
          <p class="eyebrow">Трассировка агента</p>
          <h3>Пайплайн</h3>
        </div>
        <span class="pill pill--ghost">{{ traceSteps.length }} шагов</span>
      </div>

      <div class="trace-list">
        <div
          v-for="step in traceSteps"
          :key="step.agent"
          class="trace-item"
          :class="`trace-item--${step.status}`"
        >
          <div class="trace-item__head">
            <strong>{{ step.agent }}</strong>
            <small>{{ step.latencyMs }} ms</small>
          </div>
          <p>{{ step.purpose }}</p>
          <span class="trace-item__output">{{ step.output }}</span>
        </div>
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import type { DatabaseConnection, Notebook, NotebookCell, NotebookTraceStep } from '@/types/app';

defineProps<{
  database: DatabaseConnection;
  isRunning: boolean;
  notebook: Notebook;
  selectedCell: NotebookCell | null;
  traceSteps: Array<NotebookTraceStep & { status: string }>;
}>();
</script>

<style scoped lang="scss">
.inspector {
  height: 100%;
  overflow-y: auto;
  padding: 1.25rem 1rem 1.4rem;
  background:
    radial-gradient(circle at top, rgba(138, 180, 248, 0.06), transparent 28%),
    rgba(21, 24, 34, 0.96);
}

.inspector__section + .inspector__section {
  margin-top: 1.15rem;
  padding-top: 1.15rem;
  border-top: 1px solid var(--line);
}

.inspector__section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.inspector__section-head h2,
.inspector__section-head h3 {
  margin: 0.15rem 0 0;
  letter-spacing: -0.03em;
}

.inspector__lede,
.inspector__summary {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
}

.inspector__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
  margin-top: 1rem;
}

.inspector__stats span,
.inspector__label {
  display: block;
  margin-bottom: 0.3rem;
  color: var(--muted);
  font-size: 0.78rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.inspector__stats strong {
  font-size: 0.94rem;
}

.confidence-pill {
  padding: 0.55rem 0.7rem;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.12);
  color: var(--success);
  font-weight: 600;
}

.confidence-pill--running {
  background: rgba(36, 107, 255, 0.12);
  color: var(--accent-strong);
}

.inspector__block + .inspector__block,
.inspector__warning {
  margin-top: 0.95rem;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.tag-chip {
  padding: 0.42rem 0.65rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  font-size: 0.84rem;
}

.tag-chip--accent {
  background: rgba(36, 107, 255, 0.1);
  color: var(--accent-strong);
}

.inspector__warning ul {
  margin: 0;
  padding-left: 1.05rem;
  color: var(--warning-strong);
  line-height: 1.55;
}

.trace-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.trace-item {
  padding: 0.9rem 0.95rem;
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid transparent;
  transition: border-color 180ms ease, transform 180ms ease;
}

.trace-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.trace-item__head small,
.trace-item p {
  color: var(--muted);
}

.trace-item p {
  margin: 0.45rem 0 0.5rem;
  line-height: 1.45;
}

.trace-item__output {
  display: block;
  color: var(--ink);
  font-size: 0.9rem;
  line-height: 1.4;
}

.trace-item--completed {
  border-color: rgba(18, 114, 91, 0.18);
}

.trace-item--running {
  border-color: rgba(36, 107, 255, 0.22);
  transform: translateX(-2px);
  background: rgba(36, 107, 255, 0.06);
}

@media (max-width: 760px) {
  .inspector__stats {
    grid-template-columns: 1fr;
  }
}
</style>
