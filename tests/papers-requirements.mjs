import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const paperPageUrl = new URL("../papers/index.html", import.meta.url);
const manifestUrl = new URL("../papers/manifest.json", import.meta.url);
const paperPageExists = existsSync(paperPageUrl);
const manifestExists = existsSync(manifestUrl);

assert.equal(paperPageExists, true, "papers/ should expose a static homepage");
assert.equal(manifestExists, true, "papers/ should expose a manifest.json index for project paper modules");

const html = readFileSync(paperPageUrl, "utf8");
const manifest = JSON.parse(readFileSync(manifestUrl, "utf8"));

assert.match(html, /<html lang="zh-CN">/, "papers homepage should use Chinese as the default research UI language");
assert.match(html, /<title>Literature Library \| NeuroScience x AI<\/title>/, "papers homepage should use the Literature Library page title");
assert.match(html, /data-page="papers-homepage"/, "papers/ should identify itself as the homepage, not the reader workbench");
assert.match(html, /papers\/manifest\.json/, "papers homepage should load its project modules from papers/manifest.json");
assert.match(html, /id="project-grid"/, "papers homepage should include a project module grid");
assert.match(html, /id="project-empty"/, "papers homepage should include an empty project state");
assert.match(html, /<h1 id="page-title">[\s\S]*Literature[\s\S]*Library[\s\S]*<\/h1>/, "visible page title should be Literature Library without an inline logo");
assert.match(html, /<span class="title-line">Literature<\/span>[\s\S]*<span class="title-line">Library<\/span>/, "visible page title should split into stable text lines for narrow screens");
assert.doesNotMatch(html, /<h1 id="page-title">[\s\S]*title-x-mark[\s\S]*<\/h1>/, "page title should not keep a logo beside the text");
assert.match(html, /class="home-logo-link" href="\.\.\/index\.html" aria-label="Back to NeuroScience x AI homepage"[\s\S]*class="title-x-mark"[\s\S]*viewBox="0 0 96 96"/, "hero logo should be the return link to the main homepage");
assert.match(html, /title-x-left-bleed/, "logo mark should keep the organic neuroscience-side layer");
assert.match(html, /title-x-right-core/, "logo mark should keep the cleaner AI-side layer");
assert.match(html, /--grid-line:\s*rgba\(31,\s*39,\s*36,\s*0\.018\)/, "background grid should be faint like guidelines under rice paper");
assert.match(html, /--paper-fiber:\s*rgba\(109,\s*88,\s*53,\s*0\.032\)/, "papers homepage should define a subtle CSS paper fiber texture");
assert.match(html, /--paper-speck:\s*rgba\(49,\s*41,\s*30,\s*0\.035\)/, "papers homepage should define subtle paper speckling without image assets");
assert.match(html, /body\s*\{[\s\S]*?radial-gradient\(circle at 14% 18%, var\(--paper-speck\)/, "page background should use pure CSS paper grain");
assert.match(html, /body::before\s*\{[\s\S]*?repeating-linear-gradient\(8deg,[\s\S]*?var\(--paper-fiber\)/, "page background should include soft rice-paper fiber lines");
assert.match(html, /\.home-logo-link\s*\{[\s\S]*?margin-left:\s*clamp\(-18px,\s*-1\.4vw,\s*-8px\)/, "hero logo should slightly overhang the title block for a calligraphic layout");
assert.match(html, /h1\s*\{[\s\S]*?margin:\s*0 0 0 clamp\(10px,\s*2vw,\s*28px\)/, "Literature Library title should be slightly indented from the logo");
assert.match(html, /\.project-card\s*\{[\s\S]*?place-items:\s*center/, "project card title should sit in the visual center of the card");
assert.match(html, /\.project-card\s*\{[\s\S]*?border:\s*0;/, "project cards should remove the hard outline border");
assert.match(html, /\.project-card\s*\{[\s\S]*?backdrop-filter:\s*blur\(8px\) saturate\(0\.94\)/, "project cards should use a translucent paper/glass treatment");
assert.match(html, /\.project-card\s*\{[\s\S]*?0 28px 76px var\(--ink-shadow\)/, "project cards should use a soft ink-wash shadow instead of a hard line");
assert.match(html, /\.project-card::before\s*\{[\s\S]*?right:\s*18px;[\s\S]*?var\(--seal-red\)/, "project cards should include a small cinnabar seal mark in the upper right");
assert.match(html, /\.project-card h2\s*\{[\s\S]*?max-width:\s*12ch;[\s\S]*?text-align:\s*center/, "project card titles should stay centered with readable line lengths");
assert.doesNotMatch(html, /border:\s*1px solid var\(--edge\)/, "project cards should not return to the old hard border treatment");
assert.match(html, /还没有登记 paper/, "empty modules should not fake paper records");
assert.doesNotMatch(html, /class="topline"|class="brand-link"|class="manifest-link"|<span>NeuroScience x AI<\/span>|href="manifest\.json"|<p class="kicker">papers\/<\/p>/, "top buttons and papers kicker should be removed");
assert.doesNotMatch(html, /Project Paper Modules|Loaded from papers\/manifest\.json/, "project section should not show explanatory module copy");
assert.doesNotMatch(html, /class="project-link"|Open project folder|class="badge"|project-meta/, "project cards should not include nested folder buttons or status badges");
assert.match(html, /const card = document\.createElement\("a"\);/, "project modules should render as clickable cards");
assert.match(html, /card\.href = project\.folder;/, "project card link should use the project folder");
assert.match(html, /card\.className = "project-card";/, "project card should keep the module card styling");
assert.doesNotMatch(html, /project\.summary|paperLabel|statusLabels|data-status/, "project cards should not render summary, status, or paper count");
assert.doesNotMatch(html, /id="paper-viewer"|id="note-preview"|id="paper-search"|id="status-filter"|id="evidence-filter"|id="tag-strip"/, "homepage should remove the first-screen reader workbench controls");
assert.doesNotMatch(html, /SurrealDB|embedding|openai|anthropic|\/api\/|localhost:5055/i, "first version should remain static and avoid backend or AI-provider wiring");

assert.equal(Array.isArray(manifest), true, "papers/manifest.json should be a plain project array");

const allowedStatuses = new Set(["draft", "active", "paused", "archived"]);
const ids = new Set();

for (const [index, project] of manifest.entries()) {
  assert.equal(typeof project.id, "string", `project record ${index} should include an id`);
  assert.match(project.id, /^[a-z0-9]+(?:-[a-z0-9]+)*$/, `project record ${project.id} should use a stable slug id`);
  assert.equal(ids.has(project.id), false, `project record id ${project.id} should be unique`);
  ids.add(project.id);

  assert.equal(typeof project.title, "string", `project record ${project.id} should include a title`);
  assert.ok(project.title.trim().length > 0, `project record ${project.id} title should not be blank`);
  assert.equal(typeof project.folder, "string", `project record ${project.id} should include a project folder`);
  assert.match(project.folder, /^[a-z0-9]+(?:-[a-z0-9]+)*\/$/, `project record ${project.id} folder should be a relative project directory`);
  assert.equal(existsSync(new URL(`../papers/${project.folder}`, import.meta.url)), true, `project record ${project.id} folder should exist under papers/`);
  assert.equal(existsSync(new URL(`../papers/${project.folder}index.html`, import.meta.url)), true, `project record ${project.id} folder should expose a static topic page`);
  assert.equal(typeof project.summary, "string", `project record ${project.id} should include a summary`);
  assert.ok(project.summary.trim().length > 0, `project record ${project.id} summary should not be blank`);
  assert.equal(allowedStatuses.has(project.status), true, `project record ${project.id} should use an allowed status`);
  assert.equal(Array.isArray(project.papers), true, `project record ${project.id} should include a papers array`);

  for (const [paperIndex, paper] of project.papers.entries()) {
    assert.equal(typeof paper.id, "string", `paper ${paperIndex} in ${project.id} should include an id`);
    assert.match(paper.id, /^[a-z0-9]+(?:-[a-z0-9]+)*$/, `paper ${paper.id} in ${project.id} should use a stable slug id`);
    assert.equal(typeof paper.title, "string", `paper ${paper.id} in ${project.id} should include a title`);
    assert.ok(paper.title.trim().length > 0, `paper ${paper.id} in ${project.id} title should not be blank`);
  }
}
