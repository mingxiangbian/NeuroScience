import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");

function sourceFunction(name) {
  const start = new RegExp(`^( +)function ${name}\\(`, "m").exec(html);
  assert.ok(start, `Missing production function: ${name}`);
  const rest = html.slice(start.index);
  const end = new RegExp(`^${start[1]}\\}$`, "m").exec(rest);
  assert.ok(end, `Missing function end: ${name}`);
  return rest.slice(0, end.index + end[0].length);
}

// The small vector surface uses Three.js r165's arithmetic order. No renderer,
// downloaded library, browser, or temporary baseline is needed by this test.
let vectorAllocations = 0;
let distanceCalls = 0;
class Vector3 {
  constructor(x = 0, y = 0, z = 0) { vectorAllocations += 1; Object.assign(this, { x, y, z }); }
  copy(v) { this.x = v.x; this.y = v.y; this.z = v.z; return this; }
  clone() { return new Vector3(this.x, this.y, this.z); }
  distanceTo(v) {
    distanceCalls += 1;
    const dx = this.x - v.x, dy = this.y - v.y, dz = this.z - v.z;
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
  }
  lerp(v, alpha) {
    this.x += (v.x - this.x) * alpha;
    this.y += (v.y - this.y) * alpha;
    this.z += (v.z - this.z) * alpha;
    return this;
  }
}

const functions = [
  "createCircuitRoutePath", "sampleCircuitRoutePath", "circuitRouteInputsMatch",
  "getResponsiveRoutePoints", "getResponsiveConnectorSide", "syncCircuitRoute",
  "collectBrainMaterials", "setBrainMaterialOpacity", "normalizeSearchText", "scoreSearchRecord",
];
const api = vm.runInNewContext(`${functions.map(sourceFunction).join("\n")}\n({${functions.join(",")}})`);

// Frozen pre-optimization sampler: an independent oracle for positions and
// boundary behavior, including the original accumulation/interpolation order.
function originalSample(segmentPairs, progress) {
  if (!segmentPairs.length || progress < 0 || progress > 1) return null;
  const lengths = segmentPairs.map(([start, end]) => start.distanceTo(end));
  const totalLength = lengths.reduce((sum, length) => sum + length, 0);
  if (totalLength <= 0.001) return segmentPairs[0][0].clone();
  let targetDistance = progress * totalLength;
  for (let index = 0; index < segmentPairs.length; index += 1) {
    const length = lengths[index];
    if (targetDistance <= length) {
      const ratio = length <= 0.001 ? 0 : targetDistance / length;
      return segmentPairs[index][0].clone().lerp(segmentPairs[index][1], ratio);
    }
    targetDistance -= length;
  }
  return segmentPairs.at(-1)[1].clone();
}

const layoutSource = html.match(/const CHIP_LAYOUT = (\[[\s\S]*?\n      \]);/);
assert.ok(layoutSource);
const layouts = vm.runInNewContext(layoutSource[1]);
const modes = ["desktop", "portrait", "compact"];
const segments = (points) => points.slice(1).map((end, index) => [
  new Vector3(...points[index]), new Vector3(...end),
]);
const routes = [
  [],
  segments([[2, 3, 4], [2, 3, 4]]),
  segments([[0, 0, 0], [0.0005, 0, 0], [0.001, 0, 0]]),
  segments([[0, 0, 0], [0, 0, 0], [0.0011, 0, 0], [4, 3, -2], [4, 3, -2]]),
  ...layouts.flatMap((layout) => modes.map((mode) => segments(api.getResponsiveRoutePoints(layout, mode)))),
];
const progressValues = [-Infinity, -0.1, -Number.EPSILON, -0, 0, Number.EPSILON, 0.5, 1 - Number.EPSILON, 1, 1 + Number.EPSILON, Infinity, NaN];
let seed = 731;
for (let index = 0; index < 300; index += 1) {
  seed = (1664525 * seed + 1013904223) >>> 0;
  progressValues.push(seed / 2 ** 32);
}
let comparisons = 0;
for (const pairs of routes) {
  const path = api.createCircuitRoutePath(pairs);
  const target = new Vector3();
  const before = pairs.map((pair) => pair.map((point) => [point.x, point.y, point.z]));
  const boundaryProgress = [];
  let length = 0;
  for (const segmentLength of path.lengths) {
    length += segmentLength;
    if (path.totalLength) boundaryProgress.push(length / path.totalLength);
  }
  for (const progress of [...progressValues, ...boundaryProgress]) {
    const expected = originalSample(pairs, progress);
    const actual = api.sampleCircuitRoutePath(path, progress, target);
    assert.deepEqual(actual, expected, `Trajectory mismatch at ${progress}`);
    if (actual) assert.equal(actual, target, "Sampling must reuse its output vector");
    comparisons += 1;
  }
  assert.deepEqual(pairs.map((pair) => pair.map((point) => [point.x, point.y, point.z])), before, "Sampling must not mutate path endpoints");
}

