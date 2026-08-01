import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const projectsPageUrl = new URL("../projects/index.html", import.meta.url);
const manifestUrl = new URL("../projects/manifest.json", import.meta.url);
const topicPageUrl = new URL("../projects/brain-memory-for-ai-agents/index.html", import.meta.url);
const foundationsPageUrl = new URL("../projects/foundations/index.html", import.meta.url);
const financePageUrl = new URL("../projects/finance/index.html", import.meta.url);
const zajiPageUrl = new URL("../projects/zaji/index.html", import.meta.url);
const emotionPageUrl = new URL("../projects/llm-forum-text-emotion-recognition/index.html", import.meta.url);
const emotionDataUrl = new URL("../projects/llm-forum-text-emotion-recognition/progress-data.json", import.meta.url);
const emotionCssUrl = new URL("../projects/llm-forum-text-emotion-recognition/progress.css", import.meta.url);
const emotionJsUrl = new URL("../projects/llm-forum-text-emotion-recognition/progress.js", import.meta.url);
const foundationsReadmeUrl = new URL("../projects/foundations/README.md", import.meta.url);
const foundationsPlannerUrl = new URL("../projects/foundations/multi-agent-planner.md", import.meta.url);
const foundationsRoadmapUrl = new URL("../projects/foundations/llm-agent-engineer-roadmap.md", import.meta.url);
const fontSourcesUrl = new URL("../assets/fonts/README.md", import.meta.url);
const bookmarkFontUrl = new URL("../assets/fonts/ZhiMangXing-Bookmark.woff2", import.meta.url);

assert.equal(existsSync(projectsPageUrl), true, "projects/ should expose a static project homepage");
assert.equal(existsSync(manifestUrl), true, "projects/ should expose a manifest.json index for project modules");
assert.equal(existsSync(topicPageUrl), true, "brain-memory-for-ai-agents should expose a static topic page");
assert.equal(existsSync(foundationsPageUrl), true, "foundations should expose a static project page");
assert.equal(existsSync(financePageUrl), true, "finance should expose a static learning-reader page");
assert.equal(existsSync(zajiPageUrl), true, "zaji should expose a static public notebook homepage");
assert.equal(existsSync(emotionPageUrl), true, "forum emotion recognition should expose a static progress page");
assert.equal(existsSync(emotionDataUrl), true, "forum emotion recognition should expose sanitized progress data");
assert.equal(existsSync(emotionCssUrl), true, "forum emotion recognition should expose project-scoped styles");
assert.equal(existsSync(emotionJsUrl), true, "forum emotion recognition should expose project-scoped rendering logic");
assert.equal(existsSync(foundationsReadmeUrl), true, "foundations should include a README");
assert.equal(existsSync(foundationsPlannerUrl), true, "foundations should include the reusable multi-agent planner");
assert.equal(existsSync(foundationsRoadmapUrl), true, "foundations should include the LLM/Agent engineer roadmap");
assert.equal(existsSync(fontSourcesUrl), true, "self-hosted font notes should exist");

const projectsHtml = readFileSync(projectsPageUrl, "utf8");
const manifest = JSON.parse(readFileSync(manifestUrl, "utf8"));
const topicHtml = readFileSync(topicPageUrl, "utf8");
const foundationsHtml = readFileSync(foundationsPageUrl, "utf8");
const foundationsRoadmap = readFileSync(foundationsRoadmapUrl, "utf8");
const fontSources = readFileSync(fontSourcesUrl, "utf8");
const emotionHtml = readFileSync(emotionPageUrl, "utf8");
const emotionDataText = readFileSync(emotionDataUrl, "utf8");
const emotionData = JSON.parse(emotionDataText);
const emotionCss = readFileSync(emotionCssUrl, "utf8");
const emotionJs = readFileSync(emotionJsUrl, "utf8");
const bookmarkFontCmap = execFileSync("ttx", ["-q", "-t", "cmap", "-o", "-", fileURLToPath(bookmarkFontUrl)], {
  encoding: "utf8",
});

