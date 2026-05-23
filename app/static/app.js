const state = {
  skills: [],
  workflows: [],
  mcpServers: [],
};

const $ = (id) => document.getElementById(id);

const METRIC_LABELS = {
  "Recall@5": "召回率 Recall@5",
  "MRR@10": "排序质量 MRR@10",
  CitationAccuracy: "首条引用准确率",
  ToolSuccessRate: "工具成功率",
  AgentRunSuccessRate: "Agent 运行成功率",
  "AgentCitationHit@5": "Agent 引用命中率",
  AnswerKeywordCoverage: "答案关键词覆盖率",
  AgentNodeSuccessRate: "节点成功率",
  AgentToolSuccessRate: "工具调用成功率",
  AgentAvgLatencyMs: "平均延迟",
};

const CONFIG_LABELS = {
  bm25_only: "仅 BM25",
  vector_only: "仅向量",
  hybrid_no_rerank: "混合检索",
  hybrid_rerank: "混合 + Rerank",
  hybrid_rerank_metadata: "混合 + Rerank + 元数据",
};

function apiKey() {
  return localStorage.getItem("agent_api_key") || "";
}

function headers(extra = {}) {
  const base = { ...extra };
  const key = apiKey();
  if (key) base["X-API-Key"] = key;
  return base;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: headers(options.headers || {}),
  });
  const text = await response.text();
  let payload = text;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }
  if (!response.ok) {
    const detail = payload && payload.detail ? payload.detail : payload;
    throw new Error(`${response.status} ${JSON.stringify(detail)}`);
  }
  return payload;
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  window.setTimeout(() => el.classList.remove("show"), 2800);
}

function setOutput(id, value) {
  $(id).textContent = typeof value === "string" ? value : pretty(value);
}

function selectTab(name) {
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === name);
  });
}

async function loadHealth() {
  const health = await request("/health");
  $("envLine").textContent = `环境=${health.app_env || "unknown"} 状态=${health.status}`;
  const grid = $("healthGrid");
  grid.innerHTML = "";
  Object.entries(health.dependencies || {}).forEach(([name, item]) => {
    const card = document.createElement("div");
    card.className = "metric";
    card.innerHTML = `
      <strong>${name}</strong>
      <span class="status ${item.status}">${item.status}</span>
      <p>${item.latency_ms ? item.latency_ms.toFixed(2) : "0.00"} ms</p>
      <p>${item.detail || ""}</p>
    `;
    grid.appendChild(card);
  });
}

async function loadRegistries() {
  const [skills, mcpServers, workflows] = await Promise.all([
    request("/skills"),
    request("/mcp/servers"),
    request("/workflows"),
  ]);
  state.skills = skills;
  state.mcpServers = mcpServers;
  state.workflows = workflows;
  fillSelect("skillSelect", skills, "skill_id", "name");
  fillSelect("workflowSelect", workflows, "workflow_id", "workflow_id");
  setOutput("skillsRegistry", skills);
  setOutput("mcpRegistry", mcpServers);
  setOutput("workflowRegistry", workflows);
}

function fillSelect(id, items, valueKey, labelKey) {
  const select = $(id);
  select.innerHTML = "";
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = item[valueKey];
    option.textContent = item[labelKey] || item[valueKey];
    select.appendChild(option);
  });
}

