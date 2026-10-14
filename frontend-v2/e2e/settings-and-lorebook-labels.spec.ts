import { expect, test } from './fixtures'
import { accessToken } from './support'

test('system language is shared and Agent has a separately saved token budget', async ({ page, request }, info) => {
  const baseline = await request.post('/api/config', {
    headers: { Authorization: `Bearer ${accessToken()}`, 'X-TRPG-Confirm': 'true' },
    data: { assistant_agent_max_tokens: 4096, text_gen_max_tokens: 4096 },
  })
  expect(baseline.ok()).toBe(true)
  await page.goto('/#/settings?section=appearance')
  const language = page.getByTestId('settings-system-language')
  await expect(language).toHaveValue('zh-CN')
  await language.selectOption('en')
  await expect(page.locator('.header-locale select')).toHaveValue('en')
  await page.reload()
  await expect(language).toHaveValue('en')
  await language.selectOption('zh-CN')
  await page.goto('/#/settings?section=advanced')
  const row = page.locator('.token-row').filter({ has: page.getByText('DF Agent Token', { exact: true }) })
  const input = row.locator('input')
  await expect(input).toHaveValue(/4,?096/)
  await input.fill('8192')
  await input.press('Tab')
  const saved = page.waitForResponse(response => response.url().endsWith('/api/config') && response.request().method() === 'POST')
  await page.locator('.generation-section').getByRole('button', { name: '保存', exact: true }).click()
  const response = await saved
  expect(response.ok()).toBe(true)
  expect(response.request().postDataJSON().assistant_agent_max_tokens).toBe(8192)
  await page.reload()
  await expect(row.locator('input')).toHaveValue(/8,?192/)
  await expect(page.locator('.token-row').filter({ has: page.getByText('文本生成 Token', { exact: true }) }).locator('input')).toHaveValue(/4,?096/)
  await row.scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('agent-token-settings.png'), scale: 'css' })
})

test('lorebook cards identify the actual book and its bound world', async ({ page }, info) => {
  await page.route('**/api/worlds', route => route.fulfill({ json: { worlds: [{ id: 'port', name: '港湾世界', language: 'zh-CN' }] } }))
  await page.route('**/api/lorebooks?scope=all', route => route.fulfill({ json: { books: [
    { id: 'primary:port', name: '港湾世界', language: 'zh-CN', entry_count: 12, bindings: [{ scope_kind: 'world', scope_id: 'port', role: 'primary' }] },
    { id: 'people:port', name: '港湾人物志', language: 'zh-CN', entry_count: 8, bindings: [{ scope_kind: 'world', scope_id: 'port' }] },
  ] } }))
  await page.goto('/#/library')
  await page.getByTestId('library-content-filter').selectOption('lorebook')
  const cards = page.getByTestId('library-lorebook')
  await expect(cards.first().getByRole('heading')).toHaveText('港湾世界 · 主资料册')
  await expect(cards.nth(1).getByRole('heading')).toHaveText('港湾人物志')
  await expect(cards.nth(1)).toContainText('所属世界：港湾世界')
  await expect(cards.nth(1).getByRole('link')).toHaveAttribute('href', /world=port.*book=people:port|book=people:port.*world=port/)
  await page.screenshot({ path: info.outputPath('lorebook-card-titles.png'), scale: 'css' })
})
