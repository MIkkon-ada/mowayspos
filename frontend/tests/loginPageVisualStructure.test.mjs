import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = fs.readFileSync(path.join(frontendRoot, 'src/layouts/AppLayout.tsx'), 'utf8')
const css = fs.readFileSync(path.join(frontendRoot, 'src/styles.css'), 'utf8')

test('login page uses the seamless, text-free background asset', () => {
  assert.match(css, /login-background-v5\.png/)
  assert.ok(fs.existsSync(path.join(frontendRoot, 'public/login-background-v5.png')))
})

test('login page keeps form interactions and responsive form-only layout', () => {
  assert.match(source, /onSubmit=\{handleSubmit\}/)
  assert.match(source, /onClick=\{handleWecomLogin\}/)
  assert.match(source, /onClick=\{\(\) => setShowPassword/)
  assert.match(css, /@media \(max-width: 1180px\)[\s\S]*?\.login-brand-panel \{\s*display: none;/)
  assert.match(css, /@media \(max-width: 1180px\)[\s\S]*?\.login-bg \{\s*background-image: none;/)
})

test('login page defines the 1920px desktop composition', () => {
  assert.match(css, /\.login-body \{[\s\S]*?max-width: none;/)
  assert.match(css, /\.login-body \{[\s\S]*?grid-template-columns:\s*minmax\(0, 1\.5fr\) minmax\(400px, 1fr\);/)
  assert.match(css, /\.login-form-panel \{[\s\S]*?top: 13vh;[\s\S]*?right: 10vw;[\s\S]*?width: 29vw;/)
  assert.doesNotMatch(css, /\.login-card \{[\s\S]*?min-height:/)
  assert.match(css, /\.login-bg \{[\s\S]*?background-image:\s*url\('\/login-background-v5\.png'\)/)
  assert.match(css, /\.login-submit \{[\s\S]*?linear-gradient\(90deg,/)
  assert.match(source, /<h1 className="login-title-cn">项目管理协同平台<\/h1>/)
  assert.doesNotMatch(source, /login-hero\.png/)
})

test('desktop brand area pins the transparent official logo in the upper-left at a larger scale', () => {
  assert.match(source, /src="\/moways-logo-transparent\.png"/)
  assert.ok(fs.existsSync(path.join(frontendRoot, 'public/moways-logo-transparent.png')))
  assert.match(css, /\.login-brand-panel \{[\s\S]*?overflow:\s*visible;/)
  assert.match(css, /\.login-logo \{[\s\S]*?position:\s*relative;[\s\S]*?width:\s*260px;[\s\S]*?margin-left:\s*-112px;[\s\S]*?transform:\s*translateY\(-50px\);/)
  assert.doesNotMatch(css, /\.login-logo-img \{[\s\S]*?mix-blend-mode:/)
})

test('desktop brand content keeps its position while the background remains a single asset', () => {
  assert.match(css, /\.login-brand-content \{[\s\S]*?padding:\s*6vh 0 36px;/)
  assert.match(css, /\.login-bg \{[\s\S]*?background-position:\s*center;/)
  assert.match(css, /\.login-bg \{[\s\S]*?background-color:\s*#dcecff;/)
})