async function runSkill(stream = false) {
  const skillId = $("skillSelect").value;
  const body = {
    question: $("skillQuestion").value,
    session_id: $("skillSession").value,
    inputs: {
      top_k: Number($("skillTopK").value),
    },
  };
  if (!stream) {
    const result = await request(`/skills/${skillId}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setOutput("skillOutput", result);
    return;
  }
  await streamPost(`/skills/${skillId}/stream`, body, "skillOutput");
}

async function runWorkflow(stream = false) {
  const body = {
    question: $("workflowQuestion").value,
    session_id: $("workflowSession").value,
    workflow_id: $("workflowSelect").value,
    top_k: Number($("workflowTopK").value),
    use_llm_planner: $("llmPlanner").checked,
    use_llm_critic: $("llmCritic").checked,
    use_llm_answer: $("llmAnswer").checked,
  };
  if (!stream) {
    const result = await request("/workflows/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setOutput("workflowOutput", result);
    return;
  }
  await streamPost("/workflows/stream", body, "workflowOutput");
}

async function streamPost(path, body, outputId) {
  setOutput(outputId, "");
  const response = await fetch(path, {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    setOutput(outputId, buffer);
  }
}

async function loadTraces() {
  const traces = await request("/traces?limit=30");
  const list = $("traceList");
  list.innerHTML = "";
  traces.forEach((trace) => {
    const item = document.createElement("button");
    item.type = "button";
    item.innerHTML = `${escapeHtml(trace.question.slice(0, 92))}<small>${trace.trace_id}</small>`;
    item.addEventListener("click", () => loadTraceDetail(trace.trace_id));
    list.appendChild(item);
  });
  if (traces[0]) await loadTraceDetail(traces[0].trace_id);
}

async function loadTraceDetail(traceId) {
  const detail = await request(`/traces/${traceId}`);
  setOutput("traceDetail", detail);
}

async function runEval() {
  const datasetName = $("evalDataset").value;
  const includeAgentEval = $("evalAgentMode").value === "true";
  const result = await request("/eval/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_name: datasetName,
      include_agent_eval: includeAgentEval,
    }),
  });
  renderEvalMetrics(result);
  setOutput("evalOutput", result);
}

async function loadEvalDataset() {
  const datasetName = $("evalDataset").value;
  const sampleSize = Number($("evalSampleSize").value);
  const summary = await request(`/eval/dataset?name=${encodeURIComponent(datasetName)}&sample_size=${sampleSize}`);
  renderEvalDataset(summary);
  setOutput("evalOutput", summary);
}

function renderEvalDataset(summary) {
  const summaryGrid = $("evalSummary");
  summaryGrid.innerHTML = "";
  [
    ["评测集", datasetLabel(summary.name)],
    ["样本数", summary.dataset_size],
    ["字段数", summary.fields.length],
    ["消融维度", summary.ablation_dimensions.length],
  ].forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "summary-item";
    card.innerHTML = `<strong>${escapeHtml(String(value))}</strong><span>${escapeHtml(label)}</span>`;
    summaryGrid.appendChild(card);
  });

  renderBarChart("sourceDocChart", summary.source_doc_counts);
  renderBarChart("goldCountChart", summary.gold_count_distribution, " 个 gold");
  renderBarChart("keywordCountChart", summary.keyword_count_distribution, " 个关键词");
  renderEvalCases(summary.sample_cases || []);
}

function renderBarChart(id, values, suffix = "") {
  const chart = $(id);
  chart.innerHTML = "";
  const entries = Object.entries(values || {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, value]) => value), 1);
  entries.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `
      <span class="bar-label" title="${escapeHtml(label)}">${escapeHtml(label)}${escapeHtml(suffix)}</span>
      <span class="bar-track"><span class="bar-fill" style="width: ${(value / max) * 100}%"></span></span>
      <span class="bar-value">${value}</span>
    `;
    chart.appendChild(row);
  });
}

function renderEvalCases(cases) {
  const tbody = $("evalCases");
  tbody.innerHTML = "";
  cases.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(item.question)}</td>
      <td>${escapeHtml(item.source_doc_id || "unknown")}<br><small>${escapeHtml(item.source_section || "")}</small></td>
      <td>${escapeHtml((item.gold_chunk_ids || []).join(", "))}</td>
      <td>${escapeHtml((item.answer_keywords || []).join(", "))}</td>
    `;
    tbody.appendChild(row);
  });
}

