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
vi.mock('../src/utils/tts', () => ({ initializeTts: vi.fn(), ttsRate: vi.fn(() => 1), setTtsRate: vi.fn() }))
vi.mock('../src/utils/asr', () => ({ asrLanguageFor: vi.fn(), initializeAsr: vi.fn(), startRecording: vi.fn() }))
vi.mock('../src/api/client', () => ({ api: mocks.api, apiBlob: mocks.api, errorMessage: (e: unknown) => String(e), ApiError: class extends Error {} }))
vi.mock('../src/api/speech', () => ({ speechApi: { voices: vi.fn().mockResolvedValue({ voices: [] }), test: vi.fn(), transcribeTest: vi.fn() } }))
vi.mock('../src/api/plugins', () => ({ pluginApi: { hubPreferences: vi.fn().mockResolvedValue(null), updateHubPreferences: vi.fn(), deleteHubIdentity: vi.fn() } }))
vi.mock('../src/api/security', () => ({ securityApi: { status: vi.fn().mockResolvedValue({}), prepare: vi.fn(), activate: vi.fn(), disable: vi.fn(), regenerate: vi.fn() } }))

describe('SettingsView management navigation', () => {
  beforeEach(() => {
    mocks.store.load.mockReset()
    mocks.api.mockClear()
  })

  it('selects a deep-linked section and keeps grouped navigation reachable', async () => {
    const wrapper = shallowMount(SettingsView, { global: { stubs: { ContentPageHeader: true, HelpButton: true, ProviderLibrary: true, ProviderCatalogModal: true, ModelRoutingPane: true, ProviderModelRow: true, ProviderTestSection: true, TestResultCard: true, TtsVoiceProfiles: true, BrandLogo: true } } })
    await flushPromises()
    expect(wrapper.find('.settings-nav-group-label').exists()).toBe(true)
    expect(wrapper.findAll('.settings-nav .nav-item').length).toBeGreaterThanOrEqual(10)
    expect(wrapper.find('.settings-nav .nav-item.active').text()).toContain('settingsSectionModels')
    await wrapper.findAll('.settings-nav .nav-item').find(button => button.text().includes('settingsSectionAppearance'))!.trigger('click')
    expect(mocks.replace).toHaveBeenCalledWith({ query: { section: 'appearance', focus: undefined } })
    expect(wrapper.find('.settings-nav .nav-item.active').text()).toContain('settingsSectionAppearance')
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
