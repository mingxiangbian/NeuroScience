import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const packageUrl = new URL(
  "../papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/",
  import.meta.url
);
const chunks = JSON.parse(readFileSync(new URL("chunks.json", packageUrl), "utf8")).chunks;
const figures = JSON.parse(readFileSync(new URL("figures.json", packageUrl), "utf8")).figures;

const chunkById = new Map(chunks.map((chunk) => [chunk.id, chunk]));
const figureById = new Map(figures.map((figure) => [figure.id, figure]));
const chunkText = (id) => JSON.stringify(chunkById.get(id));
const figureIds = (id) => (chunkById.get(id)?.figureRefs ?? []).map((ref) => ref.id);

assert.deepEqual(
  chunks.slice(0, 22).map((chunk) => chunk.id),
  Array.from({ length: 22 }, (_, index) => `ch-${String(index + 1).padStart(3, "0")}`),
  "published chunk IDs should remain stable"
);

assert.match(chunkText("ch-004"), /one thousand|1,000/i, "J-lens method should state the averaging corpus size");
assert.match(chunkText("ch-004"), /Sonnet 4\.5/i, "J-lens method should state the primary model scope");
assert.match(chunkText("ch-004"), /penultimate|倒数第二层/i, "J-lens method should state its default target layer");
assert.match(chunkText("ch-005"), /k[^\d]{0,12}25|25[^\d]{0,12}J-lens/i, "J-space definition should state the typical sparsity cap");
assert.match(chunkText("ch-005"), /10%/, "J-space definition should state its limited explained variance");

assert.match(chunkText("ch-007"), /14 categor/i, "verbal report should retain the category protocol");
assert.match(chunkText("ch-007"), /59%/, "verbal report should retain the J-space component result");
assert.match(chunkText("ch-008"), /positive|focus instruction/i, "directed modulation should retain the positive instruction condition");
assert.match(chunkText("ch-008"), /negative|ignore instruction/i, "directed modulation should retain the negative instruction condition");
assert.match(chunkText("ch-008"), /no-instruction|baseline/i, "directed modulation should retain the no-instruction baseline");
assert.match(chunkText("ch-008"), /J-orthogonal[^]*(1 SD|one standard deviation)[^]*(3[–-]6 SD|3 to 6 standard deviations)/i, "directed modulation should retain the J-space versus non-J-space control");
assert.match(chunkText("ch-009"), /54%[^]*70%[^]*70%/, "internal reasoning should retain cross-model causal results");
assert.match(chunkText("ch-009"), /61%[^]*28%[^]*6%/, "internal reasoning should retain probe decomposition controls");
assert.match(chunkText("ch-009"), /17%[^]*depth/i, "internal reasoning should retain the answer-leakage depth control");
assert.match(chunkText("ch-009"), /activation patching/i, "internal reasoning should retain the arithmetic causal-layer control");
assert.match(chunkText("ch-010"), /76[^]*192[^]*101[^]*192/, "flexible generalization should retain both swap success rates");
assert.match(chunkText("ch-010"), /workspace loading/i, "flexible generalization should retain the main failure predictor");
assert.match(chunkText("ch-011"), /fourteen|14 task/i, "selectivity should retain the broad task battery");
assert.match(chunkText("ch-011"), /continuation[^]*anomaly[^]*explicit report/i, "selectivity should retain its matched task controls");
assert.match(chunkText("ch-011"), /experiential[^]*k\s*=\s*10[^]*L38[–-]54/i, "selectivity should retain the experiential-report ablation settings");
assert.match(chunkText("ch-011"), /Haiku 4\.5[^]*coheren/i, "selectivity should retain the Haiku coherence failure boundary");

assert.match(chunkText("ch-012"), /CKA/, "layer-range evidence should retain the geometry comparison");
assert.match(chunkText("ch-012"), /L38[^]*L92|38[^]*92/, "layer-range evidence should retain the approximate workspace range");
assert.match(chunkText("ch-012"), /artifact|lens limitation|工具伪影/i, "layer-range evidence should retain the early-layer alternative explanation");
assert.match(chunkText("ch-012"), /(sixteen|16) pair[^]*(forty|40)[^]*carrier/i, "layer-range evidence should retain the ambiguous-input sample design");
assert.match(chunkText("ch-012"), /layer sampling|层抽样/i, "layer-range evidence should retain the sampled-layer sharpness caveat");
assert.match(chunkText("ch-013"), /occupancy[^]*25/i, "capacity evidence should retain median occupancy");
assert.match(chunkText("ch-013"), /one to two|1[^\d]+2/i, "capacity evidence should distinguish simultaneous single-layer content");
assert.match(chunkText("ch-014"), /10×|10x/i, "broadcast evidence should retain MLP gain");
assert.match(chunkText("ch-014"), /0\.67[^]*0\.86/, "broadcast evidence should retain the head-ablation control");
assert.match(chunkText("ch-014"), /0\.54[^]*0\.09/, "broadcast evidence should retain the injected-thought effect");

