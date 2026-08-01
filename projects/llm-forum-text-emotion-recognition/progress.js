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
  failed: "Failed",
};

const SPINE_KINDS = ["research-question", "experiment", "evidence", "claim", "next"];

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
  if (data.schemaVersion !== 2) throw new Error("unsupported schema version");
  if (!data.project || typeof data.project.stage !== "string") throw new Error("project state is missing");
  if (!Array.isArray(data.researchQuestions)) throw new Error("researchQuestions is not an array");
  if (!Array.isArray(data.dependencyRoute)) throw new Error("dependencyRoute is not an array");
  if (!data.activeEvidenceSpine || !Array.isArray(data.activeEvidenceSpine.nodes)) {
    throw new Error("activeEvidenceSpine is missing");
  }
  if (data.activeEvidenceSpine.nodes.map((node) => node.kind).join("|") !== SPINE_KINDS.join("|")) {
    throw new Error("activeEvidenceSpine has an unsupported node order");
  }
  if (!data.verifiedEvidence || typeof data.verifiedEvidence !== "object") {
    throw new Error("verifiedEvidence is missing");
  }
  for (const dataset of Object.values(data.verifiedEvidence)) {
    if (!dataset?.comparisonContract || !Array.isArray(dataset.models)) {
      throw new Error("dataset comparison contract is missing");
    }
    for (const model of dataset.models) {
      if (!model.uncertainty?.kind || !model.comparison) {
        throw new Error(`comparison metadata is missing for ${model.experiment ?? "a model"}`);
      }
    }
  }
  if (!data.actionDock?.nextAction || !Array.isArray(data.actionDock.blockers) || !Array.isArray(data.actionDock.testGates)) {
    throw new Error("actionDock is missing");
  }
  if (!Array.isArray(data.futurePlan) || !Array.isArray(data.recentChanges)) {
    throw new Error("planning data is missing");
  }
}

function statusChip(status, label = STATUS_LABELS[status] ?? status) {
  return `<span class="status-chip" data-status="${escapeHtml(status)}">${escapeHtml(label)}</span>`;
}

function clampScore(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.min(1, number)) : 0;
}

function formatScore(value, std) {
  const score = Number(value).toFixed(6);
  return std == null ? score : `${score} ± ${Number(std).toFixed(6)}`;
}

function formatSigned(value, digits = 6) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "N/A";
  if (number === 0) return Number(0).toFixed(digits);
  return `${number > 0 ? "+" : "−"}${Math.abs(number).toFixed(digits)}`;
}

function renderActionDock(actionDock) {
  const next = actionDock.nextAction;
  return `
    <section class="action-dock" aria-labelledby="action-dock-title" aria-label="当前行动、阻塞与测试门">
      <h2 id="action-dock-title" class="sr-only">当前行动、阻塞与测试门</h2>

      <article class="action-panel action-next">
        <div class="action-heading">
          <p class="action-label">Single next action</p>
          ${statusChip(next.status)}
        </div>
        <h3>${escapeHtml(next.title)}</h3>
        <p>${escapeHtml(next.detail)}</p>
        <a href="${safeHref(next.sourceHref)}" target="_blank" rel="noopener noreferrer">打开当前依据 →</a>
      </article>

      <section class="action-panel action-blockers" aria-labelledby="blocker-title">
        <div class="action-heading">
          <p id="blocker-title" class="action-label">Blockers</p>
          <span class="action-count">${actionDock.blockers.length}</span>
        </div>
        <ul class="blocker-list">
          ${actionDock.blockers
            .map(
              (blocker) => `
                <li data-status="${escapeHtml(blocker.status)}">
                  <div>${statusChip(blocker.status)}</div>
                  <strong>${escapeHtml(blocker.title)}</strong>
                  <p>${escapeHtml(blocker.detail)}</p>
                </li>
              `,
            )
            .join("")}
        </ul>
      </section>

      <section class="action-panel action-gates" aria-labelledby="gates-title">
        <div class="action-heading">
          <p id="gates-title" class="action-label">Test gates</p>
          <span class="action-count">${actionDock.testGates.length}</span>
        </div>
        <ul class="gate-list">
          ${actionDock.testGates
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
    </section>
  `;
}

