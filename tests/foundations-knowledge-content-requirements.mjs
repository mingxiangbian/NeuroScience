import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const modulesDir = new URL("../projects/foundations/roadmap/modules/", import.meta.url);
const readModule = (id) => readFileSync(new URL(`${id}.md`, modulesDir), "utf8");
const requiredHeadings = ["核心定义", "核心机制", "逐步示例", "边界与常见错误", "一句话总结"];

function articleTitles(markdown) {
  const knowledge = markdown.split("## 知识笔记\n")[1] ?? "";
  return [...knowledge.matchAll(/^### (.+)$/gm)].map((match) => match[1]);
}

function assertCompleteArticles(markdown, expectedTitles) {
  assert.deepEqual(articleTitles(markdown), expectedTitles);
  const knowledge = markdown.split("## 知识笔记\n")[1] ?? "";
  const blocks = knowledge.split(/^### /m).slice(1);
  for (const block of blocks) {
    for (const heading of requiredHeadings) {
      assert.match(block, new RegExp(`^#### ${heading}$`, "m"), `${block.split("\n")[0]} should include ${heading}`);
    }
    assert.doesNotMatch(block, /^面试转译[：:]$/m);
    assert.doesNotMatch(block, /^复习提示[：:]$/m);
    assert.doesNotMatch(block, /\breadiness\b|hard gate/i);
  }
}

assertCompleteArticles(readModule("coding"), ["deque、stack 与 queue", "单调队列"]);
assertCompleteArticles(readModule("evals-debugging"), ["Eval Case 的六层结构", "Benchmark 与 Agent Behavior Eval"]);

const sprint = readModule("interview-sprint");
assert.match(sprint, /^## 学习记录$/m);
assert.doesNotMatch(sprint, /^## 知识笔记$/m);
assert.match(sprint, /^### D1 冲刺卡$/m);
assert.match(sprint, /^### D2 冲刺卡$/m);

for (const id of ["agent-design", "llm-systems", "rag-memory", "research-reading", "behavioral-strategy", "logs"]) {
  assert.doesNotMatch(readModule(id), /^## 知识笔记$/m, `${id} should not publish an unlearned knowledge article`);
}

const backup = readFileSync(new URL("../projects/foundations/interview_prep_2026-07-09/08_sprint_module_for_website.md", import.meta.url), "utf8");
assert.match(backup, /## 学习记录/);
assert.doesNotMatch(backup, /## 知识笔记/);
