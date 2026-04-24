<template>
  <main class="data-shell">
    <aside class="data-shell__sidebar">
      <ChatSidebar
        :active-db-id="selectedDatabaseId"
        :active-session-id="chat.activeSessionId"
        :databases="chat.databases"
        :loading="chat.loadingSessions"
        mode="database"
        :sessions="chat.sessions"
        @add-database="showAddDatabase = true"
        @create-session="createChatSession"
        @delete-session="deleteChatSession"
        @delete-database="deleteSelectedDatabase"
        @rename-database="renameDatabase"
        @rename-session="renameChatSession"
        @select-database="selectDatabase"
        @select-session="selectChatSession"
      />
    </aside>

    <section class="data-shell__content app-route-section">
      <div class="data-view">
        <section class="data-view__panel data-view__panel--hero">
          <div class="data-view__active-db" style="margin-bottom: 16px">
            <span>Выбранная БД</span>
            <strong>{{ selectedDatabase ? selectedDatabase.name : "" }}</strong>
          </div>
          <header class="data-view__head">
            <div>
              <p class="eyebrow">Слой знаний о БД</p>
              <h1>Центр управления данными</h1>
              <p class="data-view__hint">
                Здесь команда запускает парсинг БД, следит за запусками
                сканирования, редактирует семантику таблиц и колонок и смотрит
                ERD без ручного импорта сырой схемы в словарь.
              </p>
            </div>
            <div class="data-view__actions">
              <button
                class="app-button app-button--ghost"
                type="button"
                :disabled="store.isBootstrapping"
                @click="reload"
              >
                Обновить
              </button>
              <button
                class="app-button app-button--ghost"
                type="button"
                :disabled="isScanning || !selectedDatabaseId"
                @click="runScan('incremental')"
              >
                {{ isScanning ? "Сканирование…" : "Инкрементальный скан" }}
              </button>
              <button
                class="app-button"
                type="button"
                :disabled="isScanning || !selectedDatabaseId"
                @click="runScan('full')"
              >
                {{ isScanning ? "Сканирование…" : "Полный скан" }}
              </button>
              <button
                class="app-button app-button--ghost"
                type="button"
                :disabled="isActivatingSemantic || !selectedDatabaseId"
                @click="activateSemantic"
              >
                {{
                  isActivatingSemantic
                    ? "Активирую семантику…"
                    : "Активировать семантику"
                }}
              </button>
              <button
                class="app-button app-button--danger"
                type="button"
                :disabled="
                  isDeletingDatabase ||
                  !selectedDatabaseId ||
                  selectedDatabase?.isBuiltin
                "
                @click="deleteSelectedDatabase"
              >
                {{ isDeletingDatabase ? "Удаление…" : "Удалить базу" }}
              </button>
            </div>
          </header>

          <p v-if="knowledgeFeedback" class="data-view__feedback">
            {{ knowledgeFeedback }}
          </p>
          <p v-if="semanticFeedback" class="data-view__feedback">
            {{ semanticFeedback }}
          </p>

          <div v-if="selectedDatabase" class="data-view__stats">
            <article class="data-view__stat">
              <span>Подключение</span>
              <strong>{{ selectedDatabase.engine }}</strong>
              <small>{{ translateDatabaseMode(selectedDatabase.mode) }}</small>
            </article>
            <article class="data-view__stat">
              <span>Статус слоя знаний</span>
              <strong>{{
                translateKnowledgeStatus(
                  knowledgeSummary?.status ||
                    selectedDatabase.knowledgeStatus ||
                    "not_scanned",
                )
              }}</strong>
              <small>{{
                formatTimestamp(
                  knowledgeSummary?.last_scan?.finished_at ||
                    selectedDatabase.lastScanAt,
                )
              }}</small>
            </article>
            <article class="data-view__stat">
              <span>Таблицы</span>
              <strong>{{ knowledgeSummary?.active_table_count ?? 0 }}</strong>
              <small
                >{{ knowledgeSummary?.active_column_count ?? 0 }} колонок</small
              >
            </article>
            <article class="data-view__stat">
              <span>Связи</span>
              <strong>{{
                knowledgeSummary?.active_relationship_count ?? 0
              }}</strong>
              <small>FK-граф и сохранённая история сканирования.</small>
            </article>
            <article class="data-view__stat">
              <span>Семантика</span>
              <strong>{{ semanticCatalog ? "активна" : "не активна" }}</strong>
              <small>
                {{ semanticCatalog?.tables.length ?? 0 }} таблиц ·
                {{ semanticCatalog?.relationships.length ?? 0 }} связей
              </small>
            </article>
          </div>
        </section>

        <section class="data-view__panel" v-if="knowledgeSummary">
          <header class="data-view__head">
            <div>
              <p class="eyebrow">Слой знаний о БД</p>
              <h2>Семантический слой и метаданные</h2>
              <p class="data-view__hint">
                Здесь хранится всё, что влияет на понимание базы: описание
                предметной области, словарь, запуски сканирования, semantic
                overrides таблиц и колонок, а также отдельные флаги скрытия от
                LLM.
              </p>
            </div>
            <div class="data-view__semantic-actions">
              <label class="data-view__toggle">
                <input v-model="semanticAutoRefreshEnabled" type="checkbox" />
                <span>Автообновление</span>
              </label>
              <button
                class="app-button app-button--ghost"
                type="button"
                :disabled="isActivatingSemantic"
                @click="activateSemantic"
              >
                {{
                  isActivatingSemantic
                    ? "Обновляем семантику…"
                    : "Открыть semantic activation"
                }}
              </button>
              <button
                class="app-button app-button--danger"
                type="button"
                :disabled="isDeletingSemantic"
                @click="deleteSemanticCatalog"
              >
                {{ isDeletingSemantic ? "Удаляем проекцию…" : "Сбросить LLM-проекцию" }}
              </button>
            </div>
          </header>
          <p v-if="semanticFeedback" class="data-view__feedback">
            {{ semanticFeedback }}
          </p>
          <p
            v-if="semanticFactGrainWarnings.length"
            class="data-view__feedback"
          >
            Для {{ semanticFactGrainWarnings.length }} fact-таблиц не заполнен
            grain: {{ semanticFactGrainWarnings.join(", ") }}.
          </p>
          <div class="data-view__knowledge-overview">
            <section class="data-view__subpanel">
              <header class="data-view__subhead">
                <h3>Описание базы для semantic activation</h3>
                <p>
                  Сохраняется в БД и используется при последующей пересборке
                  LLM-проекции.
                </p>
              </header>
              <label class="data-view__semantic-description">
                <textarea
                  v-model="semanticDescription"
                  rows="5"
                  placeholder="Опишите предметную область, ключевые сущности, смысл строки в основных таблицах и важные бизнес-правила."
                ></textarea>
              </label>
            </section>

            <section class="data-view__subpanel">
              <header class="data-view__subhead">
                <h3>Запуски сканирования</h3>
                <p>История снимков схемы и наполнения knowledge layer.</p>
              </header>
              <div v-if="scanRuns.length" class="data-view__scan-list">
                <article
                  v-for="run in scanRuns.slice(0, 6)"
                  :key="run.id"
                  class="data-view__scan-card"
                >
                  <div>
                    <strong>{{ translateScanType(run.scan_type) }}</strong>
                    <p>
                      {{ translateScanStatus(run.status) }} ·
                      {{ translateScanStage(run.stage) }}
                    </p>
                  </div>
                  <small>{{
                    formatTimestamp(run.finished_at || run.started_at)
                  }}</small>
                  <span>
                    таблиц {{ numberFromSummary(run.summary, "active_tables") }},
                    колонок {{ numberFromSummary(run.summary, "active_columns") }},
                    связей
                    {{ numberFromSummary(run.summary, "active_relationships") }}
                  </span>
                </article>
              </div>
              <div v-else class="data-view__empty">
                Для этой базы пока нет сохранённых запусков сканирования.
              </div>
            </section>

            <section class="data-view__subpanel">
              <header class="data-view__subhead">
                <h3>Словарь semantic layer</h3>
                <p>
                  Термины хранятся рядом с knowledge metadata и доступны
                  NL→SQL-пайплайну.
                </p>
              </header>
              <form class="data-view__create" @submit.prevent="createTerm">
                <input
                  v-model="draft.term"
                  type="text"
                  placeholder="Термин (например revenue_total)"
                  required
                />
                <input
                  v-model="draft.mappedExpression"
                  type="text"
                  placeholder="SQL-выражение (например SUM(orders.amount))"
                  required
                />
                <input
                  v-model="draft.synonyms"
                  type="text"
                  placeholder="Синонимы через запятую"
                />
                <button class="app-button" type="submit" :disabled="isCreatingTerm">
                  {{ isCreatingTerm ? "Сохранение…" : "Добавить термин" }}
                </button>
              </form>
              <p v-if="dictionaryFeedback" class="data-view__feedback">
                {{ dictionaryFeedback }}
              </p>
              <div
                v-if="!databaseDictionary.length"
                class="data-view__empty"
              >
                Словарь пуст. После сканирования он может автоматически
                наполняться терминами таблиц и колонок.
              </div>
              <table v-else class="data-view__table">
                <thead>
                  <tr>
                    <th>Термин</th>
                    <th>Выражение</th>
                    <th>Описание</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="term in databaseDictionary" :key="term.id">
                    <td>
                      <strong>{{ term.term }}</strong>
                      <p v-if="term.synonyms.length" class="data-view__syn">
                        {{ term.synonyms.join(", ") }}
                      </p>
                    </td>
                    <td>
                      <code>{{ term.mapped_expression }}</code>
                    </td>
                    <td>{{ term.description }}</td>
                    <td>
                      <button
                        class="app-button app-button--link app-button--tiny"
                        type="button"
                        @click="removeTerm(term.id)"
                      >
                        Удалить
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </section>
          </div>

          <div class="data-view__knowledge">
            <aside class="data-view__tables">
              <header class="data-view__head data-view__head--compact">
                <div>
                  <p class="eyebrow">Таблицы слоя знаний</p>
                  <h2>Сканированная схема</h2>
                </div>
              </header>
              <div
                v-if="!knowledgeSummary.tables.length"
                class="data-view__empty"
              >
                База подключена, но слой знаний ещё не заполнен.
              </div>
              <button
                v-for="table in knowledgeSummary.tables"
                :key="table.id"
                type="button"
                class="data-view__table-pill"
                :class="{ 'is-active': selectedTableId === table.id }"
                @click="selectedTableId = table.id"
              >
                <strong>{{ table.schema_name }}.{{ table.table_name }}</strong>
                <span
                  >{{ table.column_count }} кол. · PK
                  {{ table.primary_key.join(", ") || "нет" }}</span
                >
                <small
                  >{{ table.row_count ?? "—" }} строк ·
                  {{ translateTableObjectType(table.object_type) }}</small
                >
              </button>
            </aside>

            <div class="data-view__detail">
              <div v-if="selectedTable" class="data-view__detail-body">
                <header class="data-view__head data-view__head--compact">
                  <div>
                    <p class="eyebrow">Редактор таблицы</p>
                    <h2>
                      {{ selectedTable.schema_name }}.{{
                        selectedTable.table_name
                      }}
                    </h2>
                    <p class="data-view__hint">
                      Ручные поля сохраняются между сканами. Автополя
                      пересчитываются при каждом парсинге.
                    </p>
                  </div>
                  <button
                    class="app-button app-button--ghost"
                    type="button"
                    :disabled="loadingTable"
                    @click="loadSelectedTable"
                  >
                    {{ loadingTable ? "Загрузка…" : "Обновить таблицу" }}
                  </button>
                </header>

                <div class="data-view__form-grid">
                  <label>
                    <span>Описание</span>
                    <textarea
                      v-model="tableDraft.description"
                      rows="3"
                    ></textarea>
                  </label>
                  <label>
                    <span>Бизнес-смысл</span>
                    <textarea
                      v-model="tableDraft.businessMeaning"
                      rows="3"
                    ></textarea>
                  </label>
                  <label>
                    <span>Домен</span>
                    <input
                      v-model="tableDraft.domain"
                      type="text"
                      placeholder="заказы / финансы / пользователи"
                    />
                  </label>
                  <label>
                    <span>Semantic label</span>
                    <input
                      v-model="tableDraft.semanticLabel"
                      type="text"
                      placeholder="например: Заказы"
                    />
                  </label>
                  <label>
                    <span>Semantic role</span>
                    <select v-model="tableDraft.semanticRole">
                      <option value="fact">fact</option>
                      <option value="dimension">dimension</option>
                      <option value="bridge">bridge</option>
                      <option value="lookup">lookup</option>
                      <option value="event">event</option>
                      <option value="snapshot">snapshot</option>
                    </select>
                  </label>
                  <label>
                    <span>Grain</span>
                    <textarea
                      v-model="tableDraft.semanticGrain"
                      rows="2"
                      placeholder="one row = one order"
                    ></textarea>
                  </label>
                  <label>
                    <span>Главная дата</span>
                    <input
                      v-model="tableDraft.semanticMainDateColumn"
                      type="text"
                      placeholder="created_at / order_date"
                    />
                  </label>
                  <label>
                    <span>Главная сущность</span>
                    <input
                      v-model="tableDraft.semanticMainEntity"
                      type="text"
                      placeholder="заказ / клиент / платёж"
                    />
                  </label>
                  <label>
                    <span>Semantic synonyms</span>
                    <input
                      v-model="tableDraft.semanticSynonyms"
                      type="text"
                      placeholder="синонимы через запятую"
                    />
                  </label>
                  <label>
                    <span>Important metrics</span>
                    <textarea
                      v-model="tableDraft.semanticImportantMetrics"
                      rows="3"
                      placeholder="total_revenue&#10;completed_revenue"
                    ></textarea>
                  </label>
                  <label>
                    <span>Important dimensions</span>
                    <input
                      v-model="tableDraft.semanticImportantDimensions"
                      type="text"
                      placeholder="status, city, category"
                    />
                  </label>
                  <label>
                    <span>Теги</span>
                    <input
                      v-model="tableDraft.tags"
                      type="text"
                      placeholder="финансы, заказы, pii"
                    />
                  </label>
                  <label>
                    <span>Чувствительность</span>
                    <input
                      v-model="tableDraft.sensitivity"
                      type="text"
                      placeholder="pii / финансовые / внутренние"
                    />
                  </label>
                </div>

                <div class="data-view__inline-actions">
                  <button
                    class="app-button"
                    type="button"
                    :disabled="isSavingTable"
                    @click="saveTable"
                  >
                    {{
                      isSavingTable
                        ? "Сохранение…"
                        : "Сохранить переопределения таблицы"
                    }}
                  </button>
                  <p class="data-view__auto-copy">
                    Автоописание: {{ selectedTable.description_auto || "—"
                    }}<br />
                    Автодомен: {{ selectedTable.domain_auto || "—" }}<br />
                    Effective role:
                    {{
                      translateTableRole(
                        selectedSemanticTable?.table_role ||
                          selectedTable.semantic_table_role_manual,
                      )
                    }}<br />
                    Effective grain:
                    {{
                      selectedSemanticTable?.grain ||
                      selectedTable.semantic_grain_manual ||
                      "—"
                    }}
                  </p>
                </div>

                <section class="data-view__subpanel">
                  <header class="data-view__subhead">
                    <h3>Колонки</h3>
                    <p>
                      Ручные семантические метки, синонимы и флаги скрытия для
                      LLM.
                    </p>
                  </header>
                  <div class="data-view__column-list">
                    <article
                      v-for="column in selectedTable.columns || []"
                      :key="column.id"
                      class="data-view__column-card"
                    >
                      <div class="data-view__column-meta">
                        <strong>{{ column.column_name }}</strong>
                        <span
                          >{{ column.data_type }} ·
                          {{
                            column.is_nullable
                              ? "может быть NULL"
                              : "обязательно"
                          }}</span
                        >
                        <small
                          >примеры:
                          {{ column.sample_values.join(", ") || "—" }}</small
                        >
                      </div>
                      <div class="data-view__column-edit">
                        <input
                          v-model="getColumnDraft(column).semanticLabel"
                          type="text"
                          placeholder="семантическая метка"
                        />
                        <input
                          v-model="getColumnDraft(column).synonyms"
                          type="text"
                          placeholder="синонимы через запятую"
                        />
                        <input
                          v-model="getColumnDraft(column).sensitivity"
                          type="text"
                          placeholder="чувствительность"
                        />
                        <label class="data-view__check">
                          <input
                            v-model="getColumnDraft(column).hiddenForLlm"
                            type="checkbox"
                          />
                          <span>Скрыть от LLM</span>
                        </label>
                        <textarea
                          v-model="getColumnDraft(column).description"
                          rows="2"
                          placeholder="описание колонки"
                        ></textarea>
                        <button
                          class="app-button app-button--ghost app-button--tiny"
                          type="button"
                          @click="saveColumn(column.id)"
                        >
                          Сохранить колонку
                        </button>
                      </div>
                    </article>
                  </div>
                </section>

                <section class="data-view__subpanel">
                  <header class="data-view__subhead">
                    <h3>Связи</h3>
                    <p>
                      FK-рёбра из слоя сканирования. Можно подтверждать и
                      отключать связи вручную.
                    </p>
                  </header>
                  <div
                    v-if="selectedTable.relationships?.length"
                    class="data-view__relationship-list"
                  >
                    <article
                      v-for="relationship in selectedTable.relationships"
                      :key="relationship.id"
                      class="data-view__relationship-card"
                    >
                      <div>
                        <strong>
                          {{ relationship.from_table_name }}.{{
                            relationship.from_column_name
                          }}
                          →
                          {{ relationship.to_table_name }}.{{
                            relationship.to_column_name
                          }}
                        </strong>
                        <p>
                          {{
                            translateRelationType(relationship.relation_type)
                          }}
                          · уверенность
                          {{ relationship.confidence.toFixed(2) }}
                        </p>
                      </div>
                      <div class="data-view__relationship-edit">
                        <input
                          v-model="
                            getRelationshipDraft(relationship).cardinality
                          "
                          type="text"
                          placeholder="many_to_one"
                        />
                        <input
                          v-model="
                            getRelationshipDraft(relationship).confidence
                          "
                          type="number"
                          min="0"
                          max="1"
                          step="0.1"
                        />
                        <label class="data-view__check">
                          <input
                            v-model="
                              getRelationshipDraft(relationship).approved
                            "
                            type="checkbox"
                          />
                          <span>Подтвердить</span>
                        </label>
                        <label class="data-view__check">
                          <input
                            v-model="
                              getRelationshipDraft(relationship).isDisabled
                            "
                            type="checkbox"
                          />
                          <span>Отключить</span>
                        </label>
                        <input
                          v-model="
                            getRelationshipDraft(relationship).description
                          "
                          type="text"
                          placeholder="комментарий"
                        />
                        <button
                          class="app-button app-button--ghost app-button--tiny"
                          type="button"
                          @click="saveRelationship(relationship.id)"
                        >
                          Сохранить связь
                        </button>
                      </div>
                    </article>
                  </div>
                  <div v-else class="data-view__empty">
                    Для выбранной таблицы связей пока нет.
                  </div>
                </section>
              </div>
              <div v-else class="data-view__empty">
                Выберите таблицу слева, чтобы редактировать семантику и связи.
              </div>
            </div>
          </div>
        </section>

        <section class="data-view__panel" v-if="erdGraph?.nodes.length">
          <header class="data-view__head data-view__head--compact">
            <div>
              <p class="eyebrow">ERD</p>
              <h2>Граф связей</h2>
              <p class="data-view__hint">
                Физический FK-граф по последнему снимку сканирования.
              </p>
            </div>
            <div class="data-view__graph-controls">
              <label class="data-view__toggle">
                <input v-model="showGraphColumns" type="checkbox" />
                <span>Колонки</span>
              </label>
              <label class="data-view__toggle">
                <input
                  v-model="showGraphSemantic"
                  type="checkbox"
                  :disabled="!semanticCatalog?.tables.length"
                />
                <span>Семантические метки</span>
              </label>
            </div>
          </header>
          <VChart class="data-view__erd" :option="erdOption" autoresize />
        </section>

        <section class="data-view__panel" v-if="semanticCatalog">
          <header class="data-view__head data-view__head--compact">
            <div>
              <p class="eyebrow">LLM-Прослойка</p>
              <h2>Semantic Catalog Preview</h2>
              <p class="data-view__hint">
                Это вычисленная проекция knowledge layer для LLM. Редактирование
                выполняется в блоке «Слой знаний о БД», а здесь показан итог,
                который получит агент.
              </p>
            </div>
          </header>
          <div class="data-view__semantic-grid">
            <article class="data-view__semantic-stat">
              <span>Таблицы</span>
              <strong>{{ semanticCatalog.tables.length }}</strong>
            </article>
            <article class="data-view__semantic-stat">
              <span>Связи</span>
              <strong>{{ semanticCatalog.relationships.length }}</strong>
            </article>
            <article class="data-view__semantic-stat">
              <span>Маршруты JOIN</span>
              <strong>{{ semanticCatalog.join_paths.length }}</strong>
            </article>
            <article class="data-view__semantic-stat">
              <span>Диалект</span>
              <strong>{{ semanticCatalog.dialect }}</strong>
            </article>
          </div>
          <section class="data-view__subpanel data-view__subpanel--tight" style="margin-top:1rem">
            <header class="data-view__subhead">
              <h3>Граф связей для LLM</h3>
            </header>
            <div v-if="semanticCatalog.relationship_graph.length" class="data-view__graph-list">
              <article
                v-for="edge in semanticCatalog.relationship_graph"
                :key="`${edge.from_table}-${edge.to_table}-${edge.on}`"
                class="data-view__graph-card"
              >
                <span>{{ edge.from_table }} → {{ edge.to_table }}</span>
                <strong>{{ edge.on }}</strong>
              </article>
            </div>
            <div v-else class="data-view__empty">Рёбра графа отсутствуют.</div>
          </section>
        </section>
      </div>
    </section>

    <AddDatabaseModal
      v-if="showAddDatabase"
      @close="showAddDatabase = false"
      @submit="submitDatabase"
    />
    <SemanticActivationModal
      :open="showSemanticActivationModal"
      :database-name="selectedDatabase?.name ?? ''"
      :database-description="semanticDescription"
      :table-descriptions-text="semanticActivationTableDescriptionsText"
      :relationship-descriptions-text="semanticActivationRelationshipDescriptionsText"
      :column-descriptions-text="semanticActivationColumnDescriptionsText"
      :submitting="semanticActivationSubmitting"
      @close="closeSemanticActivationModal"
      @submit="submitSemanticActivation"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import VChart from "vue-echarts";

