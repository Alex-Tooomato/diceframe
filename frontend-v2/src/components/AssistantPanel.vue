<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { NButton, NIcon, NInput } from 'naive-ui'
import {
  CloseOutline, ContractOutline, DocumentTextOutline, ExpandOutline, RefreshOutline, SendOutline,
  SparklesOutline, StopCircleOutline, TrashOutline,
} from '@vicons/ionicons5'
import { useLocale } from '@/composables/useLocale'
import { useAssistant } from '@/composables/useAssistant'
import { renderSafeMarkdown } from '@/utils/markdown'
import AgentTaskCard from '@/components/assistant/AgentTaskCard.vue'
import { assistantCopy, assistantToolLabel } from '@/features/assistant/copy'
import { generatedImageUrl } from '@/api/generatedImages'

const props = withDefaults(defineProps<{ expanded?: boolean }>(), { expanded: false })
const emit = defineEmits<{ close: []; toggleExpanded: [] }>()
const { t, locale } = useLocale()
const { messages, streaming, send, stop, retryLast, clear, pendingApproval, drafts, status, navigation, actionBusy, actionError, confirmApproval, cancelApproval, reviewDraft, saveDraft, restoreSession, invalidateApproval } = useAssistant()
const draftList = computed(() => Object.values(drafts.value))
const eventList = computed(() => messages.value.flatMap(message => message.events || []))
const agentCopy = computed(() => assistantCopy(locale.value))
const imageUrls = ref<Record<string, string>>({})
const imageLoads = new Set<string>()
const draft = ref('')
const listEl = ref<HTMLElement | null>(null)
const transcriptEl = ref<HTMLElement | null>(null)
const tasksEl = ref<HTMLElement | null>(null)
const hasTasks = computed(() => draftList.value.length > 0 || pendingApproval.value || actionError.value || navigation.value || eventList.value.some(event => event.event === 'tool_result'))
onMounted(() => { if (!streaming.value && !actionBusy.value) void restoreSession() })

const quickQuestions = () => [
  { id: 'create', prompt: agentCopy.value.create },
  { id: 'start', prompt: agentCopy.value.start },
  { id: 'api', prompt: t('assistantQuickApi') },
  { id: 'plugin', prompt: t('assistantQuickPlugin') },
  { id: 'players', prompt: t('assistantQuickPlayers') },
  { id: 'tunnel', prompt: t('assistantQuickTunnel') },
  { id: 'runtime-logs', prompt: t('assistantQuickLogs') },
]

function scrollToBottom() {
  void nextTick(() => {
    for (const element of [listEl.value, transcriptEl.value, tasksEl.value]) {
      if (element && element.clientHeight > 0) element.scrollTop = element.scrollHeight
    }
  })
}

watch(messages, scrollToBottom, { deep: true })
watch([pendingApproval, status, streaming], scrollToBottom)
watch(() => props.expanded, scrollToBottom)

function renderMd(text: string): string {
  return renderSafeMarkdown(text)
}

async function onSubmit() {
  const value = draft.value.trim()
  if (!value || streaming.value) return
  draft.value = ''
  await send(value, locale.value)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    void onSubmit()
  }
}

function ask(question: string) {
  if (streaming.value) return
  draft.value = question
  void onSubmit()
}

function saveDraftLocalized(draftId: string) { return saveDraft(draftId, locale.value) }
function statusText(value: string): string {
  if (value === 'idle') return agentCopy.value.statusIdle
  if (value === 'approval_required') return agentCopy.value.statusApproval
  return value
}
function toolLabel(tool: unknown): string { return assistantToolLabel(locale.value, tool) }
function navigationLabel(route: string): string { return route === 'play' ? agentCopy.value.openGame : toolLabel('navigate') }
function resultAssetId(value: unknown): string {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return ''
  const record = value as Record<string, unknown>
  const reference = record.reference && typeof record.reference === 'object' ? record.reference as Record<string, unknown> : {}
  return reference.kind === 'generated' && typeof reference.asset_id === 'string'
    ? reference.asset_id
    : typeof record.asset_id === 'string' ? record.asset_id : ''
}
async function loadResultImage(value: unknown) {
  const assetId = resultAssetId(value)
  if (!assetId || imageLoads.has(assetId) || imageUrls.value[assetId]) return
  imageLoads.add(assetId)
  try { imageUrls.value[assetId] = await generatedImageUrl(assetId) } catch { /* Keep the result text usable when the image expires. */ }
}
watch(eventList, events => {
  for (const event of events) if (event.event === 'tool_result') void loadResultImage(event.payload.result)
}, { deep: true, immediate: true })
onBeforeUnmount(() => { for (const url of Object.values(imageUrls.value)) URL.revokeObjectURL(url) })