assert.match(projectsHtml, /<title>项目 \| NeuroScience x AI<\/title>/, "projects page should use the Chinese project directory page title");
assert.match(projectsHtml, /data-page="projects-homepage"/, "projects/ should identify itself as a homepage");
assert.match(projectsHtml, /href="\.\.\/index\.html" aria-label="Back to NeuroScience x AI homepage"/, "projects page logo should link back to the main homepage");
assert.match(projectsHtml, /projects\/manifest\.json/, "projects homepage should load its project modules from projects/manifest.json");
assert.match(projectsHtml, /<h1 id="page-title"><span class="title-line">项目<\/span><\/h1>/, "visible projects page title should be 项目");
assert.match(projectsHtml, /font-family:\s*var\(--title-calligraphy-font\)/, "projects page title should use the shared self-hosted calligraphy font stack");
assert.match(projectsHtml, /data-title-script/, "projects page should tag project title script for bookmark layout");
assert.match(projectsHtml, /\.project-card\[data-title-script="latin"\] h2\s*\{[\s\S]*writing-mode:\s*horizontal-tb/, "latin project titles should render horizontally inside bookmarks");
assert.doesNotMatch(projectsHtml, /github\.com\/mingxiangbian\/NeuroScience\/tree\/main\/projects/i, "projects page should not send users to the GitHub folder listing");
assert.deepEqual(
  manifest.map((project) => project.title),
  ["基石", "语言", "记忆与智能体", "情感与智能体", "投资", "札记"],
  "projects bookmarks should include the registered project titles in display order",
);
assert.equal(manifest.find((project) => project.id === "finance")?.folder, "finance/", "finance should link to its reader page");
assert.equal(manifest.find((project) => project.id === "zaji")?.folder, "zaji/", "zaji should link to its public notebook page");
assert.equal(
  manifest.find((project) => project.id === "llm-forum-text-emotion-recognition")?.folder,
  "llm-forum-text-emotion-recognition/",
  "emotion and agents should link to its project progress page",
);
assert.equal(
  manifest.find((project) => project.id === "ielts-academic")?.folder,
  "language/ielts-academic/",
  "IELTS Academic should be linked through the nested language project folder",
);
assert.equal(
  manifest.find((project) => project.id === "ielts-academic")?.title,
  "语言",
  "IELTS Academic should display as the Chinese language bookmark",
);
assert.match(fontSources, /ZhiMangXing-Regular\.ttf --text='记忆与智能体基石语言投资情感大模型札记'/, "bookmark font subset should include the Chinese project and paper directory titles");
for (const character of new Set(manifest.map((project) => project.title).join(""))) {
  const codePoint = character.codePointAt(0)?.toString(16);
  assert.match(
    bookmarkFontCmap,
    new RegExp(`code="0x${codePoint}"`, "i"),
    `bookmark font subset should contain the visible Chinese bookmark character ${character}`,
  );
}

assert.match(projectsHtml, /@media \(min-width:\s*681px\) and \(max-width:\s*980px\)[\s\S]*?\.project-card\s*\{[\s\S]*?flex:\s*1 1 0[\s\S]*?min-width:\s*0/, "narrow desktop bookmarks should shrink without horizontal overflow");
assert.match(projectsHtml, /@media \(max-width:\s*680px\)[\s\S]*?\.project-grid\s*\{[\s\S]*?display:\s*grid[\s\S]*?grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/, "mobile project directory should arrange six bookmarks in two columns");

assert.match(emotionHtml, /<title>论坛文本情感识别 \| NeuroScience x AI<\/title>/, "emotion project should use the approved page title");
assert.match(emotionHtml, /data-page="emotion-project-ledger"/, "emotion project should identify its page surface");
assert.match(emotionHtml, /href="\.\.\/index\.html"/, "emotion project should link back to the project directory");
assert.match(emotionHtml, /progress-data\.json|progress\.js/, "emotion project should load its sanitized progress data renderer");
assert.match(emotionHtml, /<noscript>[\s\S]*Evidence Log/, "emotion project should keep source links available without JavaScript");
assert.equal(emotionData.schemaVersion, 2, "emotion progress data should use the observatory schema");
assert.equal(emotionData.project.directoryLabel, "情感与智能体", "emotion progress data should preserve the directory label");
assert.equal(emotionData.project.title, "论坛文本情感识别", "emotion progress data should preserve the project title");
assert.deepEqual(
  emotionData.researchQuestions.map((question) => question.id),
  ["RQ-B1", "RQ-B2", "RQ-B3", "RQ-G1", "RQ-G2"],
  "emotion progress page should expose the frozen research-question registry",
);
assert.deepEqual(
  emotionData.verifiedEvidence.tweetEval.models.map((model) => model.value),
  [0.646998, 0.795761, 0.792645, 0.809973],
  "TweetEval should expose only the EXP-016 verified test ladder",
);
assert.deepEqual(
  emotionData.verifiedEvidence.goEmotions.models.map((model) => model.value),
  [0.203644, 0.241164, 0.489435],
  "GoEmotions should expose the verified dev baselines without mixing TweetEval scores",
);
assert.match(emotionData.verifiedEvidence.goEmotions.evaluation, /^DEV ·/, "GoEmotions results should be labeled as dev evidence");
assert.match(emotionData.verifiedEvidence.goEmotions.gate, /test gate 关闭/, "GoEmotions should not imply official test access");
assert.deepEqual(
  emotionData.activeEvidenceSpine.nodes.map((node) => node.kind),
  ["research-question", "experiment", "evidence", "claim", "next"],
  "the active evidence spine should keep the RQ-to-next semantic order",
);
assert.equal(emotionData.activeEvidenceSpine.nodes[0].ref, "RQ-G2", "the active spine should belong to the active LLM research question");
assert.equal(emotionData.activeEvidenceSpine.nodes[1].ref, "EXP-028", "the active spine should preserve the failed probe identity");
assert.equal(emotionData.activeEvidenceSpine.nodes[1].status, "failed", "EXP-028 should remain failed after crossing its frozen resource gate");
assert.equal(emotionData.activeEvidenceSpine.nodes[2].status, "preserved", "the failed artifact audit should remain preserved rather than verified");
assert.match(emotionData.activeEvidenceSpine.nodes[3].detail, /不能|尚无.*Verified/, "the active claim should state that no Verified probe conclusion exists");
assert.notEqual(emotionData.activeEvidenceSpine.nodes[4].ref, "EXP-028", "the successor dependency must not reuse the failed experiment ID");
assert.doesNotMatch(
  emotionData.actionDock.nextAction.title,
  /正式执行 EXP-028/,
  "EXP-028 has already failed its frozen resource gate and must not remain the next run",
);
assert.match(
  `${emotionData.actionDock.nextAction.title} ${emotionData.actionDock.nextAction.detail}`,
  /新的 matched-probe|新实验编号|登记新的/,
  "the next action should preserve EXP-028 and register a successor experiment",
);
assert.deepEqual(
  emotionData.actionDock.testGates.map((gate) => gate.label),
  ["TweetEval", "GoEmotions", "Forum holdout"],
  "the action dock should keep all test gates visible before evidence",
);
assert.deepEqual(
  emotionData.verifiedEvidence.tweetEval.comparisonContract,
  {
    split: "official-test",
    taskType: "single-label",
    labelCount: 4,
    metric: "Macro-F1",
    scale: [0, 1],
    testGate: "consumed",
    comparisonScope: "within-dataset-only",
  },
  "TweetEval should expose a machine-readable within-dataset comparison contract",
);
assert.deepEqual(
  emotionData.verifiedEvidence.goEmotions.comparisonContract,
  {
    split: "dev",
    taskType: "multi-label",
    labelCount: 28,
    metric: "Macro-F1",
    scale: [0, 1],
    testGate: "closed",
    comparisonScope: "within-dataset-only",
  },
  "GoEmotions should expose a separate DEV-only comparison contract",
);
for (const dataset of [emotionData.verifiedEvidence.tweetEval, emotionData.verifiedEvidence.goEmotions]) {
  const models = new Map(dataset.models.map((model) => [model.experiment, model]));
  for (const model of dataset.models) {
    assert.ok(model.uncertainty?.kind, `${model.experiment} should expose an uncertainty kind`);
    assert.ok(model.uncertainty?.label, `${model.experiment} should expose a visible uncertainty label`);
    if (model.uncertainty.kind === "sample-standard-deviation") {
      assert.ok(model.uncertainty.runs >= 3, `${model.experiment} should not draw a sample SD from fewer than three runs`);
      assert.ok(Number.isFinite(model.uncertainty.value), `${model.experiment} should expose a finite sample SD`);
    }
    if (model.comparison.baselineExperiment !== null) {
      const baseline = models.get(model.comparison.baselineExperiment);
      assert.ok(baseline, `${model.experiment} baseline should belong to the same dataset`);
      assert.ok(
        Math.abs(model.comparison.delta - (model.value - baseline.value)) < 1e-9,
        `${model.experiment} delta should match its named baseline`,
      );
    }
  }
}
assert.equal(emotionData.verifiedEvidence.tweetEval.models.find((model) => model.experiment === "EXP-014").comparison.delta, -0.003116, "label smoothing should keep its frozen negative delta");
assert.equal(emotionData.verifiedEvidence.tweetEval.models.find((model) => model.experiment === "EXP-015").comparison.delta, 0.017328, "domain pretraining should keep its frozen positive delta");
assert.equal(emotionData.verifiedEvidence.goEmotions.models.find((model) => model.experiment === "EXP-020").comparison.interpretation, "descriptive-only", "different GoEmotions thresholds should not be presented as a pure ablation");
assert.doesNotMatch(
  JSON.stringify(emotionData.verifiedEvidence),
  /EXP-028|0\.310534|0\.306373/,
  "failed EXP-028 diagnostics must not enter Verified evidence lanes",
);
assert.equal(emotionData.futureInterfaces.inference.endpoint, null, "the future model interface should remain architectural only in V1");
assert.doesNotMatch(emotionDataText, /"raw(?:Text|Sample|Utterance)"\s*:/i, "public progress data should not contain raw-text fields");
assert.match(emotionJs, /renderActionDock\(data\.actionDock\)[\s\S]*renderResearchRail\(data\.researchQuestions,[\s\S]*renderStory\(data\)/, "the single action dock should precede RQ navigation and evidence in DOM order");
assert.doesNotMatch(emotionJs, /mobile-next-action|workingMargin/, "the observatory should not duplicate or split the action context");
assert.match(emotionJs, /renderEvidenceSpine\(data\.activeEvidenceSpine\)/, "the observatory should render the explicit active evidence spine");
assert.match(emotionJs, /aria-label="当前证据路径"/, "the active evidence spine should have an accessible label");
assert.match(emotionJs, /renderComparisonContract\(tweetEval\.comparisonContract\)|renderComparisonContract\(goEmotions\.comparisonContract\)/, "each dataset lane should render its own comparison contract");
assert.match(emotionJs, /metric-whisker/, "multi-seed results should render uncertainty whiskers");
assert.match(emotionJs, /metric-dot/, "full-scale result rows should render point estimates");
assert.match(emotionJs, /baselineExperiment/, "result rows should render named comparison baselines");
assert.match(emotionJs, /0\.00[\s\S]*0\.25[\s\S]*0\.50[\s\S]*0\.75[\s\S]*1\.00/, "result lanes should preserve the full 0-to-1 scale");
assert.match(emotionCss, /\.action-dock\s*\{[\s\S]*grid-template-columns:/, "desktop should expose the unified action dock before evidence");
assert.match(emotionCss, /\.dataset-lanes\s*\{[\s\S]*grid-template-columns:\s*1fr/, "TweetEval and GoEmotions should remain vertically separated lanes");
assert.doesNotMatch(emotionCss, /\.rq-rail\s*\{[^}]*overflow-x:\s*auto/, "RQ navigation should not hide questions behind horizontal scrolling");
assert.doesNotMatch(emotionCss, /\.rq-list\s*\{[^}]*width:\s*max-content/, "RQ navigation should wrap within the viewport");
const emotionMobileCss = emotionCss.slice(emotionCss.indexOf("@media (max-width: 600px)"));
assert.match(emotionMobileCss, /\.action-dock\s*\{[\s\S]*grid-template-columns:\s*1fr/, "mobile should keep the complete action dock in one visible column");
assert.match(emotionMobileCss, /\.rq-list\s*\{[\s\S]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/, "mobile should wrap all research questions into two visible columns");
assert.match(emotionCss, /prefers-reduced-motion:\s*reduce/, "emotion page should respect reduced-motion preferences");
assert.match(emotionJs, /暂无 Verified 证据/, "emotion page should render an explicit no-verified-evidence state");
assert.match(emotionJs, /进度数据没有加载成功/, "emotion page should render a source-linked data error state");
assert.match(emotionJs, /requestAnimationFrame/, "emotion page should throttle its research-question scroll state");
assert.match(emotionJs, /aria-disabled="true"/, "emotion page should disable RQ anchors when their verified section is unavailable");
assert.match(emotionHtml, /<noscript>[\s\S]*#dashboard-root[\s\S]*display:\s*none !important/, "emotion page should hide the permanent loading region when JavaScript is disabled");

assert.match(topicHtml, /<title>Brain Memory for AI Agents \| NeuroScience x AI<\/title>/, "topic page should use the project title");
assert.match(topicHtml, /data-page="project-topic"/, "project topic should identify itself as a topic page");
assert.match(topicHtml, /href="\.\.\/index\.html"[\s\S]*返回项目/, "topic page should link back to the local projects homepage");
for (const file of ["README.md", "research-roadmap.md", "hypotheses.md", "mechanism-to-agent-design.md"]) {
  const renderedUrl = `https://github.com/mingxiangbian/NeuroScience/blob/main/projects/brain-memory-for-ai-agents/${file}`;
  assert.ok(topicHtml.includes(`href="${renderedUrl}"`), `topic page should open ${file} in GitHub's rendered document view`);
}
assert.equal((topicHtml.match(/target="_blank" rel="noopener noreferrer"/g) ?? []).length, 4, "rendered project documents should open safely without replacing the study page");
assert.match(topicHtml, /href="\.\.\/\.\.\/papers\/brain-memory-for-ai-agents\/"/, "topic page should link to the matching local paper topic page");
assert.doesNotMatch(topicHtml, /github\.com\/mingxiangbian\/NeuroScience\/tree\/main\/projects/i, "topic page should not send users to the GitHub folder listing");

assert.match(foundationsHtml, /data-page="foundations-roadmap-reader"/, "foundations page should identify itself as the roadmap reader");
assert.match(foundationsHtml, /id="reader-shell"/, "foundations page should use the reader shell");
assert.match(foundationsHtml, /roadmap\/roadmap-data\.json/, "foundations reader should load generated roadmap data");
assert.doesNotMatch(foundationsHtml, /class="doc-grid"|class="doc-link"/, "foundations page should not remain a document-card homepage");
assert.match(foundationsRoadmap, /Agent \/ LLM Systems Engineer/, "foundations roadmap should target Agent / LLM Systems Engineer interviews");

const financeHtml = readFileSync(financePageUrl, "utf8");
assert.match(financeHtml, /<title>投资 \| NeuroScience x AI<\/title>/, "finance page should use the Chinese project title");
assert.match(financeHtml, /data-page="finance-roadmap-reader"/, "finance should identify itself as a roadmap reader");
assert.match(financeHtml, /data-project-id="finance"/, "finance reader state should remain isolated from Foundations");
assert.match(financeHtml, /data-source="roadmap\/roadmap-data\.json"/, "finance should load its generated roadmap data");
