<script setup lang="ts">
/**
 * GM 路由编辑器：GM 来源（服务端 / user GM）+ user 模式下的模型选择。
 * 纯受控组件——创建向导（随创建载荷提交）与对局面板（PUT + revision）共用。
 */
import { computed } from 'vue'
import { useLocale } from '@/composables/useLocale'
import { gmRoutingCopy } from './copy'
import { emptyUserSettings, type GmProviderOption, type GmRouteRef, type GmRoutingSettings, type GmUserSettings } from './types'

const props = defineProps<{
  modelValue: GmRoutingSettings
  providers: GmProviderOption[]
  /** 服务端主模型描述（provider/model 展示用；空串表示服务端未配置）。 */
  serverProviderName?: string
  serverModel?: string
}>()
const emit = defineEmits<{ 'update:modelValue': [settings: GmRoutingSettings] }>()
const { locale } = useLocale()
const copy = computed(() => gmRoutingCopy[locale.value])

const user = computed<GmUserSettings>(() => props.modelValue.user || emptyUserSettings())

function update(patch: Partial<GmUserSettings>) {
  emit('update:modelValue', { ...props.modelValue, user: { ...user.value, ...patch } })
}
function setMode(mode: GmRoutingSettings['mode']) {
  if (mode === props.modelValue.mode) return
  emit('update:modelValue', mode === 'user'
    ? { mode, user: user.value.main ? user.value : { ...emptyUserSettings() } }
    : { mode, user: null })
}
function modelsOf(providerRef: string): string[] {
  return props.providers.find(item => item.id === providerRef)?.models || []
}
function setRoute(role: 'main' | 'fallback1' | 'fallback2' | 'check', value: string) {
  if (!value) { update({ [role]: null } as Partial<GmUserSettings>); return }
  const [providerRef, ...rest] = value.split('::')
  const model = rest.join('::')
  update({ [role]: { provider_ref: providerRef, model } } as Partial<GmUserSettings>)
}
function routeValue(role: 'main' | 'fallback1' | 'fallback2' | 'check'): string {
  const route = user.value[role] as GmRouteRef | null
  return route ? `${route.provider_ref}::${route.model}` : ''
}
const mainMissing = computed(() => props.modelValue.mode === 'user' && !user.value.main)
</script>

<template>
  <div class="gm-routing-editor" data-testid="gm-routing-editor">
    <div class="gm-routing-mode-cards">
      <button type="button" :class="{ active: modelValue.mode === 'server' }" data-testid="gm-mode-server" @click="setMode('server')">
        <strong>{{ copy.serverMode }}</strong>
        <small>{{ copy.serverModeHint }}</small>
      </button>
      <button type="button" :class="{ active: modelValue.mode === 'user' }" data-testid="gm-mode-user" @click="setMode('user')">
        <strong>{{ copy.userMode }}</strong>
        <small>{{ copy.userModeHint }}</small>
      </button>
    </div>

    <p v-if="modelValue.mode === 'server' && serverModel" class="gm-routing-server-note">
      {{ copy.applicationModel }}：{{ serverProviderName }} · {{ serverModel }}
    </p>

    <template v-if="modelValue.mode === 'user'">
      <div v-for="role in (['main', 'fallback1', 'fallback2', 'check'] as const)" :key="role" class="gm-routing-route">
        <label>
          <span>{{ role === 'main' ? copy.roleMain : role === 'fallback1' ? copy.roleFallback1 : role === 'fallback2' ? copy.roleFallback2 : copy.roleCheck }}</span>
          <select :data-testid="`gm-route-${role}`" :value="routeValue(role)"
                  @change="setRoute(role, ($event.target as HTMLSelectElement).value)">
            <option v-if="role !== 'main'" value="">{{ role === 'check' ? copy.checkFollowMain : copy.inheritServer }}</option>
            <optgroup v-for="provider in providers" :key="provider.id" :label="provider.name">
              <option v-for="item in provider.models" :key="`${provider.id}::${item}`" :value="`${provider.id}::${item}`">{{ item }}</option>
            </optgroup>
            <!-- 引用已失效的旧值保留展示，避免静默改配置。 -->
            <option v-if="routeValue(role) && !modelsOf(routeValue(role).split('::')[0]).includes(routeValue(role).split('::').slice(1).join('::'))" :value="routeValue(role)" disabled>{{ routeValue(role).split('::').slice(1).join('::') }} · {{ copy.unavailable }}</option>
          </select>
        </label>
      </div>
      <p v-if="mainMissing" class="gm-routing-error" role="alert">{{ copy.mainRequired }}</p>
      <label class="gm-routing-check"><input type="checkbox" :checked="user.fallback_to_server !== false" @change="update({ fallback_to_server: ($event.target as HTMLInputElement).checked })"><span>{{ copy.followServer }}</span></label>
      <small class="gm-routing-hint">{{ copy.followServerHint }}</small>
    </template>
  </div>
</template>

<style scoped>
.gm-routing-editor { display: grid; gap: .8rem; min-width: 0; }
.gm-routing-mode-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: .6rem; }
.gm-routing-mode-cards button { display: grid; gap: .3rem; padding: .7rem; text-align: left; border-radius: .5rem; border: 1px solid var(--border-color, #8884); background: transparent; cursor: pointer; }
.gm-routing-mode-cards button.active { border-color: var(--df-interactive, inherit); box-shadow: inset 0 0 0 1px var(--df-interactive, transparent); }
.gm-routing-mode-cards small { opacity: .75; }
.gm-routing-route label { display: grid; gap: .35rem; }
.gm-routing-route select { width: 100%; min-width: 0; padding: .5rem; border-radius: .4rem; }
.gm-routing-check { display: flex; gap: .5rem; align-items: center; }
.gm-routing-hint { opacity: .7; }
.gm-routing-server-note { opacity: .8; }
.gm-routing-error { color: var(--error-color, #bd5252); }
</style>
