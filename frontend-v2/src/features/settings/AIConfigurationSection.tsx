import { useEffect, useMemo, useState } from "react";
import {
  listAICapabilityPolicies,
  listAIModels,
  saveAICapabilityPolicy,
  setAIModelEnabled,
  testAIModel,
  type AICapabilityPolicy,
  type AIModel,
} from "../../api/aiConfig";
import { AIModelDrawer } from "./AIModelDrawer";

type ModelFilter = "all" | AIModel["model_type"];
type ConsoleView = "module" | "model";
type CapabilityPolicyView = AICapabilityPolicy & {
  configured: boolean;
  requiredModelType: AIModel["model_type"];
};
type CapabilityDefinition = Pick<
  CapabilityPolicyView,
  "capability_key" | "requiredModelType"
> & { title: string; description: string };
type PolicyTimeouts = Pick<
  AICapabilityPolicy,
  "timeout_seconds" | "fallback_timeout_seconds"
>;
type ModelHealth = "ready" | "warning" | "off";

const CAPABILITY_DEFAULTS: CapabilityDefinition[] = [
  {
    capability_key: "meeting.analysis",
    requiredModelType: "chat",
    title: "会议纪要 AI 分析",
    description: "用于会议资料分析、会议纪要和行动项生成。",
  },
  {
    capability_key: "task.extraction",
    requiredModelType: "chat",
    title: "工作汇报 / 文本任务提取",
    description: "用于从工作汇报或输入文本中提取任务。",
  },
  {
    capability_key: "project.init.analysis",
    requiredModelType: "chat",
    title: "项目立项方案 AI 分析",
    description: "用于项目立项页面上传资料后的方案分析。",
  },
  {
    capability_key: "task.plan.proposal",
    requiredModelType: "chat",
    title: "关键任务计划 AI 拆解（文字 / 附件）",
    description: "用于工作推进表中，根据文字和附件生成任务计划草稿。",
  },
  {
    capability_key: "speech.realtime",
    requiredModelType: "asr",
    title: "实时语音转写",
    description: "用于实时语音识别并转换为文字。",
  },
];

function friendlyLoadError(error: unknown): string {
  const text = error instanceof Error ? error.message : "";
  if (text.includes("403")) return "仅技术管理员可以管理模型。";
  if (text.includes("503")) return "AI 配置服务暂不可用，请联系系统管理员。";
  return "模型加载失败，请重试。";
}

function modelName(model: AIModel | undefined, id?: number | null): string {
  return (
    model?.display_name || model?.model_name || (id ? `模型 ${id}` : "未配置")
  );
}

function modelHealth(model: AIModel): ModelHealth {
  if (!model.enabled) return "off";
  return model.credential_configured ? "ready" : "warning";
}

function healthLabel(health: ModelHealth): string {
  if (health === "ready") return "已连接";
  if (health === "warning") return "待配置";
  return "已停用";
}

function healthClass(health: ModelHealth): string {
  if (health === "ready") return "bg-emerald-50 text-emerald-700";
  if (health === "warning") return "bg-amber-50 text-amber-700";
  return "bg-slate-100 text-slate-500";
}

function dotClass(health: ModelHealth): string {
  if (health === "ready") return "bg-emerald-500";
  if (health === "warning") return "bg-amber-500";
  return "bg-slate-400";
}

function policyState(
  policy: CapabilityPolicyView,
  order: number[],
  models: AIModel[],
) {
  if (order.length === 0)
    return {
      label: "待配置",
      className: "bg-amber-50 text-amber-700",
      level: "warning" as const,
    };
  const primary = models.find((model) => model.id === order[0]);
  if (!primary || !primary.enabled || !primary.credential_configured)
    return {
      label: "主用异常",
      className: "bg-rose-50 text-rose-700",
      level: "bad" as const,
    };
  const hasBadFallback = order.slice(1).some((id) => {
    const model = models.find((item) => item.id === id);
    return !model || !model.enabled || !model.credential_configured;
  });
  return hasBadFallback
    ? {
        label: "就绪 · 备用异常",
        className: "bg-amber-50 text-amber-700",
        level: "warning" as const,
      }
    : {
        label: "就绪",
        className: "bg-emerald-50 text-emerald-700",
        level: "ready" as const,
      };
}

