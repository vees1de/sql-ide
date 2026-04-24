<template>
  <Teleport to="body">
    <div v-if="open" class="sql-explain-backdrop" @click.self="$emit('close')">
      <div class="sql-explain-modal" role="dialog" aria-modal="true" aria-labelledby="sql-explain-title">
        <header class="sql-explain-modal__header">
          <div>
            <p class="sql-explain-modal__eyebrow">AI объяснение SQL</p>
            <h2 id="sql-explain-title">Объяснение SQL</h2>
            <p class="sql-explain-modal__subtitle">
              Разбор запроса по блокам и строкам, чтобы понять, что делает каждая часть.
            </p>
          </div>
          <button class="sql-explain-modal__close" type="button" aria-label="Закрыть" @click="$emit('close')">
            ×
          </button>
        </header>

        <div class="sql-explain-modal__body">
          <section class="sql-explain-modal__summary">
            <div class="sql-explain-modal__section-head">
              <strong>Кратко</strong>
              <span v-if="explanation" class="sql-explain-modal__badge">
                {{ explanation.generated_by_ai ? 'AI' : 'Fallback' }}
              </span>
            </div>

            <p v-if="loading" class="sql-explain-modal__message">Готовлю разбор SQL…</p>
            <p v-else-if="error" class="sql-explain-modal__message sql-explain-modal__message--error">
              {{ error }}
            </p>
            <template v-else-if="explanation">
              <p class="sql-explain-modal__summary-text">{{ explanation.summary }}</p>

              <div v-if="explanation.warnings.length" class="sql-explain-modal__warnings">
                <p class="sql-explain-modal__warnings-title">Примечания</p>
                <ul>
                  <li v-for="warning in explanation.warnings" :key="warning">{{ warning }}</li>
                </ul>
              </div>

              <div class="sql-explain-modal__blocks">
                <article
                  v-for="block in explanation.blocks"
                  :key="block.index"
                  class="sql-explain-modal__block"
                >
                  <div class="sql-explain-modal__block-head">
                    <div>
                      <p class="sql-explain-modal__block-kind">{{ block.title }}</p>
                      <h3>
                        Строки {{ block.line_start }}-{{ block.line_end }}
                      </h3>
                    </div>
                    <span class="sql-explain-modal__badge sql-explain-modal__badge--muted">
                      {{ block.kind }}
                    </span>
                  </div>
                  <pre class="sql-explain-modal__snippet"><code>{{ block.sql }}</code></pre>
                  <p class="sql-explain-modal__block-text">{{ block.explanation }}</p>
                </article>
              </div>
            </template>
            <p v-else class="sql-explain-modal__message">
              Нажмите на вопросительный знак рядом с редактором SQL, чтобы получить разбор.
            </p>
          </section>

          <section class="sql-explain-modal__source">
            <div class="sql-explain-modal__section-head">
              <strong>Исходный SQL</strong>
              <span class="sql-explain-modal__badge">{{ sqlLines.length }} строк</span>
            </div>

            <div v-if="sqlLines.length" class="sql-explain-modal__source-code">
              <div v-for="line in sqlLines" :key="line.number" class="sql-explain-modal__source-line">
                <span class="sql-explain-modal__line-no">{{ line.number }}</span>
                <code class="sql-explain-modal__line-code">{{ line.text || ' ' }}</code>
              </div>
            </div>
            <div v-else class="sql-explain-modal__message">
              SQL пока пустой.
            </div>
          </section>
        </div>

        <footer class="sql-explain-modal__footer">
          <button v-if="error" class="sql-explain-modal__btn sql-explain-modal__btn--ghost" type="button" @click="$emit('retry')">
            Повторить
          </button>
          <button class="sql-explain-modal__btn sql-explain-modal__btn--primary" type="button" @click="$emit('close')">
            Закрыть
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { ApiSqlExplanationResponse } from '@/api/types';

const props = defineProps<{
  open: boolean;
  sqlText: string;
  explanation: ApiSqlExplanationResponse | null;
  loading: boolean;
  error: string | null;
}>();

defineEmits<{
  (event: 'close'): void;
  (event: 'retry'): void;
}>();

const sqlLines = computed(() =>
  (props.sqlText.trim()
    ? props.sqlText.split(/\r?\n/)
    : []
  ).map((text, index) => ({
    number: index + 1,
    text
  }))
);
</script>

<style scoped lang="scss">
.sql-explain-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1100;
  background: rgba(6, 10, 18, 0.7);
  backdrop-filter: blur(8px);
  display: grid;
  place-items: center;
  padding: 20px;
}

