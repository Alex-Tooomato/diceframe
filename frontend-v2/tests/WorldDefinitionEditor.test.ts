import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorldDefinitionEditor from '../src/features/worlds/WorldDefinitionEditor.vue'
import { i18n } from '../src/i18n'

const mocks = vi.hoisted(() => ({ api: vi.fn() }))
vi.mock('../src/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../src/api/client')>()
  return { ...actual, api: mocks.api, errorMessage: (cause: unknown) => String((cause as Error)?.message || cause) }
})

function definition(worldId: string, source: 'builtin' | 'user' = 'user', editable = source === 'user') {
  return {
    ok: true,
    world: {
      world_id: worldId,
      world_name: worldId === 'w1' ? '我的世界' : '第二世界',
      description: '简短介绍',
      world_setting: `完整背景 ${worldId}`,
      starter_scene: `默认开场 ${worldId}`,
      language: 'zh-CN',
      source,
      editable,
    },
  }
}

describe('WorldDefinitionEditor', () => {
  beforeEach(() => {
    mocks.api.mockReset()
    mocks.api.mockImplementation(async (path: string) => {
      const id = String(path).match(/\/worlds\/([^/]+)\/definition/)?.[1] || 'w1'
      return definition(id)
    })
  })

  it('loads and persists all independent world fields', async () => {
    const wrapper = mount(WorldDefinitionEditor, {
      props: { worldId: 'w1', mode: 'edit', initialName: '我的世界' },
      global: { plugins: [i18n] },
    })
    await flushPromises()
    await wrapper.get('.world-metadata-editor input').setValue('改名世界')
    await wrapper.get('.world-metadata-editor textarea').setValue('新的简短介绍')
    await wrapper.get('[data-testid="world-setting"]').setValue('新的完整背景')
    await wrapper.get('[data-testid="starter-scene"]').setValue('新的默认开场')
    await wrapper.get('.world-definition-actions button.primary').trigger('click')
    await flushPromises()

    const save = mocks.api.mock.calls.find(([, init]) => (init as RequestInit)?.method === 'PUT')
    expect(JSON.parse(String((save?.[1] as RequestInit).body))).toEqual({
      name: '改名世界', description: '新的简短介绍', language: 'zh-CN',
      world_setting: '新的完整背景', starter_scene: '新的默认开场',
    })
    expect(wrapper.emitted('saved')?.[0]?.[0]).toMatchObject({ worldId: 'w1' })
  })

  it('keeps builtin content read-only and clones from edit mode', async () => {
    mocks.api.mockImplementation(async (path: string, init?: RequestInit) => {
      if ((init?.method || 'GET') === 'POST') return { ok: true, world_id: 'copy-1', name: '复制世界', language: 'zh-CN' }
      return definition(String(path).match(/\/worlds\/([^/]+)\/definition/)?.[1] || 'builtin', 'builtin', false)
    })
    const wrapper = mount(WorldDefinitionEditor, {
      props: { worldId: 'builtin', mode: 'edit', source: 'builtin' },
      global: { plugins: [i18n] },
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="world-setting"]').attributes('readonly')).toBeDefined()
    await wrapper.get('.world-definition-actions .world-card-clone').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('cloned')?.[0]?.[0]).toMatchObject({ sourceWorldId: 'builtin', worldId: 'copy-1' })
  })

  it('ignores an old save after switching away and back to the same world', async () => {
    let finishSave!: (value: unknown) => void
    mocks.api.mockImplementation(async (path: string, init?: RequestInit) => {
      if (init?.method === 'PUT') return new Promise(resolve => { finishSave = resolve })
      return definition(String(path).match(/\/worlds\/([^/]+)\/definition/)?.[1] || 'w1')
    })
    const wrapper = mount(WorldDefinitionEditor, {
      props: { worldId: 'w1', mode: 'edit' }, global: { plugins: [i18n] },
    })
    await flushPromises()
    await wrapper.get('[data-testid="world-setting"]').setValue('提交中的草稿')
    await wrapper.get('.world-definition-actions button.primary').trigger('click')
    expect(wrapper.get('[data-testid="world-setting"]').attributes('readonly')).toBeDefined()
    await wrapper.setProps({ worldId: 'w2' })
    await flushPromises()
    await wrapper.setProps({ worldId: 'w1' })
    await flushPromises()
    finishSave({ ok: true })
    await flushPromises()
    expect(wrapper.emitted('saved')).toBeUndefined()
    expect(wrapper.get('[data-testid="world-setting"]').element).toHaveProperty('value', '完整背景 w1')
    expect(wrapper.get('.world-definition-actions button.primary').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('does not reopen a cloned world after the editor was closed', async () => {
    let finishClone!: (value: unknown) => void
    mocks.api.mockImplementation(async (path: string, init?: RequestInit) => {
      if (init?.method === 'POST') return new Promise(resolve => { finishClone = resolve })
      return definition(String(path).match(/\/worlds\/([^/]+)\/definition/)?.[1] || 'builtin', 'builtin', false)
    })
    const wrapper = mount(WorldDefinitionEditor, {
      props: { worldId: 'builtin', mode: 'edit' }, global: { plugins: [i18n] },
    })
    await flushPromises()
    await wrapper.get('.world-card-clone').trigger('click')
    wrapper.unmount()
    finishClone({ ok: true, world_id: 'own-copy' })
    await flushPromises()
    expect(wrapper.emitted('cloned')).toBeUndefined()
  })

  it('fences late requests when identity changes and blocks save after load errors', async () => {
    const pending = new Map<string, { resolve: (value: unknown) => void; reject: (cause: unknown) => void }>()
    mocks.api.mockImplementation((path: string) => {
      const id = String(path).match(/\/worlds\/([^/]+)\/definition/)?.[1] || ''
      return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
    })
    const wrapper = mount(WorldDefinitionEditor, {
      props: { worldId: 'w1', mode: 'edit', initialName: '我的世界' },
      global: { plugins: [i18n] },
    })
    await flushPromises()
    await wrapper.setProps({ worldId: 'w2', initialName: '第二世界' })
    pending.get('w1')?.resolve(definition('w1'))
    await flushPromises()
    expect(wrapper.find('[data-testid="world-setting"]').exists()).toBe(false)
    pending.get('w2')?.reject(new Error('definition unavailable'))
    await flushPromises()
    expect(wrapper.text()).toContain('definition unavailable')
    expect(wrapper.get('.world-definition-actions button.primary').attributes('disabled')).toBeDefined()
  })
})
