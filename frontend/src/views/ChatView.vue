<template>
  <main class="chat-view">
    <div class="chat-view__layout">
      <ChatSidebar
        :active-db-id="chat.activeDbId"
        :active-session-id="chat.activeSessionId"
        :databases="chat.databases"
        :loading="chat.loadingSessions || chat.loadingMessages"
        mode="chat"
        :sessions="chat.sessions"
        @create-session="createSession"
        @delete-session="deleteSession"
        @rename-session="renameSession"
        @select-database="selectDatabase"
        @select-session="selectSession"
      />

      <div class="chat-view__panels" ref="panelsEl">
        <template v-if="!panelSwapped">
          <div class="chat-view__center-area" ref="centerPanelEl">
            <section
              class="chat-view__panel chat-view__panel--center-top"
              :style="{ height: centerTopHeightPx }"
            >
              <ChatSqlEditor
                :busy="chat.generating || chat.executing"
                :model-value="chat.sqlDraft"
                :status="editorStatus"
                @run="runSql"
                @update:modelValue="updateSqlDraft"
              />
            </section>

            <div
              class="chat-view__resizer chat-view__resizer--horizontal"
              @mousedown="startCenterResize"
            >
              <!-- <button
                class="chat-view__swap-btn"
                @click.stop="swapPanels"
                title="Поменять панели 1111"
              >
                <svg
                  viewBox="0 0 16 16"
                  width="14"
                  height="14"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M11 3l3 3-3 3M2 6h12M5 13l-3-3 3-3M14 10H2" />
                </svg>
              </button> -->
            </div>

            <section class="chat-view__panel chat-view__panel--center-bottom">
              <ChatResultPanel
                :execution="chat.executionResult"
                :view="chat.resultView"
                :sql-text="chat.sqlDraft"
                :database-connection-id="chat.activeDbId"
                @change-view="chat.setResultMode"
              />
            </section>
          </div>

          <div class="chat-view__resizer" @mousedown="startResize">
            <button
              class="chat-view__swap-btn"
              @click.stop="swapPanels"
              title="Поменять панели"
            >
              <svg
                viewBox="0 0 16 16"
                width="14"
                height="14"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M11 3l3 3-3 3M2 6h12M5 13l-3-3 3-3M14 10H2" />
              </svg>
            </button>
          </div>

          <section
            class="chat-view__panel chat-view__panel--chat"
            :style="{ width: chatWidthPx }"
          >
            <ChatAssistant
              :busy="chat.generating"
              :messages="chat.messages"
              :pending-user-message="chat.pendingUserMessage"
              :query-mode="chat.queryMode ?? 'fast'"
              :llm-model-alias="chat.llmModelAlias ?? 'gpt120'"
              :llm-model-aliases="
                chat.llmModelAliases?.length ? chat.llmModelAliases : ['gpt120']
              "
              @apply-sql="applySql"
              @clarification="sendClarification"
              @set-llm-model-alias="chat.setLlmModelAlias"
              @set-query-mode="chat.setQueryMode"
              @send="sendMessage"
            />
          </section>
        </template>

        <template v-else>
          <section
            class="chat-view__panel chat-view__panel--chat"
            :style="{ width: chatWidthPx }"
          >
            <ChatAssistant
              :busy="chat.generating"
              :messages="chat.messages"
              :pending-user-message="chat.pendingUserMessage"
              :query-mode="chat.queryMode ?? 'fast'"
              :llm-model-alias="chat.llmModelAlias ?? 'gpt120'"
              :llm-model-aliases="
                chat.llmModelAliases?.length ? chat.llmModelAliases : ['gpt120']
              "
              @apply-sql="applySql"
              @clarification="sendClarification"
              @set-llm-model-alias="chat.setLlmModelAlias"
              @set-query-mode="chat.setQueryMode"
              @send="sendMessage"
            />
          </section>

          <div class="chat-view__resizer" @mousedown="startResize">
            <button
              class="chat-view__swap-btn"
              @click.stop="swapPanels"
              title="Поменять панели 1113"
            >
              <svg
                viewBox="0 0 16 16"
                width="14"
                height="14"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M11 3l3 3-3 3M2 6h12M5 13l-3-3 3-3M14 10H2" />
              </svg>
            </button>
          </div>

          <div class="chat-view__center-area" ref="centerPanelEl">
            <section
              class="chat-view__panel chat-view__panel--center-top"
              :style="{ height: centerTopHeightPx }"
            >
              <ChatSqlEditor
                :busy="chat.generating || chat.executing"
                :model-value="chat.sqlDraft"
                :status="editorStatus"
                @run="runSql"
                @update:modelValue="updateSqlDraft"
              />
            </section>

            <div
              class="chat-view__resizer chat-view__resizer--horizontal"
              @mousedown="startCenterResize"
            ></div>

            <section class="chat-view__panel chat-view__panel--center-bottom">
              <ChatResultPanel
                :execution="chat.executionResult"
                :view="chat.resultView"
                :sql-text="chat.sqlDraft"
                :database-connection-id="chat.activeDbId"
                @change-view="chat.setResultMode"
              />
            </section>
          </div>
        </template>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import ChatAssistant from "@/components/chat/ChatAssistant.vue";