import { api } from "@/api/client";
import AddDatabaseModal from "@/components/layout/AddDatabaseModal.vue";
import SemanticActivationModal from "@/components/layout/SemanticActivationModal.vue";
import ChatSidebar from "@/components/chat/ChatSidebar.vue";
import type {
  ApiDictionaryEntryRead,
  ApiERDGraph,
  ApiKnowledgeColumn,
  ApiKnowledgeRelationship,
  ApiKnowledgeSummary,
  ApiKnowledgeTable,
  ApiSemanticCatalog,
} from "@/api/types";
import { useChatStore } from "@/stores/chat";
import { useWorkspaceStore } from "@/stores/workspace";

const store = useWorkspaceStore();
const chat = useChatStore();

const selectedDatabaseId = ref("");
const knowledgeSummary = ref<ApiKnowledgeSummary | null>(null);
const semanticCatalog = ref<ApiSemanticCatalog | null>(null);
const selectedTableId = ref<string | null>(null);
const selectedTable = ref<ApiKnowledgeTable | null>(null);
const erdGraph = ref<ApiERDGraph | null>(null);
const scanRuns = ref<
  Array<{
    id: string;
    scan_type: string;
    status: string;
    stage: string;
    summary: Record<string, unknown>;
    started_at: string;
    finished_at?: string | null;
  }>
