import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

import { analyzeBundle } from '../scripts/check-bundle-baseline.mjs'

function writeJson(path, value) {
  writeFileSync(path, JSON.stringify(value), 'utf8')
}

function createFixture({ excelIsInitial = false, includeExcel = true } = {}) {
  const root = mkdtempSync(join(tmpdir(), 'moways-bundle-baseline-'))
  const distDir = join(root, 'dist')
  const assetsDir = join(distDir, 'assets')
  const manifestDir = join(distDir, '.vite')
  mkdirSync(assetsDir, { recursive: true })
  mkdirSync(manifestDir, { recursive: true })

  writeFileSync(join(assetsDir, 'index-a.js'), 'entry', 'utf8')
  writeFileSync(join(assetsDir, 'vendor-a.js'), 'vendor', 'utf8')
  writeFileSync(join(assetsDir, 'index-a.css'), 'css', 'utf8')
  writeFileSync(join(assetsDir, 'MeetingPage-a.js'), 'route', 'utf8')
  if (includeExcel) {
    writeFileSync(join(assetsDir, 'exceljs.min-a.js'), 'excel', 'utf8')
  }

  const manifest = {
    'src/main.tsx': {
      file: 'assets/index-a.js',
      isEntry: true,
      imports: ['node_modules/vendor.js', ...(excelIsInitial ? ['node_modules/exceljs/dist/exceljs.min.js'] : [])],
      dynamicImports: excelIsInitial ? [] : ['node_modules/exceljs/dist/exceljs.min.js'],
      css: ['assets/index-a.css'],
    },
    'node_modules/vendor.js': { file: 'assets/vendor-a.js' },
    'src/pages/MeetingPage.tsx': { file: 'assets/MeetingPage-a.js' },
  }
  if (includeExcel) {
    manifest['node_modules/exceljs/dist/exceljs.min.js'] = {
      file: 'assets/exceljs.min-a.js',
    }
  }
  writeJson(join(manifestDir, 'manifest.json'), manifest)

  const baselinePath = join(root, 'baseline.json')
  writeJson(baselinePath, {
    initial_js: { raw_bytes: 100, gzip_bytes: 100 },
    initial_css: { raw_bytes: 100, gzip_bytes: 100 },
    largest_route_js: { raw_bytes: 100, gzip_bytes: 100 },
    exceljs_dynamic_js: { raw_bytes: 100, gzip_bytes: 100 },
  })
  return { root, distDir, baselinePath }
}

test('analyzes the static entry closure without loading dynamic ExcelJS', (t) => {
  const fixture = createFixture()
  t.after(() => rmSync(fixture.root, { recursive: true, force: true }))

  const report = analyzeBundle(fixture)

  assert.deepEqual(report.initial.files, ['assets/index-a.js', 'assets/vendor-a.js'])
  assert.equal(report.initial.js.rawBytes, 10)
  assert.equal(report.initial.css.rawBytes, 3)
  assert.equal(report.exceljs.file, 'assets/exceljs.min-a.js')
  assert.equal(report.exceljs.isInitial, false)
})

test('rejects an initial JavaScript budget regression', (t) => {
  const fixture = createFixture()
  t.after(() => rmSync(fixture.root, { recursive: true, force: true }))
  const tinyInitialBudget = join(fixture.root, 'tiny-initial.json')
  writeJson(tinyInitialBudget, {
    initial_js: { raw_bytes: 9, gzip_bytes: 100 },
    initial_css: { raw_bytes: 100, gzip_bytes: 100 },
    largest_route_js: { raw_bytes: 100, gzip_bytes: 100 },
    exceljs_dynamic_js: { raw_bytes: 100, gzip_bytes: 100 },
  })

  assert.throws(
    () => analyzeBundle({ ...fixture, baselinePath: tinyInitialBudget }),
    /initial_js raw bytes 10 exceed budget 9/,
  )
})

test('rejects ExcelJS when a static entry import pulls it into the initial closure', (t) => {
  const fixture = createFixture({ excelIsInitial: true })
  t.after(() => rmSync(fixture.root, { recursive: true, force: true }))

  assert.throws(
    () => analyzeBundle(fixture),
    /exceljs dynamic chunk is part of the initial entry closure/,
  )
})

test('rejects a manifest without the ExcelJS dynamic chunk', (t) => {
  const fixture = createFixture({ includeExcel: false })
  t.after(() => rmSync(fixture.root, { recursive: true, force: true }))

  assert.throws(
    () => analyzeBundle(fixture),
    /exceljs dynamic chunk is missing from the manifest/,
  )
})