// Repeated sampling must perform no new length calculations or allocations.
const cachedPath = api.createCircuitRoutePath(routes.at(-1));
const output = new Vector3();
distanceCalls = 0;
vectorAllocations = 0;
for (let index = 0; index < 1000; index += 1) api.sampleCircuitRoutePath(cachedPath, index / 1000, output);
assert.equal(distanceCalls, 0);
assert.equal(vectorAllocations, 0);

// Use the real responsive route arrays and derive pins/avoidance from position
// and scale, as the component does. Mutate each actual input after a cache hit.
let rebuilds = 0;
for (const sourceLayout of layouts) {
  const layout = structuredClone(sourceLayout);
  const position = { x: layout.position[0], y: layout.position[1], z: layout.position[2] };
  let scale = 1.32;
  let pinShift = 0;
  let boxShift = 0;
  let mode = "desktop";
  const entry = {
    layout,
    component: { userData: {
      getConnectorPinPoints() {
        const side = api.getResponsiveConnectorSide(layout, mode);
        return [-0.18, 0, 0.18].map((offset) => {
          const vertical = side === "top" || side === "bottom";
          return new Vector3(
            position.x + (vertical ? offset / 1.32 : side === "left" ? -0.7 : 0.7) * scale + pinShift,
            position.y + (vertical ? side === "top" ? 0.43 : -0.43 : offset / 1.32) * scale,
            position.z + 0.04 * scale,
          );
        });
      },
      getDisplayAvoidanceBox: () => ({
        left: position.x - 0.64 * scale + boxShift, right: position.x + 0.64 * scale,
        bottom: position.y - 0.39 * scale, top: position.y + 0.39 * scale,
      }),
    } },
    route: { userData: { setCircuitRoute() { rebuilds += 1; } } },
  };
  function expectRebuild(change = () => {}) {
    change();
    const before = rebuilds;
    api.syncCircuitRoute(entry, mode);
    assert.equal(rebuilds, before + 1, "Changed route inputs must rebuild");
    for (let index = 0; index < 100; index += 1) api.syncCircuitRoute(entry, mode);
    assert.equal(rebuilds, before + 1, "Unchanged route inputs must reuse the route");
  }
  expectRebuild();
  for (const axis of ["x", "y", "z"]) expectRebuild(() => { position[axis] += 0.125; });
  expectRebuild(() => { scale += Number.EPSILON; });
  expectRebuild(() => { pinShift = 0.125; });
  expectRebuild(() => { boxShift = 0.125; });
  expectRebuild(() => { layout.route[1][0] += 0.125; });
  expectRebuild(() => { layout.connectorSide = layout.connectorSide === "left" ? "right" : "left"; });
  expectRebuild(() => { mode = "portrait"; });
  expectRebuild(() => { mode = "compact"; });

  // Keep every representable scale change from the existing easing formula.
  // No epsilon or quantization may freeze the end of an expansion/collapse.
  let active = 0;
  let previousInputs = JSON.stringify([entry.component.userData.getConnectorPinPoints(), entry.component.userData.getDisplayAvoidanceBox()]);
  for (const target of [1, 0]) {
    for (let frame = 0; frame < 600; frame += 1) {
      active += (target - active) * 0.075;
      const eased = active * active * (3 - 2 * active);
      scale = 1.32 * (1 + eased * 0.08);
      const pins = entry.component.userData.getConnectorPinPoints();
      const box = entry.component.userData.getDisplayAvoidanceBox();
      const before = rebuilds;
      const inputs = JSON.stringify([pins, box]);
      api.syncCircuitRoute(entry, mode);
      assert.equal(rebuilds, before + (inputs === previousInputs ? 0 : 1));
      previousInputs = inputs;
      assert.ok(api.circuitRouteInputsMatch(entry.circuitRouteInputs, api.getResponsiveRoutePoints(layout, mode), api.getResponsiveConnectorSide(layout, mode), pins, box));
    }
  }
}