>([]);

const isCreatingTerm = ref(false);
const isScanning = ref(false);
const isSavingTable = ref(false);
const loadingTable = ref(false);
const isActivatingSemantic = ref(false);
const isDeletingDatabase = ref(false);
const isDeletingSemantic = ref(false);
const isSavingSemanticTable = ref(false);
const isSavingSemanticColumn = ref(false);
const showSemanticActivationModal = ref(false);
const semanticActivationSubmitting = ref(false);
const semanticActivationTableDescriptionsText = ref("");
const semanticActivationRelationshipDescriptionsText = ref("");
const semanticActivationColumnDescriptionsText = ref("");

const expandedTables = ref<Set<string>>(new Set());
const editingTable = ref<string | null>(null);
const editingColumn = ref<string | null>(null);
const databaseDictionary = ref<ApiDictionaryEntryRead[]>([]);

const tablePatchDraft = reactive({
  label: "",
  business_description: "",
  table_role: "fact",
  grain: "",
  main_date_column: "",
  synonyms_raw: "",
  important_metrics_raw: "",
});

const columnPatchDraft = reactive({
  label: "",
  business_description: "",
  synonyms_raw: "",
});
const showAddDatabase = ref(false);
const semanticDescription = ref("");
const showGraphColumns = ref(true);
const showGraphSemantic = ref(true);

const knowledgeFeedback = ref("");
const dictionaryFeedback = ref("");
const semanticFeedback = ref("");
const semanticAutoRefreshEnabled = ref(true);
const semanticAutoRefreshKey = ref("");
const SEMANTIC_AUTO_REFRESH_LS_KEY = "sql-ide.semantic-auto-refresh-enabled";

const draft = reactive({
  term: "",
  mappedExpression: "",
  synonyms: "",
});

const tableDraft = reactive({
  description: "",
  businessMeaning: "",
  domain: "",
  semanticLabel: "",
  semanticRole: "dimension",
  semanticGrain: "",
  semanticMainDateColumn: "",
  semanticMainEntity: "",
  semanticSynonyms: "",
  semanticImportantMetrics: "",
  semanticImportantDimensions: "",
  tags: "",
  sensitivity: "",
});

const columnDrafts = reactive<
  Record<
    string,
    {
      description: string;
      semanticLabel: string;
      synonyms: string;
      sensitivity: string;
      hiddenForLlm: boolean;
    }
  >
>({});

const relationshipDrafts = reactive<
  Record<
    string,
    {
      cardinality: string;
      confidence: string;
      approved: boolean;
      isDisabled: boolean;
      description: string;
    }
  >
>({});

const selectedDatabase = computed(
  () =>
    store.workspace.databases.find(
      (database) => database.id === selectedDatabaseId.value,
    ) ?? null,
);

const semanticTableLookup = computed(() => {
  const map = new Map<string, ApiSemanticCatalog["tables"][number]>();
  for (const table of semanticCatalog.value?.tables ?? []) {
    map.set(`${table.schema_name}.${table.table_name}`, table);
  }
  return map;
});

const semanticFactGrainWarnings = computed(() =>
  (semanticCatalog.value?.tables ?? [])
    .filter((table) => table.table_role === "fact" && !table.grain?.trim())
    .map((table) => table.table_name),
);

const selectedSemanticTable = computed(() => {
  if (!selectedTable.value) {
    return null;
  }
  return (
    semanticTableLookup.value.get(
      `${selectedTable.value.schema_name}.${selectedTable.value.table_name}`,
    ) ?? null
  );
});

function truncateText(value: string, limit = 88) {
  const compact = value.replace(/\s+/g, " ").trim();
  if (compact.length <= limit) {
    return compact;
  }
  return `${compact.slice(0, Math.max(limit - 1, 0)).trimEnd()}…`;
}

function tableNodeKey(node: ApiERDGraph["nodes"][number]) {
  return `${node.schema_name}.${node.table_name}`;
}

function tableNodeColumns(node: ApiERDGraph["nodes"][number]) {
  const semantic = semanticTableLookup.value.get(tableNodeKey(node));
  return semantic?.columns.map((column) => column.column_name) ?? [];
}