assert.match(chunkText("ch-015"), /71%[^]*3%/, "blackmail audit should retain the eval-awareness effect");
assert.match(chunkText("ch-015"), /13[^]*180/, "blackmail audit should retain the surfaced blackmail rate");
assert.match(chunkText("ch-015"), /same six prompts|同一组 6 个/i, "blackmail audit should disclose that token selection and intervention share prompts");
assert.match(chunkText("ch-015"), /held-out/i, "blackmail audit should state the missing held-out validation");
assert.match(chunkText("ch-016"), /fake[^]*injection[^]*false/i, "prompt-injection audit should retain the observed lens tokens");
assert.match(chunkText("ch-017"), /reward-hacking[^]*reward-model-appeasing/i, "hidden-objective audit should keep the two model organisms distinct");
assert.match(chunkText("ch-017"), /20[^]*code-for-user[^]*20[^]*test-passing/i, "hidden-objective audit should retain the coding-prompt split");
assert.match(chunkText("ch-017"), /(Assistant colon|Assistant 冒号)[^]*prefilled[^]*(first 20 on-policy|前 20 个 on-policy)/i, "hidden-objective audit should retain its readout positions");

assert.match(chunkText("ch-018"), /pretrained base model|base model/i, "Assistant perspective should be framed as a model comparison");
assert.doesNotMatch(chunkText("ch-018"), /reflective continuations/i, "Assistant perspective should not borrow reflection-training evidence");
assert.match(chunkText("ch-018"), /bereavement|Tylenol/i, "Assistant perspective should retain its reaction suites");
assert.match(chunkText("ch-018"), /tentative|speculative|推测/i, "Assistant self-monitoring interpretation should retain its caveat");
assert.doesNotMatch(chunkById.get("ch-018").claim, /自我监控.*用户回合/, "Assistant perspective should not place all self-monitoring evidence on the user turn");
assert.match(chunkText("ch-018"), /roleplay[^]*Assistant token[^]*thought suppression[^]*(copying output|复制输出)/i, "Assistant perspective should distinguish where each suite is measured");
assert.match(chunkText("ch-019"), /10,000|ten thousand/i, "reflection training should retain training-set scale");
assert.match(chunkText("ch-019"), /0\.25[^]*0\.07[^]*0\.38[^]*0\.05/, "reflection training should retain benchmark results");
assert.match(chunkText("ch-019"), /0\.22[^]*0\.23/, "reflection training should retain causal ablation results");

assert.match(chunkText("ch-020"), /bag of concepts|概念集合/i, "limitations should retain the binding limitation");
assert.match(chunkText("ch-020"), /motor/i, "limitations should retain the post-hoc workspace/motor boundary");
assert.match(chunkText("ch-020"), /early layers|早期层/i, "limitations should retain the early-layer ambiguity");
assert.match(chunkText("ch-020"), /model size|模型规模/i, "limitations should retain the scaling uncertainty");
assert.match(chunkText("ch-020"), /inconsistent interpretability|解释不一致/i, "limitations should retain uninterpretable workspace-layer readouts");
assert.match(chunkText("ch-020"), /not systematically quantified|未系统统计/i, "limitations should state that uninterpretable-readout prevalence was not quantified");
assert.match(chunkText("ch-021"), /two time dimensions|两个时间维度/i, "human comparison should retain the transformer time-axis difference");
assert.match(chunkText("ch-021"), /selfhood|自我/i, "human comparison should retain the workspace/selfhood dissociation");
assert.match(chunkText("ch-021"), /verbal|语言/i, "human comparison should retain the verbal-format limitation");

const requiredMappings = {
  "ch-009": "fig-010",
  "ch-010": "fig-011",
  "ch-011": "fig-012",
  "ch-013": "fig-013",
  "ch-014": "fig-014",
  "ch-015": "fig-015",
  "ch-016": "fig-016",
  "ch-017": "fig-017",
  "ch-018": "fig-018",
  "ch-019": "fig-019"
};

for (const [chunkId, figureId] of Object.entries(requiredMappings)) {
  assert.ok(figureIds(chunkId).includes(figureId), `${chunkId} should reference ${figureId}`);
  const figure = figureById.get(figureId);
  assert.ok(figure, `${figureId} should exist in figures.json`);
  assert.equal(figure.status, "cropped", `${figureId} should be a local source crop`);
  assert.equal(figure.cropMode, "web-screenshot-crop", `${figureId} should record its source-crop mode`);
  assert.equal(figure.publicCropPolicy, "minimal-necessary", `${figureId} should follow the public crop policy`);
  assert.ok(figure.file, `${figureId} should have a local file`);
  assert.equal(existsSync(new URL(figure.file, packageUrl)), true, `${figureId} local file should exist`);
}

const renderedFigureIds = chunks.flatMap((chunk) => figureIds(chunk.id));
assert.equal(renderedFigureIds.filter((id) => id === "fig-001").length, 1, "Figure 1 should not be rendered twice in adjacent chunks");
assert.equal(renderedFigureIds.includes("fig-009"), false, "the Discussion source anchor should not render as a figure card");
assert.equal(figureById.get("fig-002").bbox.width, 1015, "Figure 4 crop metadata should match the PNG width");

console.log("Gurnee global-workspace reading package requirements passed.");
