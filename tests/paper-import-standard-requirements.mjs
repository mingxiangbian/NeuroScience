import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const standardUrl = new URL("../papers/PAPER_IMPORT_STANDARD.md", import.meta.url);

assert.equal(existsSync(standardUrl), true, "paper import standard should exist at papers/PAPER_IMPORT_STANDARD.md");

const standard = readFileSync(standardUrl, "utf8");

assert.match(standard, /^# Paper Import Standard/m, "standard should have a stable title");
assert.match(standard, /papers\/<project-id>\/readings\/<paper-id>\//, "standard should define the reading package path");
assert.match(standard, /paper\.json[\s\S]*chunks\.json[\s\S]*notes\.json[\s\S]*embeddings\.json[\s\S]*figures\.json/, "standard should list all required reading package files");
assert.match(standard, /sourceText[\s\S]*论文原文/, "standard should define sourceText as paper source text, not a summary");
assert.match(standard, /zhTranslation[\s\S]*忠实翻译/, "standard should define zhTranslation as faithful translation");
assert.match(standard, /zhExplanation[\s\S]*解释/, "standard should separate explanation from translation");
assert.match(standard, /blocks[\s\S]*paragraph[\s\S]*math[\s\S]*code[\s\S]*table[\s\S]*figure/, "standard should define supported block types");
assert.match(standard, /figureRefs[\s\S]*near[\s\S]*supporting[\s\S]*deferred/, "standard should define cross-page figure references");
assert.match(standard, /notes\.json[\s\S]*空字符串/, "standard should allow empty notes without visible placeholder text");
assert.match(standard, /indexedFields[\s\S]*sourceText[\s\S]*zhTranslation[\s\S]*zhExplanation/, "standard should define searchable fields");
assert.match(standard, /不引入[\s\S]*\/api\/[\s\S]*provider key[\s\S]*SurrealDB/, "standard should keep the reader static and backend-free");
assert.match(standard, /Import Checklist/, "standard should include an import checklist for future agents");