function tableNodeSemanticSummary(node: ApiERDGraph["nodes"][number]) {
  const semantic = semanticTableLookup.value.get(tableNodeKey(node));
  if (!semantic || !showGraphSemantic.value) {
    return "";
  }
  const parts = [
    semantic.table_role,
    semantic.grain ? `grain: ${semantic.grain}` : "",
    semantic.main_date_column ? `date: ${semantic.main_date_column}` : "",
    semantic.business_description
      ? truncateText(semantic.business_description, 92)
      : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

function tableNodeColor(node: ApiERDGraph["nodes"][number]) {
  const semantic = semanticTableLookup.value.get(tableNodeKey(node));
  switch (semantic?.table_role) {
    case "fact":
      return "#8aa4ff";
    case "dimension":
      return "#81c995";
    case "bridge":
      return "#f4c26b";
    case "snapshot":
      return "#d9a3ff";
    case "event":
      return "#5cc8ff";
    case "lookup":
      return "#9ab1c3";
    default:
      return "#2b6fff";
  }
}

const erdOption = computed(() => {
  const graph = erdGraph.value;
  if (!graph?.nodes.length) {
    return {
      series: [],
    };
  }

  const nodes = graph.nodes.map((node) => {
    const columns = tableNodeColumns(node);
    const semantic = semanticTableLookup.value.get(tableNodeKey(node));
    const columnPreview = showGraphColumns.value
      ? columns.slice(0, 3).join(", ") +
        (columns.length > 3 ? ` · +${columns.length - 3}` : "")
      : "";
    const semanticSummary = tableNodeSemanticSummary(node);

    return {
      id: node.id,
      name: node.table_name,
      value: node.row_count ?? node.column_count,
      symbolSize: Math.max(
        42,
        Math.min(
          92,
          24 +
            node.column_count * 2 +
            (showGraphSemantic.value && semantic ? 10 : 0),
        ),
      ),
      category: node.schema_name,
      schema_name: node.schema_name,
      table_name: node.table_name,
      row_count: node.row_count,
      column_count: node.column_count,
      columns,
      column_preview: columnPreview,
      semantic_summary: semanticSummary,
      table_role: semantic?.table_role ?? null,
      business_description: semantic?.business_description ?? null,
      main_date_column: semantic?.main_date_column ?? null,
      itemStyle: {
        color: tableNodeColor(node),
      },
    };
  });

  return {
    tooltip: {
      trigger: "item",
      formatter: (params: {
        data?: Record<string, unknown>;
        name?: string;
      }) => {
        const data = (params.data ?? {}) as {
          schema_name?: string;
          table_name?: string;
          column_count?: number;
          row_count?: number | null;
          columns?: string[];
          column_preview?: string;
          semantic_summary?: string;
          business_description?: string | null;
          table_role?: string | null;
          main_date_column?: string | null;
        };
        const lines = [
          `<strong>${data.schema_name ? `${data.schema_name}.` : ""}${data.table_name ?? params.name ?? ""}</strong>`,
          `Колонки: ${data.column_count ?? 0}`,
          `Строки: ${data.row_count ?? "—"}`,
        ];
        if (showGraphColumns.value && data.columns?.length) {
          lines.push(`Список колонок: ${data.columns.join(", ")}`);
        }
        if (showGraphSemantic.value && data.semantic_summary) {
          lines.push(`Семантика: ${data.semantic_summary}`);
        }
        if (data.business_description) {
          lines.push(`Описание: ${data.business_description}`);
        }
        if (data.main_date_column) {
          lines.push(`Главная дата: ${data.main_date_column}`);
        }
        return lines.join("<br/>");
      },
    },
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        force: {
          repulsion: 180,
          edgeLength: 110,
        },
        label: {
          show: true,
          formatter: (params: {
            data?: Record<string, unknown>;
            name?: string;
          }) => {
            const data = (params.data ?? {}) as {
              name?: string;
              column_preview?: string;
              semantic_summary?: string;
            };
            const lines = [data.name ?? params.name ?? ""];
            if (showGraphColumns.value && data.column_preview) {
              lines.push(data.column_preview);
            }
            if (showGraphSemantic.value && data.semantic_summary) {
              lines.push(data.semantic_summary);
            }
            return lines.filter(Boolean).join("\n");
          },
          color: "#e8eaed",
          fontSize: 11,
          lineHeight: 15,
          width: 170,
          overflow: "truncate",
        },
        lineStyle: {
          color: "#8aa4ff",
          width: 1.4,
          opacity: 0.75,
        },
        itemStyle: {
          color: "#2b6fff",
          borderColor: "#dbe5ff",
          borderWidth: 2,
        },
        data: nodes,
        links: graph.edges.map((edge) => ({
          source: edge.source,
          target: edge.target,
          value: edge.source_label,
        })),
      },
    ],
  };
});

function formatTimestamp(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function numberFromSummary(summary: Record<string, unknown>, key: string) {
  const value = summary[key];
  return typeof value === "number" ? value : 0;
}

function translateDatabaseMode(value?: string | null) {
  switch (value) {
    case "read_only":
      return "Только чтение";
    case "read_write":
      return "Чтение и запись";
    case "demo":
      return "Демо";
    default:
      return value || "—";
  }
}

function translateKnowledgeStatus(value?: string | null) {
  switch (value) {
    case "active":
      return "Активен";
    case "connected":
      return "Подключён";
    case "syncing":
      return "Сканируется";
    case "not_scanned":
      return "Не сканировался";
    case "failed":
      return "Ошибка";
    default:
      return value || "—";
  }
}

function translateScanType(value?: string | null) {
  switch (value) {
    case "full":
      return "Полный скан";
    case "incremental":
      return "Инкрементальный скан";
    default:
      return value || "—";
  }
}

function translateScanStatus(value?: string | null) {
  switch (value) {
    case "completed":
      return "Завершён";
    case "running":
      return "В процессе";
    case "failed":
      return "Ошибка";
    case "queued":
      return "В очереди";
    default:
      return value || "—";
  }
}

function translateScanStage(value?: string | null) {
  switch (value) {
    case "queued":
      return "Ожидание";
    case "schema":
    case "schema_snapshot":
      return "Снимок схемы";
    case "columns":
      return "Колонки";
    case "relationships":
      return "Связи";
    case "semantic":
    case "semantic_catalog":
      return "Семантика";
    case "completed":
      return "Завершение";
    default:
      return value || "—";
  }
}

function translateTableObjectType(value?: string | null) {
  switch (value) {
    case "table":
      return "таблица";
    case "view":
      return "представление";
    case "materialized_view":
      return "материализованное представление";
    default:
      return value || "—";
  }
}

function translateRelationType(value?: string | null) {
  switch (value) {
    case "foreign_key":
      return "внешний ключ";
    case "semantic":
      return "семантическая связь";
    default:
      return value || "—";
  }
}

function translateTableRole(value?: string | null) {
  switch (value) {
    case "fact":
      return "факт";
    case "dimension":
      return "измерение";
    case "bridge":
      return "мост";
    case "lookup":
      return "справочник";
    case "event":
      return "событие";
    case "snapshot":
      return "срез";
    case "reference":
      return "референс";
    default:
      return value || "—";
  }
}

function splitCsv(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function syncTableDraft(table: ApiKnowledgeTable | null) {
  tableDraft.description = table?.description_manual ?? "";
  tableDraft.businessMeaning = table?.business_meaning_manual ?? "";
  tableDraft.domain = table?.domain_manual ?? "";
  tableDraft.semanticLabel = table?.semantic_label_manual ?? "";
  tableDraft.semanticRole = table?.semantic_table_role_manual ?? "dimension";
  tableDraft.semanticGrain = table?.semantic_grain_manual ?? "";
  tableDraft.semanticMainDateColumn =
    table?.semantic_main_date_column_manual ?? "";
  tableDraft.semanticMainEntity = table?.semantic_main_entity_manual ?? "";
  tableDraft.semanticSynonyms = (table?.semantic_synonyms ?? []).join(", ");
  tableDraft.semanticImportantMetrics = (
    table?.semantic_important_metrics ?? []
  ).join("\n");
  tableDraft.semanticImportantDimensions = (
    table?.semantic_important_dimensions ?? []
  ).join(", ");
  tableDraft.tags = (table?.tags ?? []).join(", ");
  tableDraft.sensitivity = table?.sensitivity ?? "";

  Object.keys(columnDrafts).forEach((key) => delete columnDrafts[key]);
  Object.keys(relationshipDrafts).forEach(
    (key) => delete relationshipDrafts[key],
  );

  for (const column of table?.columns ?? []) {
    columnDrafts[column.id] = {
      description: column.description_manual ?? "",
      semanticLabel:
        column.semantic_label_manual ?? column.semantic_label_auto ?? "",
      synonyms: column.synonyms.join(", "),
      sensitivity: column.sensitivity ?? "",
      hiddenForLlm: Boolean(column.hidden_for_llm),
    };
  }

  for (const relationship of table?.relationships ?? []) {
    relationshipDrafts[relationship.id] = {
      cardinality: relationship.cardinality ?? "",
      confidence: String(relationship.confidence ?? 1),
      approved: Boolean(relationship.approved),
      isDisabled: Boolean(relationship.is_disabled),
      description: relationship.description_manual ?? "",
    };
  }
}

function getColumnDraft(column: ApiKnowledgeColumn) {
  if (!columnDrafts[column.id]) {
    columnDrafts[column.id] = {
      description: column.description_manual ?? "",
      semanticLabel:
        column.semantic_label_manual ?? column.semantic_label_auto ?? "",
      synonyms: column.synonyms.join(", "),
      sensitivity: column.sensitivity ?? "",
      hiddenForLlm: Boolean(column.hidden_for_llm),
    };
  }
  return columnDrafts[column.id];
}

function getRelationshipDraft(relationship: ApiKnowledgeRelationship) {
  if (!relationshipDrafts[relationship.id]) {
    relationshipDrafts[relationship.id] = {
      cardinality: relationship.cardinality ?? "",
      confidence: String(relationship.confidence ?? 1),
      approved: Boolean(relationship.approved),
      isDisabled: Boolean(relationship.is_disabled),
      description: relationship.description_manual ?? "",
    };
  }
  return relationshipDrafts[relationship.id];
}

function mergeTableIntoSummary(table: ApiKnowledgeTable) {
  selectedTable.value = table;
  syncTableDraft(table);
  if (!knowledgeSummary.value) return;
  knowledgeSummary.value.tables = knowledgeSummary.value.tables.map((item) =>
    item.id === table.id
      ? {
          ...item,
          description_manual: table.description_manual,
          business_meaning_manual: table.business_meaning_manual,
          domain_manual: table.domain_manual,
          semantic_label_manual: table.semantic_label_manual,
          semantic_table_role_manual: table.semantic_table_role_manual,
          semantic_grain_manual: table.semantic_grain_manual,
          semantic_main_date_column_manual:
            table.semantic_main_date_column_manual,
          semantic_main_entity_manual: table.semantic_main_entity_manual,
          semantic_synonyms: table.semantic_synonyms,
          semantic_important_metrics: table.semantic_important_metrics,
          semantic_important_dimensions: table.semantic_important_dimensions,
          tags: table.tags,
          sensitivity: table.sensitivity,
          column_count: table.column_count,
          row_count: table.row_count,
          primary_key: table.primary_key,
        }
      : item,
  );
}

async function loadSelectedTable() {
  if (!selectedTableId.value) {
    selectedTable.value = null;
    return;
  }
  loadingTable.value = true;
  try {
    const table = await api.getKnowledgeTable(selectedTableId.value);
    selectedTable.value = table;
    syncTableDraft(table);
  } catch (error) {
    knowledgeFeedback.value =
      error instanceof Error
        ? error.message
        : "Не удалось загрузить детали таблицы.";
    selectedTable.value = null;
  } finally {
    loadingTable.value = false;
  }
}

function buildSemanticDatabaseDescription() {
  const explicitDescription = semanticDescription.value.trim();
  if (explicitDescription) {
    return `${explicitDescription}\n\nПиши все label, business_description и synonyms на русском языке.`;
  }
  const databaseName =
    selectedDatabase.value?.name?.trim() ||
    selectedDatabaseId.value ||
    "database";
  return `База данных «${databaseName}». Пиши все label, business_description и synonyms на русском языке.`;
}

function formatTableDescriptions() {
  return (semanticCatalog.value?.tables ?? [])
    .map((table) => `${table.table_name}: ${table.business_description ?? ""}`.trim())
    .filter(Boolean)
    .join("\n");
}

function formatRelationshipDescriptions() {
  return (semanticCatalog.value?.relationships ?? [])
    .map(
      (relationship) =>
        `${relationship.from_table}.${relationship.from_column} -> ${relationship.to_table}.${relationship.to_column}: ${relationship.business_meaning ?? ""}`.trim(),
    )
    .filter(Boolean)
    .join("\n");
}

function formatColumnDescriptions() {
  const lines: string[] = [];
  for (const table of semanticCatalog.value?.tables ?? []) {
    for (const column of table.columns) {
      lines.push(
        `${table.table_name}.${column.column_name}: ${column.business_description ?? ""}`.trim(),
      );
    }
  }
  return lines.join("\n");
}

function parseTableDescriptions(text: string) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^([^:=]+?)\s*[:=]\s*(.+)$/);
      if (!match) return null;
      return {
        table_name: match[1].trim(),
        business_description: match[2].trim(),
      };
    })
    .filter((item): item is { table_name: string; business_description: string } => Boolean(item));
}

