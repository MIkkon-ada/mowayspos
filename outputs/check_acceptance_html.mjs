import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

const root=path.resolve(import.meta.dirname,'..')
const require=createRequire(path.join(root,'frontend-v2/package.json'))
const {JSDOM,VirtualConsole}=require('jsdom')
const html=fs.readFileSync(path.join(root,'outputs/项目管理系统验收标准-2026-10-15.html'),'utf8')
const errors=[]
function boot(content,saved){
 const blobs=[]
 const virtualConsole=new VirtualConsole();virtualConsole.on('jsdomError',error=>errors.push(error.message))
 const dom=new JSDOM(content,{url:'http://127.0.0.1/acceptance.html',runScripts:'dangerously',virtualConsole,beforeParse(window){
  window.Blob=Blob;window.URL.createObjectURL=blob=>{blobs.push(blob);return 'blob:checked'};window.URL.revokeObjectURL=()=>{};
  window.HTMLElement.prototype.scrollIntoView=function(){};window.HTMLAnchorElement.prototype.click=function(){};window.print=()=>{};
  if(saved)window.localStorage.setItem('moways-acceptance-v1-2026-10-15',saved)
 }});return{dom,window:dom.window,document:dom.window.document,blobs}
}
const check=boot(html);let {window:w,document:d}=check
const change=(el,value,type='change')=>{el.value=value;el.dispatchEvent(new w.Event(type,{bubbles:true}))}
assert.equal(d.querySelectorAll('[data-case]').length,60)
assert.equal(d.querySelectorAll('[data-section]').length,8)
assert.equal(new Set([...d.querySelectorAll('[id]')].map(x=>x.id)).size,d.querySelectorAll('[id]').length)
assert.equal(d.getElementById('passedCount').textContent,'0')
assert.equal(d.getElementById('pendingCount').textContent,'60')
assert.ok([...d.querySelectorAll('[data-result]')].every(x=>x.value==='untested'))
change(d.querySelector('[data-result="B01"]'),'passed')
assert.equal(d.getElementById('passedCount').textContent,'0')
assert.match(d.getElementById('missing-B01').textContent,/待补证据/)
change(d.querySelector('[data-note="B01"]'),'项目 ID 2，草稿保存并刷新恢复；证据：截图 B01.png','input')
assert.equal(d.getElementById('passedCount').textContent,'1')
change(d.querySelector('[data-result="C06"]'),'failed')
assert.match(d.getElementById('gateTitle').textContent,/P0 阻断/)
change(d.getElementById('statusFilter'),'known')
assert.equal(d.querySelectorAll('.case:not(.filtered-out):not(.out-of-scope)').length,3)
assert.equal(d.getElementById('totalCount').textContent,'60')
for(const input of d.querySelectorAll('[data-scope]')){input.checked=input.dataset.scope==='B';input.dispatchEvent(new w.Event('change',{bubbles:true}))}
assert.equal(d.getElementById('totalCount').textContent,'12')
assert.doesNotMatch(d.getElementById('gateTitle').textContent,/P0 阻断/)
for(const select of d.querySelectorAll('[data-result]'))if(select.dataset.result.startsWith('B')){
 change(select,'passed');change(d.querySelector(`[data-note="${select.dataset.result}"]`),'实测通过；截图与对象 ID 记录在本批目录。','input')
}
assert.match(d.getElementById('gateTitle').textContent,/待补批次/)
for(const [key,value] of Object.entries({batch:'本地立项验收',version:'isolated-test-snapshot',tester:'验收测试',date:'2026-10-15'}))change(d.querySelector(`[data-meta="${key}"]`),value,'input')
assert.equal(d.getElementById('passedCount').textContent,'12')
assert.match(d.getElementById('gateTitle').textContent,/具备本批签收条件/)
d.getElementById('jsonBtn').click()
const saved=w.localStorage.getItem('moways-acceptance-v1-2026-10-15')
const reloaded=boot(html,saved)
assert.equal(reloaded.document.getElementById('passedCount').textContent,'12')
assert.equal(reloaded.document.querySelector('[data-meta="tester"]').value,'验收测试')
const hostile='证据字符串 </script><img src=x onerror="alert(1)"> <中文 & 标点>'
change(d.querySelector('[data-note="B01"]'),hostile,'input')
assert.equal(d.querySelectorAll('img').length,0)
d.getElementById('htmlBtn').click()
const exported=await check.blobs.at(-1).text()
assert.ok(!exported.includes('</script><img'))
const restored=boot(exported)
assert.equal(restored.document.querySelector('[data-note="B01"]').value,hostile)
assert.equal(restored.document.getElementById('passedCount').textContent,'12')
assert.equal(restored.document.querySelectorAll('img').length,0)
const payload=JSON.parse(await check.blobs[0].text())
assert.equal(payload.scope.join(''),'B');assert.equal(payload.summary.total,12)
d.getElementById('expandBtn').click()
assert.ok([...d.querySelectorAll('.case details')].every(x=>!x.open))
w.dispatchEvent(new w.Event('beforeprint'));assert.ok([...d.querySelectorAll('.case details')].every(x=>x.open))
w.dispatchEvent(new w.Event('afterprint'));assert.ok([...d.querySelectorAll('.case details')].every(x=>!x.open))
assert.equal(errors.length,0,errors.join('\n'))
assert.ok(!/<script[^>]+src=|<link[^>]+stylesheet/i.test(html))
assert.equal(d.querySelectorAll('[data-case] a.source-link').length,60)
for(const a of d.querySelectorAll('a.source-link'))assert.ok(fs.existsSync(path.resolve(root,'outputs',decodeURI(a.getAttribute('href')))))
for(const item of [check,reloaded,restored])item.window.close()
console.log('PASS: 60 criteria, 8 modules; default untested, evidence gating, P0 blocking, scope/filter isolation, storage restore, JSON/HTML round trip, escaped input, print restore, offline assets and source links.')
