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
        <section class="data-view__toolbar">
          <div class="data-view__active-db">
            <span>Выбранная БД</span>
            <strong>{{
              selectedDatabase?.name ?? "Подключение ещё не выбрано"
            }}</strong>
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
        </section>
        <div class="content-wrapper">
          <section class="data-view__panel data-view__panel--hero">
            <header class="data-view__head">
              <div class="data-view__head-copy">
                <p class="eyebrow">Слой знаний о БД</p>
                <h1>
                  Центр управления данными
                  <AppTooltip>
                    Здесь команда запускает парсинг БД, следит за запусками
                    сканирования, редактирует семантику таблиц и колонок и
                    смотрит ERD без ручного импорта сырой схемы в
                    словарь.</AppTooltip
                  >
                </h1>
                <p class="data-view__lead">
                  Верхний уровень вынесен в отдельную панель, а рабочая часть
                  страницы оставлена для knowledge layer, схемы и semantic
                  metadata.
                </p>
              </div>
            </header>

            <div v-if="pageNotices.length" class="data-view__notice-list">
              <article
                v-for="notice in pageNotices"
                :key="notice.key"
                class="data-view__notice"
                :class="`data-view__notice--${notice.tone}`"
              >
                {{ notice.text }}
              </article>
            </div>

            <div v-if="selectedDatabase" class="data-view__stats">
              <article class="data-view__stat">
                <span>Подключение</span>
                <strong>{{ selectedDatabase.engine }}</strong>
                <small>{{
                  translateDatabaseMode(selectedDatabase.mode)
                }}</small>
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
                  >{{
                    knowledgeSummary?.active_column_count ?? 0
                  }}
                  колонок</small
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
                <strong>{{
                  semanticCatalog ? "активна" : "не активна"
                }}</strong>
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
                <h2>
                  Семантический слой и метаданные
                  <AppTooltip>
                    Здесь хранится всё, что влияет на понимание базы: описание
                    предметной области, словарь, запуски сканирования, semantic
                    overrides таблиц и колонок, а также отдельные флаги скрытия
                    от LLM.</AppTooltip
                  >
                </h2>
              </div>
              <div class="data-view__semantic-actions">
                <label class="data-view__toggle">
                  <input v-model="semanticAutoRefreshEnabled" type="checkbox" />
                  <span>Автообновление</span>
                </label>
                <button
                  class="app-button app-button--ghost"
                  type="button"
                  :disabled="!semanticCatalog"
                  @click="openSemanticLayerModal"
                >
                  Открыть semantic layer
                </button>
                <button
                  class="app-button app-button--ghost"
                  type="button"
                  :disabled="isActivatingSemantic"
                  @click="openSemanticActivationModal"
                >
                  {{
                    isActivatingSemantic
                      ? "Обновляем semantic layer…"
                      : "Запустить semantic activation"
                  }}
                </button>
                <button
                  class="app-button app-button--danger"
                  type="button"
                  :disabled="isDeletingSemantic"
                  @click="deleteSemanticCatalog"
                >
                  {{
                    isDeletingSemantic
                      ? "Удаляем проекцию…"
                      : "Сбросить LLM-проекцию"
                  }}
                </button>
              </div>
            </header>
            <div v-if="semanticNotices.length" class="data-view__notice-list">
              <article
                v-for="notice in semanticNotices"
                :key="notice.key"
                class="data-view__notice"
                :class="`data-view__notice--${notice.tone}`"
              >
                {{ notice.text }}
              </article>
            </div>
            <div class="data-view__knowledge-overview">
              <div class="data-view__knowledge-overview-primary">
                <section class="data-view__subpanel data-view__subpanel--panel">
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

                <section class="data-view__subpanel data-view__subpanel--panel">
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
                        таблиц
                        {{ numberFromSummary(run.summary, "active_tables") }},
                        колонок
                        {{ numberFromSummary(run.summary, "active_columns") }},
                        связей
                        {{
                          numberFromSummary(run.summary, "active_relationships")
                        }}
                      </span>
                    </article>
                  </div>
                  <div v-else class="data-view__empty">
                    Для этой базы пока нет сохранённых запусков сканирования.
                  </div>
                </section>
              </div>

              <section class="data-view__subpanel data-view__subpanel--panel">
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
                  <button
                    class="app-button"
                    type="submit"
                    :disabled="isCreatingTerm"
                  >
                    {{ isCreatingTerm ? "Сохранение…" : "Добавить термин" }}
                  </button>
                </form>
                <article
                  v-if="dictionaryFeedback"
                  class="data-view__notice"
                  :class="`data-view__notice--${inferNoticeTone(dictionaryFeedback)}`"
                >
                  {{ dictionaryFeedback }}
                </article>
                <div v-if="!databaseDictionary.length" class="data-view__empty">
                  Словарь пуст. После сканирования он может автоматически
                  наполняться терминами таблиц и колонок.
                </div>
                <AppExpander
                  v-else
                  :items="databaseDictionary"
                  v-slot="{ items: visibleTerms }"
                >
                  <table class="data-view__table">
                    <thead>
                      <tr>
                        <th>Термин</th>
                        <th>Выражение</th>
                        <th>Описание</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="term in visibleTerms" :key="term.id">
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
                </AppExpander>
              </section>
            </div>

            <div class="data-view__knowledge">
              <div class="data-view__tables" aria-label="Сканированная схема">
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
                  <strong
                    >{{ table.schema_name }}.{{ table.table_name }}</strong
                  >
                  <span
                    >{{ table.column_count }} кол. · PK
                    {{ table.primary_key.join(", ") || "нет" }}</span
                  >
                  <small
                    >{{ table.row_count ?? "—" }} строк ·
                    {{ translateTableObjectType(table.object_type) }}</small
                  >
                </button>
              </div>

              <div class="data-view__detail">
                <div v-if="selectedTable" class="data-view__detail-body">
                  <header class="data-view__head data-view__head--compact">
                    <div>
                      <p class="eyebrow">Редактор таблицы</p>
                      <h2>
                        {{ selectedTable.schema_name }}.{{
                          selectedTable.table_name
                        }}
                        <AppTooltip>
                          Ручные поля сохраняются между сканами. Автополя
                          пересчитываются при каждом парсинге.</AppTooltip
                        >
                      </h2>
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
                    <label class="data-view__field">
                      <span>Описание</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.description"
                        rows="3"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Бизнес-смысл</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.businessMeaning"
                        rows="3"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Домен</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.domain"
                        rows="2"
                        placeholder="заказы / финансы / пользователи"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Semantic label</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.semanticLabel"
                        rows="2"
                        placeholder="например: Заказы"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Semantic role</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.semanticRole"
                        rows="2"
                        placeholder="fact / dimension / bridge / lookup / event / snapshot"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Grain</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.semanticGrain"
                        rows="2"
                        placeholder="one row = one order"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Главная дата</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.semanticMainDateColumn"
                        rows="2"
                        placeholder="created_at / order_date"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Главная сущность</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.semanticMainEntity"
                        rows="2"
                        placeholder="заказ / клиент / платёж"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Semantic synonyms</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.semanticSynonyms"
                        rows="2"
                        placeholder="синонимы через запятую"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Important metrics</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.semanticImportantMetrics"
                        rows="3"
                        placeholder="total_revenue"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Important dimensions</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.semanticImportantDimensions"
                        rows="2"
                        placeholder="status, city, category"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Теги</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.tags"
                        rows="2"
                        placeholder="финансы, заказы, pii"
                      ></textarea>
                    </label>
                    <label class="data-view__field">
                      <span>Чувствительность</span>
                      <textarea
                        v-autosize
                        v-model="tableDraft.sensitivity"
                        rows="2"
                        placeholder="pii / финансовые / внутренние"
                      ></textarea>
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
                  </div>

                  <section class="data-view__subpanel">
                    <header class="data-view__subhead">
                      <h3>Колонки</h3>
                      <p>
                        Ручные семантические метки, синонимы и флаги скрытия для
                        LLM.
                      </p>
                    </header>
                    <AppExpander
                      :items="selectedTable.columns || []"
                      v-slot="{ items: visibleColumns }"
                    >
                      <div class="data-view__column-list">
                        <article
                          v-for="column in visibleColumns"
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
                              {{
                                column.sample_values.join(", ") || "—"
                              }}</small
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
                              class="app-button app-button--tiny"
                              type="button"
                              @click="saveColumn(column.id)"
                            >
                              Сохранить колонку
                            </button>
                          </div>
                        </article>
                      </div>
                    </AppExpander>
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
                  Выберите таблицу в блоке выше, чтобы редактировать семантику и
                  связи.
                </div>
              </div>
            </div>
          </section>

          <section class="data-view__panel" v-if="erdGraph?.nodes.length">
            <header class="data-view__head data-view__head--compact">
              <div>
                <p class="eyebrow">ERD</p>
                <h2>
                  Граф связей
                  <AppTooltip>
                    Физический FK-граф по последнему снимку
                    сканирования.</AppTooltip
                  >
                </h2>
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
        </div>
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
      :relationship-descriptions-text="
        semanticActivationRelationshipDescriptionsText
      "
      :column-descriptions-text="semanticActivationColumnDescriptionsText"
      :submitting="semanticActivationSubmitting"
      @close="closeSemanticActivationModal"
      @submit="submitSemanticActivation"
    />
    <div
      v-if="showSemanticLayerModal && semanticCatalog"
      class="data-view__semantic-modal-root"
      @click.self="closeSemanticLayerModal"
    >
      <div
        class="data-view__semantic-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="semantic-layer-title"
      >
        <header class="data-view__semantic-modal-head">
          <div class="data-view__semantic-modal-title">
            <p class="eyebrow">LLM-прослойка</p>
            <h2 id="semantic-layer-title">Semantic layer</h2>
            <p class="data-view__semantic-modal-meta">
              {{ selectedDatabase?.name ?? "Текущая база" }} ·
              {{ semanticCatalog.dialect }}
            </p>
          </div>
          <button
            class="data-view__modal-close"
            type="button"
            aria-label="Закрыть"
            @click="closeSemanticLayerModal"
          >
            ✕
          </button>
        </header>

        <div class="data-view__semantic-modal-body">
          <div v-if="semanticNotices.length" class="data-view__notice-list">
            <article
              v-for="notice in semanticNotices"
              :key="`${notice.key}-modal`"
              class="data-view__notice"
              :class="`data-view__notice--${notice.tone}`"
            >
              {{ notice.text }}
            </article>
          </div>

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

          <section class="data-view__subpanel data-view__subpanel--panel">
            <header class="data-view__subhead">
              <h3>Граф связей для LLM</h3>
              <p>Итоговые join-рёбра, которые получит агент.</p>
            </header>
            <div
              v-if="semanticCatalog.relationship_graph.length"
              class="data-view__graph-list"
            >
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

          <section class="data-view__subpanel data-view__subpanel--panel">
            <header class="data-view__subhead">
              <h3>Каталог таблиц и колонок</h3>
              <p>
                Разворачиваемый preview semantic layer без отдельной секции в
                основном полотне.
              </p>
            </header>

            <div
              v-if="semanticCatalog.tables.length"
              class="data-view__sem-tables"
            >
              <article
                v-for="table in semanticCatalog.tables"
                :key="semanticTableKey(table)"
                class="data-view__sem-table"
              >
                <header class="data-view__sem-table-head">
                  <button
                    class="data-view__sem-expand"
                    type="button"
                    @click="toggleTableExpand(semanticTableKey(table))"
                  >
                    {{
                      expandedTables.has(semanticTableKey(table)) ? "−" : "+"
                    }}
                  </button>
                  <div class="data-view__sem-table-meta">
                    <strong
                      >{{ table.schema_name }}.{{ table.table_name }}</strong
                    >
                    <span>{{
                      table.label || translateTableRole(table.table_role)
                    }}</span>
                    <small>{{
                      table.business_description ||
                      "Описание для semantic layer пока не заполнено."
                    }}</small>
                  </div>
                  <div class="data-view__sem-table-counts">
                    {{ table.columns.length }} колонок ·
                    {{ table.relationships.length }} связей
                  </div>
                </header>

                <div
                  v-if="expandedTables.has(semanticTableKey(table))"
                  class="data-view__sem-columns"
                >
                  <article
                    v-for="column in table.columns"
                    :key="`${semanticTableKey(table)}-${column.column_name}`"
                    class="data-view__sem-col"
                  >
                    <div class="data-view__sem-col-head">
                      <strong class="data-view__sem-col-name">{{
                        column.column_name
                      }}</strong>
                      <span class="data-view__sem-col-label">{{
                        column.label ||
                        column.business_description ||
                        "Без семантической метки"
                      }}</span>
                      <span class="data-view__sem-col-type">{{
                        column.value_type || column.data_type
                      }}</span>
                      <span
                        v-if="column.is_pk"
                        class="data-view__sem-badge data-view__sem-badge--pk"
                      >
                        PK
                      </span>
                      <span
                        v-if="column.is_fk"
                        class="data-view__sem-badge data-view__sem-badge--fk"
                      >
                        FK
                      </span>
                    </div>
                    <small class="data-view__sem-col-note">
                      {{
                        column.synonyms.length
                          ? `Синонимы: ${column.synonyms.join(", ")}`
                          : column.example_values.length
                            ? `Примеры: ${column.example_values
                                .slice(0, 3)
                                .join(", ")}`
                            : "Дополнительные подсказки для колонки пока не заданы."
                      }}
                    </small>
                  </article>
                </div>
              </article>
            </div>
            <div v-else class="data-view__empty">
              Semantic layer ещё не содержит таблиц.
            </div>
          </section>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, type Directive } from "vue";
