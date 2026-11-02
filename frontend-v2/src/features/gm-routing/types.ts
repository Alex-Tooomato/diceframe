/** 本局 GM 路由（user GM / 服务端 GM）的前端类型与响应解析。 */

export type GmRoutingMode = 'server' | 'user'

export interface GmRouteRef {
  provider_ref: string
  model: string
}

export interface GmUserSettings {
  main: GmRouteRef | null
  fallback1: GmRouteRef | null
  fallback2: GmRouteRef | null
  check: GmRouteRef | null
  fallback_to_server: boolean
}

export interface GmRoutingSettings {
  mode: GmRoutingMode
  user: GmUserSettings | null
}

export interface GmProviderOption {
  id: string
  name: string
  models: string[]
}

export interface GmRouteView {
  ready: boolean
  reason: string
  provider_ref?: string
  provider_name?: string
  model?: string
}

export interface GmEffectiveView {
  source: 'user' | 'server'
  reason: string
  user_gm_online: boolean
  main: { provider_ref?: string; provider_name?: string; model?: string } | null
  fallbacks: Array<GmRouteView & { slot: string }>
  check_mode: 'main' | 'dedicated' | 'server'
  check: GmRouteView | null
}

export interface GmRoutingResponse {
  ok: boolean
  revision: number
  mode: GmRoutingMode
  user: GmUserSettings | null
  effective: GmEffectiveView
  providers: GmProviderOption[]
  application: {
    provider_ref: string
    model: string
    check_model_enabled: boolean
    check_provider_ref: string
    check_model: string
  }
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function str(value: unknown): boolean {
  return typeof value === 'string'
}

function optionalRef(value: unknown): GmRouteRef | null {
  if (value == null) return null
  if (!record(value) || !str(value.provider_ref) || !str(value.model)) {
    throw new Error('Invalid GM route')
  }
  return { provider_ref: String(value.provider_ref), model: String(value.model) }
}

function userSettings(value: unknown): GmUserSettings | null {
  if (value == null) return null
  if (!record(value)) throw new Error('Invalid GM user settings')
  const settings: GmUserSettings = {
    main: optionalRef(value.main),
    fallback1: optionalRef(value.fallback1),
    fallback2: optionalRef(value.fallback2),
    check: optionalRef(value.check),
    fallback_to_server: value.fallback_to_server !== false,
  }
  return settings
}

/** 严格解析服务端 project() 投影；结构不符直接抛错（面板显示加载失败）。 */
export function parseGmRoutingResponse(value: unknown): GmRoutingResponse {
  if (!record(value) || value.ok !== true || !Number.isInteger(value.revision)
    || (value.mode !== 'server' && value.mode !== 'user')
    || !record(value.effective) || !Array.isArray(value.providers)
    || !record(value.application)) {
    throw new Error('Invalid GM routing response')
  }
  const effective = value.effective
  if ((effective.source !== 'user' && effective.source !== 'server')
    || !str(effective.reason) || typeof effective.user_gm_online !== 'boolean'
    || !Array.isArray(effective.fallbacks)
    || !['main', 'dedicated', 'server'].includes(String(effective.check_mode))) {
    throw new Error('Invalid GM routing effective view')
  }
  if (!value.providers.every(p => record(p) && str(p.id) && str(p.name) && Array.isArray(p.models)
    && p.models.every(m => str(m)))) {
    throw new Error('Invalid GM routing providers')
  }
  return {
    ok: true,
    revision: value.revision as number,
    mode: value.mode as GmRoutingMode,
    user: userSettings(value.user),
    effective: effective as unknown as GmEffectiveView,
    providers: value.providers as GmProviderOption[],
    application: value.application as GmRoutingResponse['application'],
  }
}

export function emptyUserSettings(): GmUserSettings {
  return { main: null, fallback1: null, fallback2: null, check: null, fallback_to_server: true }
}

/** 服务端 payload：None 路由 = 该能力继承服务端全局配置。 */
export function settingsPayload(settings: GmRoutingSettings): GmRoutingSettings {
  if (settings.mode === 'server') return { mode: 'server', user: null }
  const user = settings.user || emptyUserSettings()
  const ref = (value: GmRouteRef | null) => (value && value.provider_ref && value.model
    ? { provider_ref: value.provider_ref, model: value.model }
    : null)
  return {
    mode: 'user',
    user: {
      main: ref(user.main),
      fallback1: ref(user.fallback1),
      fallback2: ref(user.fallback2),
      check: ref(user.check),
      fallback_to_server: user.fallback_to_server !== false,
    },
  }
}