import ChatResultPanel from "@/components/chat/ChatResultPanel.vue";
import ChatSidebar from "@/components/chat/ChatSidebar.vue";
import ChatSqlEditor from "@/components/chat/ChatSqlEditor.vue";
import { useChatStore } from "@/stores/chat";

const chat = useChatStore();

const LS_KEY = "chat-panel-layout";
const CHAT_WIDTH_MIN = 240;
const CHAT_WIDTH_MAX = 800;
const CENTER_TOP_MIN = 180;
const CENTER_TOP_MAX = 900;

const chatWidth = ref(360);
const centerTopHeight = ref(420);
const panelSwapped = ref(false);
const panelsEl = ref<HTMLElement | null>(null);
const centerPanelEl = ref<HTMLElement | null>(null);

const chatWidthPx = computed(() => `${chatWidth.value}px`);
const centerTopHeightPx = computed(() => `${centerTopHeight.value}px`);

const editorStatus = computed<"idle" | "executing" | "error" | "generating">(
  () => {
    if (chat.executing) return "executing";
    if (chat.generating) return "generating";
    if (chat.errorMessage) return "error";
    return "idle";
  },
);

function loadLayout() {
  try {
    const s = localStorage.getItem(LS_KEY);
    if (s) {
      const d = JSON.parse(s) as Record<string, unknown>;
      if (typeof d.chatWidth === "number") chatWidth.value = d.chatWidth;
      if (typeof d.centerTopHeight === "number")
        centerTopHeight.value = d.centerTopHeight;
      if (typeof d.panelSwapped === "boolean")
        panelSwapped.value = d.panelSwapped;
    }
  } catch {
    // ignore malformed storage
  }
}

function saveLayout() {
  localStorage.setItem(
    LS_KEY,
    JSON.stringify({
      chatWidth: chatWidth.value,
      centerTopHeight: centerTopHeight.value,
      panelSwapped: panelSwapped.value,
    }),
  );
}

function swapPanels() {
  panelSwapped.value = !panelSwapped.value;
  saveLayout();
}

let dragStartX = 0;
let dragStartWidth = 0;
let dragSwapped = false;
let centerDragStartY = 0;
let centerDragStartHeight = 0;

function startResize(e: MouseEvent) {
  e.preventDefault();
  dragStartX = e.clientX;
  dragStartWidth = chatWidth.value;
  dragSwapped = panelSwapped.value;
  document.addEventListener("mousemove", onResize);
  document.addEventListener("mouseup", stopResize);
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
}

function startCenterResize(e: MouseEvent) {
  e.preventDefault();
  centerDragStartY = e.clientY;
  centerDragStartHeight = centerTopHeight.value;
  document.addEventListener("mousemove", onCenterResize);
  document.addEventListener("mouseup", stopCenterResize);
  document.body.style.cursor = "row-resize";
  document.body.style.userSelect = "none";
}

function onResize(e: MouseEvent) {
  const delta = e.clientX - dragStartX;
  // when chat is on the right (not swapped): move left = wider chat
  // when chat is on the left (swapped): move right = wider chat
  const newWidth = dragSwapped
    ? dragStartWidth + delta
    : dragStartWidth - delta;
  chatWidth.value = Math.max(
    CHAT_WIDTH_MIN,
    Math.min(CHAT_WIDTH_MAX, newWidth),
  );
}

function onCenterResize(e: MouseEvent) {
  const delta = e.clientY - centerDragStartY;
  const newHeight = centerDragStartHeight + delta;
  const availableHeight = centerPanelEl.value?.clientHeight ?? CENTER_TOP_MAX;
  const maxHeight = Math.max(CENTER_TOP_MIN, availableHeight - 220);
  centerTopHeight.value = Math.max(
    CENTER_TOP_MIN,
    Math.min(maxHeight, newHeight),
  );
}

function stopResize() {
  document.removeEventListener("mousemove", onResize);
  document.removeEventListener("mouseup", stopResize);
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
  saveLayout();
}

function stopCenterResize() {
  document.removeEventListener("mousemove", onCenterResize);
  document.removeEventListener("mouseup", stopCenterResize);
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
  saveLayout();
}

