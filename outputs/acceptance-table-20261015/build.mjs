import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const out=path.dirname(fileURLToPath(import.meta.url));
const html=await fs.readFile(path.join(out,'../项目管理系统验收标准-2026-10-15.html'),'utf8');
const data=JSON.parse(html.match(/^const DATA = (.+);\r?$/m)[1]);
if(data.cases.length!==60 || new Set(data.cases.map(x=>x.id)).size!==60) throw Error('Source count');
const wb=Workbook.create(), s=wb.worksheets.add('验收总览'), d=wb.worksheets.add('验收清单');
const navy='#20334D', ink='#23344A', muted='#65758B', amber='#FFF4CF', line='#DCE3EC';
const baseline={history:'历史有记录',gap:'已知待修',proposed:'拟定改版目标',unverified:'本次待核验'};
const sourceFiles={
 '规则与权限口径':'PROJECT_LIFECYCLE_AND_PERMISSIONS.md',
 '2026-10-12 本地立项验收':'2026-10-12-project-initiation-continuity.md',
 '推进表优化建议':'2026-10-12-work-progress-optimization-review.md',
 '2026-10-12 立项前端视觉验收（仅立项子范围）':'2026-10-12-initiation-visual-redesign.md',
 '完整优化路径与会议分析记录':'系统完整优化路径清单-2026-10-08.md',
 '当前 bundle-baseline.json；体验计时为本文件建议':'bundle-baseline.json'
};
for(const sh of [s,d]) {sh.showGridLines=false; sh.tabColor=sh===s?navy:'#7188A6';}
s.getRange('A1:L40').format.font={name:'Arial',size:11,color:ink};
s.getRange('A1:L40').format.rowHeight=25;
s.getRange('A1:L40').format.verticalAlignment='center';
const sw=[26,26,13,13,13,13,14,14,14,15,14,15];
sw.forEach((w,i)=>s.getRangeByIndexes(0,i,40,1).format.columnWidth=w);
s.getRange('A2').values=[['项目管理系统验收标准']];s.getRange('A2').format.font={size:16,bold:true,color:navy};
s.getRange('A3:L3').format.borders={bottom:{style:'thin',color:navy}};
s.getRange('A4').values=[['标准日期：2026-10-15。先在清单中填写本次结果与证据，再查看本页汇总。']];
s.getRange('A4').format.font={color:muted,size:11};
const meta=[['验收批次 / 项目',null],['环境 / 地址',null],['版本 / 快照标识',null],['验收负责人',null],['验收日期',null],['角色账号 / 样例 ID',null]];
s.getRange('A6:B11').values=meta;s.getRange('B6:B11').format.fill=amber;
s.getRange('B10').setNumberFormat('yyyy-mm-dd');
s.getRange('D6').values=[['填写说明']];s.getRange('D6').format.font={bold:true,color:navy};
const instructions=[
 '黄色区域为填写项。清单中可筛选模块、优先级、结果与历史标识。',
 '填写截图、日志或录像位置及对象 ID；仅选择“通过”不会计入有效通过。',
 '本批范围在下方选择。筛选清单不会改变汇总范围。',
 '历史有记录仅表示既往局部验证，本次全部从“未验收”开始。',
 '账号记录人员标识即可，勿填写密码。长版本标识可在单元格内换行。'
];
instructions.forEach((t,i)=>s.getRange(`D${7+i}`).values=[[t]]);
s.getRange('B6:B11').format.wrapText=true;s.getRange('A6:B11').format.rowHeight=32;
s.getRange('A13').values=[['本批验收判定']];s.getRange('A13').format.font={bold:true,color:navy};
s.getRange('B13').format.font={bold:true,color:navy};
s.getRange('A14').values=[['仅适用于本批纳入范围、环境与版本；具备条件后由验收负责人确认签收。']];s.getRange('A14').format.font={color:muted};
const sumHeads=['验收模块','本批范围','条目数','有效通过','未验收','不通过','阻塞','通过缺证据','P0 总数','P0 未完成','P0 阻断','有效通过率'];
s.getRange('A16:L16').values=[sumHeads];
const rr=(col)=>`'验收清单'!$${col}$7:$${col}$66`;
for(let i=0;i<8;i++){
 const r=17+i,m=data.modules[i];
 s.getRange(`A${r}:B${r}`).values=[[m.title,'纳入']];
 const cc=(status)=>`COUNTIFS(${rr('B')},$A${r},${rr('E')},"${status}")`;
 const f=[`=COUNTIFS(${rr('B')},$A${r})`,`=COUNTIFS(${rr('B')},$A${r},${rr('R')},"计入通过")`,`=${cc('未验收')}`,`=${cc('不通过')}`,`=${cc('阻塞')}`,`=COUNTIFS(${rr('B')},$A${r},${rr('R')},"待补证据")`,`=COUNTIFS(${rr('B')},$A${r},${rr('C')},"P0")`,`=I${r}-COUNTIFS(${rr('B')},$A${r},${rr('C')},"P0",${rr('R')},"计入通过")`,`=COUNTIFS(${rr('B')},$A${r},${rr('C')},"P0",${rr('E')},"不通过")+COUNTIFS(${rr('B')},$A${r},${rr('C')},"P0",${rr('E')},"阻塞")`,`=IF(C${r}=0,0,D${r}/C${r})`];
 s.getRange(`C${r}:L${r}`).formulas=[f];
}
s.getRange('A25').values=[['本批纳入合计']];
// Row 24 is the last module, so totals live on row 25.
for(let i=2;i<11;i++) {const col=String.fromCharCode(65+i);s.getRange(`${col}25`).formulas=[[`=SUMIFS(${col}17:${col}24,$B$17:$B$24,"纳入")`]];}
s.getRange('L25').formulas=[['=IF(C25=0,0,D25/C25)']];
s.getRange('B13').formulas=[['=IF(C25=0,"请选择验收范围",IF(K25>0,"不通过：P0 阻断",IF(F25>0,"待整改",IF(G25>0,"待解除阻塞",IF(D25=C25,IF(OR(LEN(TRIM(B6))=0,LEN(TRIM(B7))=0,LEN(TRIM(B8))=0,LEN(TRIM(B9))=0,NOT(ISNUMBER(B10))),"条目通过，待补批次信息","具备本批签收条件"),"验收进行中")))))']];
s.getRange('B17:B24').dataValidation={rule:{type:'list',values:['纳入','不纳入']}};
s.getRange('B17:B24').format.fill=amber;
s.getRange('L17:L25').setNumberFormat('0%');s.getRange('C17:K25').setNumberFormat('0');
s.getRange('A16:L16').format={fill:navy,font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:34};
s.getRange('A25:L25').format.fill='#E8EDF4';s.getRange('A25:L25').format.font={bold:true};
s.getRange('C17:L25').format.horizontalAlignment='right';
s.getRange('A17:L25').format.borders={insideHorizontal:{style:'thin',color:line}};
s.getRange('A28').values=[['统计口径']];s.getRange('A28').format.font={bold:true,color:navy};
const notes=[
 '有效通过：本次结果为“通过”，且“实际结果与证据”有非空内容。证据真实性仍需验收人核对。',
 'P0 未完成：未验收、不通过、阻塞，以及已选通过但缺少证据的 P0 条目。该数量不等于缺陷数。',
 'P0 阻断：本次结果为“不通过”或“阻塞”的 P0 条目。出现任意一项，本批不能签收。',
 '拟定改版目标需要实现后逐条复验；“已知待修”和“历史有记录”均不代表本次通过。',
 '完整标准、操作步骤与来源均保留在“验收清单”。标准日期与来源沿用已交付 HTML。'
];notes.forEach((t,i)=>s.getRange(`A${29+i}`).values=[[t]]);
s.getRange('A35').values=[['签收结论（人工填写）']];s.getRange('B35').format.fill=amber;
s.getRange('B35').dataValidation={rule:{type:'list',values:['未签收','通过','不通过']}};s.getRange('B35').values=[['未签收']];
s.getRange('A36').values=[['签收人 / 日期']];s.getRange('B36').format.fill=amber;

