import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import SettingsView from '../src/features/admin/SettingsView.vue'

const mocks = vi.hoisted(() => {
  const config = {
    ai_providers: [], model: '', llm_provider_ref: '', embedding_provider_ref: '',
    tts_provider: 'browser', asr_provider: 'disabled', proxy_supported: true,
    bot_token: {}, access_password: {}, update_channel: 'stable',
  } as Record<string, any>
  return {
    store: {
      config, secrets: {}, loading: false, error: '', load: vi.fn(), saveSection: vi.fn(),
      setConfigField: vi.fn(), test: vi.fn(), saveAccessPassword: vi.fn(), clearProxy: vi.fn(), botToken: vi.fn(),
    },
    api: vi.fn().mockResolvedValue({}),
    replace: vi.fn(),
  }
})

vi.mock('../src/stores/useSettingsStore', () => ({ useSettingsStore: () => mocks.store }))
vi.mock('../src/composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }) }))
vi.mock('../src/composables/useConfirm', () => ({ useConfirm: () => ({ confirm: vi.fn().mockResolvedValue(false) }) }))
vi.mock('../src/composables/useLocale', () => ({ useLocale: () => ({ t: (key: string) => key, locale: ref('en') }) }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: { section: 'models' } }), useRouter: () => ({ push: vi.fn(), replace: mocks.replace }) }))
vi.mock('../src/composables/useUpdateCheck', () => ({ useUpdateCheck: () => ({ updateInfo: ref(null), updateChecking: ref(false), checkForUpdates: vi.fn() }) }))
vi.mock('../src/composables/useUpdater', () => ({
  shouldAutoDownloadUpdate: vi.fn(() => false), updateStateForVersion: vi.fn(),
  useUpdater: () => ({ updateStatus: ref(null), reloadCountdown: ref(0), downloadPercent: ref(0), startDownload: vi.fn(), applyUpdate: vi.fn(), refreshStatus: vi.fn(), isUpdateBusy: ref(false), restartApplication: vi.fn(), waitForApplicationRestart: vi.fn() }),
}))
vi.mock('../src/composables/useTheme', () => ({ useTheme: () => ({ current: ref('dark'), skin: ref('midnight'), builtinSkins: [], apply: vi.fn(), applySkin: vi.fn(), pluginThemes: ref([]), pluginThemeId: ref(''), loadPluginThemes: vi.fn(), applyPluginTheme: vi.fn(), clearPluginTheme: vi.fn() }) }))
vi.mock('../src/composables/useBackgroundImages', () => ({ useBackgroundImages: () => ({ options: [], previews: {}, custom: {}, loading: ref(false), initialize: vi.fn(), setBackground: vi.fn(), resetBackground: vi.fn(), resetAllBackgrounds: vi.fn() }) }))
vi.mock('../src/composables/useProviderModelSettings', () => ({ useProviderModelSettings: () => ({
  providerDrafts: ref([]), providerTestModels: {}, providerTestModes: {}, providerSearch: ref(''), providerSaving: ref(false), providerTestingId: ref(''), providerFetchingModelsId: ref(''), providerTestedId: ref(''), providerTestedKind: ref(''), providerTestResult: ref(null), providerCatalogOpen: ref(false), activeProviderId: ref(''), activeCatalogProvider: ref(null), providerCatalogSourceModels: ref([]), providerLibrarySupported: true, providerSecretValue: vi.fn(() => ''), providerById: vi.fn(), providerMark: vi.fn(() => 'P'), providerStyle: vi.fn(() => ({})), providerDraftReady: vi.fn(() => false), providerModelCapabilityOptions: [], providerTestModeOptions: [], providerTestActionLabel: vi.fn(() => 'test'), activeProvider: ref(null), activeProviderModelGroups: ref([]), readyProviderIds: [], modelRoutingSaving: ref(false), catalogAssignmentBusy: '', catalogModelAssignmentOptions: vi.fn(() => []), catalogModelAssignmentValue: vi.fn(() => ''), catalogModelCanAssign: vi.fn(() => true), addProviderDraft: vi.fn(), fetchProviderModels: vi.fn(), toggleCatalogModel: vi.fn(), addAllCatalogModels: vi.fn(), assignCatalogModelRole: vi.fn(), openProviderCatalog: vi.fn(), saveProviderDraft: vi.fn(), removeProviderDraft: vi.fn(), testProviderDraft: vi.fn(),
}) }))
vi.mock('../src/utils/tts', async () => {
  const { ref } = await import('vue')
  return { initializeTts: vi.fn(), ttsRate: vi.fn(() => 1), setTtsRate: vi.fn(), ttsRuntimeConfig: ref({ provider: 'browser' }), speakingKey: ref(''), stripHtml: (value: string) => value, ttsSpeak: vi.fn(), ttsStop: vi.fn(), ttsSupported: vi.fn(() => true) }
})
vi.mock('../src/utils/asr', () => ({ asrLanguageFor: vi.fn(), initializeAsr: vi.fn(), startRecording: vi.fn(), serverAsrReady: vi.fn(() => false) }))
vi.mock('../src/api/client', () => ({ api: mocks.api, apiBlob: mocks.api, errorMessage: (e: unknown) => String(e), ApiError: class extends Error {} }))
vi.mock('../src/api/speech', () => ({ speechApi: { voices: vi.fn().mockResolvedValue({ voices: [] }), test: vi.fn(), transcribeTest: vi.fn() } }))
vi.mock('../src/api/plugins', () => ({ pluginApi: { hubPreferences: vi.fn().mockResolvedValue(null), updateHubPreferences: vi.fn(), deleteHubIdentity: vi.fn() } }))
vi.mock('../src/api/security', () => ({ securityApi: { status: vi.fn().mockResolvedValue({}), prepare: vi.fn(), activate: vi.fn(), disable: vi.fn(), regenerate: vi.fn() } }))