function parseRelationshipDescriptions(text: string) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(
        /^([^.]+?)\.([^\s]+?)\s*->\s*([^.]+?)\.([^\s]+?)\s*[:=]\s*(.+)$/,
      );
      if (!match) return null;
      return {
        from_table: match[1].trim(),
        from_column: match[2].trim(),
        to_table: match[3].trim(),
        to_column: match[4].trim(),
        business_meaning: match[5].trim(),
      };
    })
    .filter(
      (
        item,
      ): item is {
        from_table: string;
        from_column: string;
        to_table: string;
        to_column: string;
        business_meaning: string;
      } => Boolean(item),
    );
}

function parseColumnDescriptions(text: string) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^([^.]+?)\.([^\s]+?)\s*[:=]\s*(.+)$/);
      if (!match) return null;
      return {
        table_name: match[1].trim(),
        column_name: match[2].trim(),
        business_description: match[3].trim(),
      };
    })
    .filter(
      (
        item,
      ): item is {
        table_name: string;
        column_name: string;
        business_description: string;
      } => Boolean(item),
    );
}

function openSemanticActivationModal() {
  semanticActivationTableDescriptionsText.value = formatTableDescriptions();
  semanticActivationRelationshipDescriptionsText.value =
    formatRelationshipDescriptions();
  semanticActivationColumnDescriptionsText.value = formatColumnDescriptions();
  if (!semanticDescription.value.trim()) {
    semanticDescription.value = selectedDatabase.value?.description ?? "";
  }
  showSemanticActivationModal.value = true;
}

function closeSemanticActivationModal() {
  showSemanticActivationModal.value = false;
}

async function refreshSemanticCatalog(
  options: { auto?: boolean; force?: boolean } = {},
) {
  if (!selectedDatabaseId.value) {
    return;
  }
  if (options.auto && !semanticAutoRefreshEnabled.value) {
    return;
  }

  const description = buildSemanticDatabaseDescription();
  const lastScanId = knowledgeSummary.value?.last_scan?.id ?? "no-scan";
  const autoKey = `${selectedDatabaseId.value}::${lastScanId}::${description}`;
  if (
    options.auto &&
    !options.force &&
    semanticAutoRefreshKey.value === autoKey
  ) {
    return;
  }

  isActivatingSemantic.value = true;
  if (!options.auto) {
    semanticFeedback.value = "";
  }

  try {
    semanticCatalog.value = await api.activateSemanticCatalog({
      database_id: selectedDatabaseId.value,
      refresh: true,
      database_description: description,
    });
    semanticAutoRefreshKey.value = autoKey;
    semanticFeedback.value = options.auto
      ? `Семантический каталог автоматически обновлён для ${selectedDatabase.value?.name ?? selectedDatabaseId.value}.`
      : `Семантический каталог активирован для ${selectedDatabase.value?.name ?? selectedDatabaseId.value}.`;
  } catch (error) {
    semanticFeedback.value =
      error instanceof Error
        ? error.message
        : "Не удалось активировать семантику.";
  } finally {
    isActivatingSemantic.value = false;
  }
}

async function loadKnowledge() {
  if (!selectedDatabaseId.value) {
    knowledgeSummary.value = null;
    selectedTable.value = null;
    scanRuns.value = [];
    erdGraph.value = null;
    semanticCatalog.value = null;
    semanticAutoRefreshKey.value = "";
    return;
  }

  knowledgeFeedback.value = "";
  semanticFeedback.value = "";
  const [summaryResult, graphResult, semanticResult] =
    await Promise.allSettled([
      api.getKnowledge(selectedDatabaseId.value),
      api.getERD(selectedDatabaseId.value),
      api.getSemanticCatalog(selectedDatabaseId.value),
    ]);

  if (summaryResult.status === "fulfilled") {
    const summary = summaryResult.value;
    knowledgeSummary.value = summary;
    scanRuns.value = summary.scan_runs ?? [];
    databaseDictionary.value = summary.dictionary_entries ?? [];
    if ((summary.database_description ?? "").trim()) {
      semanticDescription.value = summary.database_description ?? "";
    }

    const stillExists = summary.tables.find(
      (table) => table.id === selectedTableId.value,
    );
    if (!stillExists) {
      selectedTableId.value = summary.tables[0]?.id ?? null;
    }

    if (selectedTableId.value) {
      await loadSelectedTable();
    } else {
      selectedTable.value = null;
    }
  } else {
    knowledgeSummary.value = null;
    selectedTable.value = null;
    selectedTableId.value = null;
    scanRuns.value = [];
    databaseDictionary.value = [];
    knowledgeFeedback.value =
      summaryResult.reason instanceof Error
        ? summaryResult.reason.message
        : "Не удалось загрузить слой знаний.";
  }

  if (graphResult.status === "fulfilled") {
    erdGraph.value = graphResult.value;
  } else {
    erdGraph.value = null;
    if (!knowledgeFeedback.value) {
      knowledgeFeedback.value =
        graphResult.reason instanceof Error
          ? graphResult.reason.message
          : "Не удалось загрузить граф ERD.";
    }
  }

  if (semanticResult.status === "fulfilled") {
    semanticCatalog.value = semanticResult.value;
  } else {
    semanticCatalog.value = null;
    semanticFeedback.value =
      semanticResult.reason instanceof Error
        ? semanticResult.reason.message
        : "Не удалось загрузить семантический каталог.";
  }

  if (
    selectedDatabaseId.value &&
    semanticCatalog.value &&
    semanticAutoRefreshEnabled.value
  ) {
    await refreshSemanticCatalog({ auto: true });
  }
}

async function reload() {
  await store.refreshWorkspace(store.selectedNotebookId || undefined, "keep");
  await chat.loadDatabases();
  if (!selectedDatabaseId.value) {
    selectedDatabaseId.value = store.workspace.databases[0]?.id ?? "";
    if (selectedDatabaseId.value) {
      await selectDatabase(selectedDatabaseId.value);
      return;
    }
  }
  if (selectedDatabaseId.value) {
    await chat.loadSessions(selectedDatabaseId.value);
  }
  await loadKnowledge();
}