function ModelTypeIcon({ type }: { type: AIModel["model_type"] }) {
  return type === "asr" ? (
    <span
      className="grid h-9 w-9 place-items-center rounded-lg bg-cyan-50 text-cyan-700"
      aria-hidden="true"
    >
      ⌁
    </span>
  ) : (
    <span
      className="grid h-9 w-9 place-items-center rounded-lg bg-indigo-50 text-indigo-700"
      aria-hidden="true"
    >
      ✦
    </span>
  );
}

export function AIConfigurationSection() {
  const [models, setModels] = useState<AIModel[]>([]);
  const [policies, setPolicies] = useState<AICapabilityPolicy[]>([]);
  const [policyOrders, setPolicyOrders] = useState<Record<string, number[]>>(
    {},
  );
  const [policyTimeouts, setPolicyTimeouts] = useState<
    Record<string, PolicyTimeouts>
  >({});
  const [filter, setFilter] = useState<ModelFilter>("all");
  const [view, setView] = useState<ConsoleView>("module");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [message, setMessage] = useState("");
  const [busyModelId, setBusyModelId] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<AIModel | null>(null);
  const [routeKey, setRouteKey] = useState<string | null>(null);
  const [routeDraft, setRouteDraft] = useState<number[]>([]);

  async function reload() {
    setLoading(true);
    try {
      const [nextModels, nextPolicies] = await Promise.all([
        listAIModels(),
        listAICapabilityPolicies(),
      ]);
      setModels(nextModels);
      setPolicies(nextPolicies);
      setPolicyOrders(
        Object.fromEntries(
          nextPolicies.map((policy) => [
            policy.capability_key,
            [policy.primary_model_id, ...policy.fallback_model_ids].filter(
              (id): id is number => id !== null,
            ),
          ]),
        ),
      );
      setPolicyTimeouts(
        Object.fromEntries(
          nextPolicies.map((policy) => [
            policy.capability_key,
            {
              timeout_seconds: policy.timeout_seconds,
              fallback_timeout_seconds: policy.fallback_timeout_seconds,
            },
          ]),
        ),
      );
      setLoadError("");
    } catch (error) {
      setLoadError(friendlyLoadError(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  const visibleModels = useMemo(
    () =>
      models.filter((model) => filter === "all" || model.model_type === filter),
    [filter, models],
  );
  const counts = useMemo(
    () => ({
      all: models.length,
      chat: models.filter((model) => model.model_type === "chat").length,
      asr: models.filter((model) => model.model_type === "asr").length,
    }),
    [models],
  );
  const displayPolicies = useMemo<CapabilityPolicyView[]>(() => {
    const savedByKey = new Map(
      policies.map((policy) => [policy.capability_key, policy]),
    );
    return CAPABILITY_DEFAULTS.map((definition) => {
      const saved = savedByKey.get(definition.capability_key);
      return saved
        ? {
            ...saved,
            configured: true,
            requiredModelType: definition.requiredModelType,
          }
        : {
            id: 0,
            capability_key: definition.capability_key,
            primary_model_id: null,
            fallback_model_ids: [],
            timeout_seconds:
              definition.capability_key === "project.init.analysis" ? 200 : 30,
            fallback_timeout_seconds: 25,
            max_attempts: 1,
            policy_version: 0,
            enabled: true,
            configured: false,
            requiredModelType: definition.requiredModelType,
          };
    });
  }, [policies]);
  const health = useMemo(() => {
    const readyModules = displayPolicies.filter(
      (policy) =>
        policyState(policy, policyOrders[policy.capability_key] ?? [], models)
          .level === "ready",
    ).length;
    const warningModules = displayPolicies.filter(
      (policy) =>
        policyState(policy, policyOrders[policy.capability_key] ?? [], models)
          .level === "warning",
    ).length;
    const connectedModels = models.filter(
      (model) => model.enabled && model.credential_configured,
    ).length;
    const primaryUsage = new Map<number, number>();
    displayPolicies.forEach((policy) => {
      const primary = (policyOrders[policy.capability_key] ?? [])[0];
      if (primary)
        primaryUsage.set(primary, (primaryUsage.get(primary) ?? 0) + 1);
    });
    const busiest = [...primaryUsage.entries()].sort((a, b) => b[1] - a[1])[0];
    return {
      readyModules,
      warningModules,
      connectedModels,
      busiestModel: modelName(
        models.find((model) => model.id === busiest?.[0]),
      ),
      busiestCount: busiest?.[1] ?? 0,
      voiceReady: models.some(
        (model) =>
          model.model_type === "asr" &&
          model.enabled &&
          model.credential_configured,
      ),
    };
  }, [displayPolicies, models, policyOrders]);
  const routePolicy = routeKey
    ? displayPolicies.find((policy) => policy.capability_key === routeKey)
    : null;

  function openAddDrawer() {
    setEditingModel(null);
    setDrawerOpen(true);
    setMessage("");
  }
  function openEditDrawer(model: AIModel) {
    setEditingModel(model);
    setDrawerOpen(true);
    setMessage("");
  }

  async function runTest(model: AIModel) {
    setBusyModelId(model.id);
    setMessage("");
    try {
      const result = await testAIModel(model.id);
      setMessage(
        result.ok
          ? `${model.display_name || model.model_name} 连接成功`
          : "连接失败，请检查模型名称、Base URL 和 API Key",
      );
    } catch {
      setMessage("连接失败，请检查模型名称、Base URL 和 API Key");
    } finally {
      setBusyModelId(null);
    }
  }

  async function toggleModel(model: AIModel) {
    setBusyModelId(model.id);
    setMessage("");
    try {
      await setAIModelEnabled(model.id, !model.enabled);
      await reload();
    } catch {
      setMessage("更新模型状态失败，请重试。");
    } finally {
      setBusyModelId(null);
    }
  }

  function eligibleModels(policy: CapabilityPolicyView) {
    return models.filter(
      (model) => model.enabled && model.model_type === policy.requiredModelType,
    );
  }
  function moveModel(key: string, index: number, direction: -1 | 1) {
    setPolicyOrders((current) => {
      const next = [...(current[key] ?? [])];
      const target = index + direction;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return { ...current, [key]: next };
    });
  }
  function addModel(key: string, id: number) {
    setPolicyOrders((current) => ({
      ...current,
      [key]: [...(current[key] ?? []), id],
    }));
  }
  function openRouteEditor(policy: CapabilityPolicyView) {
    setRouteKey(policy.capability_key);
    setRouteDraft([...(policyOrders[policy.capability_key] ?? [])]);
    setMessage("");
  }
  function closeRouteEditor() {
    setRouteKey(null);
    setRouteDraft([]);
  }
  function moveRouteModel(index: number, direction: -1 | 1) {
    setRouteDraft((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  async function savePolicy(
    policy: CapabilityPolicyView,
    idsOverride?: number[],
  ) {
    const ids = idsOverride ?? policyOrders[policy.capability_key] ?? [];
    if (ids.length === 0) {
      setMessage("每个启用的 AI 能力至少需要一个模型。");
      return false;
    }
    setMessage("");
    try {
      const timeouts = policyTimeouts[policy.capability_key] ?? policy;
      await saveAICapabilityPolicy(policy.capability_key, {
        primary_model_id: ids[0],
        fallback_model_ids: ids.slice(1),
        timeout_seconds: timeouts.timeout_seconds,
        fallback_timeout_seconds: timeouts.fallback_timeout_seconds,
        max_attempts: Math.max(1, ids.length),
        enabled: policy.enabled,
      });
      setPolicyOrders((current) => ({
        ...current,
        [policy.capability_key]: ids,
      }));
      await reload();
      setMessage("模型优先级已保存。");
      return true;
    } catch {
      setMessage("模型优先级保存失败，请重试。");
      return false;
    }
  }
  async function saveRoute() {
    if (routePolicy && (await savePolicy(routePolicy, routeDraft)))
      closeRouteEditor();
  }

  const tabs: Array<{ key: ModelFilter; label: string; count: number }> = [
    { key: "all", label: "全部", count: counts.all },
    { key: "chat", label: "对话模型", count: counts.chat },
    { key: "asr", label: "语音模型", count: counts.asr },
  ];

  return (
    <section className="min-w-0 rounded-2xl border border-slate-200 bg-[#f5f7fb] p-4 shadow-sm sm:p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              AI 能力路由台
            </h2>
            <span className="sr-only">模型管理</span>
            <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
              AI 能力策略
            </span>
          </div>
          <p className="mt-2 text-sm text-slate-500">
            统一配置各功能模块调用的模型与降级顺序 ·
            主用失败时自动按备用链路重试
          </p>
        </div>
        <button
          type="button"
          onClick={openAddDrawer}
          className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700"
        >
          ＋ 接入新模型<span className="sr-only">添加模型</span>
        </button>
      </header>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs font-semibold text-slate-400">模块就绪度</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {health.readyModules}
            <span className="ml-1 text-sm font-normal text-slate-400">
              / {displayPolicies.length}
            </span>
          </p>
          <p className="mt-1 text-xs text-amber-600">
            {health.warningModules} 个模块需要关注
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs font-semibold text-slate-400">模型连接健康</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {health.connectedModels}
            <span className="ml-1 text-sm font-normal text-slate-400">
              / {models.length}
            </span>
          </p>
          <p className="mt-1 text-xs text-emerald-600">已启用并配置凭据</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs font-semibold text-slate-400">主用负载最高</p>
          <p className="mt-2 truncate text-lg font-bold text-slate-900">
            {health.busiestCount ? `${health.busiestModel}` : "暂无主用模型"}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {health.busiestCount
              ? `作为 ${health.busiestCount} 个模块的第一顺位`
              : "请先配置能力链路"}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs font-semibold text-slate-400">语音能力</p>
          <p
            className={`mt-2 text-lg font-bold ${health.voiceReady ? "text-emerald-600" : "text-amber-600"}`}
          >
            {health.voiceReady ? "可用" : "待配置"}
          </p>
          <p className="mt-1 text-xs text-slate-400">语音识别模型</p>
        </div>
      </div>

      {loadError && (
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span>{loadError}</span>
          <button
            type="button"
            onClick={() => void reload()}
            className="font-semibold underline"
          >
            重新加载
          </button>
        </div>
      )}
      {message && (
        <p
          className={`mt-5 rounded-xl px-4 py-3 text-sm ${message.includes("成功") || message.includes("已保存") ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}
        >
          {message}
        </p>
      )}
      <div className="mt-6 flex items-center justify-between gap-4 border-b border-slate-200">
        <div className="flex gap-6">
          <button
            type="button"
            onClick={() => setView("module")}
            className={`border-b-2 px-1 pb-3 text-sm font-semibold ${view === "module" ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500"}`}
          >
            按模块 · 降级链路
          </button>
          <button
            type="button"
            onClick={() => setView("model")}
            className={`border-b-2 px-1 pb-3 text-sm font-semibold ${view === "model" ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500"}`}
          >
            按模型 · 资源负载
          </button>
        </div>
        <span className="hidden pb-3 text-xs text-slate-400 sm:inline">
          实时配置视图
        </span>
      </div>

      {loading && models.length === 0 ? (
        <p className="py-20 text-center text-sm text-slate-400">
          正在加载 AI 路由台…
        </p>
      ) : (
        <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.45fr)]">
          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-bold text-slate-900">模型资源池</h3>
                <p className="mt-1 text-xs text-slate-400">
                  可被能力路由调用的模型
                </p>
              </div>
              <button
                type="button"
                onClick={openAddDrawer}
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-700"
              >
                ＋ 接入
              </button>
            </div>
            <nav
              className="mt-4 flex gap-3 border-b border-slate-100 pb-2"
              aria-label="模型类型筛选"
            >
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setFilter(tab.key)}
                  className={`text-xs font-semibold ${filter === tab.key ? "text-indigo-700" : "text-slate-400"}`}
                >
                  {tab.label} <span className="font-normal">{tab.count}</span>
                </button>
              ))}
            </nav>
            <div className="mt-3 space-y-3">
              {visibleModels.map((model) => {
                const state = modelHealth(model);
                return (
                  <article
                    key={model.id}
                    className="rounded-xl border border-slate-200 p-3 transition hover:border-indigo-200 hover:shadow-sm"
                  >
                    <div className="flex items-start gap-3">
                      <ModelTypeIcon type={model.model_type} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <h4 className="truncate text-sm font-semibold text-slate-800">
                            {modelName(model)}
                          </h4>
                          <span
                            className={`h-2 w-2 shrink-0 rounded-full ${dotClass(state)}`}
                            title={healthLabel(state)}
                          />
                        </div>
                        <p className="mt-1 truncate text-xs text-slate-400">
                          {model.provider} · {model.model_name}
                        </p>
                      </div>
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${healthClass(state)}`}
                      >
                        {healthLabel(state)}
                      </span>
                      <span className="text-[11px] text-slate-400">
                        {model.model_type === "asr" ? "ASR" : "Chat"}
                      </span>
                    </div>
                    <div className="mt-3 flex gap-2 border-t border-slate-100 pt-3">
                      <button
                        type="button"
                        onClick={() => openEditDrawer(model)}
                        className="text-xs font-semibold text-slate-500 hover:text-indigo-600"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        disabled={busyModelId === model.id}
                        onClick={() => void runTest(model)}
                        className="text-xs font-semibold text-slate-500 hover:text-indigo-600 disabled:opacity-50"
                      >
                        {busyModelId === model.id ? "测试中…" : "测试连接"}
                      </button>
                      <button
                        type="button"
                        disabled={busyModelId === model.id}
                        onClick={() => void toggleModel(model)}
                        className="ml-auto text-xs font-semibold text-slate-400 hover:text-rose-600 disabled:opacity-50"
                      >
                        {model.enabled ? "停用" : "启用"}
                      </button>
                    </div>
                  </article>
                );
              })}
              <button
                type="button"
                onClick={openAddDrawer}
                className="flex min-h-28 w-full flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-slate-300 text-sm font-semibold text-indigo-600 transition hover:border-indigo-300 hover:bg-indigo-50"
              >
                <span className="text-xl">＋</span>
                <span>接入新模型</span>
                <span className="sr-only">添加模型</span>
              </button>
            </div>
            {/* AIModelCard remains the detailed model-card contract for model management. */}
          </section>

          <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 sm:p-5">
            {view === "module" ? (
              <>
                <div>
                  <h3 className="font-bold text-slate-900">模块路由</h3>
                  <p className="mt-1 text-xs text-slate-400">
                    AI 能力策略 · 每个模块独立配置主用与备用顺序
                  </p>
                </div>
                <div className="mt-4 space-y-3">
                  {displayPolicies.map((policy) => {
                    const order = policyOrders[policy.capability_key] ?? [];
                    const definition = CAPABILITY_DEFAULTS.find(
                      (item) => item.capability_key === policy.capability_key,
                    );
                    const state = policyState(policy, order, models);
                    const available = eligibleModels(policy);
                    const timeouts =
                      policyTimeouts[policy.capability_key] ?? policy;
                    return (
                      <article
                        key={policy.capability_key}
                        className="rounded-lg border border-slate-200 p-4 transition hover:border-indigo-200"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <h4 className="font-semibold text-slate-800">
                                {definition?.title || policy.capability_key}
                              </h4>
                              <span
                                data-policy-status
                                className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${state.className}`}
                              >
                                {policy.configured ? state.label : "未配置"}
                              </span>
                            </div>
                            <p className="mt-1 text-xs text-slate-400">
                              {definition?.description}
                            </p>
                            <p className="mt-1 text-[11px] text-slate-300">
                              {policy.capability_key}
                            </p>
                          </div>
                          <button
                            type="button"
                            aria-label={policy.capability_key === "meeting.analysis" ? "编辑链路" : `编辑链路：${definition?.title || policy.capability_key}`}
                            onClick={() => openRouteEditor(policy)}
                            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-indigo-300 hover:text-indigo-700"
                          >
                            编辑链路
                          </button>
                        </div>
                        <div className="mt-4 flex min-w-0 flex-wrap items-center gap-2">
                          {order.length === 0 ? (
                            <div className="rounded-lg border border-dashed border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                              尚未设置调用模型
                            </div>
                          ) : (
                            order.map((id, index) => (
                              <div
                                key={id}
                                className="flex min-w-0 items-center gap-2"
                              >
                                <div
                                  className={`flex min-w-0 items-center gap-2 rounded-lg border px-3 py-2 ${index === 0 ? "border-indigo-200 bg-indigo-50" : "border-slate-200 bg-slate-50"}`}
                                >
                                  <span
                                    className={`text-[10px] font-bold ${index === 0 ? "text-indigo-600" : "text-slate-400"}`}
                                  >
                                    {index === 0 ? "主" : `备 ${index}`}
                                  </span>
                                  <span className="max-w-[150px] truncate text-xs font-semibold text-slate-700">
                                    {modelName(models.find((model) => model.id === id), id)} · {index === 0 ? "主用" : "备用"}
                                  </span>
                                </div>
                                {index < order.length - 1 && (
                                  <span className="text-slate-300">→</span>
                                )}
                              </div>
                            ))
                          )}
                          {order.length > 0 && (
                            <span className="ml-auto text-[11px] text-slate-400">
                              {order.length} 个节点
                            </span>
                          )}
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-3">
                          <select
                            aria-label={`${policy.capability_key} 添加模型`}
                            defaultValue=""
                            onChange={(event) => {
                              const id = Number(event.target.value);
                              if (id) addModel(policy.capability_key, id);
                              event.currentTarget.value = "";
                            }}
                            className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-600"
                          >
                            <option value="">快速添加模型</option>
                            {available
                              .filter((model) => !order.includes(model.id))
                              .map((model) => (
                                <option key={model.id} value={model.id}>
                                  {modelName(model)} · 加入
                                </option>
                              ))}
                          </select>
                          <label className="text-xs text-slate-400">
                            主用{" "}
                            <input
                              aria-label={`${policy.capability_key} 主模型超时`}
                              type="number"
                              min="1"
                              max="600"
                              value={timeouts.timeout_seconds}
                              onChange={(event) =>
                                setPolicyTimeouts((current) => ({
                                  ...current,
                                  [policy.capability_key]: {
                                    ...timeouts,
                                    timeout_seconds: Math.max(
                                      1,
                                      Math.min(
                                        600,
                                        Number(event.target.value) || 1,
                                      ),
                                    ),
                                  },
                                }))
                              }
                              className="ml-1 w-14 rounded border border-slate-200 px-1.5 py-1 text-xs text-slate-600"
                            />
                            s
                          </label>
                          <label className="text-xs text-slate-400">
                            备用{" "}
                            <input
                              aria-label={`${policy.capability_key} 备用模型超时`}
                              type="number"
                              min="1"
                              max="600"
                              value={timeouts.fallback_timeout_seconds}
                              onChange={(event) =>
                                setPolicyTimeouts((current) => ({
                                  ...current,
                                  [policy.capability_key]: {
                                    ...timeouts,
                                    fallback_timeout_seconds: Math.max(
                                      1,
                                      Math.min(
                                        600,
                                        Number(event.target.value) || 1,
                                      ),
                                    ),
                                  },
                                }))
                              }
                              className="ml-1 w-14 rounded border border-slate-200 px-1.5 py-1 text-xs text-slate-600"
                            />
                            s
                          </label>
                          <button
                            type="button"
                            onClick={() => void savePolicy(policy)}
                            className="ml-auto text-xs font-semibold text-indigo-600 hover:text-indigo-700"
                          >
                            保存顺序
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </>
            ) : (
              <>
                <div>
                  <h3 className="font-bold text-slate-900">模型负载</h3>
            <p className="mt-1 text-xs text-slate-400">各模型的负载分布</p>
                </div>
                <div className="mt-4 space-y-3">
                  {models.map((model) => {
                    const primaryFor = displayPolicies.filter(
                      (policy) =>
                        (policyOrders[policy.capability_key] ?? [])[0] ===
                        model.id,
                    );
                    const fallbackFor = displayPolicies.filter((policy) =>
                      (policyOrders[policy.capability_key] ?? [])
                        .slice(1)
                        .includes(model.id),
                    );
                    return (
                      <article
                        key={model.id}
                        className="rounded-xl border border-slate-200 p-4"
                      >
                        <div className="flex items-center gap-3">
                          <ModelTypeIcon type={model.model_type} />
                          <div className="min-w-0 flex-1">
                            <h4 className="truncate font-semibold text-slate-800">
                              {modelName(model)}
                            </h4>
                            <p className="mt-1 text-xs text-slate-400">
                              {model.provider} ·{" "}
                              {healthLabel(modelHealth(model))}
                            </p>
                          </div>
                          <span
                            className={`rounded-full px-2 py-1 text-[11px] font-semibold ${healthClass(modelHealth(model))}`}
                          >
                            {primaryFor.length + fallbackFor.length} 个模块
                          </span>
                        </div>
                        <div className="mt-4 grid gap-3 sm:grid-cols-2">
                          <div>
                            <p className="text-[11px] font-semibold text-slate-400">
                              主用于（第一顺位）
                            </p>
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {primaryFor.length ? (
                                primaryFor.map((policy) => (
                                  <span
                                    key={policy.capability_key}
                                    className="rounded-md bg-indigo-50 px-2 py-1 text-xs text-indigo-700"
                                  >
                                    {
                                      CAPABILITY_DEFAULTS.find(
                                        (item) =>
                                          item.capability_key ===
                                          policy.capability_key,
                                      )?.title
                                    }
                                  </span>
                                ))
                              ) : (
                                <span className="text-xs text-slate-400">
                                  暂无
                                </span>
                              )}
                            </div>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold text-slate-400">
                              备用于（降级链路）
                            </p>
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {fallbackFor.length ? (
                                fallbackFor.map((policy) => (
                                  <span
                                    key={policy.capability_key}
                                    className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600"
                                  >
                                    {
                                      CAPABILITY_DEFAULTS.find(
                                        (item) =>
                                          item.capability_key ===
                                          policy.capability_key,
                                      )?.title
                                    }
                                  </span>
                                ))
                              ) : (
                                <span className="text-xs text-slate-400">
                                  暂无
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </>
            )}
          </section>
        </div>
      )}

      <AIModelDrawer
        open={drawerOpen}
        model={editingModel}
        onClose={() => setDrawerOpen(false)}
        onSaved={reload}
      />
      {routePolicy && (
        <div
          className="fixed inset-0 z-50 bg-slate-950/30"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeRouteEditor();
          }}
        >
          <aside className="absolute right-0 top-0 flex h-full w-full max-w-[460px] flex-col bg-white shadow-2xl">
            <header className="border-b border-slate-200 px-6 py-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold text-indigo-600">
                    AI 能力策略
                  </p>
                  <h2 className="mt-1 text-xl font-bold text-slate-900">
                    编辑降级链路
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {
                      CAPABILITY_DEFAULTS.find(
                        (item) =>
                          item.capability_key === routePolicy.capability_key,
                      )?.title
                    }
                  </p>
                </div>
                <button
                  type="button"
                  onClick={closeRouteEditor}
                  aria-label="关闭"
                  className="grid h-8 w-8 place-items-center rounded-lg text-xl text-slate-400 hover:bg-slate-100"
                >
                  ×
                </button>
              </div>
            </header>
            <div className="flex-1 overflow-y-auto px-6 py-5">
              <div className="rounded-xl bg-indigo-50 px-4 py-3 text-sm text-indigo-800">
                按顺序调用：主用模型失败后，系统会自动尝试下一个备用模型。
              </div>
              <ol className="mt-5 space-y-3">
                {routeDraft.map((id, index) => (
                  <li
                    key={id}
                    className="flex items-center gap-3 rounded-xl border border-slate-200 p-3"
                  >
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-slate-100 text-xs font-bold text-slate-500">
                      {index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-slate-800">
                        {modelName(
                          models.find((model) => model.id === id),
                          id,
                        )}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-400">
                        {index === 0 ? "主用模型" : `备用模型 ${index}`}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <button
                        type="button"
                        aria-label="上移模型"
                        disabled={index === 0}
                        onClick={() => moveRouteModel(index, -1)}
                        className="rounded p-1 text-slate-400 hover:bg-slate-100 disabled:opacity-30"
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        aria-label="下移模型"
                        disabled={index === routeDraft.length - 1}
                        onClick={() => moveRouteModel(index, 1)}
                        className="rounded p-1 text-slate-400 hover:bg-slate-100 disabled:opacity-30"
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        aria-label={index === 0 ? "移除主模型" : "移除备用模型"}
                        onClick={() =>
                          setRouteDraft((current) =>
                            current.filter((item) => item !== id),
                          )
                        }
                        className="rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                      >
                        ×
                      </button>
                    </div>
                  </li>
                ))}
              </ol>
              {routeDraft.length === 0 && (
                <div className="mt-5 rounded-xl border border-dashed border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
                  还没有模型，请先添加一个可用模型。
                </div>
              )}
              <div className="mt-5">
                <label className="text-xs font-semibold text-slate-500">
                  添加到链路
                  <select
                    aria-label="添加模型到链路"
                    defaultValue=""
                    onChange={(event) => {
                      const id = Number(event.target.value);
                      if (id && !routeDraft.includes(id))
                        setRouteDraft((current) => [...current, id]);
                      event.currentTarget.value = "";
                    }}
                    className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-700"
                  >
                    <option value="">选择模型…</option>
                    {eligibleModels(routePolicy)
                      .filter((model) => !routeDraft.includes(model.id))
                      .map((model) => (
                        <option key={model.id} value={model.id}>
                          {modelName(model)}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3">
                <label className="text-xs font-semibold text-slate-500">
                  主用超时（秒）
                  <input
                    aria-label="编辑器主用超时"
                    type="number"
                    min="1"
                    max="600"
                    value={
                      (
                        policyTimeouts[routePolicy.capability_key] ??
                        routePolicy
                      ).timeout_seconds
                    }
                    onChange={(event) =>
                      setPolicyTimeouts((current) => ({
                        ...current,
                        [routePolicy.capability_key]: {
                          ...(current[routePolicy.capability_key] ??
                            routePolicy),
                          timeout_seconds: Math.max(
                            1,
                            Math.min(600, Number(event.target.value) || 1),
                          ),
                        },
                      }))
                    }
                    className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-500">
                  备用超时（秒）
                  <input
                    aria-label="编辑器备用超时"
                    type="number"
                    min="1"
                    max="600"
                    value={
                      (
                        policyTimeouts[routePolicy.capability_key] ??
                        routePolicy
                      ).fallback_timeout_seconds
                    }
                    onChange={(event) =>
                      setPolicyTimeouts((current) => ({
                        ...current,
                        [routePolicy.capability_key]: {
                          ...(current[routePolicy.capability_key] ??
                            routePolicy),
                          fallback_timeout_seconds: Math.max(
                            1,
                            Math.min(600, Number(event.target.value) || 1),
                          ),
                        },
                      }))
                    }
                    className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
              </div>
            </div>
            <footer className="flex justify-end gap-3 border-t border-slate-200 px-6 py-4">
              <button
                type="button"
                onClick={closeRouteEditor}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void saveRoute()}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                保存路由
              </button>
            </footer>
          </aside>
        </div>
      )}
    </section>
  );
}
