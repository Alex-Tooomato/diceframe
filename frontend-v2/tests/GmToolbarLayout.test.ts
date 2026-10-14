import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const panelStyles = readFileSync(
  join(process.cwd(), 'src/styles/v2/play-panels.css'),
  'utf8',
)
describe('GM toolbar layout contract', () => {
  it('keeps the flow controls in two columns in the desktop control rail', () => {
    expect(panelStyles).toMatch(
      /\.play-control-rail \.gm-toolbar \.gm-flow-group[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    )
    expect(panelStyles).toContain('minmax(300px, 320px)')
    expect(panelStyles).toContain('grid-template-areas: "main controls"')
  })
})