onMounted(() => {
  loadLayout();
  void chat.initialize().catch(() => {
    /* store already captures the error */
  });
});

function selectDatabase(databaseId: string) {
  void chat.selectDatabase(databaseId);
}

function selectSession(sessionId: string) {
  void chat.selectSession(sessionId);
}

function createSession(databaseId?: string) {
  void chat.createSession(databaseId);
}

function renameSession(sessionId: string, title: string) {
  void chat.renameSession(sessionId, title);
}

function deleteSession(sessionId: string) {
  void chat.deleteSession(sessionId);
}

function sendMessage(text: string, mode: "fast" | "thinking") {
  chat.setQueryMode(mode);
  void chat.sendMessage(text);
}

function sendClarification(answer: string) {
  void chat.sendMessage(answer);
}

function runSql() {
  void chat.runSql();
}

function updateSqlDraft(value: string) {
  chat.updateSqlDraft(value);
}

function applySql(sql: string) {
  chat.applyAssistantSqlDraft(sql, chat.sqlDraftVersion);
}
</script>

<style scoped lang="scss">
.chat-view {
  padding: var(--app-shell-gap);
  background: var(--bg);
  flex: 1;
  min-height: 0;
  display: flex;
}

.chat-view__layout {
  display: flex;
  gap: var(--app-shell-gap);
  flex: 1;
  min-height: 0;
  height: 100%;
}

.chat-view__layout > :deep(.chat-sidebar) {
  width: var(--app-shell-sidebar-width);
  flex: 0 0 var(--app-shell-sidebar-width);
}

.chat-view__panels {
  display: flex;
  flex: 1;
  min-width: 0;
  height: 100%;
  gap: 0;
}

.chat-view__panel {
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  padding: 12px;
}

.chat-view__panel--center {
  flex: 1;
  min-width: 0;
}

.chat-view__center-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow: hidden;
}

.chat-view__panel--center-top {
  flex: 0 0 auto;
  min-width: 0;
  overflow: hidden;
}

.chat-view__panel--center-bottom {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
}

.chat-view__panel--chat {
  flex-shrink: 0;
  display: flex;
  min-height: 0;
}

.chat-view__panel--center-top :deep(.chat-sql-editor),
.chat-view__panel--center-bottom :deep(.chat-result-panel) {
  height: 100%;
}

.chat-view__panel--chat :deep(.chat-assistant) {
  width: 100%;
  min-height: 0;
}

.chat-view__resizer {
  width: 16px;
  flex-shrink: 0;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;

  &::before {
    content: "";
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 2px;
    height: 40px;
    background: var(--line);
    border-radius: 2px;
    transition:
      background 0.15s,
      height 0.15s;
  }

  &:hover::before {
    background: var(--accent, #4f8ef7);
    height: 60px;
  }
}

.chat-view__resizer--horizontal {
  width: 100%;
  height: 16px;
  cursor: row-resize;
  flex-direction: row;

  &::before {
    width: 40px;
    height: 2px;
  }

  &:hover::before {
    width: 60px;
    height: 2px;
  }
}

.chat-view__swap-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--text-secondary, #888);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition:
    opacity 0.15s,
    color 0.15s,
    border-color 0.15s;
  z-index: 2;

  .chat-view__resizer:hover & {
    opacity: 1;
  }

  &:hover {
    color: var(--text, #fff);
    border-color: var(--accent, #4f8ef7);
  }
}

@media (max-width: 1260px) {
  .chat-view__layout {
    flex-wrap: wrap;
  }

  .chat-view__layout > :deep(.chat-sidebar) {
    width: var(--app-shell-sidebar-width);
    flex-basis: var(--app-shell-sidebar-width);
  }

  .chat-view__panels {
    flex: 1;
    flex-direction: column;
    height: auto;
  }

  .chat-view__center-area {
    flex: 1;
    min-height: 520px;
  }

  .chat-view__panel--chat {
    width: 100% !important;
    min-height: 380px;
  }

  .chat-view__resizer {
    width: 100%;
    height: 16px;
    cursor: row-resize;
    flex-direction: row;

    &::before {
      width: 40px;
      height: 2px;
    }

    &:hover::before {
      width: 60px;
      height: 2px;
    }
  }

  .chat-view__swap-btn {
    display: none;
  }
}

@media (max-width: 940px) {
  .chat-view {
    padding: 12px;
  }

  .chat-view__layout {
    flex-direction: column;
  }

  .chat-view__layout > :deep(.chat-sidebar) {
    width: 100%;
    flex-basis: auto;
  }
}
</style>