describe('SettingsView management navigation', () => {
  it('places a separate Game page directly after General', async () => {
    const wrapper = shallowMount(SettingsView, { global: { stubs: { Spin: { template: '<div><slot /></div>' }, RouterLink: true } } })
    await flushPromises()
    const general = wrapper.get('.settings-nav [data-section="general"]')
    expect(general.element.nextElementSibling?.getAttribute('data-section')).toBe('game')
    await wrapper.get('.settings-nav [data-section="game"]').trigger('click')
    expect(wrapper.get('.settings-game-pane').isVisible()).toBe(true)
    expect(wrapper.get('#settings-language').isVisible()).toBe(false)
    expect(mocks.replace).toHaveBeenCalledWith({ query: { section: 'game', focus: undefined } })
    wrapper.unmount()
  })
  beforeEach(() => {
    mocks.store.load.mockReset()
    mocks.api.mockClear()
  })

  it('lists an independent Agent token budget and includes it in the save request', async () => {
    const wrapper = shallowMount(SettingsView, { global: { stubs: { Spin: { template: '<div><slot /></div>' }, Button: { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] }, RouterLink: true } } })
    await flushPromises()
    expect(wrapper.findAll('.token-row strong').map(row => row.text())).toContain('assistantAgentTokens')
    const saveButton = wrapper.get('#settings-agent-budget .advanced-save-row > *')
    await saveButton.trigger('click')
    expect(mocks.store.saveSection).toHaveBeenCalledWith(expect.arrayContaining(['assistant_agent_max_tokens']), [])
    wrapper.unmount()
  })

  it('exposes the shared system language preference in general settings', async () => {
    const wrapper = shallowMount(SettingsView, { global: { stubs: { Spin: { template: '<div><slot /></div>' }, RouterLink: true } } })
    expect(wrapper.find('language-preferences-stub').exists()).toBe(true)
    wrapper.unmount()
  })

  it('selects a deep-linked section and keeps grouped navigation reachable', async () => {
    const wrapper = shallowMount(SettingsView, { global: { stubs: { ContentPageHeader: true, HelpButton: true, ProviderLibrary: true, ProviderCatalogModal: true, ModelRoutingPane: true, ProviderModelRow: true, ProviderTestSection: true, TestResultCard: true, TtsVoiceProfiles: true, BrandLogo: true } } })
    await flushPromises()
    expect(wrapper.find('.settings-nav-group-label').exists()).toBe(true)
    expect(wrapper.findAll('.settings-nav .nav-item').length).toBeGreaterThanOrEqual(9)
    expect(wrapper.find('.settings-nav .nav-item.active').text()).toContain('settingsSectionModels')
    await wrapper.findAll('.settings-nav .nav-item').find(button => button.text().includes('settingsSectionAppearance'))!.trigger('click')
    expect(mocks.replace).toHaveBeenCalledWith({ query: { section: 'appearance', focus: undefined } })
    expect(wrapper.find('.settings-nav .nav-item.active').text()).toContain('settingsSectionAppearance')
  })

  it('renders language, voice, Agent and maintenance together on one general page', async () => {
    const wrapper = shallowMount(SettingsView, { global: { stubs: { Spin: { template: '<div><slot /></div>' }, RouterLink: true } } })
    await flushPromises()
    await wrapper.get('.settings-nav [data-section="general"]').trigger('click')
    const pane = wrapper.get('#settings-language').element.closest('.settings-pane')!
    for (const id of ['settings-tts', 'settings-agent', 'settings-agent-budget', 'settings-runtime-logs', 'settings-test-timeout']) {
      expect(wrapper.get(`#${id}`).isVisible(), id).toBe(true)
      expect(wrapper.get(`#${id}`).element.closest('.settings-pane'), id).toBe(pane)
    }
    for (const id of ['voice', 'agent', 'system']) expect(wrapper.find(`.settings-nav [data-section="${id}"]`).exists()).toBe(false)
    expect(wrapper.findAll('.settings-nav-group-label').map(label => label.text())).toEqual(['Models and AI', 'Connection and integrations', 'Security and privacy', 'General'])
    wrapper.unmount()
  })

  it('keeps the status overview closed until the user opens it', async () => {
    const wrapper = shallowMount(SettingsView, { global: { stubs: { ContentPageHeader: true, HelpButton: true, ProviderLibrary: true, ProviderCatalogModal: true, ModelRoutingPane: true, ProviderModelRow: true, ProviderTestSection: true, TestResultCard: true, TtsVoiceProfiles: true, BrandLogo: true } } })
    await flushPromises()
    const details = wrapper.find('.settings-status-disclosure')
    expect(details.attributes('open')).toBeUndefined()
    await details.find('summary').trigger('click')
    expect(details.attributes('open')).toBeDefined()
  })
})
