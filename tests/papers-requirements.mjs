import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";

const paperPageUrl = new URL("../papers/index.html", import.meta.url);
const manifestUrl = new URL("../papers/manifest.json", import.meta.url);
const fontsDirUrl = new URL("../assets/fonts/", import.meta.url);
const titleFontUrl = new URL("../assets/fonts/MaShanZheng-WenXianGe.woff2", import.meta.url);
const bookmarkFontUrl = new URL("../assets/fonts/ZhiMangXing-Bookmark.woff2", import.meta.url);
const fontSourcesUrl = new URL("../assets/fonts/README.md", import.meta.url);
const paperPageExists = existsSync(paperPageUrl);
const manifestExists = existsSync(manifestUrl);

assert.equal(paperPageExists, true, "papers/ should expose a static homepage");
assert.equal(manifestExists, true, "papers/ should expose a manifest.json index for project paper modules");
assert.equal(existsSync(titleFontUrl), true, "title calligraphy subset font should be self-hosted as woff2");
assert.equal(existsSync(bookmarkFontUrl), true, "bookmark calligraphy subset font should be self-hosted as woff2");
assert.equal(existsSync(fontSourcesUrl), true, "self-hosted fonts should include source and license notes");
assert.ok(statSync(titleFontUrl).size > 0 && statSync(titleFontUrl).size < 120_000, "title subset font should be present without committing a full CJK font");
assert.ok(statSync(bookmarkFontUrl).size > 0 && statSync(bookmarkFontUrl).size < 160_000, "bookmark subset font should be present without committing a full CJK font");
assert.equal(
  readdirSync(fontsDirUrl).some((file) => /\.(?:ttf|otf)$/i.test(file)),
  false,
  "assets/fonts should not commit full source ttf or otf font files",
);

const html = readFileSync(paperPageUrl, "utf8");
const manifest = JSON.parse(readFileSync(manifestUrl, "utf8"));
const fontSources = readFileSync(fontSourcesUrl, "utf8");
const projectCardAfterCss = html.match(/\.project-card::after\s*\{[\s\S]*?\n      \}/)?.[0] ?? "";