import VChart from "vue-echarts";

import { api } from "@/api/client";
import AddDatabaseModal from "@/components/layout/AddDatabaseModal.vue";
import SemanticActivationModal from "@/components/layout/SemanticActivationModal.vue";
import ChatSidebar from "@/components/chat/ChatSidebar.vue";
import AppExpander from "@/components/ui/AppExpander.vue";
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
import AppTooltip from "@/components/ui/AppTooltip.vue";

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
const showSemanticActivationModal = ref(false);
const showSemanticLayerModal = ref(false);
const semanticActivationSubmitting = ref(false);
const semanticActivationTableDescriptionsText = ref("");
const semanticActivationRelationshipDescriptionsText = ref("");
const semanticActivationColumnDescriptionsText = ref("");

const expandedTables = ref<Set<string>>(new Set());
const databaseDictionary = ref<ApiDictionaryEntryRead[]>([]);
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
  semanticRole: "",
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

type ViewNoticeTone = "neutral" | "success" | "warning" | "danger";

type ViewNotice = {
  key: string;
  text: string;
  tone: ViewNoticeTone;
};

const TABLE_ROLE_OPTIONS = [
  "fact",
  "dimension",
  "bridge",
  "lookup",
  "event",
  "snapshot",
] as const;

type SemanticTableRole = (typeof TABLE_ROLE_OPTIONS)[number];

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