function eventResult(value: unknown, detailed = false): string {
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return detailed ? value : value.slice(0, 180)
  try {
    const text = JSON.stringify(value)
    return detailed ? text : text.slice(0, 240)
  } catch { return detailed ? String(value) : String(value).slice(0, 180) }
}

const approvalTarget = computed(() => {
  const preview = pendingApproval.value?.preview
  if (!preview || typeof preview !== 'object' || Array.isArray(preview)) return ''
  const record = preview as Record<string, unknown>
  return typeof record.target_name === 'string' ? record.target_name : ''
})

function followNavigation() {
  const target = navigation.value
  if (!target) return
  const query = target.query ? new URLSearchParams(target.query).toString() : ''
  window.location.hash = `#/${target.route}${query ? `?${query}` : ''}`
}
</script>

<template>
  <section class="assistant-panel" :class="{ 'assistant-panel-expanded': props.expanded }" aria-labelledby="assistant-panel-title">
    <header class="assistant-panel-head">
      <span class="assistant-brand" aria-hidden="true"><NIcon :component="SparklesOutline" size="21" /></span>
      <div class="assistant-head-copy">
        <strong id="assistant-panel-title">{{ t('assistantTitle') }}</strong>
        <span>{{ t('assistantSubtitle') }}</span>
      </div>
      <NButton size="small" quaternary circle :title="t('assistantClear')" :disabled="!messages.length" @click="clear">
        <template #icon><NIcon :component="TrashOutline" /></template>
      </NButton>
      <NButton size="small" quaternary circle data-testid="assistant-toggle-expanded" :title="props.expanded ? agentCopy.shrinkWindow : agentCopy.expandWindow" :aria-label="props.expanded ? agentCopy.shrinkWindow : agentCopy.expandWindow" :aria-expanded="props.expanded" @click="emit('toggleExpanded')">
        <template #icon><NIcon :component="props.expanded ? ContractOutline : ExpandOutline" /></template>
      </NButton>
      <NButton size="small" quaternary circle :title="t('close')" @click="emit('close')">
        <template #icon><NIcon :component="CloseOutline" /></template>
      </NButton>
    </header>

    <div ref="listEl" class="assistant-messages" aria-live="polite">
      <div ref="transcriptEl" class="assistant-transcript">
        <div v-if="!messages.length" class="assistant-empty">
          <span class="assistant-empty-icon"><NIcon :component="SparklesOutline" size="28" /></span>
          <strong>{{ t('assistantEmpty') }}</strong>
          <p>{{ t('assistantEmptyHint') }}</p>
          <div class="assistant-quick-grid">
            <button v-for="question in quickQuestions()" :key="question.id" type="button" :data-assistant-intent="question.id" @click="ask(question.prompt)">
              {{ question.prompt }}
            </button>
          </div>
          <small>{{ t('assistantVersionHint') }}</small>
        </div>

        <article
          v-for="(message, index) in messages"
          :key="index"
          class="assistant-message"
          :class="`assistant-message-${message.role}`"
        >
          <span v-if="message.role === 'assistant'" class="assistant-avatar" aria-hidden="true">
            <NIcon :component="SparklesOutline" />
          </span>
          <div class="assistant-message-stack">
            <div
              v-if="message.content || ((streaming || pendingApproval) && message.role === 'assistant' && index === messages.length - 1)"
              class="assistant-bubble"
              :class="message.role"
            >
              <span v-if="pendingApproval && index === messages.length - 1 && !message.content">{{ agentCopy.statusApproval }}</span>
              <span
                v-else-if="streaming && index === messages.length - 1 && !message.content"
                class="assistant-thinking"
              >
                <i /><i /><i /><span class="sr-only">{{ t('assistantThinking') }}</span>
              </span>
              <div v-else-if="message.role === 'assistant'" class="safe-markdown" v-html="renderMd(message.content)" />
              <span v-else>{{ message.content }}</span>
            </div>

            <details v-if="message.sources?.length" class="assistant-sources">
              <summary><NIcon :component="DocumentTextOutline" />{{ t('assistantSources') }}</summary>
              <ul>
                <li v-for="source in message.sources" :key="`${source.source}:${source.heading}`">
                  <span>{{ source.heading }}</span>
                </li>
              </ul>
            </details>

            <div v-if="message.error || message.stopped" class="assistant-inline-state">
              <span>{{ message.error || t('assistantStopped') }}</span>
              <NButton
                v-if="index === messages.length - 1"
                size="tiny"
                quaternary
                @click="retryLast(locale)"
              >
                <template #icon><NIcon :component="RefreshOutline" /></template>
                {{ t('assistantRetry') }}
              </NButton>
            </div>
          </div>
        </article>
      </div>

      <div ref="tasksEl" class="assistant-tasks">
        <h3 v-if="props.expanded" class="assistant-tasks-title">{{ agentCopy.workspaceTitle }}</h3>
        <p v-if="props.expanded && !hasTasks" class="assistant-tasks-empty">{{ agentCopy.workspaceHint }}</p>
        <div v-if="pendingApproval || (streaming && status)" class="assistant-status" role="status">{{ agentCopy.status }}: {{ pendingApproval ? agentCopy.statusApproval : statusText(status) }}</div>

        <AgentTaskCard v-for="task in draftList" :key="task.draft_id" :draft="task" :busy="actionBusy" :streaming="streaming" @edit="invalidateApproval" @review="reviewDraft($event.draft_id, $event.draft)" @save="saveDraftLocalized" />

        <div v-if="actionError" class="assistant-inline-state" role="alert">{{ actionError }}</div>

        <details v-if="eventList.some(event => event.event === 'tool_result')" class="assistant-tool-results">
          <summary>{{ agentCopy.tool }}</summary>
          <div v-for="(event, index) in eventList.filter(item => item.event === 'tool_result')" :key="index" class="assistant-tool-result">
            <strong :class="event.payload.ok === false ? 'assistant-result-failure' : 'assistant-result-success'">{{ event.payload.ok === false ? agentCopy.failure : event.payload.partial ? agentCopy.partial : agentCopy.success }}</strong>
            <span>{{ toolLabel(event.payload.tool) }} · {{ eventResult(event.payload.result) }}</span>
            <img v-if="resultAssetId(event.payload.result) && imageUrls[resultAssetId(event.payload.result)]" :src="imageUrls[resultAssetId(event.payload.result)]" alt="Generated result" class="assistant-result-image">
            <details><summary>{{ agentCopy.details }}</summary><pre>{{ eventResult(event.payload.result, true) }}</pre></details>
          </div>
        </details>

        <button v-if="navigation" type="button" class="assistant-navigation" @click="followNavigation">{{ navigationLabel(navigation.route) }}</button>
        <button v-if="messages.length && !streaming && !pendingApproval" type="button" class="assistant-continue" @click="ask(agentCopy.continuePrevious)">{{ agentCopy.continuePrevious }}</button>

        <article v-if="pendingApproval" class="assistant-approval" data-agent-approval>
          <strong>{{ agentCopy.pending }}</strong>
          <span>{{ toolLabel(pendingApproval.tool) }}</span>
          <strong v-if="approvalTarget">{{ agentCopy.target }}: {{ approvalTarget }}</strong>
          <span v-if="pendingApproval.expired || pendingApproval.recovery_required" class="assistant-approval-invalid">{{ agentCopy.approvalInvalid }}</span>
          <details v-if="pendingApproval.preview || pendingApproval.arguments">
            <summary>{{ agentCopy.details }}</summary>
            <pre>{{ eventResult(pendingApproval.preview || pendingApproval.arguments, true) }}</pre>
          </details>
          <div class="assistant-approval-actions">
            <NButton size="small" type="primary" :loading="actionBusy" :disabled="actionBusy || pendingApproval.expired || pendingApproval.recovery_required" @click="confirmApproval(true)">{{ agentCopy.approve }}</NButton>
            <NButton size="small" quaternary :loading="actionBusy" :disabled="actionBusy" @click="cancelApproval">{{ agentCopy.cancel }}</NButton>
          </div>
        </article>
      </div>
    </div>

    <footer class="assistant-composer">
      <NInput
        v-model:value="draft"
        type="textarea"
        :placeholder="t('assistantPlaceholder')"
        :autosize="{ minRows: 1, maxRows: 5 }"
        @keydown="onKeydown"
      />
      <NButton v-if="streaming" type="warning" class="assistant-send" @click="stop">
        <template #icon><NIcon :component="StopCircleOutline" /></template>
        {{ t('assistantStop') }}
      </NButton>
      <NButton v-else type="primary" class="assistant-send" :disabled="!draft.trim()" @click="onSubmit">
        <template #icon><NIcon :component="SendOutline" /></template>
        {{ t('assistantSend') }}
      </NButton>
      <span class="assistant-composer-hint">{{ pendingApproval ? `${agentCopy.statusApproval} · ${toolLabel(pendingApproval.tool)}` : t('assistantInputHint') }}</span>
    </footer>
  </section>