assert.match(html, /<html lang="zh-CN">/, "papers homepage should use Chinese as the default research UI language");
assert.match(html, /<title>文献阁 \| NeuroScience x AI<\/title>/, "papers homepage should use the Chinese literature library page title");
assert.match(html, /data-page="papers-homepage"/, "papers/ should identify itself as the homepage, not the reader workbench");
assert.match(html, /papers\/manifest\.json/, "papers homepage should load its project modules from papers/manifest.json");
assert.match(html, /id="project-grid"/, "papers homepage should include a project module grid");
assert.match(html, /id="project-empty"/, "papers homepage should include an empty project state");
assert.match(html, /<h1 id="page-title"><span class="title-line">文献阁<\/span><\/h1>/, "visible page title should be the Chinese title 文献阁 without an inline logo");
assert.doesNotMatch(html, /<h1 id="page-title">[\s\S]*title-x-mark[\s\S]*<\/h1>/, "page title should not keep a logo beside the text");
assert.match(html, /class="home-logo-link" href="\.\.\/index\.html" aria-label="Back to NeuroScience x AI homepage"[\s\S]*class="title-x-mark"[\s\S]*viewBox="0 0 96 96"/, "hero logo should be the return link to the main homepage");
assert.match(html, /title-x-left-bleed/, "logo mark should keep the organic neuroscience-side layer");
assert.match(html, /title-x-right-core/, "logo mark should keep the cleaner AI-side layer");
assert.match(html, /--grid-line:\s*rgba\(31,\s*39,\s*36,\s*0\.018\)/, "background grid should be faint like guidelines under rice paper");
assert.match(html, /--paper-fiber:\s*rgba\(109,\s*88,\s*53,\s*0\.032\)/, "papers homepage should define a subtle CSS paper fiber texture");
assert.match(html, /--paper-speck:\s*rgba\(49,\s*41,\s*30,\s*0\.035\)/, "papers homepage should define subtle paper speckling without image assets");
assert.match(html, /--dai-blue:\s*#183c49/, "papers homepage should define a dai-blue ink tone for vertical bookmark titles");
assert.match(html, /@font-face\s*\{[\s\S]*?font-family:\s*"WenXianGe Title";[\s\S]*?url\("\.\.\/assets\/fonts\/MaShanZheng-WenXianGe\.woff2"\)\s*format\("woff2"\);[\s\S]*?font-display:\s*swap;[\s\S]*?font-weight:\s*400;/, "papers homepage should self-host the Ma Shan Zheng subset for the main title");
assert.match(html, /@font-face\s*\{[\s\S]*?font-family:\s*"WenXianGe Bookmark";[\s\S]*?url\("\.\.\/assets\/fonts\/ZhiMangXing-Bookmark\.woff2"\)\s*format\("woff2"\);[\s\S]*?font-display:\s*swap;[\s\S]*?font-weight:\s*400;/, "papers homepage should self-host the Zhi Mang Xing subset for bookmark titles");
assert.match(html, /--title-calligraphy-font:\s*"WenXianGe Title"[\s\S]*?"Ma Shan Zheng"[\s\S]*?serif;/, "main title should have a dedicated title calligraphy font stack");
assert.match(html, /--bookmark-calligraphy-font:\s*"WenXianGe Bookmark"[\s\S]*?"Zhi Mang Xing"[\s\S]*?serif;/, "bookmark titles should have a dedicated slender calligraphy font stack");
assert.match(html, /--mist-jade:\s*rgba\(194,\s*221,\s*214,\s*0\.36\)/, "bookmark cards should use a more transparent pale jade glass tone");
assert.match(html, /--ice-edge:\s*rgba\(255,\s*255,\s*255,\s*0\.68\)/, "bookmark cards should define a brighter translucent white ice edge");
assert.match(html, /body\s*\{[\s\S]*?radial-gradient\(circle at 14% 18%, var\(--paper-speck\)/, "page background should use pure CSS paper grain");
assert.match(html, /body::before\s*\{[\s\S]*?repeating-linear-gradient\(8deg,[\s\S]*?var\(--paper-fiber\)/, "page background should include soft rice-paper fiber lines");
assert.match(html, /radial-gradient\(ellipse at 18% 76%, rgba\(24,\s*60,\s*73,\s*0\.09\)/, "background should add a faint dai-blue ink wash");
assert.match(html, /\.shell\s*\{[\s\S]*?display:\s*grid;[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\) clamp\(178px,\s*19vw,\s*238px\);[\s\S]*?grid-template-areas:\s*"project-scroll title-axis"/, "desktop layout should place project bookmarks to the left and the title axis to the right");
assert.match(html, /header\s*\{[\s\S]*?grid-area:\s*title-axis;[\s\S]*?justify-self:\s*end/, "desktop header should occupy the right-side title axis");
assert.match(html, /main\s*\{[\s\S]*?grid-area:\s*project-scroll/, "project modules should occupy the left-side scroll area");
assert.match(html, /h1\s*\{[\s\S]*?font-family:\s*var\(--title-calligraphy-font\);[\s\S]*?font-weight:\s*400;[\s\S]*?writing-mode:\s*vertical-rl;[\s\S]*?text-orientation:\s*upright;[\s\S]*?white-space:\s*nowrap/, "desktop 文献阁 title should use the bold self-hosted calligraphy font and render as a vertical right-side axis");
assert.match(html, /h1\s*\{[\s\S]*?filter:\s*drop-shadow\(0 0 0\.45px rgba\(31,\s*39,\s*36,\s*0\.42\)\)/, "main title should add a subtle ink edge without image assets");
assert.match(html, /\.title-line\s*\{[\s\S]*?display:\s*block/, "desktop title words should stack as vertical title lines");
assert.match(html, /\.project-grid\s*\{[\s\S]*?display:\s*flex;[\s\S]*?flex-flow:\s*row-reverse wrap/, "project bookmarks should spread from right to left on desktop");
assert.match(html, /\.project-card\s*\{[\s\S]*?width:\s*clamp\(96px,\s*9vw,\s*124px\);[\s\S]*?height:\s*clamp\(360px,\s*62vh,\s*500px\)/, "project cards should become narrow and elongated bookmark slips");
assert.match(html, /\.project-card\s*\{[\s\S]*?place-items:\s*stretch center/, "project card content should align within the vertical bookmark shape");
assert.match(html, /\.project-card\s*\{[\s\S]*?border:\s*0;/, "project cards should remove the hard outline border");
assert.match(html, /\.project-card\s*\{[\s\S]*?clip-path:\s*polygon\(0 0,\s*100% 0,\s*100% 100%,\s*50% 92%,\s*0 100%\)/, "project cards should use a swallowtail bookmark silhouette instead of a plain rectangle");
assert.match(html, /\.project-card\s*\{[\s\S]*?var\(--mist-jade\);[\s\S]*?backdrop-filter:\s*blur\(26px\) saturate\(1\.28\)/, "bookmark cards should use stronger and more transparent jade glass");
assert.match(html, /\.project-card\s*\{[\s\S]*?inset 0 0 0 1px var\(--ice-edge\)[\s\S]*?0 36px 104px var\(--ink-shadow\)/, "bookmark cards should use a brighter white ice edge and soft ink-wash shadow");
assert.match(html, /\.project-card\s*\{[\s\S]*?--card-lift:\s*0px;[\s\S]*?transform:\s*translateY\(var\(--card-lift\)\)/, "bookmark cards should expose a stable vertical offset variable for future staggered projects");
assert.match(html, /\.project-card:nth-child\(3n \+ 2\)\s*\{[\s\S]*?--card-lift:\s*-18px/, "second bookmark column should sit slightly higher on desktop for handscroll rhythm");
assert.match(html, /\.project-card:nth-child\(3n\)\s*\{[\s\S]*?--card-lift:\s*14px/, "third bookmark column should sit slightly lower on desktop for handscroll rhythm");
assert.match(html, /\.project-card::before\s*\{[\s\S]*?top:\s*60px;[\s\S]*?left:\s*50%;[\s\S]*?var\(--seal-red\)[\s\S]*?translateX\(-50%\) rotate\(-2deg\)/, "cinnabar seal should sit near the top center below the bookmark hole");
assert.match(html, /\.project-card::after\s*\{[\s\S]*?radial-gradient\(circle at 50% 24px,[\s\S]*?radial-gradient\(circle at 50% 42px,[\s\S]*?linear-gradient\(90deg,\s*transparent calc\(50% - 0\.65px\),\s*rgba\(112,\s*38,\s*34,\s*0\.42\)[\s\S]*?100% 54px/, "bookmark cards should draw only a short top cord with a knot cue");
assert.match(html, /\.project-card::after\s*\{[\s\S]*?linear-gradient\(90deg,\s*transparent 0 47%,\s*rgba\(24,\s*60,\s*73,\s*0\.035\) 49\.6% 50\.4%,\s*transparent 53% 100%\)/, "bookmark cards should keep only a faint paper crease after the cord stops");
assert.match(html, /\.project-card h2\s*\{[\s\S]*?color:\s*var\(--dai-blue\);[\s\S]*?font-family:\s*var\(--bookmark-calligraphy-font\);[\s\S]*?font-weight:\s*400;[\s\S]*?writing-mode:\s*vertical-rl;[\s\S]*?text-orientation:\s*upright;[\s\S]*?white-space:\s*nowrap/, "project card titles should use the self-hosted slender calligraphy font with dai-blue upright Chinese vertical text");
assert.match(html, /@media \(min-width:\s*681px\) and \(max-width:\s*980px\)[\s\S]*?\.shell\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\) clamp\(96px,\s*13vw,\s*132px\);[\s\S]*?gap:\s*clamp\(22px,\s*5vw,\s*48px\)/, "narrow desktop should keep the right title axis while tightening columns and gaps");
assert.match(html, /@media \(min-width:\s*681px\) and \(max-width:\s*980px\)[\s\S]*?\.home-logo-link\s*\{[\s\S]*?width:\s*clamp\(52px,\s*7vw,\s*68px\);[\s\S]*?h1\s*\{[\s\S]*?font-size:\s*clamp\(68px,\s*9vw,\s*88px\)/, "narrow desktop should scale down the logo and vertical title instead of switching to mobile");
assert.match(html, /@media \(max-width:\s*680px\)[\s\S]*?\.shell\s*\{[\s\S]*?display:\s*block;[\s\S]*?header\s*\{[\s\S]*?width:\s*100%;[\s\S]*?justify-self:\s*auto/, "mobile should reset the header from the right-side desktop axis");
assert.match(html, /@media \(max-width:\s*680px\)[\s\S]*?\.hero\s*\{[\s\S]*?justify-items:\s*center;[\s\S]*?h1\s*\{[\s\S]*?writing-mode:\s*horizontal-tb;[\s\S]*?justify-content:\s*center/, "mobile should center the logo and horizontal title on one axis");
assert.match(html, /@media \(max-width:\s*680px\)[\s\S]*?\.project-grid\s*\{[\s\S]*?flex-direction:\s*column;[\s\S]*?align-items:\s*center;[\s\S]*?justify-content:\s*center/, "mobile should keep bookmark modules centered under the title axis");
assert.match(html, /@media \(max-width:\s*680px\)[\s\S]*?\.project-card(?:\:nth-child\(3n \+ 2\),\s*\.project-card\:nth-child\(3n\)|[\s\S]*?\.project-card:nth-child\(3n\))\s*\{[\s\S]*?--card-lift:\s*0px/, "mobile should disable desktop bookmark staggering");
assert.doesNotMatch(html, /@media \(max-width:\s*820px\)/, "mobile breakpoint should not trigger at narrow desktop widths");
assert.doesNotMatch(html, /border:\s*1px solid var\(--edge\)/, "project cards should not return to the old hard border treatment");
assert.doesNotMatch(html, /\.project-card::before\s*\{[\s\S]*?bottom:\s*24px/, "cinnabar seal should not return to the bottom bookmark signature position");
assert.doesNotMatch(projectCardAfterCss, /100%\s+100%/, "bookmark cord should not return to a full-height hanging line");
assert.doesNotMatch(html, /Brain Memory for AI Agents|Literature Library/, "visible papers homepage copy should be localized to Chinese");
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
assert.match(fontSources, /Ma Shan Zheng[\s\S]*?SIL Open Font License/i, "font notes should document Ma Shan Zheng source and OFL license");
assert.match(fontSources, /Zhi Mang Xing[\s\S]*?SIL Open Font License/i, "font notes should document Zhi Mang Xing source and OFL license");
assert.match(fontSources, /pyftsubset[\s\S]*?文献阁[\s\S]*?记忆与智能体/, "font notes should document the subset command intent and included characters");

assert.equal(Array.isArray(manifest), true, "papers/manifest.json should be a plain project array");
assert.equal(manifest[0]?.title, "记忆与智能体", "current project module should use the Chinese bookmark title");

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
