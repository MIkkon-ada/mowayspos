/**
 * 成员视图 Mock 数据（三层结构：Project → Workstream → KeyTask）
 *
 * 此文件使用的三层命名已对齐文档口径：
 *   Project → Workstream（重点工作）→ Task/KeyTask（关键任务）
 *
 * 注意：主工作推进表（TaskManagementPage）中 Task=Workstream、SubTask=KeyTask。
 * 成员视图 mock 的 MockMemberWorkstream.tasks 是成员视图内部的 Task 概念，
 * 不与主表 tasks 直接对应，仅供前端成员视图独立展示。
 */
export type MockMemberTaskRole = 'owner' | 'assistant'

export type MockMemberTask = {
  id: string
  name: string
  role: MockMemberTaskRole
  status: string
  dueDate: string
  planStartDate: string
  planEndDate: string
  description: string
  evaluationCriteria: string
  latestProgress: string
  pmStatus: '待 PM 确认' | 'PM 已确认' | '被退回需修改' | '未提交'
  pmFeedback?: string
  ownerName?: string
  myCollaboration?: string
  history: Array<{
    date: string
    summary: string
    status: string
  }>
  linkedAchievements: string[]
  linkedIssues: string[]
  linkedRisks: string[]
}

export type MockMemberWorkstream = {
  id: string
  name: string
  description: string
  evaluationCriteria: string
  tasks: MockMemberTask[]
}

export type MockMemberSubmission = {
  id: string
  projectId: string
  taskId: string
  taskName: string
  submittedAt: string
  submitter: string
  contentSummary: string
  aiExtractResult: string
  pmStatus: '待 PM 确认' | '已退回' | 'PM 已确认'
  pmFeedback?: string
  finalWriteTargets: string[]
}

export type MockMemberProject = {
  id: string
  name: string
  status: string
  description: string
  latestReminder: string
  nearestDueTaskId: string
  workstreams: MockMemberWorkstream[]
  submissions: MockMemberSubmission[]
}

export const MEMBER_VIEW_MOCK_TODAY = '2026-07-03'