function inferNoticeTone(message: string): ViewNoticeTone {
  const normalized = message.toLowerCase();
  if (
    normalized.includes("не удалось") ||
    normalized.includes("ошиб") ||
    normalized.includes("удал")
  ) {
    return "danger";
  }
  if (normalized.includes("grain") || normalized.includes("предуп")) {
    return "warning";
  }
  if (
    normalized.includes("заверш") ||
    normalized.includes("сохран") ||
    normalized.includes("актив") ||
    normalized.includes("обнов")
  ) {
    return "success";
  }
  return "neutral";
}

const pageNotices = computed<ViewNotice[]>(() =>
  knowledgeFeedback.value
    ? [
        {
          key: "knowledge",
          text: knowledgeFeedback.value,
          tone: inferNoticeTone(knowledgeFeedback.value),
        },
      ]
    : [],
);

const semanticNotices = computed<ViewNotice[]>(() => {
  const notices: ViewNotice[] = [];

  if (semanticFeedback.value) {
    notices.push({
      key: "semantic-feedback",
      text: semanticFeedback.value,
      tone: inferNoticeTone(semanticFeedback.value),
    });
  }

  if (semanticFactGrainWarnings.value.length) {
    notices.push({
      key: "semantic-grain",
      text: `Для ${semanticFactGrainWarnings.value.length} fact-таблиц не заполнен grain: ${semanticFactGrainWarnings.value.join(", ")}.`,
      tone: "warning",
    });
  }

  return notices;
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

function semanticTableKey(table: { schema_name: string; table_name: string }) {
  return `${table.schema_name}.${table.table_name}`;
}

function normalizeSemanticRole(value: string): SemanticTableRole | null {
  const normalized = value.trim().toLowerCase();
  return TABLE_ROLE_OPTIONS.includes(normalized as SemanticTableRole)
    ? (normalized as SemanticTableRole)
    : null;
}

function syncTextareaHeight(element: HTMLTextAreaElement) {
  if (typeof window === "undefined") {
    return;
  }
  element.style.height = "0px";
  const minHeight =
    Number.parseFloat(window.getComputedStyle(element).minHeight) || 0;
  element.style.height = `${Math.max(element.scrollHeight, minHeight)}px`;
}

const vAutosize: Directive<HTMLTextAreaElement, unknown> = {
  mounted(element) {
    syncTextareaHeight(element);
  },
  updated(element) {
    syncTextareaHeight(element);
  },
};

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
      return "#6f56a0";
    case "dimension":
      return "#8570ad";
    case "bridge":
      return "#9a82bc";
    case "snapshot":
      return "#b09acb";
    case "event":
      return "#5d477f";
    case "lookup":
      return "#76638f";
    default:
      return "#2a1f3d";
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
          color: "#f4efff",
          fontSize: 11,
          lineHeight: 15,
          width: 170,
          overflow: "truncate",
        },
        lineStyle: {
          color: "#d1bfff",
          width: 1.4,
          opacity: 0.75,
        },
        itemStyle: {
          color: "#2a1f3d",
          borderColor: "#efe6ff",
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
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function syncTableDraft(table: ApiKnowledgeTable | null) {
  tableDraft.description = table?.description_manual ?? "";
  tableDraft.businessMeaning = table?.business_meaning_manual ?? "";
  tableDraft.domain = table?.domain_manual ?? "";
  tableDraft.semanticLabel = table?.semantic_label_manual ?? "";
  tableDraft.semanticRole = table?.semantic_table_role_manual ?? "";
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
    .map((table) =>
      `${table.table_name}: ${table.business_description ?? ""}`.trim(),
    )
    .filter(Boolean)
    .join("\n");
}

function formatRelationshipDescriptions() {
  return (semanticCatalog.value?.relationships ?? [])
    .map((relationship) =>
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
    .filter(
      (item): item is { table_name: string; business_description: string } =>
        Boolean(item),
    );
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
    selectedTableId.value = null;
    scanRuns.value = [];
    erdGraph.value = null;
    semanticCatalog.value = null;
    databaseDictionary.value = [];
    semanticDescription.value = "";
    semanticAutoRefreshKey.value = "";
    showSemanticLayerModal.value = false;
    expandedTables.value = new Set();
    return;
  }

  knowledgeFeedback.value = "";
  semanticFeedback.value = "";
  const [summaryResult, graphResult, semanticResult] = await Promise.allSettled(
    [
      api.getKnowledge(selectedDatabaseId.value),
      api.getERD(selectedDatabaseId.value),
      api.getSemanticCatalog(selectedDatabaseId.value),
    ],
  );

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
    showSemanticLayerModal.value = false;
    expandedTables.value = new Set();
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
      column_descriptions: parseColumnDescriptions(
        payload.columnDescriptionsText,
      ),
    });
    const lastScanId = knowledgeSummary.value?.last_scan?.id ?? "no-scan";
    semanticAutoRefreshKey.value = `${selectedDatabaseId.value}::${lastScanId}::${buildSemanticDatabaseDescription()}`;
    if (knowledgeSummary.value) {
      knowledgeSummary.value.database_description =
        payload.databaseDescription || null;
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
      semantic_table_role_manual: normalizeSemanticRole(
        tableDraft.semanticRole,
      ),
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

function toggleTableExpand(tableKey: string) {
  const next = new Set(expandedTables.value);
  if (next.has(tableKey)) {
    next.delete(tableKey);
  } else {
    next.add(tableKey);
  }
  expandedTables.value = next;
}

function openSemanticLayerModal() {
  if (!semanticCatalog.value) {
    return;
  }
  if (!expandedTables.value.size && semanticCatalog.value.tables[0]) {
    expandedTables.value = new Set([
      semanticTableKey(semanticCatalog.value.tables[0]),
    ]);
  }
  showSemanticLayerModal.value = true;
}

function closeSemanticLayerModal() {
  showSemanticLayerModal.value = false;
}

async function deleteSemanticCatalog() {
  if (!selectedDatabaseId.value) return;
  const confirmed = window.confirm(
    "Удалить активный семантический каталог? Его можно будет пересоздать.",
  );
  if (!confirmed) return;
  isDeletingSemantic.value = true;
  try {
    await api.deleteSemanticCatalog(selectedDatabaseId.value);
    semanticCatalog.value = null;
    showSemanticLayerModal.value = false;
    expandedTables.value = new Set();
    semanticFeedback.value = "Семантический каталог удалён.";
  } catch (error) {
    semanticFeedback.value =
      error instanceof Error ? error.message : "Не удалось удалить каталог.";
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
    databaseDictionary.value = await api.getDictionary(
      selectedDatabaseId.value,
    );
  } catch {
    databaseDictionary.value = [];
  }
}

watch(selectedDatabaseId, async (value, previousValue) => {
  if (!value || value === previousValue) return;
  selectedTableId.value = null;
  selectedTable.value = null;
  showSemanticLayerModal.value = false;
  expandedTables.value = new Set();
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
.content-wrapper {
  display: grid;
  gap: 16px;
  padding: 12px;
  border-radius: 16px;
  background-color: var(--canvas);
}

.data-shell {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: var(--app-shell-sidebar-width) minmax(0, 1fr);
  gap: var(--app-shell-gap);
  padding: var(--app-shell-gap);
  background: var(--bg);
  transition: grid-template-columns 220ms ease;
}

.data-shell__sidebar {
  min-height: 0;
  width: var(--app-shell-sidebar-width);
  max-width: 100%;
  transition: width 220ms ease;
}

.data-shell__content {
  min-height: 0;
  overflow: auto;
}

.data-view {
  --data-surface: var(--bg);
  --data-surface-strong: var(--canvas);
  --data-accent: #2a1f3d;
  --data-accent-strong: #2a1f3d;
  --data-line: rgba(255, 255, 255, 0.18);
  --data-line-strong: rgba(255, 255, 255, 0.28);
  --data-muted: rgba(255, 255, 255, 0.88);
  --data-muted-soft: rgba(255, 255, 255, 0.72);
  --data-field-height: calc(1.45em + 1.3rem + 2px);
  min-height: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.data-view__toolbar,
.data-view__panel {
  border: 1px solid var(--data-line);
  border-radius: var(--radius-lg);
  background: var(--data-surface);
  padding: 1.1rem 1.15rem;
  box-shadow: var(--shadow-soft);
}

.data-view__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.data-view__panel--hero {
  position: relative;
  overflow: hidden;
  background: var(--data-surface);
}

.data-view__panel--hero::after {
  content: "";
  position: absolute;
  right: -84px;
  bottom: -126px;
  width: 260px;
  height: 260px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(42, 31, 61, 0.58), transparent 72%);
  pointer-events: none;
}

.data-view__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.data-view__head-copy {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  max-width: 760px;
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

.data-view__lead {
  margin: 0;
  color: var(--data-muted-soft);
  font-size: 0.88rem;
  line-height: 1.5;
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
  padding: 0;
}

.data-view__active-db span,
.data-view__active-db strong {
  display: block;
}

.data-view__active-db span {
  color: var(--data-muted-soft);
  font-size: 0.72rem;
}

.data-view__active-db strong {
  color: var(--ink-strong);
  font-size: 1rem;
  margin-top: 0.15rem;
}

.data-view__form-grid textarea,
.data-view__column-edit textarea,
.data-view__semantic-description textarea {
  min-height: var(--data-field-height);
  height: var(--data-field-height);
}

.data-view__form-grid textarea,
.data-view__create input,
.data-view__column-edit input,
.data-view__column-edit textarea,
.data-view__relationship-edit input {
  width: 100%;
  border: 1px solid var(--data-line);
  border-radius: 10px;
  padding: 0.65rem 0.75rem;
  background: var(--data-surface-strong);
  color: var(--ink);
}

.data-view__form-grid textarea,
.data-view__create input,
.data-view__column-edit input,
.data-view__column-edit textarea,
.data-view__relationship-edit input {
  line-height: 1.45;
}

.data-view__form-grid textarea:focus,
.data-view__create input:focus,
.data-view__column-edit input:focus,
.data-view__column-edit textarea:focus,
.data-view__relationship-edit input:focus,
.data-view__semantic-description textarea:focus {
  outline: none;
  border-color: var(--data-line-strong);
}

.data-view__notice-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1rem;
  position: relative;
  z-index: 1;
}

.data-view__notice {
  flex: 1 1 240px;
  margin: 0;
  padding: 0.8rem 0.95rem;
  border: 1px solid var(--data-line);
  border-radius: 12px;
  background: var(--data-surface-strong);
  color: var(--ink-strong);
  font-size: 0.84rem;
  line-height: 1.45;
}

.data-view__notice--success {
  background: #34264c;
}

.data-view__notice--warning {
  background: #52421f;
}

.data-view__notice--danger {
  background: #4f2b31;
}

.data-view__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
  margin-top: 12px;
}

.data-view__stat {
  border: 1px solid var(--data-line);
  border-radius: 14px;
  padding: 0.85rem;
  background: var(--data-surface-strong);
}

.data-view__stat span,
.data-view__stat small {
  display: block;
  color: var(--data-muted-soft);
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
  border: 1px solid var(--data-line);
  border-radius: 12px;
  padding: 0.8rem;
  background: var(--data-surface-strong);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.data-view__scan-card p,
.data-view__scan-card span,
.data-view__scan-card small {
  margin: 0;
  color: var(--data-muted-soft);
  font-size: 0.82rem;
}

.data-view__knowledge {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.data-view__knowledge-overview {
  display: grid;
  gap: 1rem;
  margin-bottom: 1rem;
}

.data-view__knowledge-overview-primary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.data-view__tables {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.data-view__table-pill {
  flex: 1 1 300px;
  max-width: calc(33.333% - 0.5rem);
  text-align: left;
  border: 1px solid var(--data-line);
  border-radius: 12px;
  padding: 0.9rem;
  min-height: 116px;
  background: var(--data-surface-strong);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.35rem;
}

.data-view__table-pill strong,
.data-view__table-pill span,
.data-view__table-pill small {
  display: block;
}

.data-view__table-pill span,
.data-view__table-pill small {
  color: var(--data-muted-soft);
  font-size: 0.8rem;
}

.data-view__table-pill.is-active {
  border-color: var(--data-line-strong);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08);
  background: var(--data-accent);
}

.data-view__detail {
  min-width: 0;
}

.data-view__detail-body,
.data-view__subpanel,
.data-view__semantic-description {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.data-view__form-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.data-view__field,
.data-view__column-edit,
.data-view__relationship-edit {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.data-view__field {
  flex: 1 1 calc((100% - 1.5rem) / 3);
  min-width: 240px;
}

.data-view__form-grid span {
  font-size: 0.78rem;
  color: var(--data-muted-soft);
}

.data-view__form-grid textarea,
.data-view__column-edit textarea {
  resize: none;
  overflow: hidden;
}

.data-view__inline-actions {
  display: flex;
  justify-content: flex-end;
  height: 50px;
}

.data-view__auto-copy {
  margin: 0;
  max-width: 420px;
  padding: 0.85rem 1rem;
  border: 1px solid var(--data-line);
  border-radius: 14px;
  background: var(--data-surface-strong);
  color: var(--data-muted);
  font-size: 0.8rem;
  line-height: 1.55;
}

.data-view__subpanel {
  border-top: 1px solid var(--data-line);
  padding-top: 0.85rem;
}

.data-view__subpanel--panel {
  border: 1px solid var(--data-line);
  border-radius: 16px;
  padding: 1rem;
  background: var(--data-surface-strong);
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
  color: var(--data-muted-soft);
  font-size: 0.82rem;
}

.data-view__column-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
}

.data-view__relationship-list {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.data-view__column-card {
  flex: 1 1 calc((100% - 1.4rem) / 3);
  min-width: 280px;
}

.data-view__column-card,
.data-view__relationship-card {
  border: 1px solid var(--data-line);
  border-radius: 12px;
  padding: 0.8rem;
  background: var(--data-surface-strong);
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
  color: var(--data-muted-soft);
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
  color: var(--data-muted);
}

.data-view__erd {
  width: 100%;
  height: 480px;
  border: 1px solid var(--data-line);
  border-radius: 16px;
  background: linear-gradient(180deg, #312547 0%, #2a1f3d 100%);
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
  border: 1px solid var(--data-line);
  border-radius: 999px;
  background: var(--data-accent);
  color: var(--data-muted);
  font-size: 0.8rem;
}

.data-view__toggle input {
  accent-color: #ffffff;
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
  border: 1px solid var(--data-line);
  border-radius: 12px;
  padding: 0.75rem;
  background: var(--data-surface-strong);
}

.data-view__graph-card span,
.data-view__graph-card strong {
  display: block;
}

.data-view__graph-card span {
  color: var(--data-muted-soft);
  font-size: 0.78rem;
  margin-bottom: 0.2rem;
}

.data-view__graph-card strong {
  color: var(--ink-strong);
  font-size: 0.82rem;
  line-height: 1.4;
  word-break: break-word;
}

.data-view__semantic-description span,
.data-view__semantic-description small {
  color: var(--data-muted-soft);
  font-size: 0.78rem;
}

.data-view__semantic-description textarea {
  width: 100%;
  border: 1px solid var(--data-line);
  border-radius: 12px;
  padding: 0.75rem 0.8rem;
  background: var(--data-surface-strong);
  color: var(--ink);
  resize: vertical;
}

.data-view__semantic-stat {
  border: 1px solid var(--data-line);
  border-radius: 12px;
  padding: 0.8rem;
  background: var(--data-surface-strong);
}

.data-view__semantic-stat span {
  display: block;
  color: var(--data-muted-soft);
  font-size: 0.78rem;
}

.data-view__semantic-stat strong {
  display: block;
  margin-top: 0.25rem;
  color: var(--ink-strong);
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
  border-bottom: 1px solid var(--data-line);
}

.data-view__syn {
  margin: 0.25rem 0 0;
  color: var(--data-muted-soft);
  font-size: 0.78rem;
}

.data-view__empty {
  padding: 1rem;
  color: var(--data-muted);
  text-align: center;
  border: 1px dashed var(--data-line);
  border-radius: 12px;
  background: var(--data-surface-strong);
}

.data-view__sem-tables {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.data-view__sem-table {
  border: 1px solid var(--data-line);
  border-radius: 12px;
  background: var(--data-surface-strong);
  overflow: hidden;
}

.data-view__sem-table-head {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.8rem 0.95rem;
}

.data-view__sem-expand {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--data-line);
  border-radius: 10px;
  background: transparent;
  color: var(--ink-strong);
  font-size: 0.9rem;
  cursor: pointer;
  flex-shrink: 0;
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
  color: var(--data-muted-soft);
  font-size: 0.78rem;
}

.data-view__sem-table-counts {
  color: var(--data-muted-soft);
  font-size: 0.78rem;
  white-space: nowrap;
}

.data-view__sem-columns {
  border-top: 1px solid var(--data-line);
  padding: 0.45rem 0.95rem 0.95rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.data-view__sem-col {
  padding: 0.65rem 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: var(--data-accent-strong);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
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
  font-family: var(--font-mono, monospace);
  min-width: 120px;
}

.data-view__sem-col-label {
  font-size: 0.78rem;
  color: var(--data-muted-soft);
  flex: 1;
}

.data-view__sem-col-type {
  font-size: 0.72rem;
  color: var(--data-muted-soft);
  font-family: var(--font-mono, monospace);
}

.data-view__sem-col-note {
  color: var(--data-muted-soft);
  font-size: 0.76rem;
  line-height: 1.45;
}

.data-view__sem-badge {
  font-size: 0.68rem;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.16);
  white-space: nowrap;
}

.data-view__sem-badge--pk {
  background: rgba(244, 194, 107, 0.18);
  color: #f6d392;
  border-color: rgba(244, 194, 107, 0.34);
}

.data-view__sem-badge--fk {
  background: rgba(129, 201, 149, 0.18);
  color: #9ed8af;
  border-color: rgba(129, 201, 149, 0.34);
}

.data-view__semantic-modal-root {
  position: fixed;
  inset: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(12, 12, 12, 0.62);
  backdrop-filter: blur(10px);
}

.data-view__semantic-modal {
  width: min(1200px, 100%);
  max-height: min(92vh, 960px);
  display: flex;
  flex-direction: column;
  border: 1px solid var(--data-line);
  border-radius: 24px;
  background: var(--data-surface);
  overflow: hidden;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
}

.data-view__semantic-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem 1.35rem;
  border-bottom: 1px solid var(--data-line);
  background: var(--data-surface);
}

.data-view__semantic-modal-title {
  min-width: 0;
}

.data-view__semantic-modal-title h2 {
  margin: 0.15rem 0 0;
  color: var(--ink-strong);
  font-size: 1.2rem;
}

.data-view__semantic-modal-meta {
  margin: 0.2rem 0 0;
  color: var(--data-muted-soft);
  font-size: 0.84rem;
}

.data-view__semantic-modal-body {
  overflow: auto;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.data-view__modal-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: 1px solid var(--data-line);
  border-radius: 12px;
  background: var(--data-accent);
  color: var(--ink-strong);
}

@media (max-width: 1260px) {
  .data-view__table-pill {
    max-width: calc(50% - 0.4rem);
  }

  .data-view__column-card {
    flex-basis: calc((100% - 0.7rem) / 2);
  }
}

@media (max-width: 1100px) {
  .data-shell {
    grid-template-columns: 1fr;
  }

  .data-view__knowledge-overview-primary,
  .data-view__stats,
  .data-view__semantic-grid,
  .data-view__column-card,
  .data-view__relationship-card,
  .data-view__create {
    grid-template-columns: 1fr;
  }

  .data-view__toolbar,
  .data-view__inline-actions,
  .data-view__head,
  .data-view__semantic-modal-head {
    flex-direction: column;
    align-items: stretch;
  }

  .data-view__field,
  .data-view__table-pill {
    flex-basis: 100%;
    max-width: none;
  }

  .data-view__relationship-edit {
    grid-template-columns: 1fr 1fr;
  }

  .data-view__sem-table-head {
    flex-wrap: wrap;
  }

  .data-view__sem-table-counts {
    white-space: normal;
  }

  .data-view__semantic-modal {
    max-height: calc(100vh - 32px);
  }
}

@media (max-width: 760px) {
  .data-view__column-card {
    flex-basis: 100%;
  }

  .data-view__create,
  .data-view__relationship-edit {
    grid-template-columns: 1fr;
  }

  .data-view__semantic-modal-root {
    padding: 12px;
  }

  .data-view__semantic-modal-body {
    padding: 1rem;
  }
}
</style>
