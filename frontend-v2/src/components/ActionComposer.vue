<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { NIcon } from 'naive-ui'
import { MicOutline, StopCircleOutline, CloseOutline } from '@vicons/ionicons5'
import { api, ApiError } from '@/api/client'
import type { ActionSubmitResponse, GameDetail } from '@/api/types'
import { useLocale } from '@/composables/useLocale'
import { appendDictated, asrLanguageFor, initializeAsr, useVoiceInput, voiceInputSupported } from '@/utils/asr'
import ActionRecoveryBanner from '@/features/play/recovery/ActionRecoveryBanner.vue'
import {
  actionRecoveryMessage,
  actionRecoveryConfirmedMessage,
  type ActionRecoveryCode,
} from '@/features/play/recovery/copy'
import {
  clearActionRecovery,
  useActionRecovery,
  type ActionRecoveryIdentity,
  type ActionRecoveryRecord,
  type ActionRecoverySnapshot,
} from '@/features/play/recovery/useActionRecovery'

const props = defineProps<{ gameKey: string; userId: string; detail: GameDetail; disabled?: boolean; recoveryRefreshToken?: string }>()
const emit = defineEmits<{
  refresh: [token?: string]
  processing: [value: boolean]
  'recovery-status': [value: { count: number; message: string }]
}>()
const { t, locale } = useLocale()

const text = ref(''), busy = ref(false), notice = ref('')
const textarea = ref<HTMLTextAreaElement | null>(null)
const recoveryBanner = ref<HTMLElement | null>(null)
const identity = computed<ActionRecoveryIdentity>(() => ({
  gameKey: props.gameKey,
  runId: String(props.detail.run_id || ''),
  actorId: props.userId,
  round: Math.max(0, Number(props.detail.round_number || 0)),
}))
const { snapshot, save, read } = useActionRecovery(identity)
const recovery = computed(() => snapshot.value?.recovery || null)
const requiresRefresh = computed(() => recovery.value?.kind === 'refresh')
const identityKey = computed(() => JSON.stringify(identity.value))
let submitSerial = 0
let activeAttempt: { serial: number; identityKey: string } | null = null
let disposed = false

const own = computed(() => props.detail.multiplayer?.submitted_actions?.find(a => a.user_id === props.userId))
const hint = computed(() => props.detail.solo_mode ? t('soloHint') : own.value ? t('submittedHint', { count: own.value.revision_count || 1 }) : t('defaultHint'))
const defaultQuickActions = computed(() => [t('quickObserve'), t('quickExplore'), t('quickTalk'), t('quickPrepareCombat')])
const quickActions = computed(() => (props.detail.quick_actions?.length ? props.detail.quick_actions : defaultQuickActions.value) as string[])
const locked = computed(() => props.disabled || busy.value || requiresRefresh.value)

function hydrateRecovery() {
  const current = read()
  text.value = current?.draft || ''
}

function draftChanged(value: string) {
  const current = snapshot.value
  if (!value.trim() && !current?.recovery) {
    clearActionRecovery(identity.value)
    return
  }
  save(value, current?.recovery || null)
}

function codeOf(error: unknown): ActionRecoveryCode {
  const code = typeof ApiError === 'function' && error instanceof ApiError
    ? error.code
    : error && typeof error === 'object' && 'code' in error
      ? String((error as { code?: unknown }).code || '')
      : ''
  if (code === 'ROUND_PROCESSING_FAILED' || code === 'ROUND_POST_COMMIT_FAILED' || code === 'ROUND_NOT_PROCESSED') return code
  return 'UNKNOWN'
}

function showRecovery(error: unknown) {
  const code = codeOf(error)
  const kind: ActionRecoveryRecord['kind'] = code === 'ROUND_PROCESSING_FAILED' ? 'editable' : 'refresh'
  const record: ActionRecoveryRecord = {
    code,
    message: actionRecoveryMessage(locale.value, code),
    kind,
    createdAt: Date.now(),
  }
  save(text.value, record)
}

function sameIdentityKey(key: string) { return key === identityKey.value }

function clearRecovery(attemptIdentityKey = identityKey.value) {
  if (!sameIdentityKey(attemptIdentityKey)) return
  clearActionRecovery(identity.value)
  snapshot.value = null
}

