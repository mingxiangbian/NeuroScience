import assert from "node:assert/strict";
import {
  markdownToSafeHtml,
  parseKnowledgeArticles,
} from "../projects/foundations/scripts/roadmap-markdown.mjs";

const completeArticle = `### 单调队列

> 维护仍可能成为最大值的候选。

\`deque\` · \`O(n)\`

#### 核心定义
队列保存候选索引。

#### 核心机制
1. 删除被支配候选
2. 加入新索引

#### 程序流程
1. 新索引进入窗口
2. 删除队尾候选
3. 清理过期队首

#### 逐步示例
在 \`[3, 5, 2, 4]\` 中，5 淘汰 3。

#### 代码实现
\`\`\`python
queue.popleft()
\`\`\`

#### 边界与常见错误
\`pop()\` 处理支配，\`popleft()\` 处理过期。

#### 一句话总结
每个索引最多入队和出队一次。`;

const articles = parseKnowledgeArticles("coding", completeArticle);
assert.equal(articles.length, 1);
assert.equal(articles[0].id, "coding-单调队列");
assert.match(articles[0].intro, /<blockquote>/);
assert.deepEqual(
  articles[0].sections.map(({ title, kind }) => [title, kind]),
  [
    ["核心定义", "definition"],
    ["核心机制", "mechanism"],
    ["程序流程", "flow"],
    ["逐步示例", "example"],
    ["代码实现", "code"],
    ["边界与常见错误", "boundary"],
    ["一句话总结", "summary"],
  ],
);
assert.match(articles[0].sections[4].body, /class="language-python"/);
assert.match(articles[0].text, /每个索引最多入队和出队一次/);

const articleWithUnknownSection = parseKnowledgeArticles(
  "coding",
  completeArticle.replace(
    "#### 一句话总结",
    "#### 延伸理解\n这是一段允许保留的自定义扩展。\n\n#### 一句话总结",
  ),
)[0];
assert.equal(
  articleWithUnknownSection.sections.find((section) => section.title === "延伸理解")?.kind,
  "generic",
);

const safe = markdownToSafeHtml(`> lead

| A | B |
| - | - |
| 1 | 2 |

<script>alert(1)</script>
[unsafe](javascript:alert(1))`);
assert.match(safe.html, /<blockquote>/);
assert.match(safe.html, /<table>/);
assert.doesNotMatch(safe.html, /<script|javascript:/i);

assert.throws(
  () => parseKnowledgeArticles("coding", completeArticle.replace("#### 一句话总结", "#### 结论")),
  /coding.*单调队列.*一句话总结/,
);
assert.throws(
  () => parseKnowledgeArticles(
    "coding",
    completeArticle.replace("队列保存候选索引。", "<script>alert(1)</script>"),
  ),
  /coding.*单调队列.*核心定义/,
);
assert.throws(
  () => parseKnowledgeArticles("coding", `${completeArticle}\n\n${completeArticle}`),
  /duplicate knowledge article id/i,
);
assert.throws(
  () => parseKnowledgeArticles("coding", completeArticle.replace(
    "1. 新索引进入窗口\n2. 删除队尾候选\n3. 清理过期队首",
    "1. 新索引进入窗口",
  )),
  /程序流程.*at least two ordered steps/i,
);
