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
const exp047ProtocolUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/protocols/exp-047-stage-5-generative-lora.md", import.meta.url);
const exp047ConfigUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/config.json", import.meta.url);
const exp047DryRunUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/preflight/exp-047-runner-dry-run.json", import.meta.url);
const exp047DryRunVerificationUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/preflight/exp-047-runner-dry-run-verification.json", import.meta.url);
const exp047Seed44TrainingVerificationUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-44/verification.json", import.meta.url);
const exp047Seed44ReplayVerificationUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-44-replay/verification.json", import.meta.url);
const exp047MatchedAggregateUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/matched-validation-v1/aggregate.json", import.meta.url);
const exp047MatchedReportUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/matched-validation-v1/REPORT.md", import.meta.url);
const exp047MatchedVerificationUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/matched-validation-v1/verification.json", import.meta.url);
const exp048ProtocolUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/protocols/exp-048-frozen-dev-error-analysis.md", import.meta.url);
const exp048ReportUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/REPORT.md", import.meta.url);
const exp048VerificationUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/verification.json", import.meta.url);
const exp049ProtocolUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/test-gate/protocols/exp-049-frozen-test-gate.md", import.meta.url);
const exp049ReportUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/test-gate/runs/exp-049-frozen-test/REPORT.md", import.meta.url);
const exp049VerificationUrl = new URL("../projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/test-gate/runs/exp-049-frozen-test/verification.json", import.meta.url);
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
assert.equal(existsSync(exp047ProtocolUrl), true, "EXP-047 should expose its registered Major protocol");
assert.equal(existsSync(exp047ConfigUrl), true, "EXP-047 should expose its machine-readable frozen config");
assert.equal(existsSync(exp047DryRunUrl), true, "EXP-047 should expose its no-model dry-run report");
assert.equal(existsSync(exp047DryRunVerificationUrl), true, "EXP-047 should expose independent dry-run verification");
assert.equal(existsSync(exp047Seed44TrainingVerificationUrl), true, "EXP-047 should expose seed-44 training verification");
assert.equal(existsSync(exp047Seed44ReplayVerificationUrl), true, "EXP-047 should expose seed-44 replay verification");
assert.equal(existsSync(exp047MatchedAggregateUrl), true, "EXP-047 should expose its matched-validation aggregate");
assert.equal(existsSync(exp047MatchedReportUrl), true, "EXP-047 should expose its matched-validation report");
assert.equal(existsSync(exp047MatchedVerificationUrl), true, "EXP-047 should expose independent matched-validation verification");
assert.equal(existsSync(exp048ProtocolUrl), true, "EXP-048 should expose its frozen error-analysis protocol");
assert.equal(existsSync(exp048ReportUrl), true, "EXP-048 should expose its public error-analysis report");
assert.equal(existsSync(exp048VerificationUrl), true, "EXP-048 should expose independent error-analysis verification");
assert.equal(existsSync(exp049ProtocolUrl), true, "EXP-049 should expose its frozen test protocol");
assert.equal(existsSync(exp049ReportUrl), true, "EXP-049 should expose its formal test report");
assert.equal(existsSync(exp049VerificationUrl), true, "EXP-049 should expose independent test verification");
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
const exp047Config = JSON.parse(readFileSync(exp047ConfigUrl, "utf8"));
const exp047DryRun = JSON.parse(readFileSync(exp047DryRunUrl, "utf8"));
const exp047DryRunVerification = JSON.parse(readFileSync(exp047DryRunVerificationUrl, "utf8"));
const exp047Seed44TrainingVerification = JSON.parse(readFileSync(exp047Seed44TrainingVerificationUrl, "utf8"));
const exp047Seed44ReplayVerification = JSON.parse(readFileSync(exp047Seed44ReplayVerificationUrl, "utf8"));
const exp047MatchedAggregate = JSON.parse(readFileSync(exp047MatchedAggregateUrl, "utf8"));
const exp047MatchedVerification = JSON.parse(readFileSync(exp047MatchedVerificationUrl, "utf8"));
const exp048Verification = JSON.parse(readFileSync(exp048VerificationUrl, "utf8"));
const exp049Verification = JSON.parse(readFileSync(exp049VerificationUrl, "utf8"));
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
  ["RQ-B1", "RQ-B2", "RQ-B3", "RQ-G1", "RQ-G2", "RQ-F1", "RQ-F2"],
  "emotion progress page should expose the frozen research-question registry",
);
assert.deepEqual(
  emotionData.verifiedEvidence.tweetEval.models.map((model) => model.value),
  [0.646998, 0.795761, 0.792645, 0.809973],
  "TweetEval should expose only the EXP-016 verified test ladder",
);
assert.deepEqual(
  emotionData.verifiedEvidence.goEmotions.models.map((model) => model.value),
  [0.196197, 0.233653, 0.450652, 0.488328, 0.444675],
  "GoEmotions should expose the EXP-038 verified test matrix without mixing TweetEval scores",
);
assert.match(emotionData.verifiedEvidence.goEmotions.evaluation, /^Official test ·/, "GoEmotions results should be labeled as official test evidence");
assert.match(emotionData.verifiedEvidence.goEmotions.gate, /Verified · Consumed/, "GoEmotions should expose the consumed frozen test gate");
assert.deepEqual(
  emotionData.activeEvidenceSpine.nodes.map((node) => node.kind),
  ["research-question", "experiment", "evidence", "claim", "next"],
  "the active evidence spine should keep the RQ-to-next semantic order",
);
assert.equal(emotionData.activeEvidenceSpine.nodes[0].ref, "RQ-F1", "the active spine should connect the current same-task model question");
assert.equal(emotionData.activeEvidenceSpine.nodes[1].ref, "EXP-049", "the active spine should identify the frozen formal test gate");
assert.equal(emotionData.activeEvidenceSpine.nodes[1].status, "verified", "EXP-049 should be verified after independent reconstruction");
assert.equal(emotionData.activeEvidenceSpine.nodes[2].ref, "EVID-044", "the active spine should expose the formal test evidence");
assert.equal(emotionData.activeEvidenceSpine.nodes[2].status, "verified", "the formal test evidence should be verified");
assert.match(emotionData.activeEvidenceSpine.nodes[2].detail, /0\.649621|0\.636612|11,457/i, "the verified evidence should preserve both model-family results and the reconstructed prediction count");
assert.match(emotionData.activeEvidenceSpine.nodes[3].detail, /跨 0|encoder|机制/i, "the active claim should preserve the uncertainty and mechanism boundary");
assert.match(emotionData.activeEvidenceSpine.nodes[4].ref, /Stage 9|post-test|read-only/i, "the next dependency should be read-only post-test work");
assert.equal(exp047Config.experiment_id, "EXP-047", "the Stage 5 config should bind the registered experiment ID");
assert.equal(exp047Config.status, "Registered", "the Stage 5 config should remain registered before execution");
assert.equal(exp047Config.execution.authorized, false, "protocol registration must not authorize model execution");
assert.equal(exp047Config.data.test_access, false, "EXP-047 must keep the sealed test closed");
assert.deepEqual(exp047Config.training.seeds, [42, 43, 44], "EXP-047 should freeze all three formal seeds");
assert.equal(exp047Config.generation.batch_size, 1, "EXP-047 reasoning-on inference should use singleton execution");
assert.equal(exp047DryRun.status, "Passed", "EXP-047 no-model dry-run should pass before formal implementation");
assert.equal(exp047DryRun.train.rows, 5995, "EXP-047 dry-run should render every frozen train row");
assert.equal(exp047DryRun.train.truncated_rows, 0, "EXP-047 dry-run should not silently truncate train rows");
assert.equal(exp047DryRun.model_weights_loaded, false, "EXP-047 dry-run must not load model weights");
assert.equal(exp047DryRun.validation_split_accessed, false, "EXP-047 dry-run must keep validation closed");
assert.equal(exp047DryRun.test_split_accessed, false, "EXP-047 dry-run must keep test closed");
assert.equal(exp047DryRunVerification.status, "Passed", "EXP-047 dry-run verification should pass");
assert.equal(exp047DryRunVerification.checks_passed, 11, "EXP-047 dry-run should pass all independent checks");
assert.deepEqual(exp047DryRunVerification.mismatches, [], "EXP-047 dry-run verification should have zero mismatches");
assert.equal(exp047Seed44TrainingVerification.status, "Passed", "EXP-047 seed-44 training verification should pass");
assert.equal(exp047Seed44TrainingVerification.formal_training_verified, true, "EXP-047 seed-44 should pass the formal training gate");
assert.equal(exp047Seed44TrainingVerification.validation_split_accessed, false, "EXP-047 seed-44 training must keep validation closed");
assert.equal(exp047Seed44TrainingVerification.test_split_accessed, false, "EXP-047 seed-44 training must keep test closed");
assert.equal(exp047Seed44ReplayVerification.status, "Passed", "EXP-047 seed-44 replay verification should pass");
assert.deepEqual(
  exp047Seed44ReplayVerification.recalculated.comparison,
  { final_label_equal_count: 16, parser_state_equal_count: 16, raw_output_equal_count: 16, rows: 16 },
  "EXP-047 seed-44 replay should preserve all three singleton equality gates",
);
assert.equal(exp047Seed44ReplayVerification.validation_split_accessed, false, "EXP-047 seed-44 replay must keep validation closed");
assert.equal(exp047Seed44ReplayVerification.test_split_accessed, false, "EXP-047 seed-44 replay must keep test closed");
assert.equal(exp047MatchedAggregate.status, "Verified", "EXP-047 matched validation should be verified");
assert.equal(exp047MatchedAggregate.validation_split_accessed, true, "EXP-047 matched validation should record authorized validation access");
assert.equal(exp047MatchedAggregate.test_split_accessed, false, "EXP-047 matched validation must keep test sealed");
assert.equal(exp047MatchedAggregate.primary_contrast.reference_macro_f1, 0.33359776854597856, "EXP-047 should preserve the matched reference Macro-F1");
assert.equal(exp047MatchedAggregate.primary_contrast.lora_macro_f1_mean, 0.562471137987231, "EXP-047 should preserve the three-seed LoRA mean");
assert.equal(exp047MatchedAggregate.primary_contrast.lora_macro_f1_sample_std, 0.021407872500813357, "EXP-047 should preserve the sample SD");
assert.equal(exp047MatchedAggregate.primary_contrast.mean_delta, 0.22887336944125247, "EXP-047 should preserve the matched mean delta");
assert.equal(exp047MatchedAggregate.primary_contrast.decision, "material_improvement", "EXP-047 should preserve the frozen primary decision");
assert.equal(exp047MatchedVerification.status, "Passed", "EXP-047 independent matched-validation verification should pass");
assert.equal(exp047MatchedVerification.mismatch_count, 0, "EXP-047 matched-validation verification should have zero mismatches");
assert.equal(exp047MatchedVerification.recalculated.formal_generations, 5088, "EXP-047 verifier should reconstruct all four full-validation conditions");
assert.equal(exp047MatchedVerification.test_split_accessed, false, "EXP-047 verifier must confirm the sealed test was untouched");
assert.equal(exp048Verification.status, "Verified", "EXP-048 independent error-analysis verification should pass");
assert.equal(exp048Verification.analysis_rows, 1272, "EXP-048 should independently reconstruct every validation row");
assert.equal(exp048Verification.prediction_files_checked, 7, "EXP-048 should verify the reference, three LoRA and three encoder prediction files");
assert.equal(exp048Verification.annotation_rows, 48, "EXP-048 should verify every frozen qualitative annotation");
assert.equal(exp048Verification.max_absolute_numeric_difference, 0, "EXP-048 independent recomputation should have zero numeric difference");
assert.equal(exp048Verification.test_accessed, false, "EXP-048 must keep the sealed test untouched");
assert.equal(exp049Verification.status, "Verified", "EXP-049 independent formal-test verification should pass");
assert.equal(exp049Verification.mismatch_count, 0, "EXP-049 formal-test verification should have zero mismatches");
assert.equal(exp049Verification.test_inputs_accessed, true, "EXP-049 should record authorized test-input access");
assert.equal(exp049Verification.test_labels_accessed, true, "EXP-049 should record the one-time test-label opening");
assert.equal(exp049Verification.recalculated.rows, 1273, "EXP-049 should independently reconstruct every formal test row");
assert.equal(exp049Verification.recalculated.prediction_files, 9, "EXP-049 should independently verify all nine frozen prediction files");
assert.equal(exp049Verification.recalculated.prediction_rows, 11457, "EXP-049 should independently verify all frozen row-level predictions");
assert.equal(exp049Verification.recalculated.privacy.private_gitignored, true, "EXP-049 private outputs should remain Git ignored");
assert.equal(exp049Verification.recalculated.privacy.private_tracked, false, "EXP-049 private outputs must not be tracked");
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-028")).status,
  "failed",
  "EXP-028 should remain failed in the separate representation branch",
);
assert.doesNotMatch(
  emotionData.actionDock.nextAction.title,
  /正式执行 EXP-028/,
  "EXP-028 has already failed its frozen resource gate and must not remain the next run",
);
assert.match(
  `${emotionData.actionDock.nextAction.title} ${emotionData.actionDock.nextAction.detail}`,
  /只读|归档|系统|test 已消费/i,
  "the next action should expose read-only post-test work without reopening model selection",
);
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-042")).status,
  "verified",
  "EXP-042 should be independently verified in the dependency route",
);
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-043")).status,
  "verified",
  "EXP-043 should be independently verified in the dependency route",
);
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-044/046")).status,
  "verified",
  "EXP-044/046 should expose the verified Stage 5 resource and runtime gates",
);
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-047")).status,
  "verified",
  "EXP-047 should be verified after independent matched-validation reconstruction",
);
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-048")).status,
  "verified",
  "EXP-048 should be verified after independent frozen-error reconstruction",
);
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-049")).status,
  "verified",
  "EXP-049 should be verified after independent frozen-test reconstruction",
);
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-031")).status,
  "verified",
  "EXP-031 should remain independently verified in the dependency route",
);
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-035")).status,
  "verified",
  "EXP-035 should remain independently verified in the dependency route",
);
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-036")).status,
  "verified",
  "EXP-036 should be independently verified in the dependency route",
);
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-037")).status,
  "verified",
  "EXP-037 should be independently verified in the dependency route",
);
assert.equal(
  emotionData.dependencyRoute.find((step) => step.label.startsWith("EXP-038")).status,
  "verified",
  "EXP-038 should be independently verified in the dependency route",
);
assert.equal(
  emotionData.verifiedEvidence.goEmotions.raterAwareDiagnostic.comparison.classification,
  "practical_tie_or_uncertain",
  "the 174-row diagnostic should remain a local practical tie",
);
assert.equal(
  emotionData.verifiedEvidence.goEmotions.raterAwareDiagnostic.boundary.includes("不改变 full-dev Macro-F1"),
  true,
  "the rater-aware diagnostic must not replace the full-dev official comparison",
);
assert.equal(
  emotionData.verifiedEvidence.goEmotions.fullDevRaterAwareDiagnostic.comparison.classification,
  "gap_remains",
  "the full-dev diagnostic should preserve the verified Qwen-BERT gap",
);
assert.equal(
  emotionData.verifiedEvidence.goEmotions.fullDevRaterAwareDiagnostic.comparison.materialShift,
  false,
  "rater-aware soft scoring should not be presented as a material shift",
);
assert.equal(
  emotionData.verifiedEvidence.goEmotions.fullDevRaterAwareDiagnostic.comparison.softDelta,
  -0.036218,
  "the dashboard should expose the frozen full-dev soft Macro-F1 delta",
);
assert.deepEqual(
  emotionData.actionDock.testGates.map((gate) => gate.label),
  ["TweetEval", "GoEmotions", "Weibo EClass"],
  "the action dock should keep all test gates visible before evidence",
);
assert.deepEqual(
  emotionData.actionDock.testGates.map((gate) => gate.detail),
  ["Frozen · Verified · Consumed", "Frozen · Verified · Consumed", "Frozen · Verified · Consumed"],
  "all completed formal test gates should be visibly frozen, verified and consumed",
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
    split: "official-test",
    taskType: "multi-label",
    labelCount: 28,
    metric: "Macro-F1",
    scale: [0, 1],
    testGate: "consumed",
    comparisonScope: "within-dataset-only",
  },
  "GoEmotions should expose a separate consumed official-test comparison contract",
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
assert.equal(emotionData.verifiedEvidence.goEmotions.models.find((model) => model.experiment === "EXP-029").uncertainty.runs, 3, "LoRA should report all three registered seeds");
assert.equal(emotionData.verifiedEvidence.goEmotions.models.find((model) => model.experiment === "EXP-029").comparison.delta, -0.037676, "legacy LoRA should preserve its frozen test gap to BERT");
assert.equal(emotionData.verifiedEvidence.goEmotions.models.find((model) => model.experiment === "EXP-033").uncertainty.runs, 1, "target-aligned LoRA should remain a single-seed test result");
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