const names=Object.fromEntries(data.modules.map(x=>[x.id,x.title]));
const head=['编号','模块','优先级','验收事项','本次结果','实际结果与证据','执行人','验收日期','整改与复测跟进','执行角色','准备条件','操作步骤','通过条件','证据要求','历史标识','标准类型','依据','证据判定'];
d.getRange('A1:R66').format.font={name:'Arial',size:11,color:ink};
d.getRange('A2').values=[['项目管理系统验收清单']];d.getRange('A2').format.font={size:16,bold:true,color:navy};
d.getRange('A3').values=[['标准日期：2026-10-15。黄色列填写本次结果、证据、执行人和跟进信息。共 60 项，全部初始为未验收。']];
d.getRange('A4').values=[['来源：项目管理系统验收标准-2026-10-15.html。历史标识不作为本次验收结论，证据判定自动计算。']];
d.getRange('A3:R4').format.font={color:muted,size:11};
d.getRange('A6:R6').values=[head];
const numbered=a=>a.map((x,i)=>`${i+1}. ${x}`).join('\n');
d.getRange('A7:R66').values=data.cases.map(c=>[c.id,names[c.module],c.priority,c.title,'未验收',null,null,null,null,c.role,c.pre,numbered(c.steps),numbered(c.expected),c.evidence,baseline[c.baseline],c.kind,c.source+'\n'+sourceFiles[c.source],null]);
const table=d.tables.add('A6:R66',true,'AcceptanceRegister');table.showFilterButton=true;
d.getRange('R7:R66').formulas=data.cases.map((c,i)=>{const r=7+i;return [`=IF(E${r}="通过",IF(LEN(TRIM(F${r}))>0,"计入通过","待补证据"),"未通过")`];});
const widths=[9,18,10,31,14,46,15,15,40,26,45,52,56,48,20,27,46,17];
widths.forEach((w,i)=>d.getRangeByIndexes(0,i,66,1).format.columnWidth=w);
d.getRange('A7:R66').format.wrapText=true;d.getRange('A7:R66').format.verticalAlignment='top';
d.getRange('A7:R66').format.fill='#FFFFFF';
d.getRange('E7:I66').format.fill=amber;d.getRange('H7:H66').setNumberFormat('yyyy-mm-dd');
d.getRange('E7:E66').dataValidation={rule:{type:'list',values:['未验收','通过','不通过','阻塞']}};
d.getRange('A6:R6').format={fill:navy,font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:34,horizontalAlignment:'center',verticalAlignment:'center',wrapText:true};
function lines(t,w){return String(t??'').split('\n').reduce((n,line)=>n+Math.max(1,Math.ceil([...line].reduce((a,c)=>a+(c.charCodeAt(0)>255?2:1),0)/(w-2))),0);}
data.cases.forEach((c,i)=>{const vals=[c.title,c.role,c.pre,numbered(c.steps),numbered(c.expected),c.evidence,c.source]; const ws=[31,26,45,52,56,48,46]; const n=Math.max(...vals.map((v,j)=>lines(v,ws[j])));d.getRange(`A${i+7}:R${i+7}`).format.rowHeight=Math.max(94,n*17+16);});
d.freezePanes.freezeRows(6);d.freezePanes.freezeColumns(4);
for(const [text,color,fill] of [['不通过','#9C2525','#FDE8E8'],['阻塞','#995713','#FFF0DB'],['通过','#17664C','#E4F3EC']])d.getRange('E7:E66').conditionalFormats.addCustom(`$E7="${text}"`,{fill,font:{color,bold:true}});
d.getRange('R7:R66').conditionalFormats.addCustom('$R7="待补证据"',{fill:'#FFF0DB',font:{color:'#995713',bold:true}});
d.getRange('O7:O66').conditionalFormats.addCustom('$O7="已知待修"',{fill:'#FDE8E8',font:{color:'#9C2525'}});
d.getRange('C7:C66').conditionalFormats.addCustom('$C7="P0"',{font:{bold:true,color:'#9C2525'}});
s.getRange('F17:H25').conditionalFormats.addCustom('F17>0',{font:{color:'#9C2525',bold:true}});
s.getRange('J17:K25').conditionalFormats.addCustom('J17>0',{font:{color:'#9C2525',bold:true}});