function renderEvalMetrics(result) {
  const grid = $("evalMetricCards");
  grid.innerHTML = "";
  $("evalCharts").innerHTML = "";
  $("agentCharts").innerHTML = "";
  const primaryRun = result.runs && result.runs.length ? result.runs[result.runs.length - 1] : null;
  const metrics = primaryRun ? primaryRun.metrics : result.metrics || [];
  metrics.forEach((metric) => {
    const value = formatMetric(metric.name, metric.value);
    const card = document.createElement("div");
    card.className = "metric";
    card.innerHTML = `<strong>${escapeHtml(metricLabel(metric.name))}</strong><p>${escapeHtml(value)}</p>`;
    grid.appendChild(card);
  });
  renderAblationCharts(result.runs || []);
  renderAgentCharts(result.agent_runs || []);
}

function renderAblationCharts(runs) {
  const host = $("evalCharts");
  if (!runs.length) return;
  host.appendChild(sectionTitle("检索消融指标对比"));
  ["Recall@5", "MRR@10", "CitationAccuracy", "ToolSuccessRate"].forEach((metricName) => {
    const values = runs.map((run) => ({
      label: configLabel(run.config.name),
      value: metricValue(run.metrics, metricName),
    }));
    host.appendChild(metricChart(metricName, values));
  });
}

function renderAgentCharts(agentRuns) {
  const host = $("agentCharts");
  if (!agentRuns.length) return;
  host.appendChild(sectionTitle("Agent 端到端评测指标"));
  const metrics = agentRuns[0].metrics || [];
  metrics.forEach((metric) => {
    host.appendChild(metricChart(metric.name, [{ label: agentRuns[0].name, value: metric.value }]));
  });
}

function metricChart(metricName, values) {
  const card = document.createElement("div");
  card.className = "chart-card";
  const max = metricName.toLowerCase().includes("latency")
    ? Math.max(...values.map((item) => item.value), 1)
    : 1;
  card.innerHTML = `<h3>${escapeHtml(metricLabel(metricName))}</h3>`;
  values.forEach((item) => {
    const row = document.createElement("div");
    row.className = "metric-bar-row";
    row.innerHTML = `
      <span class="bar-label" title="${escapeHtml(item.label)}">${escapeHtml(item.label)}</span>
      <span class="bar-track"><span class="bar-fill" style="width: ${Math.max((item.value / max) * 100, 2)}%"></span></span>
      <span class="bar-value">${escapeHtml(formatMetric(metricName, item.value))}</span>
    `;
    card.appendChild(row);
  });
  return card;
}

function sectionTitle(text) {
  const title = document.createElement("h3");
  title.className = "chart-section-title";
  title.textContent = text;
  return title;
}

function metricValue(metrics, name) {
  const metric = metrics.find((item) => item.name === name);
  return metric ? metric.value : 0;
}

function metricLabel(name) {
  return METRIC_LABELS[name] || name;
}

function configLabel(name) {
  return CONFIG_LABELS[name] || name;
}

function datasetLabel(name) {
  return name === "large" ? "大评测集" : "默认集";
}

function formatMetric(name, value) {
  if (name.toLowerCase().includes("latency")) {
    return `${value.toFixed(2)} ms`;
  }
  return `${(value * 100).toFixed(2)}%`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

function bind(id, handler) {
  $(id).addEventListener("click", async () => {
    try {
      await handler();
      toast("完成");
    } catch (error) {
      toast(error.message);
    }
  });
}

function init() {
  $("apiKey").value = apiKey();
  $("saveKey").addEventListener("click", () => {
    localStorage.setItem("agent_api_key", $("apiKey").value.trim());
    toast("已保存");
  });
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => selectTab(button.dataset.tab));
  });

  bind("refreshHealth", loadHealth);
  bind("loadSkills", loadRegistries);
  bind("loadWorkflows", loadRegistries);
  bind("refreshRegistry", loadRegistries);
  bind("runSkill", () => runSkill(false));
  bind("streamSkill", () => runSkill(true));
  bind("runWorkflow", () => runWorkflow(false));
  bind("streamWorkflow", () => runWorkflow(true));
  bind("loadTraces", loadTraces);
  bind("loadEvalDataset", loadEvalDataset);
  bind("runEval", runEval);

  Promise.all([loadHealth(), loadRegistries(), loadEvalDataset()]).catch((error) => toast(error.message));
}

init();
