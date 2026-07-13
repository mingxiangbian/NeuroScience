import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const financePageUrl = new URL("../projects/finance/index.html", import.meta.url);
const financeThemeUrl = new URL("../projects/finance/finance-theme.css", import.meta.url);
const financeReadmeUrl = new URL("../projects/finance/README.md", import.meta.url);
const financeBuildUrl = new URL("../projects/finance/scripts/build-roadmap-data.mjs", import.meta.url);
const financeDataUrl = new URL("../projects/finance/roadmap/roadmap-data.json", import.meta.url);
const financeModulesUrl = new URL("../projects/finance/roadmap/modules/", import.meta.url);
const originalGuideUrl = new URL("../projects/finance/investment_beginner_guide_zh.md", import.meta.url);
const sharedReaderUrl = new URL("../projects/foundations/roadmap/roadmap-reader.js", import.meta.url);

const expectedModules = [
  ["overview", "学习总览"],
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
assert.equal(existsSync(financeThemeUrl), true, "finance should expose a project-scoped gold theme");
assert.equal(existsSync(financeReadmeUrl), true, "finance should document its use and privacy boundary");

for (const [id] of expectedModules) {
  const moduleUrl = new URL(`${id}.md`, financeModulesUrl);
  assert.equal(existsSync(moduleUrl), true, `finance should keep ${id}.md as source content`);
}

const financeHtml = readFileSync(financePageUrl, "utf8");
const financeTheme = readFileSync(financeThemeUrl, "utf8");
const financeReadme = readFileSync(financeReadmeUrl, "utf8");
const builder = readFileSync(financeBuildUrl, "utf8");
const data = JSON.parse(readFileSync(financeDataUrl, "utf8"));
const sharedReader = readFileSync(sharedReaderUrl, "utf8");
const closeSearchSource = sharedReader.match(/function closeSearchModal\(\) \{([\s\S]*?)\n\}/)?.[1] ?? "";
const escapeKeySource = sharedReader.match(/if \(event\.key === "Escape"\) \{([\s\S]*?)\n    \}/)?.[1] ?? "";

assert.match(financeHtml, /<title>投资 \| NeuroScience x AI<\/title>/, "finance page should use the project title");
assert.match(financeHtml, /data-page="finance-roadmap-reader"/, "finance page should identify the reader");
assert.match(financeHtml, /data-project-id="finance"/, "finance annotations should be project-scoped");
assert.match(financeHtml, /src="\.\.\/foundations\/roadmap\/roadmap-reader\.js"/, "finance should reuse the maintained reader");
assert.match(financeHtml, /data-source="roadmap\/roadmap-data\.json"/, "finance reader should load finance-generated data");
assert.match(financeHtml, /href="\.\.\/index\.html" aria-label="返回项目"/, "finance should return to the project directory");
const sharedCssIndex = financeHtml.indexOf('../foundations/roadmap/roadmap-reader.css');
const financeThemeIndex = financeHtml.indexOf('finance-theme.css');
assert.ok(sharedCssIndex >= 0 && financeThemeIndex > sharedCssIndex, "finance theme should load after shared reader CSS");
assert.match(financeHtml, /class="directory-kicker">学习路径<\/p>/, "finance directory chrome should use Chinese copy");
assert.match(financeTheme, /body\[data-page="finance-roadmap-reader"\]/, "finance theme should be page-scoped");
assert.match(financeTheme, /oklch\(/, "finance theme should use the approved perceptual color space");
assert.match(financeTheme, /body\[data-page="finance-roadmap-reader"\]\[data-theme="dark"\]\s+\.route-ledger-label\s*\{\s*color:\s*var\(--reader-ink\);\s*\}/, "dark finance ledger labels should use dedicated high-contrast text");
assert.match(financeTheme, /--reader-panel-blur:\s*blur\(18px\)/, "finance should reduce the inherited glass blur");
assert.match(financeTheme, /\.toolbar-search:focus-within/, "finance search should expose a visible focus state");
assert.match(financeTheme, /@media \(max-width:\s*480px\)/, "finance should have a narrow-toolbar layout");
assert.match(financeTheme, /grid-template-rows:\s*auto auto/, "narrow finance toolbar should use two rows");
assert.match(financeTheme, /width:\s*44px[\s\S]*height:\s*44px/, "narrow finance controls should expose 44px targets");
assert.doesNotMatch(financeTheme, /#2e704d|rgba\(46,\s*112,\s*77|rgba\(152,\s*217,\s*166/, "finance theme should not retain the inherited visible green palette");
assert.match(financeReadme, /本地批注只保存在当前浏览器/, "README should explain annotation persistence");
assert.match(financeReadme, /不保存持仓、交易、账户或个人财务信息/, "README should preserve the public privacy boundary");
assert.ok(data.modules[0].sections["学习导航"], "finance overview should expose the Chinese navigation section");
assert.equal(data.modules[0].sections.Dashboard, undefined, "finance should not retain the visible Dashboard heading");
assert.match(builder, /throw new Error/, "finance builder should reject malformed modules");
assert.match(sharedReader, /function renderFinanceOverviewDashboard\(module\)[\s\S]*?getFinanceReentryState\(learningModules\)/, "finance dashboard should consume the tested re-entry view state");
assert.match(sharedReader, /financeReentry\.nextStepLabel/, "finance dashboard should render the tested all-complete copy");
assert.match(sharedReader, /getStatusLabel\(financeReentry\.status\)/, "finance dashboard should render the tested re-entry status");
assert.match(sharedReader, /PROJECT_ID\s*!==\s*"finance"/, "finance metadata should hide redundant raw priority");
assert.match(sharedReader, /PROJECT_ID === "finance" \? "未找到结果" : "No results found"/, "finance empty search results should use Chinese copy");
assert.match(sharedReader, /进入任一概念模块底部的「知识笔记」，选中文字即可添加本地批注。批注只保存在当前浏览器。/, "empty note panels should explain the actual annotation boundary");
assert.match(closeSearchSource, /els\.searchResults\.hidden = true;/, "closing search should always hide results");
assert.doesNotMatch(closeSearchSource, /if \(!state\.searchQuery\)/, "closing search should not depend on an empty query");
assert.match(escapeKeySource, /if \(els\.shell\.classList\.contains\("is-searching"\)\) event\.preventDefault\(\);[\s\S]*closeSearchModal\(\);/, "Escape should prevent the native search-input default only while search is open, before preserving and hiding results");
assert.match(escapeKeySource, /if \(els\.shell\.classList\.contains\("is-searching"\)\) els\.searchInput\.blur\(\);[\s\S]*closeSearchModal\(\);/, "Escape should blur the search input only while search is open so one click can restore preserved results");
assert.doesNotMatch(sharedReader, /status !== "(?:done|complete)"\) \?\? learningModules\[0\]/, "completed dashboards should not fall back to their first module");

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
