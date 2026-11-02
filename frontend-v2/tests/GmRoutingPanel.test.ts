import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { i18n } from '../src/i18n'
import GmRoutingPanel from '../src/features/play/gm-routing/GmRoutingPanel.vue'
import { emptyUserSettings, parseGmRoutingResponse, settingsPayload } from '../src/features/gm-routing/types'

const apiMock = vi.hoisted(() => ({ call: vi.fn() }))
vi.mock('../src/api/client', () => ({ api: apiMock.call }))

function view(overrides: Record<string, unknown> = {}) {
  return {
    ok: true, revision: 2, mode: 'user',
    user: { main: { provider_ref: 'user', model: 'qwen' }, fallback1: null, fallback2: null, check: null, fallback_to_server: true },
    effective: {
      source: 'user', reason: '', user_gm_online: true,
      main: { provider_ref: 'user', provider_name: 'User', model: 'qwen' },
      fallbacks: [], check_mode: 'main', check: null,
    },
    providers: [{ id: 'user', name: 'User', models: ['qwen', 'phi'] }, { id: 'srv', name: 'Server', models: ['big'] }],
    application: { provider_ref: 'srv', model: 'big', check_model_enabled: false, check_provider_ref: '', check_model: '' },
    ...overrides,
  }
}
function render(isGm = true, preview = false) {
  return mount(GmRoutingPanel, { global: { plugins: [i18n], stubs: { Teleport: true } }, props: {
    gameKey: 'web|room|bot', isGm: isGm, preview,
  } })
}
afterEach(() => { vi.clearAllMocks() })

describe('GM routing panel', () => {
  it('shows the effective GM source, model and online state', async () => {
    i18n.global.locale.value = 'zh-CN'
    apiMock.call.mockResolvedValue(view())
    const wrapper = render(); await flushPromises()
    expect(wrapper.text()).toContain('你的模型')
    expect(wrapper.text()).toContain('qwen')
    expect(wrapper.text()).toContain('在线')
    wrapper.unmount()
  })

  it('explains the server takeover while the user GM is offline', async () => {
    apiMock.call.mockResolvedValue(view({
      effective: { source: 'server', reason: 'gm_offline', user_gm_online: false,
        main: null, fallbacks: [], check_mode: 'server', check: null },
    }))
    const wrapper = render(); await flushPromises()
    expect(wrapper.text()).toContain('服务端模型')
    expect(wrapper.text()).toContain('离线')
    expect(wrapper.text()).toContain('user GM 离线')
    wrapper.unmount()
  })

  it('saves mode and model references with the captured revision', async () => {
    apiMock.call.mockResolvedValue(view())
    const wrapper = render(); await flushPromises()
    await wrapper.get('button').trigger('click') // configure
    await wrapper.get('[data-testid="gm-route-main"]').setValue('user::phi')
    await wrapper.get('[data-testid="gm-route-check"]').setValue('srv::big')
    await wrapper.get('[data-testid="gm-routing-save"]').trigger('submit'); await flushPromises()
    const mutation = apiMock.call.mock.calls.find(call => call[1]?.method === 'PUT')
    expect(mutation?.[0]).toBe('/games/web%7Croom%7Cbot/gm-routing')
    expect(JSON.parse(mutation?.[1]?.body)).toEqual({
      expected_revision: 2,
      settings: {
        mode: 'user',
        user: { main: { provider_ref: 'user', model: 'phi' }, fallback1: null, fallback2: null,
          check: { provider_ref: 'srv', model: 'big' }, fallback_to_server: true },
      },
    })
    wrapper.unmount()
  })

  it.each([[false, false], [true, true]])('does not fetch or display routing outside the GM seat', async (gm, preview) => {
    const wrapper = render(gm, preview); await flushPromises()
    expect(apiMock.call).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="gm-routing"]').exists()).toBe(false)
    wrapper.unmount()
  })
})

describe('GM routing payload helpers', () => {
  it('keeps server mode free of user overrides and trims unusable routes', () => {
    expect(settingsPayload({ mode: 'server', user: emptyUserSettings() })).toEqual({ mode: 'server', user: null })
    const payload = settingsPayload({
      mode: 'user',
      user: { main: { provider_ref: 'user', model: 'qwen' }, fallback1: { provider_ref: '', model: '' },
        fallback2: null, check: { provider_ref: 'user', model: '' }, fallback_to_server: false },
    })
    expect(payload.user).toEqual({
      main: { provider_ref: 'user', model: 'qwen' }, fallback1: null, fallback2: null,
      check: null, fallback_to_server: false,
    })
  })

  it('rejects malformed projections instead of rendering partial state', () => {
    expect(() => parseGmRoutingResponse({ ok: true })).toThrow()
    expect(() => parseGmRoutingResponse(view({ providers: 'nope' }))).toThrow()
    expect(() => parseGmRoutingResponse(view({ effective: { source: 'ghost' } }))).toThrow()
    expect(parseGmRoutingResponse(view()).revision).toBe(2)
  })
})