// Check workflow calculations with temporary edits; restore all test inputs.
wb.recalculate();
function eq(cell,value){const got=s.getRange(cell).values[0][0];if(got!==value)throw Error(`${cell}: ${JSON.stringify(got)} != ${JSON.stringify(value)}`);}
eq('C25',60);eq('D25',0);eq('E25',60);eq('I25',41);eq('J25',41);eq('K25',0);
d.getRange('E7').values=[['通过']];eq('H25',1);eq('D25',0);
d.getRange('F7').values=[['   ']];eq('H25',1);
d.getRange('F7').values=[['项目 1，截图 A01，已核对实际结果']];eq('D25',1);eq('J25',40);
d.getRange('E7').values=[['不通过']];eq('K25',1);eq('B13','不通过：P0 阻断');
s.getRange('B17').values=[['不纳入']];eq('C25',54);eq('K25',0);
s.getRange('B17').values=[['纳入']];d.getRange('E7').values=[['未验收']];d.getRange('F7').values=[[null]];
d.getRange('E7:E66').values=[['通过']];d.getRange('F7:F66').values=[['验证样例证据']];eq('D25',60);eq('B13','条目通过，待补批次信息');
s.getRange('B6:B9').values=[['测试批次']];s.getRange('B10').values=[[new Date('2026-10-15T00:00:00Z')]];eq('B13','具备本批签收条件');
s.getRange('B6').values=[['   ']];eq('B13','条目通过，待补批次信息');
s.getRange('B17:B24').values=[['不纳入']];eq('C25',0);eq('B13','请选择验收范围');s.getRange('B17:B24').values=[['纳入']];
s.getRange('B6:B10').values=[[null]];d.getRange('E7:E66').values=[['未验收']];d.getRange('F7:F66').values=[[null]];
wb.recalculate();eq('E25',60);eq('D25',0);eq('B13','验收进行中');
console.log((await wb.inspect({kind:'table',range:'验收总览!A25:L25',include:'values,formulas',tableMaxRows:1,tableMaxCols:12,maxChars:4000})).ndjson);
const err=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'formula error scan'});console.log(err.ndjson);
for(const [sheetName,range,name] of [['验收总览','A1:L36','总览预览'],['验收清单','A6:I10','填写区预览'],['验收清单','J6:R8','标准区预览']]){
 const img=await wb.render({sheetName,range,scale:1.3,format:'png'});await fs.writeFile(path.join(out,`${name}.png`),new Uint8Array(await img.arrayBuffer()));
}
const target=path.join(out,'项目管理系统验收标准-表格版-2026-10-15.xlsx');await(await SpreadsheetFile.exportXlsx(wb)).save(target);
console.log(JSON.stringify({output:target,cases:data.cases.length,p0:data.cases.filter(x=>x.priority==='P0').length,checks:'input-change, evidence, priority, scope and signoff checks passed'}));
