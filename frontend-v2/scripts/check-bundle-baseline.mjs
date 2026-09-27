import { readFileSync, statSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import { dirname, isAbsolute, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const excelChunkPattern = /^assets\/exceljs\.min-.*\.js$/

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

function fileSizeReport(distDir, file) {
  const contents = readFileSync(join(distDir, file))
  return {
    file,
    rawBytes: statSync(join(distDir, file)).size,
    gzipBytes: gzipSync(contents).length,
  }
}

function totalSize(files) {
  return files.reduce(
    (total, file) => ({
      rawBytes: total.rawBytes + file.rawBytes,
      gzipBytes: total.gzipBytes + file.gzipBytes,
    }),
    { rawBytes: 0, gzipBytes: 0 },
  )
}

function requireBudget(name, actual, budget) {
  if (actual.rawBytes > budget.raw_bytes) {
    throw new Error(`${name} raw bytes ${actual.rawBytes} exceed budget ${budget.raw_bytes}`)
  }
  if (actual.gzipBytes > budget.gzip_bytes) {
    throw new Error(`${name} gzip bytes ${actual.gzipBytes} exceed budget ${budget.gzip_bytes}`)
  }
}

function resolvePath(value, fallback) {
  return value ? (isAbsolute(value) ? value : resolve(projectRoot, value)) : fallback
}

export function analyzeBundle({ distDir, baselinePath } = {}) {
  const resolvedDistDir = resolvePath(distDir, join(projectRoot, 'dist'))
  const resolvedBaselinePath = resolvePath(baselinePath, join(projectRoot, 'performance', 'bundle-baseline.json'))
  const manifest = readJson(join(resolvedDistDir, '.vite', 'manifest.json'))
  const baseline = readJson(resolvedBaselinePath)
  const entryModules = Object.entries(manifest).filter(([, chunk]) => chunk.isEntry)
  if (entryModules.length !== 1) {
    throw new Error(`manifest must contain exactly one application entry; found ${entryModules.length}`)
  }
  const [entryModule] = entryModules[0]

  const visited = new Set()
  const initialJavaScriptFiles = new Set()
  const initialCssFiles = new Set()
  const visitStaticImports = (moduleId) => {
    if (visited.has(moduleId)) return
    visited.add(moduleId)
    const chunk = manifest[moduleId]
    if (!chunk) {
      throw new Error(`manifest static import ${moduleId} is missing`)
    }
    if (chunk.file?.endsWith('.js')) initialJavaScriptFiles.add(chunk.file)
    for (const cssFile of chunk.css ?? []) initialCssFiles.add(cssFile)
    for (const importedModule of chunk.imports ?? []) visitStaticImports(importedModule)
  }
  visitStaticImports(entryModule)

  const initialJs = [...initialJavaScriptFiles].sort().map((file) => fileSizeReport(resolvedDistDir, file))
  const initialCss = [...initialCssFiles].sort().map((file) => fileSizeReport(resolvedDistDir, file))
  const excelChunks = Object.values(manifest)
    .filter((chunk) => excelChunkPattern.test(chunk.file ?? ''))
    .map((chunk) => fileSizeReport(resolvedDistDir, chunk.file))
  if (excelChunks.length !== 1) {
    throw new Error('exceljs dynamic chunk is missing from the manifest')
  }
  const exceljs = excelChunks[0]
  const excelIsInitial = initialJavaScriptFiles.has(exceljs.file)
  if (excelIsInitial) {
    throw new Error('exceljs dynamic chunk is part of the initial entry closure')
  }

  const initial = {
    files: initialJs.map(({ file }) => file),
    js: totalSize(initialJs),
    css: totalSize(initialCss),
  }
  const routeChunks = Object.entries(manifest)
    .filter(([moduleId, chunk]) => moduleId.startsWith('src/pages/') && chunk.file?.endsWith('.js'))
    .filter(([, chunk]) => !initialJavaScriptFiles.has(chunk.file))
    .map(([, chunk]) => fileSizeReport(resolvedDistDir, chunk.file))
    .sort((left, right) => right.rawBytes - left.rawBytes)
  const largestRoute = routeChunks[0] ?? { file: null, rawBytes: 0, gzipBytes: 0 }

  requireBudget('initial_js', initial.js, baseline.initial_js)
  requireBudget('initial_css', initial.css, baseline.initial_css)
  requireBudget('largest_route_js', largestRoute, baseline.largest_route_js)
  requireBudget('exceljs_dynamic_js', exceljs, baseline.exceljs_dynamic_js)

  return {
    initial,
    largestRoute,
    exceljs: { ...exceljs, isInitial: excelIsInitial },
  }
}

function main() {
  try {
    const report = analyzeBundle()
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
  } catch (error) {
    process.stderr.write(`bundle baseline failed: ${error.message}\n`)
    process.exitCode = 1
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main()
}
