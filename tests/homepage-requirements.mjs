import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const body = html.match(/<body[^>]*>([\s\S]*)<\/body>/i)?.[1] ?? "";

assert.match(html, /<html lang="en">/, "homepage should be English-only");
assert.match(body, /NeuroScience × AI/, "homepage should keep the title");
assert.doesNotMatch(body, /[\u4e00-\u9fff]/, "visible body should not include Chinese text");
assert.match(html, /three@/, "homepage should load Three.js");
assert.match(body, /id="brain-stage"/, "homepage should expose a 3D brain stage");
assert.match(body, /data-region="cortex"/, "homepage should map Cortex to a region");
assert.match(body, /Knowledge/, "Cortex region should map to Knowledge");
assert.match(html, /createBrainSilhouette/, "homepage should build a brain-like anatomical silhouette");
assert.match(html, /lobeAnchors/, "homepage should organize the model around brain lobe anchors");
assert.match(html, /corticalFoldPaths/, "homepage should use irregular cortical fold paths");
assert.doesNotMatch(html, /function addEllipsoid/, "homepage should not use the old ellipsoid cluster brain model");
assert.match(html, /pointerdown|click/i, "homepage should support pointer or click interaction");
assert.match(html, /selectedRegion|selectRegion/, "homepage should track selected brain region");
assert.match(html, /overflow:\s*hidden/, "homepage should be a non-scrolling single screen");
