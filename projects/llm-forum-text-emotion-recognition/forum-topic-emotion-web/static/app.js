"use strict";
const $ = id => document.getElementById(id);
const labels = ["love", "joy", "surprise", "anger", "sadness", "fear"];
const names = {queued:"排队中",fetching:"采集中",snapshot_sealed:"快照已封存",inferencing:"推理中",aggregating:"聚合中",completed:"已完成",completed_with_fallback:"已完成 · 含降级",failed:"失败",cancel_requested:"正在取消",cancelled:"已取消",deleting:"正在删除"};
const modes = {m1_only:"M1 only",research:"Research",demo:"Demo"};
let currentId = null, jobs = [], currentRows = [], currentData = null;
let authenticated = false, refreshing = false, filename = "pasted.jsonl", detailVersion = null;
const fmt = value => value == null ? "—" : new Intl.NumberFormat("zh-CN", {maximumFractionDigits:2}).format(value);
const pct = value => value == null ? "—" : `${(value * 100).toFixed(1)}%`;
const date = value => value ? new Date(typeof value === "number" ? value * 1000 : value).toLocaleString("zh-CN", {hour12:false}) : "无日期";

function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
function approvedLicenseUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol === "https:" && ["creativecommons.org", "www.creativecommons.org"].includes(url.hostname)
        && /^\/licenses\/[a-z-]+\/\d+\.\d+\/?$/.test(url.pathname) && !url.username && !url.password
        && !url.port && !url.search && !url.hash) return url.href;
  } catch { /* Missing and unapproved URLs are not links. */ }
  return null;
}
function notice(message) {
  $("notice").textContent = message; $("notice").hidden = false;
  clearTimeout(notice.timer); notice.timer = setTimeout(() => $("notice").hidden = true, 6000);
}
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers:{"Content-Type":"application/json", ...options.headers}});
  if (response.status === 401) { setAuth(false); throw new Error("访问令牌无效或会话已过期"); }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail === "runtime_safety_stopped" ? "资源安全门已停止运行器，后续任务不会自动启动。请先检查失败任务的记录。" : body.detail || `请求失败 (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}
function setAuth(value) {
  authenticated = value; $("workspace").hidden = !value; $("login-panel").hidden = value; $("logout").hidden = !value;
}
async function loadSources() {
  const result = await api("/api/sources");
  for (const source of result.sources) {
    const option = [...$("source").options].find(item => item.value === source.id);
    if (option) option.disabled = !source.available;
  }
}
function showNew() {
  currentId = null; detailVersion = null; currentData = null;
  $("new-panel").hidden = false; $("detail-panel").hidden = true; renderJobs(); $("job-name").focus();
}
function renderJobs() {
  const root = $("job-list"); root.replaceChildren();
  if (!jobs.length) { root.append(el("p", "尚无任务。创建一次分析，快照与结果将保存在本机。", "empty")); return; }
  for (const job of jobs) {
    const button = el("button", undefined, "job-button"); button.type = "button";
    button.setAttribute("aria-current", String(job.id === currentId));
    button.append(el("span", job.name, "name"), el("small", `${names[job.state] || job.state} · ${job.completed_items}/${job.total_items}`));
    button.onclick = () => selectJob(job.id); root.append(button);
  }
}
async function selectJob(id) {
  currentId = id; detailVersion = null; $("new-panel").hidden = true; $("detail-panel").hidden = false;
  renderJobs(); await loadDetail();
}
async function refresh() {
  if (!authenticated || refreshing) return;
  refreshing = true;
  try { jobs = (await api("/api/jobs")).jobs; renderJobs(); if (currentId) await loadDetail(); }
  catch (error) { notice(error.message); }
  finally { refreshing = false; }
}
async function loadDetail() {
  const id = currentId; if (!id) return;
  $("detail-panel").setAttribute("aria-busy", "true");
  try {
    const info = await api(`/api/jobs/${id}`);
    const version = `${id}:${info.job.updated_at}:${info.job.raw_expired}:${info.job.items_expired}`;
    if (id !== currentId || version === detailVersion) return;
    const [dashboard, rows] = await Promise.all([api(`/api/jobs/${id}/dashboard`), api(`/api/jobs/${id}/items?limit=500`)]);
    if (id !== currentId) return;
    renderDetail(info.job, dashboard, rows); detailVersion = version;
  } catch (error) { if (id === currentId) notice(error.message); }
  finally { $("detail-panel").setAttribute("aria-busy", "false"); }
}
function definition(root, entries) {
  root.replaceChildren();
  for (const [term, value] of entries) { const row = el("div"); row.append(el("dt", term), el("dd", value)); root.append(row); }
}
function dataTable(root, headings, rows, caption) {
  root.replaceChildren();
  const wrap = el("div", undefined, "table-wrap"); wrap.tabIndex = 0;
  wrap.setAttribute("role", "region"); wrap.setAttribute("aria-label", caption);
  const table = el("table"), head = el("tr"), thead = el("thead"), body = el("tbody");
  table.append(el("caption", caption, "table-caption"));
  for (const title of headings) { const cell = el("th", title); cell.scope = "col"; head.append(cell); }
  thead.append(head); table.append(thead);
  for (const values of rows) { const row = el("tr"); for (const value of values) row.append(el("td", String(value))); body.append(row); }
  table.append(body); wrap.append(table); root.append(wrap);
}
function renderDetail(job, data, rows) {
  currentData = data;
  $("detail-title").textContent = job.name; $("detail-source").textContent = `${job.source.toUpperCase()} / ${modes[job.mode]}`;
  $("detail-state").textContent = names[job.state] || job.state;
  $("job-meta").textContent = `创建于 ${date(job.created_at)} · 快照 ${job.snapshot_hash ? job.snapshot_hash.slice(0, 12) : "等待采集"} · 全文保留至 ${date(job.raw_expires_at)}`;
  $("job-progress").max = Math.max(1, job.total_items); $("job-progress").value = job.completed_items;
  $("progress-copy").textContent = `${job.completed_items} / ${job.total_items} 条最终结果`;
  const execution = job.progress?.staged_execution;
  const stages = {waiting_m1_quiet:"等待 M1 前的安静窗口", m1_prepass:"M1 计算", waiting_m3_quiet:"M1 已退出，等待 M3 前的安静窗口", m3_replay:"复用本任务 M1 结果，按需执行 M3", completed:"分阶段计算及退出检查已完成"};
  $("execution-progress").hidden = !execution;
  $("execution-progress").textContent = execution ? `${stages[execution.stage] || "分阶段处理中"} · 当前阶段 ${fmt(execution.phase_completed_items)} / ${fmt(execution.phase_total_items)} 条。${execution.stage === "m1_prepass" && job.mode !== "m1_only" ? "最终预测将在后续阶段返回。" : ""}` : "";
  $("job-error").hidden = !job.error_code;
  const stage = job.progress?.source_error?.stage || job.progress?.worker_error?.stage;
  $("job-error").textContent = job.error_code ? `任务停止：${job.error_code}${stage ? `（${stage}）` : ""}。已封存内容保留，不会自动重试。` : "";
  const terminal = ["completed", "completed_with_fallback", "failed", "cancelled"].includes(job.state);
  $("cancel-job").hidden = terminal; $("replay-job").disabled = !terminal || !!job.raw_expired || !job.snapshot_hash;
  $("export-job").href = `/api/jobs/${job.id}/export`;
  $("export-csv").href = `/api/jobs/${job.id}/export.csv`;
  $("export-csv").hidden = !!job.items_expired || !job.snapshot_hash;
  $("clear-raw-job").disabled = !terminal || !!job.raw_expired;
  const summary = data.summary;
  definition($("summary"), [["采样内容 · 对象", fmt(summary.eligible_items)], ["成功预测 / 覆盖率", `${fmt(summary.successful_items)} / ${pct(summary.coverage)}`], ["未检出六标签 · 对象", pct(summary.neutral_rate)], ["精确输入组", fmt(summary.exact_input_groups)]]);
  const available = data.derived?.available === true;
  $("weighting").options[1].disabled = !available; $("trend-resolution").options[1].disabled = !available;
  if (!available) { $("weighting").value = "object_weighted"; $("trend-resolution").value = "daily"; }
  $("derived-unavailable").hidden = available;
  $("derived-unavailable").textContent = "逐条结果已清除，无法重算 Unique-text、周趋势或新增诊断。下方保留原封存的对象口径；缺失视图不记为零。";
  renderViews(); renderDiagnostics(data);
  $("manifest").textContent = JSON.stringify({sampling:data.manifest, object_types:data.object_types, boundary:data.evidence_boundary, undated_items:summary.undated_items, normalized_text_groups:summary.normalized_text_groups, missing_predictions:summary.missing_predictions, derived_schema:data.derived?.schema_version, model_progress:job.progress}, null, 2);
  currentRows = rows.items; renderItems();
  $("items-note").textContent = rows.items_expired ? "逐条结果已按 30 天保留期清除。" : "内容表保留每次真实出现，不随 Unique-text 视图删行。预览最多 280 字符；普通导出不包含全文。";
}
function renderViews() {
  const data = currentData; if (!data) return;
  const available = data.derived?.available === true, unique = $("weighting").value === "normalized_unique_text", metric = $("distribution-metric").value;
  const view = available ? data.derived.views[$("weighting").value] : null;
  const emotions = view ? view.emotions : data.emotions, summary = view?.summary;
  const denominator = metric === "prevalence" ? (unique ? "至少有一次成功预测的规范化文本组" : "成功预测的内容条数") : "六类阳性标签的加权总数";
  const weightNote = unique ? `每组总权重 1，组内成功出现均分权重；不同预测取平均，不选代表、不做 OR。${fmt(summary?.mixed_prediction_groups)} 组有不同预测，${fmt(summary?.partially_predicted_groups)} 组仍有缺失预测。` : "每条来源内容各计一次；相同文本的多次真实出现保留。";
  const coverageNote = summary ? `成功 ${fmt(summary.successful_units)} / ${fmt(summary.eligible_units)} ${unique ? "组" : "条"}，${unique ? "组" : "对象"}覆盖率 ${pct(summary.coverage)}；未检出比例 ${pct(summary.neutral_rate)}，平均标签数 ${fmt(summary.cardinality)}。` : "";
  $("view-note").textContent = `分母：${denominator}。${coverageNote}${weightNote}${metric === "positive_share" ? "有阳性标签时构成比例合计为 100%；无阳性时不可定义。它不是内容出现率。" : "多标签出现率之和可以超过 100%。"}`;
  const root = $("emotion-bars"); root.replaceChildren();
  for (const emotion of emotions) {
    const row = el("div", undefined, "emotion-row"), bar = el("progress"); bar.max = 1; bar.value = emotion[metric] || 0;
    bar.setAttribute("aria-label", `${emotion.label} ${pct(emotion[metric])}`);
    row.append(el("span", emotion.label), bar, el("output", pct(emotion[metric])), el("small", fmt(emotion.count))); root.append(row);
  }
  renderTrend(view, metric, unique);
  renderStrata(view, metric);
}
function renderStrata(view, metric) {
  for (const [kind, id, title] of [["object_type", "object-strata", "对象类型"], ["route_requested", "route-strata", "实际请求路由"]]) {
    const strata = view?.strata?.[kind];
    if (!strata) { $(id).replaceChildren(el("p", `${title}的分层视图未封存；明细清除后无法补算。`, "empty")); continue; }
    const rows = strata.map(group => [group.group, `${fmt(group.summary.successful_units)} / ${fmt(group.summary.eligible_units)}`, ...labels.map(label => pct(group.emotions.find(value => value.label === label)[metric]))]);
    if (!rows.length) { $(id).replaceChildren(el("p", "尚无可分层的已封存对象。", "empty")); continue; }
    dataTable($(id), [title, "成功 / 纳入单位", ...labels], rows, `${title}分层 · ${metric === "prevalence" ? "标签出现率" : "阳性标签构成"}`);
  }
}
function renderTrend(view, metric, unique) {
  const resolution = $("trend-resolution").value, root = $("trend"); let rows;
  if (view) rows = view.trends[resolution].map(bucket => [bucket.date, `${fmt(bucket.summary.successful_units)} / ${fmt(bucket.summary.eligible_units)}`, ...labels.map(label => pct(bucket.emotions.find(emotion => emotion.label === label)[metric]))]);
  else if (metric === "prevalence") rows = currentData.daily.map(day => [day.date, fmt(day.n), ...labels.map(label => pct(day.prevalence[label]))]);
  else { root.replaceChildren(el("p", "封存的旧日趋势未保存该构成口径；逐条结果到期后无法补算。", "empty")); return; }
  if (!rows.length) { root.replaceChildren(el("p", "没有可用于此趋势的来源日期与预测记录。缺日期不补零。", "empty")); return; }
  dataTable(root, [resolution === "weekly" ? "周起始 · UTC" : "日期 · UTC", view ? "成功 / 纳入单位" : "成功条数", ...labels], rows, `${resolution === "weekly" ? "周一开始的周" : "每日"}六标签${metric === "prevalence" ? "出现率" : "阳性构成"}，按${unique ? "文本组" : "对象"}统计`);
  $("trend-note").textContent = `每个${resolution === "weekly" ? "UTC 周（周一开始）" : "UTC 日"}独立${unique ? "归组并均分组内成功出现的权重" : "按内容条数计算"}。不同时间桶的组数不应直接相加作为全期唯一组数。无来源日期的内容不进入趋势，缺少的日期不补零。`;
}
function renderDiagnostics(data) {
  const route = data.routing, costs = route.cost || {}, diagnostics = data.derived?.diagnostics;
  $("routing-note").textContent = "始终按真实内容与 forward 计数，不随 Unique-text 视图变化。成对分歧只覆盖同时获得两模型决策的子集。" + (route.prelude_transfer_reuses > 0 ? "本分阶段任务的逐条 latency_ms 仅含回放阶段，不含 M1 预计算或安静窗口，不是端到端延迟。" : "");
  const scopes = {acknowledged_items_lower_bound:"已回执下界；未完成调用未知", job_cumulative:"任务累计，包含失败尝试", completed_job:"完整任务回执", staged_known_lower_bound:"两阶段已知累计下界；未回执调用未知", staged_job_cumulative:"两阶段完整物理调用累计"}, actual = diagnostics?.routing;
  definition($("routing"), [["计算次数口径", scopes[route.cost_scope] || "对象 / forward"], ["请求路由至 M3（回执）", fmt(route.route_requested)], ["实际请求路由比例", actual ? `${pct(actual.actual_rate)}（n=${actual.actual_known_n}）` : "不可用"], ["假设启用路由的触发比例", actual ? `${pct(actual.hypothetical_rate)}（n=${actual.hypothetical_known_n}）` : "不可用"], ["最终采用 M3", actual ? fmt(actual.m3_used) : fmt(route.paths?.m3 || 0)], ["M1 尝试 / 缓存命中", `${fmt(costs.m1_attempts || 0)} / ${fmt(costs.m1_cache_hit || 0)}`], ["M3 尝试 / 成功", `${fmt(costs.m3_attempts || 0)} / ${fmt(costs.m3_succeeded || 0)}`], ["M3 缓存命中", fmt(costs.m3_cache_hit || 0)], ["降级条数 / 回执比例", actual ? `${fmt(actual.fallback_count)} / ${pct(actual.fallback_rate)}` : fmt(Object.values(route.fallbacks).reduce((a, b) => a + b, 0))], ["成对分歧 / 样本数", `${pct(route.paired_disagreement)} / ${fmt(route.paired_n)}`]]);
  if (Number.isInteger(route.prelude_transfer_reuses)) {
    const row = el("div"); row.append(el("dt", "跨阶段 M1 结果复用（不计 forward）"), el("dd", fmt(route.prelude_transfer_reuses))); $("routing").append(row);
  }
  if (!diagnostics) {
    definition($("diagnostics"), [["新增逐条诊断", "到期后不可重算"], ["原封存 M1 二元熵 (nats)", fmt(data.uncertainty.m1_mean_binary_entropy_nats)]]);
    $("cardinality").textContent = ""; $("token-diagnostics").replaceChildren(el("p", "逐条长度记录已清除，无法计算新增 token 诊断。", "empty")); return;
  }
  const entropy = diagnostics.m1_binary_entropy_nats, margin = diagnostics.m1_threshold_margin;
  definition($("diagnostics"), [["对象覆盖率", `${pct(diagnostics.coverage)}（${diagnostics.successful_items}/${diagnostics.eligible_items}）`], ["平均标签数 / P95", `${fmt(diagnostics.cardinality.mean)} / ${fmt(diagnostics.cardinality.p95)}`], ["M1 二元熵 · 均值 / P95", `${fmt(entropy.mean)} / ${fmt(entropy.p95)}（n=${entropy.n}）`], ["M1 阈值距 · 均值 / 中位数", `${fmt(margin.mean)} / ${fmt(margin.median)}（n=${margin.n}）`], ["无来源日期的对象", fmt(diagnostics.undated_items)]]);
  $("cardinality").textContent = `触发标签数 0–6 的对象计数：${diagnostics.cardinality.counts.map((count, i) => `${i}类 ${count}`).join(" · ")}`;
  const tokenRows = ["m1", "m3"].map(model => {
    const values = diagnostics.tokenlengths[model];
    return [model.toUpperCase(), fmt(values.used_tokens.n), fmt(values.input_tokens.mean), fmt(values.used_tokens.mean), fmt(values.used_tokens.p95), fmt(values.input_tokens.max), values.truncation_n ? `${values.truncated_count} / ${values.truncation_n}（${pct(values.truncated_rate)}）` : "不可用"];
  });
  dataTable($("token-diagnostics"), ["模型", "长度记录 n", "原输入均值", "实际使用均值", "使用长度 P95", "原输入最大值", "截断 / 有记录"], tokenRows, "成功回执的 token 长度；M3 仅对应已获得输出的子集");
}
function renderItems() {
  const root = $("items"), filter = $("label-filter").value; root.replaceChildren(); let shown = 0;
  for (const item of currentRows) {
    const record = item.record, result = item.result, active = result ? labels.filter((_, i) => result.prediction?.[i]) : [];
    if (filter !== "all" && !(filter === "neutral" ? result && active.length === 0 : active.includes(filter))) continue;
    shown++;
    const article = el("article", undefined, "item"), meta = el("div", undefined, "item-meta"); meta.append(el("span", `${record.object_type} · ${date(record.created_at)}`));
    if (record.source_url) { const link = el("a", "查看原来源 ↗"); link.href = record.source_url; link.target = "_blank"; link.rel = "noopener noreferrer"; meta.append(link); }
    else if (record.provenance?.row_number) meta.append(el("span", `${record.provenance.filename} · 第 ${record.provenance.row_number} 条`));
    if (record.author_display_name) meta.append(el("span", record.author_display_name));
    if (record.content_license) {
      let license = el("span", record.content_license);
      const href = approvedLicenseUrl(record.provenance?.license_url);
      if (href) {
        license = el("a", record.content_license); license.href = href;
        license.target = "_blank"; license.rel = "noopener noreferrer";
      }
      meta.append(license);
    }
    article.append(meta, el("p", record.display_text ?? "全文预览已按保留期清除。", "item-text"), el("p", result ? `${active.length ? active.join(" · ") : "neutral"}   /   ${result.used_path}${result.fallback_reason ? " · 已降级" : ""}` : "尚未预测", "item-labels"));
    const details = el("details");
    details.append(el("summary", "查看输入指纹与推理记录"), el("pre", JSON.stringify({record_id:record.record_id, model_input_hash:record.model_input_hash, dedup_hash:record.dedup_hash, recorded_source_url:record.recorded_source_url, provenance:record.provenance, result}, null, 2)));
    article.append(details); root.append(article);
  }
  if (!shown) root.append(el("p", currentRows.length ? "没有符合筛选条件的内容。" : "暂无已封存内容。", "empty"));
}
$("login-form").onsubmit = async event => {
  event.preventDefault();
  try { await api("/api/login", {method:"POST", body:JSON.stringify({token:$("token").value})}); $("token").value = ""; setAuth(true); await loadSources(); await refresh(); }
  catch (error) { notice(error.message); }
};
$("logout").onclick = async () => { await api("/api/logout", {method:"POST"}); setAuth(false); currentRows = []; jobs = []; currentId = null; currentData = null; $("items").replaceChildren(); };
$("new-task").onclick = showNew;
$("source").onchange = () => { $("upload-fields").hidden = $("source").value !== "upload"; $("stack-fields").hidden = $("source").value !== "stackexchange"; $("discourse-fields").hidden = $("source").value !== "discourse"; };
$("mode").onchange = () => {
  const mode = $("mode").value; $("budget-field").hidden = mode !== "demo";
  $("mode-note").textContent = {m1_only:"只加载 M1，适合检查采集与任务链路。它不是完整路由系统；假设路由比例仅作观测，不代表实际 M3 调用。", research:"按冻结路由分数和阈值调用 M3；必需的 M3 失败则任务停止，不降级、不按样本排名截取。", demo:"按冻结路由请求 M3；预算耗尽或可降级的 M3 失败时采用本条 M1 结果，并逐条标记。"}[mode];
};
$("mode").onchange();
$("upload-file").onchange = async () => {
  const file = $("upload-file").files[0]; if (!file) return;
  try {
    if (file.size > 5 * 1024 * 1024) throw new Error("文件超过 5 MiB");
    $("upload-content").value = new TextDecoder("utf-8", {fatal:true}).decode(await file.arrayBuffer()); filename = file.name;
    const extension = filename.split(".").pop().toLowerCase(); if (["csv", "json", "jsonl"].includes(extension)) $("format").value = extension;
  } catch (error) { notice(error.message); $("upload-file").value = ""; }
};
$("job-form").onsubmit = async event => {
  event.preventDefault(); const source = $("source").value;
  const payload = {name:$("job-name").value, source, mode:$("mode").value, max_qwen_calls:Number($("qwen-budget").value), audit_rate:0};
  if (source === "upload") payload.upload = {content:$("upload-content").value, format:$("format").value, text_column:$("text-column").value, filename};
  else if (source === "discourse") payload.query = {site:"discuss.python.org", category_id:7, max_topics:Number($("topic-limit").value), max_items:Number($("discourse-item-limit").value)};
  else payload.query = {site:"stackoverflow", tags:$("tags").value, query:$("query").value, from_utc:`${$("from-date").value}T00:00:00Z`, to_utc:`${$("to-date").value}T00:00:00Z`, max_questions:Number($("question-limit").value), max_items:Number($("item-limit").value), include_questions:$("include-questions").checked, include_answers:$("include-answers").checked, include_comments:$("include-comments").checked};
  $("submit-job").disabled = true;
  try { const {job} = await api("/api/jobs", {method:"POST", body:JSON.stringify(payload)}); await refresh(); await selectJob(job.id); notice("任务已创建，快照与结果仅保存在本机。"); }
  catch (error) { notice(error.message); }
  finally { $("submit-job").disabled = false; }
};
$("cancel-job").onclick = async () => { try { await api(`/api/jobs/${currentId}/cancel`, {method:"POST"}); await refresh(); } catch (error) { notice(error.message); } };
$("replay-job").onclick = async () => { try { const {job} = await api(`/api/jobs/${currentId}/replay`, {method:"POST"}); await refresh(); await selectJob(job.id); } catch (error) { notice(error.message); } };
$("delete-job").onclick = () => $("delete-dialog").showModal();
$("clear-raw-job").onclick = () => $("clear-raw-dialog").showModal();
$("clear-raw-dialog").addEventListener("close", async () => {
  if ($("clear-raw-dialog").returnValue !== "confirm") return;
  try { await api(`/api/jobs/${currentId}/raw`, {method:"DELETE"}); await refresh(); notice("全文已清除，元数据、预测和聚合保留。此快照不能再重放。"); }
  catch (error) { notice(error.message); }
});
$("delete-dialog").addEventListener("close", async () => {
  if ($("delete-dialog").returnValue !== "confirm") return; const id = currentId;
  try { await api(`/api/jobs/${id}`, {method:"DELETE"}); showNew(); await refresh(); notice("删除已提交。运行中的子进程退出后将清除任务数据。"); }
  catch (error) { notice(error.message); }
});
$("label-filter").onchange = renderItems;
for (const id of ["weighting", "distribution-metric", "trend-resolution"]) $(id).onchange = renderViews;
const today = new Date(); today.setUTCHours(0, 0, 0, 0);
$("to-date").value = today.toISOString().slice(0, 10);
$("from-date").value = new Date(today.getTime() - 7 * 86400000).toISOString().slice(0, 10);
(async () => { try { jobs = (await api("/api/jobs")).jobs; setAuth(true); renderJobs(); await loadSources(); } catch { setAuth(false); } })();
setInterval(refresh, 5000);