async function runScan(mode: "full" | "incremental") {
  if (!selectedDatabaseId.value) return;
  isScanning.value = true;
  knowledgeFeedback.value = "";
  try {
    if (mode === "full") {
      await api.runKnowledgeFullScan(selectedDatabaseId.value);
    } else {
      await api.runKnowledgeIncrementalScan(selectedDatabaseId.value);
    }
    await store.refreshWorkspace(store.selectedNotebookId || undefined, "keep");
    await chat.loadDatabases();
    await loadKnowledge();
    knowledgeFeedback.value = `${mode === "full" ? "Полный" : "Инкрементальный"} скан завершён.`;
  } catch (error) {
    knowledgeFeedback.value =
      error instanceof Error
        ? error.message
        : "Не удалось выполнить сканирование.";
  } finally {
    isScanning.value = false;
  }
}

async function activateSemantic() {
  openSemanticActivationModal();
}

async function submitSemanticActivation(payload: {
  databaseDescription: string;
  tableDescriptionsText: string;
  relationshipDescriptionsText: string;
  columnDescriptionsText: string;
}) {
  if (!selectedDatabaseId.value) {
    return;
  }
  semanticActivationSubmitting.value = true;
  try {
    semanticDescription.value = payload.databaseDescription;
    semanticCatalog.value = await api.activateSemanticCatalog({
      database_id: selectedDatabaseId.value,
      refresh: true,
      database_description: payload.databaseDescription || null,
      table_descriptions: parseTableDescriptions(payload.tableDescriptionsText),
      relationship_descriptions: parseRelationshipDescriptions(
        payload.relationshipDescriptionsText,
      ),
      column_descriptions: parseColumnDescriptions(payload.columnDescriptionsText),
    });
    const lastScanId = knowledgeSummary.value?.last_scan?.id ?? "no-scan";
    semanticAutoRefreshKey.value = `${selectedDatabaseId.value}::${lastScanId}::${buildSemanticDatabaseDescription()}`;
    if (knowledgeSummary.value) {
      knowledgeSummary.value.database_description = payload.databaseDescription || null;
    }
    semanticFeedback.value = `Семантический каталог активирован для ${selectedDatabase.value?.name ?? selectedDatabaseId.value}.`;
    showSemanticActivationModal.value = false;
  } catch (error) {
    semanticFeedback.value =
      error instanceof Error
        ? error.message
        : "Не удалось активировать семантику.";
  } finally {
    semanticActivationSubmitting.value = false;
  }
}

async function deleteSelectedDatabase(databaseId?: string) {
  const targetId = databaseId ?? selectedDatabaseId.value;
  const previousSelectedId = selectedDatabaseId.value;
  const targetDatabase =
    store.workspace.databases.find((database) => database.id === targetId) ??
    selectedDatabase.value ??
    null;
  if (!targetDatabase || targetDatabase.isBuiltin || !targetId) {
    return;
  }
  const confirmed = window.confirm(
    `Удалить базу данных «${targetDatabase.name}»?`,
  );
  if (!confirmed) {
    return;
  }
  isDeletingDatabase.value = true;
  try {
    await api.deleteDatabase(targetId);
    await store.refreshWorkspace(store.selectedNotebookId || undefined, "keep");
    await chat.loadDatabases();
    const stillSelectedExists = store.workspace.databases.some(
      (database) => database.id === previousSelectedId,
    );
    if (targetId === previousSelectedId || !stillSelectedExists) {
      const nextDatabase = store.workspace.databases[0]?.id ?? "";
      selectedDatabaseId.value = nextDatabase;
      if (nextDatabase) {
        await chat.selectDatabase(nextDatabase);
        semanticDescription.value = selectedDatabase.value?.description ?? "";
      } else {
        semanticCatalog.value = null;
        knowledgeSummary.value = null;
        selectedTable.value = null;
        scanRuns.value = [];
        erdGraph.value = null;
        semanticDescription.value = "";
      }
    }
    knowledgeFeedback.value = "База данных удалена.";
  } catch (error) {
    knowledgeFeedback.value =
      error instanceof Error ? error.message : "Не удалось удалить базу.";
  } finally {
    isDeletingDatabase.value = false;
  }
}

async function selectDatabase(databaseId: string) {
  if (!databaseId) {
    return;
  }
  if (databaseId === selectedDatabaseId.value) {
    await chat.selectDatabase(databaseId);
    if (!semanticDescription.value.trim()) {
      semanticDescription.value = selectedDatabase.value?.description ?? "";
    }
    return;
  }
  selectedDatabaseId.value = databaseId;
  await chat.selectDatabase(databaseId);
  if (!semanticDescription.value.trim()) {
    semanticDescription.value = selectedDatabase.value?.description ?? "";
  }
}

function selectChatSession(sessionId: string) {
  void chat.selectSession(sessionId);
}

function createChatSession(databaseId?: string) {
  void chat.createSession(databaseId || selectedDatabaseId.value || undefined);
}

function renameChatSession(sessionId: string, title: string) {
  void chat.renameSession(sessionId, title);
}

function deleteChatSession(sessionId: string) {
  void chat.deleteSession(sessionId);
}

async function renameDatabase(databaseId: string, title: string) {
  if (!databaseId || !title.trim()) {
    return;
  }
  try {
    await api.updateDatabase(databaseId, { name: title.trim() });
    await store.refreshWorkspace(store.selectedNotebookId || undefined, "keep");
    await chat.loadDatabases();
    if (databaseId === selectedDatabaseId.value) {
      selectedDatabaseId.value = databaseId;
      if (!semanticDescription.value.trim()) {
        semanticDescription.value = selectedDatabase.value?.description ?? "";
      }
    }
    knowledgeFeedback.value = "База данных переименована.";
  } catch (error) {
    knowledgeFeedback.value =
      error instanceof Error ? error.message : "Не удалось переименовать базу.";
  }
}

async function submitDatabase(payload: {
  name: string;
  engine: string;
  host: string;
  port: string;
  database: string;
  user: string;
  password: string;
  tables: number;
  importSchemaToDictionary: boolean;
  allowedTables: string[] | null;
}) {
  try {
    const created = await store.connectDatabase({
      name: payload.name,
      engine: payload.engine,
      host: payload.host,
      port: payload.port,
      database: payload.database,
      user: payload.user,
      password: payload.password,
      tables: payload.tables,
      importSchemaToDictionary: payload.importSchemaToDictionary,
      allowedTables: payload.allowedTables,
    });
    showAddDatabase.value = false;
    selectedDatabaseId.value = created.id;
    semanticDescription.value = created.description ?? "";
    await chat.selectDatabase(created.id);
    await reload();
  } catch {
    // banner already shows the error
  }
}

async function saveTable() {
  if (!selectedTable.value) return;
  isSavingTable.value = true;
  try {
    const table = await api.updateKnowledgeTable(selectedTable.value.id, {
      description_manual: tableDraft.description || null,
      business_meaning_manual: tableDraft.businessMeaning || null,
      domain_manual: tableDraft.domain || null,
      semantic_label_manual: tableDraft.semanticLabel || null,
      semantic_table_role_manual: tableDraft.semanticRole || null,
      semantic_grain_manual: tableDraft.semanticGrain || null,
      semantic_main_date_column_manual:
        tableDraft.semanticMainDateColumn || null,
      semantic_main_entity_manual: tableDraft.semanticMainEntity || null,
      semantic_synonyms: splitCsv(tableDraft.semanticSynonyms),
      semantic_important_metrics: tableDraft.semanticImportantMetrics
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean),
      semantic_important_dimensions: splitCsv(
        tableDraft.semanticImportantDimensions,
      ),
      tags: splitCsv(tableDraft.tags),
      sensitivity: tableDraft.sensitivity || null,
    });
    mergeTableIntoSummary(table);
    erdGraph.value = await api.getERD(selectedDatabaseId.value);
    await refreshSemanticCatalog({ auto: true, force: true });
    knowledgeFeedback.value = "Переопределения таблицы сохранены.";
  } catch (error) {
    knowledgeFeedback.value =
      error instanceof Error ? error.message : "Не удалось сохранить таблицу.";
  } finally {
    isSavingTable.value = false;
  }
}

async function saveColumn(columnId: string) {
  const draftState = columnDrafts[columnId];
  if (!draftState) return;
  try {
    const table = await api.updateKnowledgeColumn(columnId, {
      description_manual: draftState.description || null,
      semantic_label_manual: draftState.semanticLabel || null,
      synonyms: splitCsv(draftState.synonyms),
      sensitivity: draftState.sensitivity || null,
      hidden_for_llm: draftState.hiddenForLlm,
    });
    mergeTableIntoSummary(table);
    await refreshSemanticCatalog({ auto: true, force: true });
    knowledgeFeedback.value = "Переопределения колонки сохранены.";
  } catch (error) {
    knowledgeFeedback.value =
      error instanceof Error ? error.message : "Не удалось сохранить колонку.";
  }
}

async function saveRelationship(relationshipId: string) {
  const draftState = relationshipDrafts[relationshipId];
  if (!draftState) return;
  try {
    const table = await api.updateKnowledgeRelationship(relationshipId, {
      cardinality: draftState.cardinality || null,
      confidence: Number.parseFloat(draftState.confidence) || 0,
      approved: draftState.approved,
      is_disabled: draftState.isDisabled,
      description_manual: draftState.description || null,
    });
    mergeTableIntoSummary(table);
    erdGraph.value = await api.getERD(selectedDatabaseId.value);
    await refreshSemanticCatalog({ auto: true, force: true });
    knowledgeFeedback.value = "Переопределения связи сохранены.";
  } catch (error) {
    knowledgeFeedback.value =
      error instanceof Error ? error.message : "Не удалось сохранить связь.";
  }
}

