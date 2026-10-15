import { expect, test } from './fixtures'
import { PLAY_READY_TIMEOUT } from './support'

test('desktop navigation keeps visible labels through intermediate widths', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop')
  await page.goto('/#/overview')
  const links = page.locator('.desktop-nav-link')
  await expect(links).toHaveCount(5)
  for (const language of ['zh-CN', 'en']) {
    await page.locator('.header-locale select').selectOption(language)
    for (const width of [801, 900, 980, 981, 1100, 1280]) {
      await page.setViewportSize({ width, height: 900 })
      for (const link of await links.all()) await expect(link.locator('span')).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth), `${language} at ${width}px`).toBeLessThanOrEqual(1)
      const lastLabel = (await links.last().locator('span').boundingBox())!
      const actions = (await page.locator('.app-header-actions').boundingBox())!
      expect(lastLabel.x + lastLabel.width).toBeLessThanOrEqual(actions.x)
    }
  }
})

test('play edge controls align and sidebar controls retain their meaning on resize', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/play?game=web%7Ce2e-dnd2024%7Cweb_bot')
  const left = page.getByTestId('play-character-toggle')
  const right = page.locator('.ruleset-context-tools button:visible')
  await expect(left).toBeVisible({ timeout: PLAY_READY_TIMEOUT })
  await expect(right.first()).toBeVisible()
  const bounds = (await left.boundingBox())!
  const tools = await right.evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect()
    return { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
  }))
  expect(tools.length).toBeGreaterThanOrEqual(1)
  expect(Math.abs(tools[0]!.y - bounds.y)).toBeLessThanOrEqual(1)
  for (const tool of tools) {
    expect(tool.height).toBe(bounds.height)
    expect(tool.width).toBe(bounds.width)
    expect(Math.abs(tool.x + tool.width - 390)).toBeLessThanOrEqual(1)
  }
  await page.screenshot({ path: info.outputPath('play-edge-controls.png') })
  await left.click()
  const close = page.locator('.game-sidebar .sidebar-toggle')
  await expect(close).toHaveAttribute('aria-label', '关闭')
  await close.click()
  await expect(left).toBeVisible()
  if (info.project.name === 'desktop') {
    for (const width of [801, 980, 1280]) {
      await page.setViewportSize({ width, height: 900 })
      await expect(close).toBeVisible()
      await expect(close).toHaveAttribute('aria-label', '收起侧栏')
      await close.click()
      await expect(page.locator('.game-sidebar')).toHaveClass(/collapsed/)
      await close.click()
      await expect(page.locator('.game-sidebar')).not.toHaveClass(/collapsed/)
    }
  }
})
