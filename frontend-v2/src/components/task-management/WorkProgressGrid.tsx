import { useEffect, useRef } from 'react'
import { ListTable, type ListTableConstructorOptions } from '@visactor/vtable'
import { InputEditor, TextAreaEditor, DateInputEditor, ListEditor } from '@visactor/vtable-editors'
import type { SubTaskItem } from '../../types'
import type { PlanTableRow } from './planTableViewModel'
import { GRID_COLUMNS, buildCellChange, parseClipboard, type GridView, type GridColumnKey } from './workProgressGridModel'

export type GridRecord = Record<string, unknown> & { _source: SubTaskItem | null; _plan: PlanTableRow }
export type GridCellChange = { source: SubTaskItem; key: string; value: string }
type Props = {
  records: GridRecord[]
  view: GridView
  canEdit: boolean
  memberNames: string[]
  onChanges: (cells: GridCellChange[]) => boolean
  onSelect: (record: GridRecord | null) => void
  onError: (message: string) => void
  onWidths: (widths: Partial<Record<GridColumnKey, number>>) => void
}

export function WorkProgressGrid(props: Props) {
  const host = useRef<HTMLDivElement>(null)
  const latest = useRef(props)
  latest.current = props
  useEffect(() => {
    if (!host.current) return
    const columns = props.view.columns.map(key => GRID_COLUMNS.find(column => column.key === key)!)
    const input = new InputEditor(), textarea = new TextAreaEditor(), date = new DateInputEditor()
    const people = new ListEditor({ values: props.memberNames })
    const options: ListTableConstructorOptions = {
      records: props.records.map(record => ({ ...record })),
      columns: columns.map(column => ({
        field: column.key, title: column.label, width: props.view.widths[column.key] ?? column.width, minWidth: 90,
        description: column.field ? '双击编辑；修改后点击保存修改' : '来源字段只读，点击任务后打开详情',
        editor: args => {
          const record = args.table.getCellOriginRecord(args.col, args.row) as GridRecord | undefined
          if (!props.canEdit || !column.field || !record?._source || ['已完成', '完成', 'completed'].includes(record._source.status)) return ''
          return column.key === 'owner' ? people : column.key === 'startDate' || column.key === 'dueDate' ? date : column.key === 'keyTask' ? input : textarea
        },
        style: {
          autoWrapText: true, lineClamp: 3, textBaseline: 'middle',
          color: args => column.key === 'status' ? ((args.table.getCellOriginRecord(args.col, args.row) as GridRecord)?.status === '已完成' ? '#24745a' : '#526273') : column.key === 'keyTask' ? '#254b75' : '#46566a',
          bgColor: args => (args.table.getCellOriginRecord(args.col, args.row) as GridRecord)?._dirty ? '#fffbef' : '#ffffff',
        },
      })),
      rowSeriesNumber: { title: '#', width: 42, disableColumnResize: true },
      frozenColCount: props.view.frozen + 1,
      groupBy: props.view.groupBy === 'none' ? undefined : [props.view.groupBy],
      hierarchyExpandLevel: 2,
      defaultRowHeight: 64, defaultHeaderRowHeight: 38,
      customComputeRowHeight: ({ row, table }) => row === 0 ? 38 : table.getGroupTitleLevel(1, row) != null ? 34 : 64,
      autoWrapText: true, widthMode: 'standard', heightMode: 'standard',
      editCellTrigger: ['doubleclick', 'keydown'],
      keyboardOptions: { copySelected: true, pasteValueToCell: false, selectAllOnCtrlA: true, moveFocusCellOnEnter: true, moveFocusCellOnTab: true, editCellOnEnter: true },
      tooltip: { isShowOverflowTextTooltip: true },
      theme: {
        headerStyle: { fontFamily: 'Microsoft YaHei, PingFang SC, sans-serif', bgColor: '#f5f7fa', color: '#617084', fontSize: 12, fontWeight: 500, borderColor: '#e4e8ee', padding: [8, 12] },
        bodyStyle: { fontFamily: 'Microsoft YaHei, PingFang SC, sans-serif', fontSize: 12, color: '#46566a', borderColor: '#e9edf2', padding: [10, 12], hover: { cellBgColor: '#f4f8fd' } },
        groupTitleStyle: { bgColor: '#f8fafc', color: '#394d64', borderColor: '#e4e8ee', borderLineWidth: 1, fontSize: 12, fontWeight: 600, padding: [8, 12] },
        selectionStyle: { cellBorderColor: '#3579c5', cellBgColor: 'rgba(53, 121, 197, 0.08)', cellBorderLineWidth: 2 },
        frameStyle: { borderColor: '#e4e8ee', borderLineWidth: 1 },
        scrollStyle: { visible: 'scrolling', width: 8, scrollSliderColor: '#bcc8d5' },
      },
    }
    const table = new ListTable(host.current, options)
    table.on('selected_cell', event => latest.current.onSelect(table.getCellOriginRecord(event.col, event.row) as GridRecord | null))
    table.on('change_cell_value', event => {
      const record = table.getCellOriginRecord(event.col, event.row) as GridRecord | undefined
      if (!record?._source) return
      const key = columns[event.col - 1]?.key
      try {
        if (!key || !latest.current.canEdit) throw new Error('当前记录只读')
        buildCellChange(record._source, key, String(event.changedValue ?? ''), latest.current.memberNames)
        if (!latest.current.onChanges([{ source: record._source, key, value: String(event.changedValue ?? '') }])) {
          table.changeCellValue(event.col, event.row, String(event.currentValue ?? ''), false, false)
        }
      } catch (error) {
        table.changeCellValue(event.col, event.row, String(event.currentValue ?? ''), false, false)
        latest.current.onError(error instanceof Error ? error.message : '单元格修改失败')
      }
    })
    table.on('resize_column_end', () => {
      const widths = Object.fromEntries(columns.map((column, index) => [column.key, table.getColWidth(index + 1)]))
      latest.current.onWidths(widths)
    })
    const paste = (event: ClipboardEvent) => {
      // The native editor owns paste while a text/date editor is focused.
      if ((event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) && !event.target.classList.contains('table-focus-control') && event.target.style.opacity !== '0') return
      event.preventDefault()
      event.stopPropagation()
      try {
        if (!latest.current.canEdit) throw new Error('当前表格只读')
        const range = table.getSelectedCellRanges()[0]
        if (!range) throw new Error('请先选择粘贴的起始单元格')
        const values = parseClipboard(event.clipboardData?.getData('text/plain') ?? '')
        if (!values.length) return
        if (values.length > 200) throw new Error('每次最多粘贴 200 行')
        const startCol = Math.min(range.start.col, range.end.col), startRow = Math.min(range.start.row, range.end.row)
        const cells: GridCellChange[] = []
        values.forEach((line, dy) => line.forEach((value, dx) => {
          const col = startCol + dx, row = startRow + dy
          const record = table.getCellOriginRecord(col, row) as GridRecord | undefined
          const key = columns[col - 1]?.key
          if (!record?._source || !key) throw new Error('粘贴范围包含分组行或超出记录，请分组内粘贴，或切换为不分组')
          buildCellChange(record._source, key, value, latest.current.memberNames)
          cells.push({ source: record._source, key, value })
        }))
        latest.current.onChanges(cells)
      } catch (error) { latest.current.onError(error instanceof Error ? error.message : '粘贴失败，未修改任何单元格') }
    }
    const element = host.current
    element.addEventListener('paste', paste, true)
    const observer = new ResizeObserver(() => table.resize())
    observer.observe(element)
    return () => { observer.disconnect(); element.removeEventListener('paste', paste, true); table.release() }
  }, [props.records, props.view, props.canEdit, props.memberNames])
  return <div ref={host} className="wp-grid-canvas" role="region" aria-label={props.canEdit ? '可编辑工作推进表，双击编辑，选择区域后复制或粘贴' : '只读工作推进表，可以选择并复制记录'} tabIndex={0} />
}