</template>

<style scoped>
.assistant-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  color: var(--df-text);
  background:
    radial-gradient(circle at 100% 0, color-mix(in srgb, var(--df-interactive) 12%, transparent), transparent 26%),
    var(--df-surface-1);
}

.assistant-panel-head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto auto;
  align-items: center;
  gap: 9px;
  padding: 14px 15px;
  border-bottom: 1px solid var(--df-border-soft);
  background: color-mix(in srgb, var(--df-surface-raised) 88%, transparent);
  backdrop-filter: blur(16px);
}

.assistant-brand,
.assistant-empty-icon,
.assistant-avatar {
  display: grid;
  place-items: center;
  color: var(--df-interactive-strong);
  border: 1px solid color-mix(in srgb, var(--df-interactive) 38%, var(--df-border-soft));
  background: color-mix(in srgb, var(--df-interactive) 10%, var(--df-control-bg));
}

.assistant-brand {
  width: 38px;
  height: 38px;
  border-radius: 12px;
}

.assistant-head-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.assistant-head-copy strong {
  color: var(--df-accent-strong);
  font-size: 15px;
}

.assistant-head-copy span {
  overflow: hidden;
  color: var(--df-text-muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.assistant-messages {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow-y: auto;
  flex-direction: column;
  gap: 14px;
  padding: 18px 15px;
  scroll-behavior: smooth;
}

.assistant-transcript,
.assistant-tasks {
  display: contents;
}

.assistant-tasks-title {
  position: sticky;
  top: -18px;
  z-index: 1;
  margin: -18px -15px 0;
  padding: 16px 15px 12px;
  border-bottom: 1px solid var(--df-border-soft);
  color: var(--df-accent-strong);
  background: var(--df-surface-1);
  font-size: 14px;
}

.assistant-tasks-empty {
  margin: 0;
  color: var(--df-text-muted);
  font-size: 13px;
  line-height: 1.7;
}

@media (min-width: 801px) {
  .assistant-panel-expanded .assistant-messages {
    display: grid;
    grid-template-columns: minmax(0, 7fr) minmax(280px, 3fr);
    grid-template-rows: minmax(0, 1fr);
    gap: 0;
    overflow: hidden;
    padding: 0;
  }

  .assistant-panel-expanded .assistant-transcript,
  .assistant-panel-expanded .assistant-tasks {
    display: flex;
    min-width: 0;
    min-height: 0;
    flex-direction: column;
    gap: 14px;
    overflow-y: auto;
    padding: 18px 15px;
    scroll-behavior: smooth;
  }

  .assistant-panel-expanded .assistant-tasks {
    border-left: 1px solid var(--df-border-soft);
    background: color-mix(in srgb, var(--df-surface-2) 45%, var(--df-surface-1));
  }
}

.assistant-empty {
  display: grid;
  width: min(100%, 360px);
  margin: auto;
  justify-items: center;
  gap: 9px;
  padding: 24px 6px;
  text-align: center;
}

.assistant-empty-icon {
  width: 56px;
  height: 56px;
  margin-bottom: 4px;
  border-radius: 18px;
  box-shadow: var(--df-shadow);
}

.assistant-empty strong {
  color: var(--df-accent-strong);
  font-size: 17px;
}

.assistant-empty p,
.assistant-empty small {
  margin: 0;
  color: var(--df-text-muted);
  line-height: 1.6;
}

.assistant-quick-grid {
  display: grid;
  width: 100%;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 8px 0 2px;
}

.assistant-quick-grid button {
  min-height: 54px;
  padding: 9px 10px;
  border: 1px solid var(--df-border-soft);
  border-radius: var(--df-radius-md);
  color: var(--df-text-secondary);
  background: color-mix(in srgb, var(--df-control-bg) 82%, transparent);
  font-size: 12px;
  line-height: 1.4;
  text-align: left;
}

.assistant-quick-grid button:last-child {
  grid-column: 1 / -1;
}

.assistant-message {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.assistant-message-user {
  justify-content: flex-end;
}

.assistant-avatar {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  margin-top: 2px;
  border-radius: 9px;
}

.assistant-message-stack {
  display: grid;
  max-width: 88%;
  min-width: 0;
  gap: 6px;
}

.assistant-bubble {
  padding: 10px 12px;
  border: 1px solid var(--df-border-soft);
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.assistant-bubble.user {
  border-bottom-right-radius: 5px;
  border-color: color-mix(in srgb, var(--df-interactive) 50%, var(--df-border-soft));
  background: color-mix(in srgb, var(--df-interactive) 15%, var(--df-surface-raised));
  white-space: pre-wrap;
}

.assistant-bubble.assistant {
  border-top-left-radius: 5px;
  background: linear-gradient(155deg, var(--df-surface-raised), var(--df-surface-2));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .04);
}

.assistant-thinking {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 20px;
}

.assistant-thinking i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--df-interactive-strong);
  animation: assistant-pulse 1s ease-in-out infinite;
}

.assistant-thinking i:nth-child(2) { animation-delay: .14s; }
.assistant-thinking i:nth-child(3) { animation-delay: .28s; }

@keyframes assistant-pulse {
  0%, 70%, 100% { opacity: .25; transform: translateY(0); }
  35% { opacity: 1; transform: translateY(-3px); }
}

.assistant-sources {
  color: var(--df-text-muted);
  font-size: 11px;
}

.assistant-sources summary {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.assistant-sources ul {
  display: grid;
  gap: 5px;
  margin: 7px 0 0;
  padding: 8px 10px 8px 24px;
  border-left: 1px solid var(--df-border-soft);
}

.assistant-sources li span {
  display: block;
}

.assistant-inline-state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 9px;
  border: 1px solid color-mix(in srgb, var(--df-danger) 38%, var(--df-border-soft));
  border-radius: var(--df-radius-sm);
  color: var(--df-danger-strong);
  background: color-mix(in srgb, var(--df-danger) 8%, transparent);
  font-size: 11px;
}

.assistant-status,
.assistant-approval,
.assistant-tool-results {
  padding: 9px 10px;
  border: 1px solid var(--df-border-soft);
  border-radius: var(--df-radius-sm);
  color: var(--df-text-secondary);
  background: color-mix(in srgb, var(--df-control-bg) 84%, transparent);
  font-size: 11px;
}

.assistant-approval { display: grid; gap: 7px; }
.assistant-approval > span { color: var(--df-text-muted); }
.assistant-approval-actions { display: flex; gap: 7px; }
.assistant-tool-result { display: grid; gap: 5px; padding-top: 7px; overflow-wrap: anywhere; }
.assistant-result-success { color: var(--df-success-strong); }
.assistant-result-failure { color: var(--df-danger-strong); }
.assistant-result-image { display: block; max-width: 100%; max-height: 220px; border: 1px solid var(--df-border-soft); border-radius: var(--df-radius-sm); object-fit: contain; }
.assistant-tool-result pre,
.assistant-approval pre { max-height: 12rem; overflow: auto; white-space: pre-wrap; }
.assistant-navigation { align-self: flex-start; padding: 7px 10px; border: 1px solid var(--df-interactive); border-radius: var(--df-radius-sm); color: var(--df-on-accent); background: var(--df-interactive); cursor: pointer; }

.assistant-composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: end;
  padding: 12px 14px calc(10px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--df-border-soft);
  background: color-mix(in srgb, var(--df-surface-raised) 94%, transparent);
  box-shadow: 0 -12px 28px color-mix(in srgb, #000 10%, transparent);
}

.assistant-send {
  min-height: 36px;
}

.assistant-composer-hint {
  grid-column: 1 / -1;
  color: var(--df-text-muted);
  font-size: 10px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

@media (max-width: 420px) {
  .assistant-quick-grid { grid-template-columns: 1fr; }
  .assistant-message-stack { max-width: 92%; }
}
</style>