export const memberViewMockProjects: MockMemberProject[] = [
  {
    id: 'client-dashboard',
    name: 'AI驾驶舱客户版',
    status: '进行中',
    description: '面向客户侧交付的 AI 驾驶舱产品，聚焦信息架构、权限入口与帮助内容闭环。',
    latestReminder: '客户版首页信息架构草图，2天后截止',
    nearestDueTaskId: 'client-home-ia',
    workstreams: [
      {
        id: 'client-home-design',
        name: '客户版首页设计',
        description: '承接客户进入后的首页信息组织、功能范围提示和首屏路径设计。',
        evaluationCriteria: '首页结构能清晰呈现客户最常用的信息、操作入口和状态提醒。',
        tasks: [
          {
            id: 'client-home-ia',
            name: '客户版首页信息架构草图',
            role: 'owner',
            status: '进行中',
            dueDate: '2026-07-05',
            planStartDate: '2026-06-28',
            planEndDate: '2026-07-05',
            description: '梳理客户版首页的信息层级、核心模块顺序、任务入口和异常提醒表达方式。',
            evaluationCriteria: '草图覆盖首页主要模块，能解释客户进入后的首屏信息优先级，并标注关键交互入口。',
            latestProgress: '草图结构已完成，等待评审',
            pmStatus: '待 PM 确认',
            history: [
              { date: '07-02', summary: '提交首页信息架构第一版，补充了首屏模块顺序。', status: '待 PM 确认' },
              { date: '07-01', summary: '完成客户角色进入路径梳理。', status: 'PM 已确认' },
            ],
            linkedAchievements: ['客户版首页草图 v1'],
            linkedIssues: [],
            linkedRisks: ['评审时间压缩，可能影响视觉细化节奏'],
          },
          {
            id: 'client-feature-list',
            name: '客户版功能清单梳理',
            role: 'assistant',
            status: '进行中',
            dueDate: '2026-07-06',
            planStartDate: '2026-06-30',
            planEndDate: '2026-07-06',
            description: '协助关键任务承担者补充功能项说明、边界条件和暂不纳入范围。',
            evaluationCriteria: '协助内容能覆盖客户可见功能、内部管理功能和后续版本功能的边界。',
            latestProgress: '已补充客户可见功能说明',
            pmStatus: '待 PM 确认',
            ownerName: '温会林',
            myCollaboration: '补充功能说明和边界',
            history: [
              { date: '07-02', summary: '补充客户可见功能边界。', status: '待 PM 确认' },
            ],
            linkedAchievements: [],
            linkedIssues: [],
            linkedRisks: [],
          },
        ],
      },
      {
        id: 'client-permission-design',
        name: '客户版权限入口设计',
        description: '定义客户版与内部版的访问边界、入口关系和角色可见范围。',
        evaluationCriteria: '权限入口说明能让 PM 判断客户可见内容与内部管理内容不会混用。',
        tasks: [
          {
            id: 'client-permission-entry',
            name: '客户版权限入口说明',
            role: 'owner',
            status: '进行中',
            dueDate: '2026-07-03',
            planStartDate: '2026-06-29',
            planEndDate: '2026-07-03',
            description: '说明客户版入口、内部版入口、客户可见模块和内部管理模块之间的边界。',
            evaluationCriteria: '能清晰区分客户版和内部版权限，不混用项目负责人 / PM 与关键任务承担者口径。',
            latestProgress: '已补充客户版入口说明，角色边界仍需再展开',
            pmStatus: '被退回需修改',
            pmFeedback: '角色边界说明不清楚，请补充客户版和内部版区别',
            history: [
              { date: '07-01', summary: '提交客户版权限入口说明初稿。', status: '已退回' },
              { date: '06-30', summary: '完成客户版入口清单。', status: 'PM 已确认' },
            ],
            linkedAchievements: ['客户版权限入口说明初稿'],
            linkedIssues: ['客户版与内部版入口边界需要补充'],
            linkedRisks: [],
          },
          {
            id: 'client-interaction-standard',
            name: '客户版交互规范确认',
            role: 'assistant',
            status: '进行中',
            dueDate: '2026-07-04',
            planStartDate: '2026-06-30',
            planEndDate: '2026-07-04',
            description: '协助关键任务承担者核对按钮、筛选、空状态和提示反馈的交互一致性。',
            evaluationCriteria: '交互问题记录完整，能支持 PM 判断是否进入下一轮视觉确认。',
            latestProgress: '列出 5 条交互细节问题',
            pmStatus: '未提交',
            ownerName: '刘万超',
            myCollaboration: '补充交互细节问题',
            history: [
              { date: '07-01', summary: '完成筛选和空状态问题记录。', status: '未提交' },
            ],
            linkedAchievements: [],
            linkedIssues: ['空状态文案与客户版语气不一致'],
            linkedRisks: [],
          },
        ],
      },
      {
        id: 'client-help-design',
        name: '客户版帮助中心设计',
        description: '搭建客户自助支持内容框架，覆盖首次使用、常见问题和资料入口。',
        evaluationCriteria: '帮助中心框架能支撑客户独立完成高频操作并定位支持入口。',
        tasks: [
          {
            id: 'client-help-center',
            name: '客户版帮助中心框架',
            role: 'owner',
            status: '进行中',
            dueDate: '2026-07-08',
            planStartDate: '2026-07-01',
            planEndDate: '2026-07-08',
            description: '搭建帮助中心一级目录、常见问题分类、操作说明和客户交付资料入口。',
            evaluationCriteria: '框架覆盖客户首次使用、数据查看、异常处理和联系支持四类高频场景。',
            latestProgress: '内容结构补充中',
            pmStatus: '未提交',
            history: [
              { date: '07-02', summary: '完成帮助中心一级栏目草稿。', status: '未提交' },
            ],
            linkedAchievements: [],
            linkedIssues: [],
            linkedRisks: [],
          },
        ],
      },
    ],
    submissions: [
      {
        id: 'sub-client-0702',
        projectId: 'client-dashboard',
        taskId: 'client-home-ia',
        taskName: '客户版首页信息架构草图',
        submittedAt: '07-02',
        submitter: '我',
        contentSummary: '首页信息架构草图已完成，等待评审。',
        aiExtractResult: '提取为关键任务进展草稿',
        pmStatus: '待 PM 确认',
        finalWriteTargets: [],
      },
      {
        id: 'sub-client-0701',
        projectId: 'client-dashboard',
        taskId: 'client-permission-entry',
        taskName: '客户版权限入口说明',
        submittedAt: '07-01',
        submitter: '我',
        contentSummary: '提交客户版权限入口说明初稿。',
        aiExtractResult: '提取为关键任务进展草稿',
        pmStatus: '已退回',
        pmFeedback: '角色边界不清楚',
        finalWriteTargets: [],
      },
      {
        id: 'sub-client-0630',
        projectId: 'client-dashboard',
        taskId: 'client-page-flow',
        taskName: '客户版页面流程梳理',
        submittedAt: '06-30',
        submitter: '我',
        contentSummary: '完成客户版页面主流程和异常流程说明。',
        aiExtractResult: '提取为关键任务进展',
        pmStatus: 'PM 已确认',
        finalWriteTargets: ['关键任务进展'],
      },
    ],
  },
  {
    id: 'knowledge-ai',
    name: '知识资产AI化',
    status: '进行中',
    description: '将内部知识资产结构化、标签化，并形成可复用的 AI 检索和问答基础。',
    latestReminder: '知识条目标签口径今日截止',
    nearestDueTaskId: 'knowledge-tag-standard',
    workstreams: [
      {
        id: 'knowledge-structure',
        name: '知识结构化',
        description: '定义知识条目的分类、标签和适用场景字段。',
        evaluationCriteria: '口径能支撑后续检索、推荐和权限过滤。',
        tasks: [
          {
            id: 'knowledge-tag-standard',
            name: '知识条目标签口径',
            role: 'owner',
            status: '进行中',
            dueDate: '2026-07-03',
            planStartDate: '2026-06-27',
            planEndDate: '2026-07-03',
            description: '定义知识条目的分类、标签和适用场景字段。',
            evaluationCriteria: '口径能支撑后续检索、推荐和权限过滤。',
            latestProgress: '标签分层已完成，等待补充示例',
            pmStatus: '未提交',
            history: [{ date: '07-02', summary: '完成标签分层草案。', status: '未提交' }],
            linkedAchievements: [],
            linkedIssues: [],
            linkedRisks: [],
          },
          {
            id: 'knowledge-case-review',
            name: '历史案例补充校对',
            role: 'assistant',
            status: '进行中',
            dueDate: '2026-07-09',
            planStartDate: '2026-07-01',
            planEndDate: '2026-07-09',
            description: '协助关键任务承担者校对历史案例摘要和适用场景。',
            evaluationCriteria: '校对结果能减少重复知识和场景误标。',
            latestProgress: '已校对 12 条案例',
            pmStatus: '未提交',
            ownerName: '陈思源',
            myCollaboration: '补充案例摘要和适用场景',
            history: [{ date: '07-02', summary: '完成第一批案例校对。', status: '未提交' }],
            linkedAchievements: [],
            linkedIssues: [],
            linkedRisks: [],
          },
        ],
      },
    ],
    submissions: [],
  },
  {
    id: 'internal-process',
    name: '内部流程优化',
    status: '计划中',
    description: '梳理跨部门协作流程，减少重复确认和人工流转成本。',
    latestReminder: '流程节点访谈材料已逾期',
    nearestDueTaskId: 'process-interview-material',
    workstreams: [
      {
        id: 'process-current-state',
        name: '现状流程盘点',
        description: '梳理当前跨部门协作的关键节点、输入输出和耗时。',
        evaluationCriteria: '节点图能支持后续识别重复流转和自动化机会。',
        tasks: [
          {
            id: 'process-node-map',
            name: '流程节点梳理',
            role: 'owner',
            status: '未开始',
            dueDate: '2026-07-10',
            planStartDate: '2026-07-04',
            planEndDate: '2026-07-10',
            description: '梳理当前跨部门协作的关键节点、输入输出和耗时。',
            evaluationCriteria: '节点图能支持后续识别重复流转和自动化机会。',
            latestProgress: '等待启动',
            pmStatus: '未提交',
            history: [],
            linkedAchievements: [],
            linkedIssues: [],
            linkedRisks: [],
          },
          {
            id: 'process-interview-material',
            name: '流程节点访谈材料',
            role: 'assistant',
            status: '进行中',
            dueDate: '2026-07-01',
            planStartDate: '2026-06-25',
            planEndDate: '2026-07-01',
            description: '协助关键任务承担者整理访谈问题、访谈对象和原始材料。',
            evaluationCriteria: '访谈材料覆盖核心岗位，问题能定位流程卡点。',
            latestProgress: '访谈材料整理到 70%',
            pmStatus: '未提交',
            ownerName: '周祺',
            myCollaboration: '补充访谈问题和材料链接',
            history: [{ date: '06-30', summary: '补充第二批访谈问题。', status: '未提交' }],
            linkedAchievements: [],
            linkedIssues: ['访谈对象时间未全部确认'],
            linkedRisks: ['访谈延迟会影响流程节点梳理'],
          },
        ],
      },
    ],
    submissions: [],
  },
]