.sql-explain-modal {
  width: min(1180px, calc(100vw - 40px));
  max-height: calc(100vh - 40px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background:
    radial-gradient(circle at top right, rgba(112, 59, 247, 0.18), transparent 36%),
    linear-gradient(180deg, rgba(14, 18, 30, 0.98), rgba(9, 12, 20, 0.98));
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
}

.sql-explain-modal__header,
.sql-explain-modal__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
}

.sql-explain-modal__header {
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.sql-explain-modal__footer {
  justify-content: flex-end;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.sql-explain-modal__eyebrow {
  margin: 0 0 4px;
  color: rgba(255, 255, 255, 0.52);
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.sql-explain-modal__header h2 {
  margin: 0;
  color: var(--ink-strong);
  font-size: 1.1rem;
}

.sql-explain-modal__subtitle {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 0.86rem;
}

.sql-explain-modal__close {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  color: var(--ink-strong);
  font-size: 1.2rem;
  line-height: 1;
}

.sql-explain-modal__body {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.8fr);
  gap: 16px;
  padding: 18px 20px;
  overflow: hidden;
}

.sql-explain-modal__summary,
.sql-explain-modal__source {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow: hidden;
}

.sql-explain-modal__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.sql-explain-modal__section-head strong {
  color: var(--ink-strong);
  font-size: 0.95rem;
}

.sql-explain-modal__badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(112, 59, 247, 0.6);
  background: rgba(112, 59, 247, 0.14);
  color: #e7ddff;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.sql-explain-modal__badge--muted {
  border-color: rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
}

.sql-explain-modal__message,
.sql-explain-modal__summary-text,
.sql-explain-modal__block-text {
  margin: 0;
  color: var(--ink);
  font-size: 0.92rem;
  line-height: 1.55;
}

.sql-explain-modal__message--error {
  color: #ffb3b3;
}

.sql-explain-modal__warnings {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(255, 184, 77, 0.2);
  background: rgba(255, 184, 77, 0.08);
}

.sql-explain-modal__warnings-title {
  margin: 0 0 8px;
  color: #ffd79a;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.sql-explain-modal__warnings ul {
  margin: 0;
  padding-left: 18px;
  color: #ffe7bd;
}

.sql-explain-modal__blocks {
  min-height: 0;
  display: grid;
  gap: 12px;
  overflow: auto;
  padding-right: 4px;
}

.sql-explain-modal__block {
  padding: 14px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
}

.sql-explain-modal__block-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.sql-explain-modal__block-kind {
  margin: 0 0 3px;
  color: rgba(255, 255, 255, 0.56);
  font-size: 0.74rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.sql-explain-modal__block h3 {
  margin: 0;
  color: var(--ink-strong);
  font-size: 0.95rem;
}

.sql-explain-modal__snippet {
  margin: 0 0 10px;
  padding: 12px;
  border-radius: 14px;
  overflow: auto;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(2, 6, 12, 0.7);
  color: #d7e6ff;
  font-size: 0.8rem;
  line-height: 1.5;
}

.sql-explain-modal__source-code {
  min-height: 0;
  overflow: auto;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(2, 6, 12, 0.7);
}

.sql-explain-modal__source-line {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  padding: 2px 0;
}

.sql-explain-modal__line-no {
  color: rgba(255, 255, 255, 0.4);
  font-variant-numeric: tabular-nums;
  text-align: right;
  user-select: none;
}

.sql-explain-modal__line-code {
  white-space: pre-wrap;
  word-break: break-word;
  color: #dbe7ff;
  font-size: 0.8rem;
  line-height: 1.45;
}

.sql-explain-modal__btn {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid transparent;
  font-size: 0.84rem;
  transition:
    background 180ms ease,
    border-color 180ms ease,
    color 180ms ease;
}

.sql-explain-modal__btn--ghost {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--ink);
}

.sql-explain-modal__btn--ghost:hover {
  background: rgba(255, 255, 255, 0.07);
  color: var(--ink-strong);
}

.sql-explain-modal__btn--primary {
  border-color: rgba(112, 59, 247, 0.8);
  background: rgba(112, 59, 247, 0.25);
  color: var(--ink-strong);
}

.sql-explain-modal__btn--primary:hover {
  background: rgba(112, 59, 247, 0.34);
}

@media (max-width: 980px) {
  .sql-explain-modal__body {
    grid-template-columns: 1fr;
  }
}
</style>
