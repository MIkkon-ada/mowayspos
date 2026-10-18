from pathlib import Path
import zipfile, json, xml.etree.ElementTree as ET

root=Path(__file__).parent
target=root/'项目管理系统验收标准-表格版-2026-10-15.xlsx'
html=(root.parent/'项目管理系统验收标准-2026-10-15.html').read_text(encoding='utf-8')
data=json.JSONDecoder().raw_decode(html.split('const DATA = ',1)[1])[0]
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    strings=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
    def read_sheet(n):
        tree=ET.fromstring(z.read(f'xl/worksheets/sheet{n}.xml'))
        result={}
        for c in tree.findall('.//s:sheetData/s:row/s:c',ns):
            t=c.get('t'); v=c.find('s:v',ns)
            if t=='s': value=strings[int(v.text)]
            elif t=='inlineStr': value=''.join(c.find('s:is',ns).itertext())
            else: value=None if v is None else v.text
            result[c.get('r')]=value
        return tree,result
    overview,ov=read_sheet(1)
    detail,dt=read_sheet(2)
    for row,c in enumerate(data['cases'],7):
        for col,value in {'A':c['id'],'C':c['priority'],'D':c['title'],'E':'未验收','J':c['role'],'K':c['pre'],'L':'\n'.join(f'{i+1}. {x}' for i,x in enumerate(c['steps'])),'M':'\n'.join(f'{i+1}. {x}' for i,x in enumerate(c['expected'])),'N':c['evidence']}.items():
            assert dt[f'{col}{row}']==value,(row,col)
        assert dt.get(f'F{row}') in (None,''),row
    pane=detail.find('.//s:pane',ns)
    assert pane is not None and pane.get('xSplit')=='4' and pane.get('ySplit')=='6', ET.tostring(pane)
    validations=detail.findall('.//s:dataValidation',ns)
    assert any(v.get('sqref')=='E7:E66' for v in validations)
    table=ET.fromstring(z.read('xl/tables/table1.xml'))
    assert table.get('ref')=='A6:R66'
    assert table.find('s:autoFilter',ns) is not None
    assert len(detail.findall('.//s:f',ns))==60
    for sheet in (overview,detail):
        assert not sheet.findall('.//s:c[@t="e"]',ns)
    print(json.dumps({'saved_file':str(target),'bytes':target.stat().st_size,'cases_preserved':60,'default_result':'未验收','frozen_rows':6,'frozen_columns':4,'dropdowns':'verified','table_filter':'verified','formula_errors':0},ensure_ascii=False))