function recoveryToken(value: ActionRecoverySnapshot | null = snapshot.value): string {
  if (!value?.recovery) return ''
  return JSON.stringify({
    identity: value.identity,
    updatedAt: value.updatedAt,
    code: value.recovery.code,
    createdAt: value.recovery.createdAt,
  })
}

function requestRecoveryRefresh() {
  const token = recoveryToken()
  if (token) emit('refresh', token)
}

watch(identity, () => {
  if (activeAttempt && !sameIdentityKey(activeAttempt.identityKey)) {
    submitSerial++
    activeAttempt = null
    if (busy.value) { busy.value = false; emit('processing', false) }
  }
  hydrateRecovery()
}, { immediate: true })
watch(text, value => { draftChanged(value) })
watch(recovery, value => emit('recovery-status', { count: value ? 1 : 0, message: value?.message || '' }), { immediate: true })
watch(() => props.recoveryRefreshToken, value => {
  const current = recovery.value
  if (!value || !current || !requiresRefresh.value || value !== recoveryToken()) return
  if (current.code === 'ROUND_POST_COMMIT_FAILED') {
    text.value = ''
    clearRecovery()
    return
  }
  save(text.value, { ...current, kind: 'editable', message: actionRecoveryConfirmedMessage(locale.value), createdAt: Date.now() })
})

const micAvailable = computed(() => voiceInputSupported())
const {
  recording, transcribing, errorCode, serverMessage, elapsedSeconds,
  toggle: toggleVoice, release: releaseVoice,
} = useVoiceInput({
  gameKey: props.gameKey,
  lang: () => asrLanguageFor(locale.value),
  onText: chunk => { text.value = appendDictated(text.value, chunk) },
})

const dictationError = computed(() => {
  if (errorCode.value === 'asr-mic-denied') return t('asrMicDenied')
  if (errorCode.value === 'asr-record-failed') return t('asrRecordFailed')
  if (errorCode.value === 'asr-failed') return t('asrFailed')
  return serverMessage.value
})

// 用户可手动关掉错误条；新错误出现时重新显示
const dictationErrorDismissed = ref(false)
watch(dictationError, value => { if (!value) dictationErrorDismissed.value = false })
function dismissDictationError() { dictationErrorDismissed.value = true }

onMounted(() => { void initializeAsr() })

watch(locked, value => { if (value) releaseVoice() })

function resetSubmissionState() {
  notice.value = ''
}

const ownSignature = computed(() => own.value
  ? JSON.stringify([own.value.text, own.value.revision_count])
  : '')

watch(
  [() => props.detail.round_number, ownSignature],
  ([roundNumber, signature], [previousRoundNumber, previousSignature]) => {
    if (roundNumber !== previousRoundNumber || (previousSignature && !signature)) {
      resetSubmissionState()
    }
  },
)

async function submit() {
  const action = text.value.trim()
  if (!action || locked.value) return
  releaseVoice()
  const attemptIdentityKey = identityKey.value
  const serial = ++submitSerial
  activeAttempt = { serial, identityKey: attemptIdentityKey }
  busy.value = true; notice.value = ''; clearRecovery(attemptIdentityKey); emit('processing', true)
  try {
    const r = await api<ActionSubmitResponse>(`/games/${encodeURIComponent(props.gameKey)}/action`, { method: 'POST', body: JSON.stringify({ text: action }) })
    if (disposed || activeAttempt?.serial !== serial || !sameIdentityKey(attemptIdentityKey)) return
    text.value = ''
    notice.value = r.phase === 'luck' ? t('luckDecisionRequired') : t('actionRecorded')
    emit('refresh')
  } catch (e: unknown) {
    if (disposed || activeAttempt?.serial !== serial || !sameIdentityKey(attemptIdentityKey)) return
    showRecovery(e)
  } finally {
    if (disposed || activeAttempt?.serial !== serial || !sameIdentityKey(attemptIdentityKey)) return
    activeAttempt = null; busy.value = false; emit('processing', false)
  }
}

function focusComposer() { textarea.value?.focus() }
function focusRecovery() {
  const target = requiresRefresh.value
    ? recoveryBanner.value?.querySelector<HTMLElement>('button')
    : textarea.value
  if (!target) return
  target.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
  target.focus()
}
defineExpose({ focusRecovery })

