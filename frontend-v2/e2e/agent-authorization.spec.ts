import { expect, test } from './fixtures'

type Auth = { mode: 'suggest' | 'routine' | 'task'; scope: Record<string, string>; domains: string[]; expires_at: number; max_steps: number; remaining_steps: number }
const SESSION_ID = '0123456789abcdef0123456789abcdef'

const auth = (mode: Auth['mode'] = 'suggest'): Auth => ({ mode, scope: { game_key: 'game-e2e' }, domains: ['lorebook'], expires_at: 4102444800, max_steps: 32, remaining_steps: 32 })

async function openAssistant(page: import('@playwright/test').Page) {
  await page.goto('/#/overview?game=game-e2e')
  await page.getByTestId('assistant-shell-fab').click()
  await expect(page.getByTestId('agent-authorization')).toBeVisible()
}

test('Agent authorization restores server state, searches capabilities, and sends scoped grants', async ({ page }, info) => {
  const authorizationBodies: Record<string, unknown>[] = []
  const capabilityQueries: Array<{ q: string; domain: string }> = []
  await page.addInitScript(({ sessionId }) => {
    localStorage.setItem('diceframe_assistant_session_id', sessionId)
    localStorage.setItem('diceframe_assistant_messages', JSON.stringify([{ role: 'user', content: '恢复授权状态' }]))
    localStorage.setItem('diceframe_assistant_conversations', JSON.stringify({
      activeId: 'conversation-e2e',
      items: [{ id: 'conversation-e2e', title: 'Agent E2E', createdAt: 1, updatedAt: 1, sessionId, messages: [{ role: 'user', content: '恢复授权状态' }] }],
    }))
  }, { sessionId: SESSION_ID })
  await page.route('**/api/assistant/agent/session/**', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ ok: true, session_id: SESSION_ID, pending: null, drafts: {}, receipts: [], status: 'idle', authorization: auth('routine'), task: { status: 'running', completed_steps: 2, total_steps: 5 } }),
  }))
  await page.route('**/api/assistant/agent/capabilities*', route => {
    const url = new URL(route.request().url())
    capabilityQueries.push({ q: url.searchParams.get('q') || '', domain: url.searchParams.get('domain') || '' })
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, revision: 'r-e2e', total: 1, capabilities: [{ name: 'write_lorebook_entries', label: 'Write lorebook', domain: 'lorebook', version: 1, effect: 'write', automatic: false, description: 'Edit entries', requires_confirmation: true }] }) })
  })
  await page.route('**/api/assistant/agent/authorization*', async route => {
    authorizationBodies.push(route.request().postDataJSON())
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, session_id: SESSION_ID, authorization: auth('task') }) })
  })

  await openAssistant(page)
  const panel = page.getByTestId('agent-authorization')
  await expect(panel).toContainText('已授权')
  await expect(panel).toContainText('执行中')
  await panel.locator('button.agent-authorization-toggle').click()
  await panel.locator('details.agent-authorization-capabilities').click()
  const search = panel.locator('.agent-capability-filters input')
  await search.fill('lore')
  await panel.getByText('All', { exact: true }).click()
  await page.getByText('lorebook', { exact: true }).last().click()
  await expect(panel).toContainText('Write lorebook')
  await panel.locator('.agent-authorization-scope input[value="current"]').check()
  await panel.getByText('32', { exact: true }).click()
  await page.getByText('64', { exact: true }).last().click()
  const taskGrant = panel.locator('.agent-authorization-actions').getByRole('button', { name: '接管本次任务' })
  await expect(taskGrant).toBeEnabled()
  await taskGrant.click()
  await expect.poll(() => authorizationBodies.length).toBe(1)
  expect(authorizationBodies[0]).toMatchObject({ session_id: SESSION_ID, mode: 'task', scope: { game_key: 'game-e2e' }, max_steps: 64 })
  expect(capabilityQueries).toContainEqual({ q: 'lore', domain: 'lorebook' })
  await expect(panel).toContainText('接管本次任务')
  await page.screenshot({ path: info.outputPath('agent-authorization-desktop.png'), scale: 'css' })
})

test('Agent access grants and revocations reach the real owner service', async ({ page }) => {
  await openAssistant(page)
  const panel = page.getByTestId('agent-authorization')
  await panel.locator('button.agent-authorization-toggle').click()
  await panel.locator('.agent-authorization-scope input[value="all"]').check()
  const granted = page.waitForResponse(response => response.url().includes('/api/assistant/agent/authorization') && response.request().method() === 'POST')
  await panel.locator('.agent-authorization-actions').getByRole('button', { name: '接管本次任务' }).click()
  const response = await granted
  expect(response.ok()).toBeTruthy()
  const payload = await response.json()
  expect(payload.authorization).toMatchObject({ mode: 'task', scope: {}, remaining_steps: 32 })
  await expect(panel.locator('.agent-authorization-state').first()).toContainText('已授权')
  const revoked = page.waitForResponse(response => response.url().includes('/api/assistant/agent/authorization') && response.request().method() === 'POST')
  await panel.getByRole('button', { name: '撤回，改为建议' }).click()
  expect((await (await revoked).json()).authorization).toBeNull()
  await expect(panel.locator('.agent-authorization-state').first()).toHaveText('建议')
})

test('Agent authorization stays compact on mobile and clearly reports an unavailable capability endpoint', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', 'Mobile compact layout contract.')
  await page.route('**/api/assistant/agent/capabilities*', route => route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: 'HTTP_404' }) }))
  await page.route('**/api/assistant/agent/session/**', route => route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: 'HTTP_404' }) }))
  await openAssistant(page)
  const panel = page.getByTestId('agent-authorization')
  await panel.locator('button.agent-authorization-toggle').click()
  await panel.locator('details.agent-authorization-capabilities').click()
  await expect(panel).toContainText('HTTP_404')
  const box = await panel.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.width).toBeLessThanOrEqual((page.viewportSize()?.width || 390) + 1)
  await page.screenshot({ path: info.outputPath('agent-authorization-mobile.png'), scale: 'css' })
})