// Validate the actual route-channel integration passes the persistent particle
// scratch vector to the sampler; validating the helper alone would miss call-site errors.
const channelSource = sourceFunction("createCircuitRouteChannel");
assert.match(channelSource, /\.map\(createCircuitRoutePath\)/);
assert.match(channelSource, /sampleCircuitRoutePath\(path, progress, sampledPoint\)/);
assert.match(html, /item\.curve\.getPointAt\(t, item\.marker\.position\)/);

// Retain the old opacity algorithm as an oracle, including shared materials,
// material arrays, opacity=0, and an explicitly stored base opacity.
function originalOpacity(model, factor) {
  model.traverse((object) => {
    if (!object.isMesh || !object.material) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.forEach((material) => {
      if (material.userData.baseOpacity === undefined) material.userData.baseOpacity = material.opacity ?? 1;
      material.transparent = true;
      material.opacity = material.userData.baseOpacity * factor;
    });
  });
}
function materialFixture() {
  const materials = [{ opacity: 0.58, userData: {} }, { opacity: 0, userData: {} }, { userData: {} }, { opacity: 0.7, userData: { baseOpacity: 0.4 } }];
  const nodes = [{}, { isMesh: true }, { isMesh: true, material: materials[0] }, { isMesh: true, material: [materials[1], materials[2]] }, { isMesh: true, material: materials[0] }, { isMesh: true, material: materials[3] }];
  return { materials, visits: 0, traverse(fn) { this.visits += 1; nodes.forEach(fn); } };
}
const originalMaterials = materialFixture();
const cachedMaterials = materialFixture();
const collected = api.collectBrainMaterials(cachedMaterials);
for (let index = 0; index < 600; index += 1) {
  const factor = 1 - (index % 300) / 300 * 0.62;
  originalOpacity(originalMaterials, factor);
  api.setBrainMaterialOpacity(collected, factor);
  assert.deepEqual(cachedMaterials.materials, originalMaterials.materials);
}
assert.equal(originalMaterials.visits, 600);
assert.equal(cachedMaterials.visits, 1);