async function createTerm() {
  isCreatingTerm.value = true;
  dictionaryFeedback.value = "";
  try {
    const synonyms = splitCsv(draft.synonyms);
    await api.createDictionaryEntry({
      term: draft.term.trim(),
      synonyms,
      mapped_expression: draft.mappedExpression.trim(),
      description: "Добавлено вручную из раздела «Данные».",
      object_type: "manual",
      database_id: selectedDatabaseId.value || undefined,
      source_database: selectedDatabase.value?.name || undefined,
    });
    draft.term = "";
    draft.mappedExpression = "";
    draft.synonyms = "";
    dictionaryFeedback.value = "Термин добавлен.";
    await loadKnowledge();
  } finally {
    isCreatingTerm.value = false;
  }
}

async function removeTerm(id: string) {
  await api.deleteDictionaryEntry(id);
  await loadKnowledge();
}

function toggleTableExpand(tableName: string) {
  const next = new Set(expandedTables.value);
  if (next.has(tableName)) {
    next.delete(tableName);
  } else {
    next.add(tableName);
  }
  expandedTables.value = next;
}

function openTableEdit(table: ApiSemanticCatalog["tables"][number]) {
  editingTable.value = table.table_name;
  tablePatchDraft.label = table.label ?? "";
  tablePatchDraft.business_description = table.business_description ?? "";
  tablePatchDraft.table_role = table.table_role ?? "fact";
  tablePatchDraft.grain = table.grain ?? "";
  tablePatchDraft.main_date_column = table.main_date_column ?? "";
  tablePatchDraft.synonyms_raw = (table.synonyms ?? []).join(", ");
  tablePatchDraft.important_metrics_raw = (table.important_metrics ?? []).join("\n");
}

async function saveTablePatch(tableName: string) {
  if (!selectedDatabaseId.value) return;
  isSavingSemanticTable.value = true;
  try {
    await api.patchSemanticTable(selectedDatabaseId.value, tableName, {
      label: tablePatchDraft.label || null,
      business_description: tablePatchDraft.business_description || null,
      table_role: (tablePatchDraft.table_role as "fact" | "dimension" | "bridge" | "lookup" | "event" | "snapshot") || null,
      grain: tablePatchDraft.grain || null,
      main_date_column: tablePatchDraft.main_date_column || null,
      synonyms: splitCsv(tablePatchDraft.synonyms_raw),
      important_metrics: tablePatchDraft.important_metrics_raw
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean),
    });
    semanticCatalog.value = await api.getSemanticCatalog(selectedDatabaseId.value);
    editingTable.value = null;
    semanticFeedback.value = `Таблица «${tableName}» обновлена.`;
  } catch (error) {
    semanticFeedback.value = error instanceof Error ? error.message : "Не удалось сохранить таблицу.";
  } finally {
    isSavingSemanticTable.value = false;
  }
}

function openColumnEdit(tableName: string, columnName: string) {
  const table = semanticCatalog.value?.tables.find((t) => t.table_name === tableName);
  const col = table?.columns.find((c) => c.column_name === columnName);
  editingColumn.value = `${tableName}.${columnName}`;
  columnPatchDraft.label = col?.label ?? "";
  columnPatchDraft.business_description = col?.business_description ?? "";
  columnPatchDraft.synonyms_raw = (col?.synonyms ?? []).join(", ");
}

async function saveColumnPatch(tableName: string, columnName: string) {
  if (!selectedDatabaseId.value) return;
  isSavingSemanticColumn.value = true;
  try {
    await api.patchSemanticColumn(selectedDatabaseId.value, tableName, columnName, {
      label: columnPatchDraft.label || null,
      business_description: columnPatchDraft.business_description || null,
      synonyms: splitCsv(columnPatchDraft.synonyms_raw),
    });
    semanticCatalog.value = await api.getSemanticCatalog(selectedDatabaseId.value);
    editingColumn.value = null;
    semanticFeedback.value = `Колонка «${tableName}.${columnName}» обновлена.`;
  } catch (error) {
    semanticFeedback.value = error instanceof Error ? error.message : "Не удалось сохранить колонку.";
  } finally {
    isSavingSemanticColumn.value = false;
  }
}

async function deleteSemanticCatalog() {
  if (!selectedDatabaseId.value) return;
  const confirmed = window.confirm("Удалить активный семантический каталог? Его можно будет пересоздать.");
  if (!confirmed) return;
  isDeletingSemantic.value = true;
  try {
    await api.deleteSemanticCatalog(selectedDatabaseId.value);
    semanticCatalog.value = null;
    semanticFeedback.value = "Семантический каталог удалён.";
  } catch (error) {
    semanticFeedback.value = error instanceof Error ? error.message : "Не удалось удалить каталог.";
  } finally {
    isDeletingSemantic.value = false;
  }
}

async function loadDatabaseDictionary() {
  if (!selectedDatabaseId.value) {
    databaseDictionary.value = [];
    return;
  }
  try {
    databaseDictionary.value = await api.getDictionary(selectedDatabaseId.value);
  } catch {
    databaseDictionary.value = [];
  }
}

watch(selectedDatabaseId, async (value, previousValue) => {
  if (!value || value === previousValue) return;
  selectedTableId.value = null;
  selectedTable.value = null;
  if (!semanticDescription.value.trim()) {
    semanticDescription.value = selectedDatabase.value?.description ?? "";
  }
  await loadKnowledge();
});

watch(selectedTableId, async (value, previousValue) => {
  if (!value || value === previousValue) return;
  await loadSelectedTable();
});

onMounted(async () => {
  const storedSemanticAutoRefresh =
    typeof window !== "undefined"
      ? window.localStorage.getItem(SEMANTIC_AUTO_REFRESH_LS_KEY)
      : null;
  if (storedSemanticAutoRefresh !== null) {
    semanticAutoRefreshEnabled.value = storedSemanticAutoRefresh !== "false";
  }
  await Promise.allSettled([
    store.refreshWorkspace(store.selectedNotebookId || undefined, "keep"),
    chat.initialize(),
  ]);
  selectedDatabaseId.value =
    chat.activeDbId || store.workspace.databases[0]?.id || "";
  if (
    selectedDatabaseId.value &&
    chat.activeDbId !== selectedDatabaseId.value
  ) {
    await chat.selectDatabase(selectedDatabaseId.value);
  }
  if (selectedDatabaseId.value) {
    await loadKnowledge();
  }
});

watch(semanticAutoRefreshEnabled, (enabled) => {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(SEMANTIC_AUTO_REFRESH_LS_KEY, String(enabled));
  }
  if (enabled && selectedDatabaseId.value && semanticCatalog.value) {
    void refreshSemanticCatalog({ auto: true, force: true });
  }
});
</script>

<style scoped lang="scss">
.data-shell {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: var(--app-shell-sidebar-width) minmax(0, 1fr);
  gap: var(--app-shell-gap);
  padding: var(--app-shell-gap);
  background: var(--bg);
}

.data-shell__sidebar {
  min-height: 0;
  width: var(--app-shell-sidebar-width);
  max-width: 100%;
}

.data-shell__content {
  min-height: 0;
  overflow: auto;
}

.data-view {
  min-height: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.data-view__panel {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background:
    radial-gradient(
      circle at top right,
      rgba(138, 180, 248, 0.08),
      transparent 28%
    ),
    linear-gradient(180deg, rgba(26, 29, 36, 0.96), rgba(18, 20, 27, 0.98));
  padding: 1.1rem 1.15rem;
  box-shadow: var(--shadow-soft);
}

.data-view__panel--hero {
  background:
    radial-gradient(
      circle at top right,
      rgba(129, 201, 149, 0.08),
      transparent 24%
    ),
    radial-gradient(
      circle at top left,
      rgba(138, 180, 248, 0.14),
      transparent 28%
    ),
    linear-gradient(180deg, rgba(21, 24, 34, 0.98), rgba(15, 17, 23, 0.99));
}

.data-view__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.data-view__head--compact {
  margin-bottom: 0.8rem;
}

.data-view__head h1,
.data-view__head h2 {
  margin: 0.2rem 0 0.25rem;
  color: var(--ink-strong);
}

.data-view__head h1 {
  font-size: 1.28rem;
}

.data-view__head h2 {
  font-size: 1.04rem;
}

.data-view__hint {
  margin: 0;
  color: var(--muted);
  font-size: 0.86rem;
  line-height: 1.45;
  max-width: 760px;
}

.data-view__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  align-items: center;
  justify-content: flex-end;
}

.data-view__active-db {
  min-width: 220px;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(18, 20, 27, 0.92);
}

.data-view__active-db span,
.data-view__active-db strong {
  display: block;
}

.data-view__active-db span {
  color: var(--muted);
  font-size: 0.72rem;
}

.data-view__active-db strong {
  color: var(--ink-strong);
  font-size: 0.88rem;
  margin-top: 0.15rem;
}

.data-view__select,
.data-view__form-grid input,
.data-view__form-grid select,
.data-view__form-grid textarea,
.data-view__create input,
.data-view__column-edit input,
.data-view__column-edit textarea,
.data-view__relationship-edit input {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.55rem 0.65rem;
  background: rgba(18, 20, 27, 0.92);
  color: var(--ink);
}

.data-view__select {
  min-width: 240px;
}

.data-view__feedback {
  margin: 0;
  color: var(--muted);
  font-size: 0.84rem;
}

.data-view__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
  margin-top: 12px;
}

.data-view__stat {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 0.85rem;
  background: rgba(18, 20, 27, 0.92);
}

.data-view__stat span,
.data-view__stat small {
  display: block;
  color: var(--muted);
}