function renderResearchRail(questions, availableAnchors) {
  const links = questions
    .map((question) => {
      const available = availableAnchors.has(question.anchor);
      const content = `
        <span class="rq-id">${escapeHtml(question.id)}</span>
        <span class="rq-name">${escapeHtml(question.title)}</span>
        <span class="rq-status">${escapeHtml(STATUS_LABELS[question.status] ?? question.status)}</span>
      `;

      if (!available) {
        return `
          <li>
            <span class="rq-link" data-status="${escapeHtml(question.status)}" aria-disabled="true">
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
            data-project-active="${question.status === "active" ? "true" : "false"}"
          >
            ${content}
          </a>
        </li>
      `;
    })
    .join("");

  return `
    <nav class="rq-rail" aria-label="研究问题索引">
      <div>
        <p class="rq-rail-title">Research questions</p>
        <p class="rq-rail-note">点击定位到该问题的已验证证据；状态与当前滚动位置分别表达。</p>
      </div>
      <ol class="rq-list">${links}</ol>
    </nav>
  `;
}

function renderEvidenceSpine(spine) {
  const nodes = spine.nodes
    .map(
      (node) => `
        <li
          class="spine-node"
          data-kind="${escapeHtml(node.kind)}"
          data-status="${escapeHtml(node.status)}"
          ${node.kind === "next" ? 'aria-current="step" data-active="true"' : ""}
        >
          <span class="spine-marker" aria-hidden="true"></span>
          <span class="spine-label">${escapeHtml(node.label)}</span>
          <span class="spine-ref">${escapeHtml(node.ref)}</span>
          <h3>${escapeHtml(node.title)}</h3>
          <p>${escapeHtml(node.detail)}</p>
          ${node.sourceHref ? `<a href="${safeHref(node.sourceHref)}" target="_blank" rel="noopener noreferrer">查看依据 →</a>` : ""}
        </li>
      `,
    )
    .join("");

  return `
    <section class="story-section evidence-spine" aria-label="当前证据路径" aria-labelledby="spine-title">
      <div class="section-head">
        <div>
          <p class="section-kicker">Active evidence spine</p>
          <h2 id="spine-title">${escapeHtml(spine.title)}</h2>
        </div>
        <p class="data-scope">RQ → EXP → Evidence → Claim → Next</p>
      </div>
      <p class="section-intro">${escapeHtml(spine.summary)}</p>
      <ol class="spine-grid">${nodes}</ol>
    </section>
  `;
}

function renderComparisonContract(contract) {
  const splitLabels = {
    "official-test": "Official test",
    dev: "DEV",
  };
  const taskLabels = {
    "single-label": `Single-label · ${contract.labelCount} classes`,
    "multi-label": `Multi-label · ${contract.labelCount} labels`,
  };
  const gateLabels = {
    consumed: "Frozen · Verified · Consumed",
    closed: "Closed · official test unavailable",
  };

  const items = [
    ["Split", splitLabels[contract.split] ?? contract.split],
    ["Task", taskLabels[contract.taskType] ?? contract.taskType],
    ["Metric", contract.metric],
    ["Scale", `${contract.scale[0]}–${contract.scale[1]}`],
    ["Test gate", gateLabels[contract.testGate] ?? contract.testGate],
  ];

  return `
    <dl class="comparison-contract" aria-label="数据集比较契约">
      ${items
        .map(
          ([term, value]) => `
            <div>
              <dt>${escapeHtml(term)}</dt>
              <dd>${escapeHtml(value)}</dd>
            </div>
          `,
        )
        .join("")}
      <div class="contract-boundary">
        <dt>Comparison</dt>
        <dd>仅限本数据集内部</dd>
      </div>
    </dl>
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

      const value = clampScore(model.value);
      const uncertainty = model.uncertainty;
      const hasWhisker = uncertainty.kind === "sample-standard-deviation" && Number.isFinite(Number(uncertainty.value));
      const low = hasWhisker ? clampScore(value - Number(uncertainty.value)) : value;
      const high = hasWhisker ? clampScore(value + Number(uncertainty.value)) : value;
      const comparison = model.comparison;
      const deltaLabel = comparison.baselineExperiment
        ? `Δ ${formatSigned(comparison.delta)} vs ${comparison.baselineExperiment}`
        : "Comparison reference";
      const comparisonBoundary = comparison.interpretation === "descriptive-only" ? "descriptive only" : comparison.interpretation;
      const accessibleLabel = [
        `${model.experiment} ${model.label}`,
        `Macro-F1 ${formatScore(model.value, model.std)}`,
        uncertainty.label,
        deltaLabel,
        comparisonBoundary,
        "打开证据",
      ].join("，");

      return `
        <li class="metric-item"${id}>
          <a
            class="metric-row"
            data-role="${escapeHtml(model.visualRole)}"
            href="${safeHref(model.sourceHref ?? dataset.sourceHref)}"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="${escapeHtml(accessibleLabel)}"
          >
            <span class="metric-label">
              <span class="metric-exp">${escapeHtml(model.experiment)} · ${escapeHtml(model.rq)}</span>
              <span class="metric-name">${escapeHtml(model.label)}</span>
              <span class="metric-uncertainty">${escapeHtml(uncertainty.label)}</span>
            </span>
            <span
              class="metric-plot"
              style="--value: ${value}; --low: ${low}; --high: ${high}"
              aria-hidden="true"
            >
              ${hasWhisker ? '<span class="metric-whisker"></span>' : ""}
              <span class="metric-dot"></span>
            </span>
            <span class="metric-reading">
              <strong>${escapeHtml(formatScore(model.value, model.std))}</strong>
              <span class="metric-delta" data-interpretation="${escapeHtml(comparison.interpretation)}">${escapeHtml(deltaLabel)}</span>
            </span>
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
        点位使用 0–1 完整量尺；whisker 表示三随机种子的 ±1 sample SD。单次运行明确标注，不制造误差范围。
      </figcaption>
    </figure>
  `;
}

function renderFindings(findings) {
  return `
    <div class="finding-list" aria-label="关键结论">
      ${findings
        .map(
          (finding) => `
            <article class="finding" data-status="${escapeHtml(finding.status)}">
              <div class="finding-meta">
                <span>${escapeHtml(finding.rq)}</span>
                <span>${escapeHtml(finding.experiment)}</span>
                <strong>${escapeHtml(finding.delta)}</strong>
              </div>
              <h3>${escapeHtml(finding.title)}</h3>
              <p>${escapeHtml(finding.body)}</p>
              <div class="finding-foot">
                <span>${escapeHtml(finding.next)}</span>
                <a href="${safeHref(finding.sourceHref)}" target="_blank" rel="noopener noreferrer">Evidence →</a>
              </div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderErrorAnalysis(errorAnalysis) {
  return `
    <details class="details-panel error-details">
      <summary>
        <span>冻结错误结构</span>
        <span>EXP-017 · 按需展开</span>
      </summary>
      <div class="details-body">
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
        <a class="details-source" href="${safeHref(errorAnalysis.sourceHref)}" target="_blank" rel="noopener noreferrer">查看 EXP-017 证据 →</a>
      </div>
    </details>
  `;
}

function renderTweetEval(tweetEval) {
  return `
    <section id="dataset-tweeteval" class="story-section dataset-lane" aria-labelledby="tweeteval-title">
      <div class="section-head">
        <div>
          <p class="section-kicker">Dataset lane · Verified evidence</p>
          <h2 id="tweeteval-title">${escapeHtml(tweetEval.label)}</h2>
        </div>
        <div class="lane-state">
          ${statusChip("verified")}
          <span>仅限数据集内比较</span>
        </div>
      </div>
      ${renderComparisonContract(tweetEval.comparisonContract)}
      ${renderMetricChart(tweetEval, {
        anchorByRq: { "RQ-B1": "rq-b1", "RQ-B2": "rq-b2", "RQ-B3": "rq-b3" },
      })}
      ${renderFindings(tweetEval.findings)}
      ${renderErrorAnalysis(tweetEval.errorAnalysis)}
      <details class="details-panel limitations">
        <summary><span>证据使用边界</span><span>Test consumed</span></summary>
        <div class="details-body">
          <p>TweetEval test 已在 EXP-016 中一次性消费并冻结。后续可做描述性分析，但不能用它继续挑模型、调参、改标签、改 prompt 或替换既有 gate。</p>
        </div>
      </details>
    </section>
  `;
}

function renderDecoderDiff(comparisons) {
  return `
    <section class="decoder-diff" aria-labelledby="decoder-diff-title">
      <div class="subsection-head">
        <h3 id="decoder-diff-title">Diff only · U − C</h3>
        <p>同一方向比较 unconstrained − constrained</p>
      </div>
      <ul class="diff-list">
        ${comparisons
          .map(
            (comparison) => `
              <li class="diff-row">
                <strong>${escapeHtml(comparison.condition)}</strong>
                <span><b>${escapeHtml(formatSigned(comparison.macroF1Delta))}</b><small>Macro-F1</small></span>
                <span><b>${escapeHtml(formatSigned(comparison.parserDeltaPp, 4))} pp</b><small>parser valid</small></span>
                <span><b>${escapeHtml(formatSigned(comparison.latencyDeltaSeconds, 3))} s</b><small>median latency</small></span>
                <p>${escapeHtml(comparison.interpretation)}</p>
              </li>
            `,
          )
          .join("")}
      </ul>
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
        <a href="${safeHref(matrix.sourceHref)}" target="_blank" rel="noopener noreferrer">EXP-025/026 · Evidence →</a>
      </div>
      <div class="table-wrap">
        <table class="decoder-table">
          <caption>GoEmotions dev；每格依次展示 Macro-F1、parser 有效率、中位生成延迟与峰值 MLX memory。</caption>
          <thead>
            <tr>
              <th scope="col">Decoder</th>
              ${matrix.columns.map((column) => `<th scope="col">${escapeHtml(column)}</th>`).join("")}
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
      ${renderDecoderDiff(matrix.comparisons)}
      <p class="matrix-finding">${escapeHtml(matrix.finding)}</p>
    </section>
  `;
}

function renderLongTail(goEmotions) {
  return `
    <details class="details-panel long-tail-details">
      <summary><span>简单基线暴露的长尾</span><span>EXP-018 · 按需展开</span></summary>
      <div class="details-body">
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
      </div>
    </details>
  `;
}

function renderGoEmotions(goEmotions) {
  return `
    <section id="dataset-goemotions" class="story-section dataset-lane" aria-labelledby="goemotions-title">
      <div class="section-head">
        <div>
          <p class="section-kicker">Dataset lane · DEV evidence</p>
          <h2 id="goemotions-title">${escapeHtml(goEmotions.label)}</h2>
        </div>
        <div class="lane-state">
          ${statusChip("preserved", "DEV ONLY")}
          <span>仅限数据集内比较</span>
        </div>
      </div>
      ${renderComparisonContract(goEmotions.comparisonContract)}
      ${renderMetricChart(goEmotions, { anchorByRq: { "RQ-G1": "rq-g1" } })}
      <p class="comparison-warning"><strong>比较边界：</strong>${escapeHtml(goEmotions.longTail.boundary)}</p>
      ${renderLongTail(goEmotions)}
      ${goEmotions.decoderMatrix?.rows?.length ? renderDecoderMatrix(goEmotions.decoderMatrix) : ""}
      <details class="details-panel limitations">
        <summary><span>为什么不能和 TweetEval 横向比较？</span><span>Different task contract</span></summary>
        <div class="details-body">
          <p>TweetEval 是四分类单标签 official test；GoEmotions 是 28 标签多标签 dev，任务定义、split 与评估协议不同。GoEmotions 的 BERT 结果也不能包装为 official test 或公开 benchmark。</p>
        </div>
      </details>
    </section>
  `;
}

function renderPlan(plan) {
  return `
    <section class="story-section future-work" aria-labelledby="plan-title">
      <div class="section-head">
        <div>
          <p class="section-kicker">After the current dependency</p>
          <h2 id="plan-title">后续只沿证据门推进</h2>
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

function renderCompactLedger(verifiedEvidence) {
  const datasets = [verifiedEvidence.tweetEval, verifiedEvidence.goEmotions].filter(Boolean);
  const rows = datasets
    .flatMap((dataset) =>
      dataset.models.map((model) => {
        const comparison = model.comparison;
        const comparisonText = comparison.baselineExperiment
          ? `${formatSigned(comparison.delta)} vs ${comparison.baselineExperiment}`
          : "Reference";
        return `
          <tr>
            <th scope="row"><a href="${safeHref(model.sourceHref ?? dataset.sourceHref)}" target="_blank" rel="noopener noreferrer">${escapeHtml(model.experiment)}</a></th>
            <td>${escapeHtml(dataset.label)}</td>
            <td>${escapeHtml(model.rq)}</td>
            <td>${escapeHtml(Number(model.value).toFixed(6))}</td>
            <td>${escapeHtml(model.uncertainty.label)}</td>
            <td>${escapeHtml(comparisonText)}</td>
          </tr>
        `;
      }),
    )
    .join("");

  return `
    <details class="details-panel ledger-details">
      <summary><span>完整实验指标台账</span><span>Verified / DEV evidence</span></summary>
      <div class="details-body table-wrap">
        <table class="ledger-table">
          <caption>本页展示的实验、数据集、RQ、Macro-F1、不确定性与 named baseline。</caption>
          <thead>
            <tr><th scope="col">EXP</th><th scope="col">Dataset</th><th scope="col">RQ</th><th scope="col">Macro-F1</th><th scope="col">Uncertainty</th><th scope="col">Comparison</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </details>
  `;
}

function renderTraceability(data) {
  const route = data.dependencyRoute
    .map(
      (item) => `
        <li data-status="${escapeHtml(item.status)}">
          ${statusChip(item.status)}
          <div><strong>${escapeHtml(item.label)}</strong><p>${escapeHtml(item.detail)}</p></div>
          <span>${escapeHtml(item.rq)}</span>
        </li>
      `,
    )
    .join("");
  const changes = data.recentChanges
    .map(
      (change) => `
        <li><time datetime="${escapeHtml(change.date)}">${escapeHtml(change.date)}</time><span>${escapeHtml(change.title)}</span></li>
      `,
    )
    .join("");

  return `
    <section class="traceability" aria-labelledby="traceability-title">
      <div class="section-head">
        <div>
          <p class="section-kicker">Details on demand</p>
          <h2 id="traceability-title">追溯与完整记录</h2>
        </div>
        <p class="data-scope">Overview first · evidence on demand</p>
      </div>
      ${renderCompactLedger(data.verifiedEvidence)}
      <details class="details-panel route-details">
        <summary><span>完整依赖路线与最近变更</span><span>${data.recentChanges.length} updates</span></summary>
        <div class="details-body trace-grid">
          <div>
            <h3>Dependency route</h3>
            <ol class="route-list">${route}</ol>
          </div>
          <div>
            <h3>Recent changes</h3>
            <ol class="change-list">${changes}</ol>
          </div>
        </div>
      </details>
      <p class="privacy-note">
        <strong>Public boundary.</strong> ${escapeHtml(data.privacy.publicData)}
        本页不嵌入：${escapeHtml(data.privacy.excluded.join("、"))}。
      </p>
    </section>
  `;
}

function renderStory(data) {
  const tweetEval = data.verifiedEvidence.tweetEval;
  const goEmotions = data.verifiedEvidence.goEmotions;
  const evidenceCount = [tweetEval, goEmotions].filter((dataset) => Array.isArray(dataset?.models) && dataset.models.length > 0).length;

  if (evidenceCount === 0) {
    return `
      <main id="project-story" class="story">
        ${renderEvidenceSpine(data.activeEvidenceSpine)}
        <section class="load-state" aria-labelledby="no-evidence-title">
          <p class="section-kicker">Evidence gate</p>
          <h2 id="no-evidence-title">暂无 Verified 证据</h2>
          <p>当前证据路径仍可查看；定量结果会在 Evidence Log 中晋升为 Verified 后进入数据集 lane。</p>
        </section>
        ${renderPlan(data.futurePlan)}
      </main>
    `;
  }

  return `
    <main id="project-story" class="story">
      ${renderEvidenceSpine(data.activeEvidenceSpine)}
      <div class="dataset-lanes" aria-label="按数据集分隔的证据">
        ${tweetEval?.models?.length ? renderTweetEval(tweetEval) : ""}
        ${goEmotions?.models?.length ? renderGoEmotions(goEmotions) : ""}
      </div>
      ${renderPlan(data.futurePlan)}
    </main>
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
  if (goEmotions?.decoderMatrix?.rows?.length) anchors.add("rq-g2");
  return anchors;
}

function renderApp(data) {
  const availableAnchors = collectAvailableAnchors(data);
  root.innerHTML = `
    ${renderActionDock(data.actionDock)}
    ${renderResearchRail(data.researchQuestions, availableAnchors)}
    ${renderStory(data)}
    ${renderTraceability(data)}
  `;
  root.setAttribute("aria-busy", "false");
  loadAnnouncer.textContent = "项目行动、证据路径与数据集结果已加载。";
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
      if (link.dataset.rqLink === active) link.setAttribute("aria-current", "location");
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
