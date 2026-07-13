import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const financePageUrl = new URL("../projects/finance/index.html", import.meta.url);
const financeBuildUrl = new URL("../projects/finance/scripts/build-roadmap-data.mjs", import.meta.url);
const financeDataUrl = new URL("../projects/finance/roadmap/roadmap-data.json", import.meta.url);
const financeModulesUrl = new URL("../projects/finance/roadmap/modules/", import.meta.url);
const originalGuideUrl = new URL("../projects/finance/investment_beginner_guide_zh.md", import.meta.url);

const expectedModules = [
  ["overview", "Overview"],
  ["investment-basics", "投资的本质与前提"],
  ["asset-classes", "资产类别"],
  ["risk-allocation", "风险与配置"],
  ["fund-company-analysis", "基金与公司分析"],
  ["valuation", "估值"],
  ["trading-execution", "交易与执行"],
  ["behavior-process", "行为与流程"],
  ["study-plan-tools", "学习计划与工具"],
  ["terms-further-reading", "术语速查与延伸"],
];

assert.equal(existsSync(financePageUrl), true, "finance should expose a static reader page");
assert.equal(existsSync(financeBuildUrl), true, "finance should expose a roadmap data builder");
assert.equal(existsSync(financeDataUrl), true, "finance should expose generated roadmap data");
assert.equal(existsSync(originalGuideUrl), false, "the monolithic guide should be replaced by modules");

for (const [id] of expectedModules) {
  const moduleUrl = new URL(`${id}.md`, financeModulesUrl);
  assert.equal(existsSync(moduleUrl), true, `finance should keep ${id}.md as source content`);
}

const financeHtml = readFileSync(financePageUrl, "utf8");
const builder = readFileSync(financeBuildUrl, "utf8");
const data = JSON.parse(readFileSync(financeDataUrl, "utf8"));

assert.match(financeHtml, /<title>投资 \| NeuroScience x AI<\/title>/, "finance page should use the project title");
assert.match(financeHtml, /data-page="finance-roadmap-reader"/, "finance page should identify the reader");
assert.match(financeHtml, /data-project-id="finance"/, "finance annotations should be project-scoped");
assert.match(financeHtml, /src="\.\.\/foundations\/roadmap\/roadmap-reader\.js"/, "finance should reuse the maintained reader");
assert.match(financeHtml, /data-source="roadmap\/roadmap-data\.json"/, "finance reader should load finance-generated data");
assert.match(financeHtml, /href="\.\.\/index\.html" aria-label="返回项目"/, "finance should return to the project directory");
assert.match(builder, /throw new Error/, "finance builder should reject malformed modules");

assert.equal(data.project.id, "finance", "generated data should identify the finance project");
assert.equal(data.project.title, "投资", "generated data should use the visible project title");
assert.equal(data.project.dashboardModuleId, "overview", "overview should be the dashboard");
assert.equal(data.project.glossaryModuleId, "terms-further-reading", "dashboard should expose the glossary module");
assert.equal(typeof data.project.dashboardFocus, "string", "dashboard should have a re-entry action");
assert.equal(data.project.overallLearningProgress, 0, "initial finance progress should be zero");
assert.deepEqual(data.modules.map((module) => [module.id, module.title]), expectedModules, "finance modules should follow the approved concept order");

for (const module of data.modules) {
  assert.equal(module.learningProgress, 0, `${module.id} should start with zero progress`);
  assert.ok(module.sections && Object.keys(module.sections).length > 0, `${module.id} should render Markdown sections`);
  assert.ok(Array.isArray(module.searchEntries) && module.searchEntries.length > 0, `${module.id} should expose section-level search`);
  assert.ok(module.searchEntries.every((entry) => entry.moduleId === module.id), `${module.id} search entries should retain their module`);
  assert.ok(Array.isArray(module.knowledgeNotes), `${module.id} should expose knowledge articles for local annotations`);
}

const termsModule = data.modules.find((module) => module.id === "terms-further-reading");
assert.match(termsModule.searchText, /市盈率|P\/E/, "the glossary module should retain investment terminology");
assert.match(termsModule.searchText, /延伸学习资料/, "the glossary module should retain further-reading material");

const studyPlanModule = data.modules.find((module) => module.id === "study-plan-tools");
const targetSection = studyPlanModule.sections["目标"] ?? "";
const policyTemplateSection = studyPlanModule.sections["21.1 投资政策声明模板"] ?? "";
assert.deepEqual(
  {
    targetRetainsIntendedProse: /按 12 周节奏完成概念练习/.test(targetSection),
    targetExcludesTemplateFields: !/长期目标|目标日期|预计投入频率/.test(targetSection),
    fencedHeadingStaysOutOfSectionKeys: !Object.hasOwn(studyPlanModule.sections, "财务安全"),
    policyTemplateRetainsFencedContent: /<pre><code class="hljs language-markdown">[\s\S]*我的投资政策声明[\s\S]*财务安全[\s\S]*<\/code><\/pre>/.test(policyTemplateSection),
  },
  {
    targetRetainsIntendedProse: true,
    targetExcludesTemplateFields: true,
    fencedHeadingStaysOutOfSectionKeys: true,
    policyTemplateRetainsFencedContent: true,
  },
  "fenced Markdown template headings should not split or overwrite Finance module sections",
);

console.log(`finance reader contract passed for ${fileURLToPath(financeDataUrl)}`);