.data-view__stat strong {
  display: block;
  margin: 0.2rem 0;
  color: var(--ink-strong);
}

.data-view__scan-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.75rem;
}

.data-view__scan-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.8rem;
  background: rgba(21, 24, 34, 0.94);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.data-view__scan-card p,
.data-view__scan-card span,
.data-view__scan-card small {
  margin: 0;
  color: var(--muted);
  font-size: 0.82rem;
}

.data-view__knowledge {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 1rem;
}

.data-view__knowledge-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.data-view__tables {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.data-view__table-pill {
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.75rem;
  background: rgba(21, 24, 34, 0.88);
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.data-view__table-pill strong,
.data-view__table-pill span,
.data-view__table-pill small {
  display: block;
}

.data-view__table-pill span,
.data-view__table-pill small {
  color: var(--muted);
  font-size: 0.8rem;
}

.data-view__table-pill.is-active {
  border-color: rgba(138, 180, 248, 0.34);
  box-shadow: 0 0 0 1px rgba(138, 180, 248, 0.12);
  background: rgba(26, 39, 64, 0.92);
}

.data-view__detail {
  min-width: 0;
}

.data-view__detail-body,
.data-view__subpanel {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.data-view__form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.data-view__form-grid label,
.data-view__column-edit,
.data-view__relationship-edit {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.data-view__form-grid span {
  font-size: 0.78rem;
  color: var(--muted);
}

.data-view__form-grid textarea {
  resize: vertical;
}

.data-view__inline-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.data-view__auto-copy {
  margin: 0;
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.45;
}

.data-view__subpanel {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 0.85rem;
}

.data-view__subpanel--tight {
  border-top: 0;
  padding-top: 0;
  margin-bottom: 0.8rem;
}

.data-view__subhead h3 {
  margin: 0;
  font-size: 0.98rem;
  color: var(--ink-strong);
}

.data-view__subhead p {
  margin: 0.2rem 0 0;
  color: var(--muted);
  font-size: 0.82rem;
}

.data-view__column-list,
.data-view__relationship-list {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.data-view__column-card,
.data-view__relationship-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.8rem;
  background: rgba(18, 20, 27, 0.9);
  display: grid;
  grid-template-columns: minmax(180px, 220px) minmax(0, 1fr);
  gap: 0.75rem;
}

.data-view__column-meta,
.data-view__relationship-card > div:first-child {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.data-view__column-meta span,
.data-view__column-meta small,
.data-view__relationship-card p {
  color: var(--muted);
  font-size: 0.8rem;
  margin: 0;
}

.data-view__relationship-edit {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.55rem;
  align-items: center;
}

.data-view__check {
  display: inline-flex;
  gap: 0.4rem;
  align-items: center;
  font-size: 0.78rem;
  color: var(--muted);
}

.data-view__erd {
  width: 100%;
  height: 480px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background:
    radial-gradient(circle at top, rgba(138, 180, 248, 0.06), transparent 32%),
    rgba(18, 20, 27, 0.92);
}

.data-view__graph-controls {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
  align-items: center;
}

.data-view__semantic-actions {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
}

.data-view__toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.65rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(18, 20, 27, 0.88);
  color: var(--muted);
  font-size: 0.8rem;
}

.data-view__toggle input {
  accent-color: #8aa4ff;
}

.data-view__toggle:has(input:disabled) {
  opacity: 0.5;
}

.data-view__semantic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.9rem;
}

.data-view__graph-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.65rem;
}

.data-view__graph-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.75rem;
  background: rgba(18, 20, 27, 0.92);
}

.data-view__graph-card span,
.data-view__graph-card strong {
  display: block;
}

.data-view__graph-card span {
  color: var(--muted);
  font-size: 0.78rem;
  margin-bottom: 0.2rem;
}

.data-view__graph-card strong {
  color: var(--ink-strong);
  font-size: 0.82rem;
  line-height: 1.4;
  word-break: break-word;
}

.data-view__semantic-source {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1.5fr) minmax(0, 1fr);
  gap: 0.75rem;
  margin-bottom: 0.85rem;
}

.data-view__semantic-compose {
  margin-bottom: 0.85rem;
}

.data-view__semantic-description {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.data-view__semantic-description span,
.data-view__semantic-description small {
  color: var(--muted);
  font-size: 0.78rem;
}

.data-view__semantic-description textarea {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.75rem 0.8rem;
  background: rgba(18, 20, 27, 0.92);
  color: var(--ink);
  resize: vertical;
  min-height: 140px;
}

.data-view__semantic-description textarea:focus {
  outline: none;
  border-color: rgba(138, 180, 248, 0.75);
}

.data-view__semantic-source-item {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.8rem;
  background: rgba(18, 20, 27, 0.92);
}

.data-view__semantic-source-item span,
.data-view__semantic-source-item small {
  display: block;
  color: var(--muted);
  font-size: 0.78rem;
}

.data-view__semantic-source-item strong {
  display: block;
  margin: 0.25rem 0 0.15rem;
  color: var(--ink-strong);
  word-break: break-word;
}

.data-view__semantic-stat {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.8rem;
  background: rgba(18, 20, 27, 0.92);
}

.data-view__semantic-stat span {
  display: block;
  color: var(--muted);
  font-size: 0.78rem;
}

.data-view__semantic-stat strong {
  display: block;
  margin-top: 0.25rem;
  color: var(--ink-strong);
}

.data-view__semantic-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.65rem;
}

.data-view__semantic-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.8rem;
  background: rgba(21, 24, 34, 0.9);
}

.data-view__semantic-card strong,
.data-view__semantic-card p,
.data-view__semantic-card small {
  display: block;
  margin: 0;
}

.data-view__semantic-card p,
.data-view__semantic-card small {
  color: var(--muted);
  font-size: 0.8rem;
}

.data-view__create {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr auto;
  gap: 0.55rem;
  margin-bottom: 0.9rem;
}

.data-view__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
}

.data-view__table th,
.data-view__table td {
  text-align: left;
  padding: 0.55rem 0.65rem;
  border-bottom: 1px solid var(--line);
}

.data-view__syn {
  margin: 0.25rem 0 0;
  color: var(--muted);
  font-size: 0.78rem;
}

.data-view__empty {
  padding: 1rem;
  color: var(--muted);
  text-align: center;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  background: rgba(21, 24, 34, 0.72);
}

.data-view__sem-tables {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  margin-bottom: 1rem;
}

.data-view__sem-table {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(18, 20, 27, 0.92);
  overflow: hidden;
}

.data-view__sem-table-head {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.65rem 0.75rem;
}

.data-view__sem-expand {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 0.9rem;
  cursor: pointer;
  flex-shrink: 0;
  width: 20px;
}

.data-view__sem-table-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.data-view__sem-table-meta strong {
  color: var(--ink-strong);
  font-size: 0.9rem;
}

.data-view__sem-table-meta span,
.data-view__sem-table-meta small {
  color: var(--muted);
  font-size: 0.78rem;
}

.data-view__sem-table-counts {
  color: var(--muted);
  font-size: 0.78rem;
  white-space: nowrap;
}

.data-view__sem-columns {
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  padding: 0.45rem 0.75rem 0.55rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.data-view__sem-col {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.data-view__sem-col-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0;
  flex-wrap: wrap;
}

.data-view__sem-col-name {
  font-size: 0.82rem;
  color: var(--ink-strong);
  font-family: var(--mono, monospace);
  min-width: 120px;
}

.data-view__sem-col-label {
  font-size: 0.78rem;
  color: var(--muted);
  flex: 1;
}

.data-view__sem-col-type {
  font-size: 0.72rem;
  color: var(--muted);
  font-family: var(--mono, monospace);
}

.data-view__sem-badge {
  font-size: 0.68rem;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: rgba(138, 180, 248, 0.15);
  color: #8aa4ff;
  border: 1px solid rgba(138, 180, 248, 0.25);
  white-space: nowrap;
}

.data-view__sem-badge--pk {
  background: rgba(244, 194, 107, 0.15);
  color: #f4c26b;
  border-color: rgba(244, 194, 107, 0.3);
}

.data-view__sem-badge--fk {
  background: rgba(129, 201, 149, 0.15);
  color: #81c995;
  border-color: rgba(129, 201, 149, 0.3);
}

.data-view__sem-edit-form {
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  padding: 0.75rem;
  background: rgba(21, 24, 34, 0.7);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.data-view__sem-edit-row {
  display: grid;
  grid-template-columns: 130px minmax(0, 1fr);
  gap: 0.5rem;
  align-items: start;
}

.data-view__sem-edit-row label {
  font-size: 0.78rem;
  color: var(--muted);
  padding-top: 0.45rem;
}

.data-view__sem-edit-row input,
.data-view__sem-edit-row textarea,
.data-view__sem-edit-row select {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0.4rem 0.55rem;
  background: rgba(18, 20, 27, 0.92);
  color: var(--ink);
  font-size: 0.82rem;
  width: 100%;
}

.data-view__sem-edit-row textarea {
  resize: vertical;
}

.data-view__sem-edit-actions {
  display: flex;
  gap: 0.45rem;
  padding-left: 130px;
}

@media (max-width: 1100px) {
  .data-shell {
    grid-template-columns: 1fr;
  }

  .data-view__knowledge,
  .data-view__stats,
  .data-view__semantic-grid,
  .data-view__form-grid,
  .data-view__column-card,
  .data-view__relationship-card,
  .data-view__relationship-edit,
  .data-view__create {
    grid-template-columns: 1fr;
  }

  .data-view__inline-actions,
  .data-view__head {
    flex-direction: column;
    align-items: stretch;
  }

  .data-view__select {
    min-width: 0;
  }
}
</style>
