const DATA_URL = new URL("progress-data.json", window.location.href);

const root = document.getElementById("dashboard-root");
const stageCopy = document.getElementById("stage-copy");
const curatedDate = document.getElementById("curated-date");
const evidenceDate = document.getElementById("evidence-date");
const staleNote = document.getElementById("stale-note");
const loadAnnouncer = document.getElementById("load-announcer");

const STATUS_LABELS = {
  verified: "Verified",
  completed: "Completed",
  active: "In progress",
  planned: "Planned",
  blocked: "Blocked",
  preserved: "Preserved",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function safeHref(value) {
  try {
    const url = new URL(String(value));
    return url.protocol === "https:" ? url.href : "#";
  } catch {
    return "#";
  }
}

function assertDataShape(data) {
  if (!data || typeof data !== "object") throw new Error("data is not an object");
  if (data.schemaVersion !== 1) throw new Error("unsupported schema version");
  if (!data.project || typeof data.project.stage !== "string") throw new Error("project state is missing");
  if (!Array.isArray(data.researchQuestions)) throw new Error("researchQuestions is not an array");
  if (!Array.isArray(data.dependencyRoute)) throw new Error("dependencyRoute is not an array");
  if (!data.verifiedEvidence || typeof data.verifiedEvidence !== "object") {
    throw new Error("verifiedEvidence is missing");
  }
  if (!data.workingMargin || !Array.isArray(data.futurePlan)) throw new Error("planning data is missing");
}

function statusChip(status, label = STATUS_LABELS[status] ?? status) {
  return `<span class="status-chip" data-status="${escapeHtml(status)}">${escapeHtml(label)}</span>`;
}

function formatScore(value, std) {
  const score = Number(value).toFixed(6);
  return std == null ? score : `${score} ± ${Number(std).toFixed(6)}`;
}

function renderResearchRail(questions, availableAnchors) {
  let currentAssigned = false;
  const links = questions
    .map((question) => {
      const available = availableAnchors.has(question.anchor);
      const current = available && !currentAssigned;
      if (current) currentAssigned = true;
      const content = `
        <span>
          <span class="rq-id">${escapeHtml(question.id)}</span>
          <span class="rq-name">${escapeHtml(question.title)}</span>
          <span class="sr-only">状态：${escapeHtml(STATUS_LABELS[question.status] ?? question.status)}</span>
        </span>
      `;
      if (!available) {
        return `
        <li>
          <span
            class="rq-link"
            data-status="${escapeHtml(question.status)}"
            aria-disabled="true"
          >
            ${content}
          </span>
        </li>
        `;
      }
      return `
        <li>
          <a
            class="rq-link"
            href="#${escapeHtml(question.anchor)}"
            data-rq-link="${escapeHtml(question.anchor)}"
            data-status="${escapeHtml(question.status)}"
            ${current ? 'aria-current="true"' : ""}
          >
            ${content}
          </a>
        </li>
      `;
    })
    .join("");

  return `
    <nav class="rq-rail" aria-label="研究问题索引">
      <p class="rq-rail-title">Research questions</p>
      <ol class="rq-list">${links}</ol>
    </nav>
  `;
}

function renderDependencyRoute(route) {
  const items = route
    .map(
      (item) => `
        <li class="route-item" data-status="${escapeHtml(item.status)}">
          <span class="route-node" aria-hidden="true"></span>
          <div class="route-copy">
            <strong>${escapeHtml(item.label)}</strong>
            <p>${escapeHtml(item.detail)}</p>
            <span class="sr-only">状态：${escapeHtml(STATUS_LABELS[item.status] ?? item.status)}</span>
          </div>
          <span class="route-rq">${escapeHtml(item.rq)}</span>
        </li>
      `,
    )
    .join("");

  return `
    <section id="project-story" class="story-section" aria-labelledby="route-title">
      <div class="section-head">
        <div>
          <p class="section-kicker">研究路径</p>
          <h2 id="route-title">按证据依赖推进</h2>
        </div>
        <p class="data-scope">Research question → experiment → evidence → thesis</p>
      </div>
      <ol class="route-list">${items}</ol>
    </section>
  `;
}

function renderMetricChart(dataset, options = {}) {
  const anchorByRq = options.anchorByRq ?? {};
  const usedAnchors = new Set();
  const rows = dataset.models
    .map((model) => {
      const anchor = anchorByRq[model.rq];
      const id = anchor && !usedAnchors.has(anchor) ? ` id="${escapeHtml(anchor)}"` : "";
      if (anchor) usedAnchors.add(anchor);
      const value = Math.max(0, Math.min(1, Number(model.value)));
      return `
        <li class="metric-item"${id}>
          <a
            class="metric-row"
            href="${safeHref(model.sourceHref ?? dataset.sourceHref)}"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="${escapeHtml(`${model.experiment} ${model.label}，Macro-F1 ${formatScore(model.value, model.std)}，打开证据`)}"
          >
            <span class="metric-label">
              <span class="metric-exp">${escapeHtml(model.experiment)} · ${escapeHtml(model.rq)}</span>
              <span class="metric-name">${escapeHtml(model.label)}</span>
            </span>
            <span class="metric-track" aria-hidden="true">
              <span class="metric-fill" style="--value: ${value}"></span>
            </span>
            <span class="metric-value">${escapeHtml(formatScore(model.value, model.std))}</span>
            <span class="metric-note">${escapeHtml(model.note)}</span>
          </a>
        </li>
      `;
    })
    .join("");

  return `
    <figure class="metric-chart">
      <ul class="metric-list">${rows}</ul>
      <div class="axis" aria-hidden="true">
        <div class="axis-scale">
          <span>0.00</span><span>0.25</span><span>0.50</span><span>0.75</span><span>1.00</span>
        </div>
      </div>
      <figcaption class="chart-caption">
        0–1 完整量尺；数值链接到对应证据台账。误差项为三随机种子的 sample standard deviation。
      </figcaption>
    </figure>
  `;
}

function renderFindings(findings) {
  return `
    <div class="finding-list">
      ${findings
        .map(
          (finding) => `
            <article class="finding" data-status="${escapeHtml(finding.status)}">
              <strong>${escapeHtml(finding.title)}</strong>
              <p>${escapeHtml(finding.body)}</p>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderErrorAnalysis(errorAnalysis) {
  return `
    <section class="error-strip" aria-labelledby="error-title">
      <div class="subsection-head">
        <h3 id="error-title">冻结错误结构</h3>
        <a href="${safeHref(errorAnalysis.sourceHref)}" target="_blank" rel="noopener noreferrer">EXP-017 · 查看证据</a>
      </div>
      <div class="error-grid">
        ${errorAnalysis.metrics
          .map(
            (metric) => `
              <div class="error-metric">
                <span class="error-value">${escapeHtml(metric.value)}</span>
                <span class="error-label">${escapeHtml(metric.label)}</span>
                <span class="error-detail">${escapeHtml(metric.detail)}</span>
              </div>
            `,
          )
          .join("")}
      </div>
      <p class="boundary-note">${escapeHtml(errorAnalysis.boundary)}</p>
    </section>
  `;
}

function renderTweetEval(tweetEval) {
  return `
    <section class="story-section evidence-sheet" aria-labelledby="tweeteval-title">
      <div class="section-head">
        <div>
          <p class="section-kicker">已验证证据 · TweetEval</p>
          <h2 id="tweeteval-title">${escapeHtml(tweetEval.label)}</h2>
        </div>
        <p class="data-scope">${escapeHtml(tweetEval.evaluation)}</p>
      </div>
      <div class="evidence-intro">
        <p class="gate-label">${escapeHtml(tweetEval.gate)} · Verified</p>
        ${statusChip("verified")}
      </div>
      ${renderMetricChart(tweetEval, {
        anchorByRq: { "RQ-B1": "rq-b1", "RQ-B2": "rq-b2", "RQ-B3": "rq-b3" },
      })}
      ${renderFindings(tweetEval.findings)}
      ${renderErrorAnalysis(tweetEval.errorAnalysis)}
      <details class="limitations">
        <summary>这组 test 结果不能再被怎样使用？</summary>
        <p>TweetEval test 已在 EXP-016 中一次性消费并冻结。后续可做描述性分析，但不能用它继续挑模型、调参、改标签、改 prompt 或替换既有 gate。</p>
      </details>
    </section>
  `;
}

function renderDecoderMatrix(matrix) {
  const body = matrix.rows
    .map(
      (row) => `
        <tr>
          <th scope="row">${escapeHtml(row.decoder)}</th>
          ${row.cells
            .map(
              (cell, index) => `
                <td data-prompt="${escapeHtml(matrix.columns[index])}">
                  <span class="matrix-primary">${escapeHtml(Number(cell.macroF1).toFixed(6))}</span>
                  <span class="matrix-meta">
                    <span>${escapeHtml(cell.experiment)} · Macro-F1</span>
                    <span>parser ${escapeHtml(cell.parserValid)}</span>
                    <span>median ${escapeHtml(cell.medianLatency)}</span>
                    <span>peak ${escapeHtml(cell.peakMemory)}</span>
                  </span>
                </td>
              `,
            )
            .join("")}
        </tr>
      `,
    )
    .join("");

  return `
    <section id="rq-g2" class="matrix-wrap" aria-labelledby="matrix-title">
      <div class="subsection-head">
        <h3 id="matrix-title">Decoder × prompt 2×2</h3>
        <a href="${safeHref(matrix.sourceHref)}" target="_blank" rel="noopener noreferrer">EXP-025/026 · 查看证据</a>
      </div>
      <table class="decoder-table">
        <caption class="chart-caption">GoEmotions dev；每格依次展示 Macro-F1、parser 有效率、中位生成延迟与峰值 MLX memory。</caption>
        <thead>
          <tr>
            <th scope="col">Decoder</th>
            ${matrix.columns.map((column) => `<th scope="col">${escapeHtml(column)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
      <p class="matrix-finding">${escapeHtml(matrix.finding)}</p>
    </section>
  `;
}

function renderGoEmotions(goEmotions) {
  return `
    <section id="rq-g1" class="story-section evidence-sheet" aria-labelledby="goemotions-title">
      <div class="section-head">
        <div>
          <p class="section-kicker">已验证证据 · GoEmotions</p>
          <h2 id="goemotions-title">${escapeHtml(goEmotions.label)}</h2>
        </div>
        <p class="data-scope">${escapeHtml(goEmotions.evaluation)}</p>
      </div>
      <div class="evidence-intro">
        <p class="gate-label">${escapeHtml(goEmotions.gate)}</p>
        ${statusChip("preserved", "DEV ONLY")}
      </div>
      ${renderMetricChart(goEmotions)}
      <section class="error-strip" aria-labelledby="tail-title">
        <div class="subsection-head">
          <h3 id="tail-title">简单基线暴露的长尾</h3>
        </div>
        <div class="error-grid">
          <div class="error-metric">
            <span class="error-value">${escapeHtml(goEmotions.longTail.emptyRate)}</span>
            <span class="error-label">空预测</span>
            <span class="error-detail">${escapeHtml(goEmotions.longTail.emptyPredictions)}</span>
          </div>
          <div class="error-metric">
            <span class="error-value">${escapeHtml(goEmotions.longTail.zeroRecallLabels.length)}</span>
            <span class="error-label">零召回标签</span>
            <span class="error-detail">TF-IDF OVR · threshold 0.5</span>
          </div>
          <div class="error-metric error-metric-wide">
            <span class="error-label">labels</span>
            <span class="error-detail">${escapeHtml(goEmotions.longTail.zeroRecallLabels.join(" · "))}</span>
          </div>
        </div>
        <p class="boundary-note">${escapeHtml(goEmotions.longTail.boundary)}</p>
      </section>
      ${goEmotions.decoderMatrix?.rows?.length ? renderDecoderMatrix(goEmotions.decoderMatrix) : ""}
      <details class="limitations">
        <summary>为什么这些分数不能和 TweetEval 横向比较？</summary>
        <p>TweetEval 是四分类单标签 official test；GoEmotions 是 28 标签多标签 dev，任务定义、split 与评估协议不同。GoEmotions 的 BERT 结果也不能包装为 official test 或公开 benchmark。</p>
      </details>
    </section>
  `;
}

function renderPlan(plan) {
  return `
    <section class="story-section" aria-labelledby="plan-title">
      <div class="section-head">
        <div>
          <p class="section-kicker">后续依赖</p>
          <h2 id="plan-title">未来工作只沿证据依赖推进</h2>
        </div>
        <p class="data-scope">No model demo in V1</p>
      </div>
      <ol class="plan-list">
        ${plan
          .map(
            (item) => `
              <li class="plan-item">
                <span class="plan-label">${escapeHtml(item.label)}</span>
                <div class="plan-copy">
                  <strong>${escapeHtml(item.title)}</strong>
                  <p>${escapeHtml(item.detail)}</p>
                </div>
                ${statusChip(item.status)}
              </li>
            `,
          )
          .join("")}
      </ol>
    </section>
  `;
}

function renderStory(data) {
  const tweetEval = data.verifiedEvidence.tweetEval;
  const goEmotions = data.verifiedEvidence.goEmotions;
  const evidenceCount = [tweetEval, goEmotions].filter((dataset) => Array.isArray(dataset?.models) && dataset.models.length > 0).length;

  if (evidenceCount === 0) {
    return `
      <main class="story">
        ${renderDependencyRoute(data.dependencyRoute)}
        <section class="load-state" aria-labelledby="no-evidence-title">
          <p class="section-kicker">Evidence gate</p>
          <h2 id="no-evidence-title">暂无 Verified 证据</h2>
          <p>项目路线仍可查看；定量结果会在 Evidence Log 中晋升为 Verified 后进入这里。</p>
        </section>
        ${renderPlan(data.futurePlan)}
      </main>
    `;
  }

  return `
    <main class="story">
      ${renderDependencyRoute(data.dependencyRoute)}
      ${tweetEval?.models?.length ? renderTweetEval(tweetEval) : ""}
      ${goEmotions?.models?.length ? renderGoEmotions(goEmotions) : ""}
      ${renderPlan(data.futurePlan)}
    </main>
  `;
}

function renderNextAction(next, className = "margin-block next-action") {
  return `
    <section class="${escapeHtml(className)}" aria-label="唯一下一步行动">
      <p class="margin-label">Single next action</p>
      ${statusChip(next.status)}
      <h2>${escapeHtml(next.title)}</h2>
      <p class="margin-copy">${escapeHtml(next.detail)}</p>
      <a class="margin-source" href="${safeHref(next.sourceHref)}" target="_blank" rel="noopener noreferrer">打开对应 Roadmap →</a>
    </section>
  `;
}

function renderWorkingMargin(margin, privacy) {
  return `
    <aside class="working-margin" aria-label="当前行动与研究边界">
      ${renderNextAction(margin.nextAction)}

      <section class="margin-block">
        <p class="margin-label">Blocker</p>
        <ul class="margin-list">
          ${margin.blockers
            .map(
              (blocker) => `
                <li class="blocker-item">
                  <strong>${escapeHtml(blocker.title)}</strong>
                  <p>${escapeHtml(blocker.detail)}</p>
                </li>
              `,
            )
            .join("")}
        </ul>
      </section>

      <section class="margin-block">
        <p class="margin-label">Test gates</p>
        <ul class="gate-list">
          ${margin.testGates
            .map(
              (gate) => `
                <li class="gate-item">
                  <div>
                    <strong>${escapeHtml(gate.label)}</strong>
                    <p>${escapeHtml(gate.detail)}</p>
                  </div>
                  ${statusChip(gate.status)}
                </li>
              `,
            )
            .join("")}
        </ul>
      </section>

      <section class="margin-block">
        <p class="margin-label">Recent changes</p>
        <ol class="change-list">
          ${margin.recentChanges
            .map(
              (change) => `
                <li class="change-item">
                  <time class="change-date" datetime="${escapeHtml(change.date)}">${escapeHtml(change.date.slice(5))}</time>
                  <span>${escapeHtml(change.title)}</span>
                </li>
              `,
            )
            .join("")}
        </ol>
      </section>

      <p class="privacy-note">
        <strong>Public boundary.</strong> ${escapeHtml(privacy.publicData)}
        本页不嵌入：${escapeHtml(privacy.excluded.join("、"))}。
      </p>
    </aside>
  `;
}

function collectAvailableAnchors(data) {
  const anchors = new Set();
  const anchorByRq = new Map(data.researchQuestions.map((question) => [question.id, question.anchor]));
  const tweetEval = data.verifiedEvidence.tweetEval;
  const goEmotions = data.verifiedEvidence.goEmotions;

  for (const model of tweetEval?.models ?? []) {
    const anchor = anchorByRq.get(model.rq);
    if (anchor) anchors.add(anchor);
  }
  if (goEmotions?.models?.length) anchors.add("rq-g1");
  if (goEmotions?.models?.length && goEmotions.decoderMatrix?.rows?.length) anchors.add("rq-g2");
  return anchors;
}

function renderApp(data) {
  const availableAnchors = collectAvailableAnchors(data);
  root.innerHTML = `
    ${renderNextAction(data.workingMargin.nextAction, "margin-block next-action mobile-next-action")}
    ${renderResearchRail(data.researchQuestions, availableAnchors)}
    ${renderStory(data)}
    ${renderWorkingMargin(data.workingMargin, data.privacy)}
  `;
  root.setAttribute("aria-busy", "false");
  loadAnnouncer.textContent = "项目进度与证据已加载。";
  bindResearchRail();
}

function updateHeader(data) {
  stageCopy.textContent = data.project.stage;
  curatedDate.textContent = `页面审校 ${data.project.curatedAt}`;
  evidenceDate.textContent = `证据截至 ${data.project.evidenceThrough}`;

  const evidenceTimestamp = new Date(`${data.project.evidenceThrough}T00:00:00+08:00`).getTime();
  const ageInDays = Math.floor((Date.now() - evidenceTimestamp) / 86_400_000);
  if (Number.isFinite(ageInDays) && ageInDays > Number(data.project.staleAfterDays)) {
    staleNote.textContent = `这份证据快照已超过 ${data.project.staleAfterDays} 天，请先核对 Evidence Log 再引用。`;
    staleNote.hidden = false;
  }
}

function bindResearchRail() {
  const links = [...document.querySelectorAll("[data-rq-link]")];
  const sections = links
    .map((link) => document.getElementById(link.dataset.rqLink))
    .filter(Boolean);
  if (!links.length || !sections.length) return;

  let frame = 0;
  const update = () => {
    frame = 0;
    const threshold = Math.min(190, window.innerHeight * 0.3);
    let active = sections[0].id;
    for (const section of sections) {
      if (section.getBoundingClientRect().top <= threshold) active = section.id;
    }
    for (const link of links) {
      if (link.dataset.rqLink === active) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    }
  };

  const schedule = () => {
    if (frame) return;
    frame = window.requestAnimationFrame(update);
  };

  window.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule, { passive: true });
  update();
}

function renderError(error) {
  root.setAttribute("aria-busy", "false");
  root.innerHTML = `
    <main id="project-story" class="load-state error-state" aria-labelledby="load-error-title">
      <p class="section-kicker">Data unavailable</p>
      <h2 id="load-error-title">进度数据没有加载成功</h2>
      <p>页面没有用旧数字替代当前数据。可直接打开原始记录继续查看。</p>
      <p><code>${escapeHtml(error.message)}</code></p>
      <div class="fallback-links">
        <a href="https://github.com/mingxiangbian/NeuroScience/blob/main/projects/llm-forum-text-emotion-recognition/README.md">打开 README</a>
        <a href="https://github.com/mingxiangbian/NeuroScience/blob/main/projects/llm-forum-text-emotion-recognition/evidence-log.md">打开 Evidence Log</a>
        <a href="https://github.com/mingxiangbian/NeuroScience/blob/main/projects/llm-forum-text-emotion-recognition/research-roadmap.md">打开 Roadmap</a>
      </div>
    </main>
  `;
  loadAnnouncer.setAttribute("role", "alert");
  loadAnnouncer.textContent = "项目进度数据没有加载成功，请打开原始记录。";
  stageCopy.textContent = "当前无法核对项目状态；请改看原始记录。";
  curatedDate.textContent = "页面数据不可用";
  evidenceDate.textContent = "";
}

async function loadProgress() {
  try {
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`progress-data.json · HTTP ${response.status}`);
    const data = await response.json();
    assertDataShape(data);
    updateHeader(data);
    renderApp(data);
  } catch (error) {
    renderError(error instanceof Error ? error : new Error(String(error)));
  }
}

void loadProgress();
