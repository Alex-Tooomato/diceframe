<script setup lang="ts">
/**
 * GM 工作台的本局 GM 路由面板：当前生效来源状态卡 + 模式/模型配置。
 * 轮询读取（同 AISeatsPanel 的 4s 节奏）；PUT 使用 expected_revision 乐观并发。
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import Modal from '@/components/ui/Modal.vue'
import { useLocale } from '@/composables/useLocale'
import GmRoutingEditor from '@/features/gm-routing/GmRoutingEditor.vue'
import { gmRoutingCopy, gmRoutingReason } from '@/features/gm-routing/copy'
import {
  parseGmRoutingResponse, settingsPayload, type GmRoutingResponse, type GmRoutingSettings,
} from '@/features/gm-routing/types'

const props = defineProps<{ gameKey: string; isGm: boolean; preview?: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const { locale } = useLocale()
const copy = computed(() => gmRoutingCopy[locale.value])
const visible = computed(() => props.isGm && !props.preview && Boolean(props.gameKey))
const state = ref<GmRoutingResponse | null>(null)
const error = ref(''), busy = ref(false), stale = ref(false)
const editorOpen = ref(false)
const draft = ref<GmRoutingSettings>({ mode: 'server', user: null })
let epoch = 0, timer: ReturnType<typeof setInterval> | undefined
const base = computed(() => `/games/${encodeURIComponent(props.gameKey)}/gm-routing`)

async function refresh() {
  if (!visible.value) return
  const current = epoch, url = base.value
  try {
    const result = parseGmRoutingResponse(await api<unknown>(url))
    if (current === epoch && visible.value) {
      const changed = state.value !== null && (
        state.value.effective.source !== result.effective.source
        || state.value.effective.reason !== result.effective.reason
        || state.value.mode !== result.mode)
      state.value = result
      if (!editorOpen.value && !busy.value) { error.value = ''; stale.value = false }
      if (changed) emit('changed')
    }
  } catch { if (current === epoch) error.value = copy.value.error }
}
watch([visible, () => props.gameKey], () => {
  epoch++; state.value = null; editorOpen.value = false; error.value = ''; stale.value = false; busy.value = false
  if (timer) clearInterval(timer)
  if (visible.value) { void refresh(); timer = setInterval(() => { if (!busy.value) void refresh() }, 4000) }
}, { immediate: true })
onUnmounted(() => { epoch++; if (timer) clearInterval(timer) })

const effective = computed(() => state.value?.effective || null)
const statusLine = computed(() => {
  if (!state.value) return ''
  if (effective.value) {
    const source = effective.value.source === 'user' ? copy.value.effectiveUser : copy.value.effectiveServer
    const model = effective.value.source === 'user' && effective.value.main
      ? `${effective.value.main.provider_name || ''} · ${effective.value.main.model || ''}`.trim()
      : `${state.value.application.provider_ref || ''} · ${state.value.application.model || ''}`.trim()
    return model ? `${source}（${model}）` : source
  }
  return ''
})
function reasonText(reason: string) { return gmRoutingReason(copy.value, reason || '') }

function open() {
  if (!state.value) return
  draft.value = { mode: state.value.mode, user: state.value.user }
  error.value = ''; stale.value = false; editorOpen.value = true
}
async function save() {
  if (!state.value || busy.value) return
  const current = epoch, url = base.value
  busy.value = true; error.value = ''; stale.value = false
  try {
    const result = parseGmRoutingResponse(await api<unknown>(url, {
      method: 'PUT',
      body: JSON.stringify({ settings: settingsPayload(draft.value), expected_revision: state.value.revision }),
    }))
    if (current === epoch) { state.value = result; editorOpen.value = false; emit('changed') }
  } catch {
    if (current === epoch) { error.value = copy.value.error; stale.value = true }
  } finally { if (current === epoch) busy.value = false }
}
</script>

<template>
  <section v-if="visible" class="panel gm-routing" data-testid="gm-routing">
    <div class="gm-routing-heading">
      <h2>{{ copy.title }}</h2>
      <button :disabled="!state || busy" @click="open">{{ copy.configure }}</button>
    </div>
    <p v-if="!state && !error" role="status">{{ copy.loading }}</p>
    <p v-if="error && !editorOpen" role="alert">{{ error }} <button @click="refresh">{{ copy.reload }}</button></p>
    <div v-if="state && effective" class="gm-routing-status" data-testid="gm-routing-status">
      <p><strong>{{ copy.effectiveTitle }}：</strong>{{ statusLine }}</p>
      <p v-if="state.mode === 'user'" :data-online="effective.user_gm_online">
        <small>{{ effective.user_gm_online ? copy.online : copy.offline }}</small>
        <small v-if="!effective.user_gm_online"> · {{ copy.offlineHint }}</small>
      </p>
      <p v-if="reasonText(effective.reason)" class="gm-routing-reason" role="status">{{ reasonText(effective.reason) }}</p>
    </div>
    <Modal v-if="editorOpen" :title="copy.title" dialog-class="gm-routing-dialog" @close="editorOpen = false">
      <form @submit.prevent="save">
        <GmRoutingEditor v-model="draft" :providers="state?.providers || []"
                         :server-provider-name="state?.providers.find(p => p.id === state?.application.provider_ref)?.name || state?.application.provider_ref"
                         :server-model="state?.application.model" />
        <p v-if="stale" class="gm-routing-reason" role="alert">{{ copy.stale }}</p>
        <p v-if="error" role="alert">{{ error }}</p>
        <div class="gm-routing-actions">
          <button type="submit" data-testid="gm-routing-save" :disabled="busy || (draft.mode === 'user' && !draft.user?.main)">{{ copy.save }}</button>
          <button type="button" :disabled="busy" @click="editorOpen = false">{{ copy.cancel }}</button>
          <button type="button" :disabled="busy" @click="open">{{ copy.reload }}</button>
        </div>
      </form>
    </Modal>
  </section>
</template>

<style scoped>
.gm-routing-heading, .gm-routing-actions { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }
.gm-routing-heading { justify-content: space-between; }
.gm-routing p { margin: .4rem 0; overflow-wrap: anywhere; }
.gm-routing-status { border-top: 1px solid var(--border-color, #8883); padding-top: .6rem; }
.gm-routing-reason { color: var(--error-color, #bd5252); }
small { opacity: .75; }
button { padding: .35rem .55rem; }
form { max-width: 100%; display: grid; gap: .8rem; }
</style>
