import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const clientApi = fs.readFileSync(path.join(root, 'src/api/client.ts'), 'utf8')

test('WeCom directory disabled errors explain the local configuration', () => {
  assert.match(clientApi, /wecom_directory_disabled/)
  assert.match(clientApi, /WECOM_CORPID/)
})