onUnmounted(() => {
  disposed = true; submitSerial++; activeAttempt = null
  emit('recovery-status', { count: 0, message: '' })
  if (busy.value) emit('processing', false)
})
</script>

<template>
  <div class="composer">
    <div class="composer-head">
      <div class="composer-title-row">
        <strong>{{ t('composerTitle') }}</strong>
        <span v-if="hint" class="composer-hint">{{ hint }}</span>
      </div>
      <slot name="tools" />
    </div>
    <div class="quick-actions" :aria-label="t('quickActions')">
      <button v-for="action in quickActions" :key="action" :disabled="locked" @click="text = action">{{ action }}</button>
    </div>
    <div v-if="dictationError && !dictationErrorDismissed" class="dictation-status error">
      <span class="dictation-error-copy">{{ dictationError }}</span>
      <button type="button" class="dictation-error-close" :aria-label="t('close')" @click="dismissDictationError">
        <NIcon :component="CloseOutline" />
      </button>
    </div>
    <div v-else-if="recording" class="dictation-status">{{ t('asrRecording', { seconds: elapsedSeconds }) }}</div>
    <div v-else-if="transcribing" class="dictation-status">{{ t('asrTranscribing') }}</div>
    <div v-if="recovery" ref="recoveryBanner">
      <ActionRecoveryBanner
        :message="recovery.message"
        :requires-refresh="requiresRefresh"
        @refresh="requestRecoveryRefresh"
        @focus="focusComposer"
      />
    </div>
    <div class="composer-row" :class="{ 'has-dictation': micAvailable }">
      <textarea ref="textarea" v-model="text" :disabled="locked" :placeholder="t('actionPlaceholder')" @keydown.ctrl.enter.prevent="submit()" />
      <button
        v-if="micAvailable"
        type="button"
        class="dictation-toggle"
        :class="{ active: recording }"
        :title="recording ? t('asrStop') : t('asrVoice')"
        :aria-label="recording ? t('asrStop') : t('asrVoice')"
        :aria-pressed="recording"
        :disabled="transcribing || (locked && !recording)"
        @click="toggleVoice()"
      >
        <NIcon :component="recording ? StopCircleOutline : MicOutline" />
      </button>
      <button class="primary" @click="submit()" :disabled="locked || !text.trim()">{{ busy ? t('processing') : t('action') }}</button>
    </div>
    <div v-if="notice" class="notice">{{ notice }}</div>
  </div>
</template>

<style scoped>
.composer-row.has-dictation {
  grid-template-columns: minmax(0, 1fr) 44px 92px;
}

.dictation-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--df-interactive) 38%, var(--df-border-soft));
  border-radius: var(--df-radius-md);
  color: var(--df-text-secondary);
  background: color-mix(in srgb, var(--df-interactive) 10%, var(--df-control-bg));
  font-size: 19px;
}

.dictation-toggle.active {
  border-color: color-mix(in srgb, var(--df-danger) 55%, var(--df-border-soft));
  color: var(--df-danger-strong);
  background: color-mix(in srgb, var(--df-danger) 12%, transparent);
}

.dictation-toggle:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.dictation-status {
  margin-bottom: 7px;
  padding: 6px 10px;
  border: 1px solid color-mix(in srgb, var(--df-interactive) 32%, var(--df-border-soft));
  border-radius: 6px;
  color: var(--df-text);
  background: color-mix(in srgb, var(--df-interactive) 8%, transparent);
  font-size: 12px;
  line-height: 1.5;
}

.dictation-status.error {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  border-color: color-mix(in srgb, var(--df-danger) 38%, var(--df-border-soft));
  color: var(--df-danger-strong);
  background: color-mix(in srgb, var(--df-danger) 8%, transparent);
}

.dictation-error-copy {
  min-width: 0;
  overflow-wrap: anywhere;
}

.dictation-error-close {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 14px;
}

.dictation-error-close:hover {
  background: color-mix(in srgb, var(--df-danger) 16%, transparent);
}

@media (max-width: 800px) {
  .composer-row.has-dictation {
    grid-template-columns: minmax(0, 1fr) 40px 72px;
  }

  .dictation-toggle {
    min-width: 40px;
  }
}
</style>