// Execute the production frame function and actual activity updater with a
// renderer stub. Compare every visible frame against uninterrupted time updates.
const activityUpdate = html.match(/group\.userData\.update = \(time\) => \{([\s\S]*?)\n        \};/);
assert.ok(activityUpdate);
for (const reduced of [false, true]) {
  function flowFixture() {
    const scope = {
      prefersReducedMotion: reduced,
      inkContourMaterials: [{ uniforms: { time: { value: 0 } } }],
      surfaceFlowMaterials: [{ uniforms: { time: { value: 0 } } }],
      flowTextures: [{ phase: 0.71, speed: 0.065, texture: { offset: { x: 0 } } }],
      flowPulses: [0.21, 0.63].map((phase) => ({
        phase, speed: 0.034,
        curve: { getPointAt(t, target) { return target.copy({ x: t * 2, y: t * t, z: 1 - t }); } },
        marker: { position: new Vector3(), scale: { value: 0, setScalar(value) { this.value = value; } } },
        glow: { material: { opacity: 0 } }, pulse: { material: { opacity: 0 } },
      })),
    };
    return { scope, update: vm.runInNewContext(`(time) => {${activityUpdate[1]}\n}`, scope) };
  }
  const reference = flowFixture();
  const optimized = flowFixture();
  const visualState = ({ scope }) => JSON.stringify([scope.inkContourMaterials, scope.surfaceFlowMaterials, scope.flowTextures, scope.flowPulses]);
  let elapsed = 0;
  let frame = 0;
  let measurements = 0;
  let scheduled = 0;
  let updates = 0;
  let viewport;
  const activityFlow = { visible: true, userData: { update(time) { updates += 1; optimized.update(time); } } };
  const view = { brain: {}, shell: { rotation: { y: 0 } }, scene: {}, camera: {}, renderer: { render() {
    if (activityFlow.visible) assert.equal(visualState(optimized), visualState(reference), `Visible activity must resume at current time, frame ${frame}`);
  } } };
  const context = {
    clock: { getElapsedTime: () => elapsed }, prefersReducedMotion: reduced, activityFlow, view,
    getViewportLayout() { measurements += 1; viewport = { width: frame < 180 ? 1400 : 390, height: 844, frame }; return viewport; },
    controls: { update() {} },
    explodedView: { update(time, brain, flow, layout) {
      assert.equal(time, elapsed); assert.equal(brain, view.brain); assert.equal(layout, viewport);
      flow.visible = frame < 100 || frame >= 250;
    } },
    moduleUi: { getState: () => ({ expanded: frame >= 100 && frame < 250 }) },
    gpuPedestal: { update(time, interaction, layout) { assert.equal(time, elapsed); assert.equal(layout, viewport); } },
    requestAnimationFrame() { scheduled += 1; return scheduled; }, app: null,
  };
  const render = vm.runInNewContext(`${sourceFunction("render")}\nrender`, context);
  for (frame = 0; frame < 360; frame += 1) {
    elapsed = frame / 60;
    reference.update(elapsed);
    render();
  }
  assert.equal(measurements, 360, "Every frame must obtain exactly one fresh layout, including changes without resize events");
  assert.equal(scheduled, 360, "The optimization must preserve frame scheduling");
  assert.equal(updates, 210, "Only invisible activity updates should be skipped");
}

// Frozen old scoring formula: compare both scores and complete sorted results.
function originalScore(record, query) {
  const tokens = query.split(" ").filter(Boolean);
  if (!tokens.every((token) => record.normalizedSearchText.includes(token))) return 0;
  let score = 20 + tokens.length * 4;
  if (record.normalizedTitle === query) score += 90;
  else if (record.normalizedTitle.startsWith(query)) score += 62;
  else if (record.normalizedTitle.includes(query)) score += 44;
  if (record.group === "Projects") score += 5;
  if (record.group === "Papers") score += 3;
  return score;
}
const records = ["Memory", "memory systems", "AI memory survey", "记忆与智能体", "Café", "cafe", "mémory", "Other"]
  .flatMap((title) => ["Projects", "Papers", "Sections"].map((group) => ({ title, group, normalizedTitle: api.normalizeSearchText(title), normalizedSearchText: api.normalizeSearchText(`${title} AI agent neuroscience`) })));
for (const query of ["", "memory", "MEMORY", "memory systems", "memory  memory", "café", "记忆", "agent ai", "missing", "\t memory  \n"]) {
  const normalized = api.normalizeSearchText(query);
  const tokens = normalized.split(" ").filter(Boolean);
  for (const record of records) assert.equal(api.scoreSearchRecord(record, normalized, tokens), originalScore(record, normalized));
  const sorted = (score) => records.map((record) => ({ record, score: score(record) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.record.title.localeCompare(b.record.title)).slice(0, 36);
  assert.deepEqual(sorted((record) => api.scoreSearchRecord(record, normalized, tokens)), sorted((record) => originalScore(record, normalized)));
}
console.log(`Homepage performance equivalence passed: ${comparisons} trajectory comparisons; exact route invalidation; cached materials; visible activity and fresh per-frame viewport; unchanged search scores/order.`);
