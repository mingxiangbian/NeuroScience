import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

// Frozen pre-change behavior. Only the small directory loader is retained here;
// the test has no dependency on temporary baseline files or an external DOM package.
function legacyProgram(kind) {
  return `
    const MANIFEST_LABEL = "${kind}/manifest.json";
    const MANIFEST_URL = "manifest.json";
    const els = {
      grid: document.getElementById("project-grid"),
      empty: document.getElementById("project-empty")
    };
    function escapeHtml(value) {
      return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
    }
    function normalizeProject(record) {
      return { title: String(record.title ?? "Untitled project"), folder: String(record.folder ?? "") };
    }
    function renderProjects(projects) {
      els.grid.replaceChildren();
      els.empty.hidden = projects.length !== 0;
      for (const project of projects) {
        const card = document.createElement("a");
        card.className = "project-card";
        card.href = project.folder;
        ${kind === "projects" ? 'card.setAttribute("data-title-script", /[A-Za-z]/.test(project.title) ? "latin" : "cjk");' : ""}
        card.innerHTML = "\\n <h2>" + escapeHtml(project.title) + "</h2>\\n";
        els.grid.append(card);
      }
    }
    async function loadProjects() {
      try {
        const response = await fetch(MANIFEST_URL);
        if (!response.ok) throw new Error("HTTP " + response.status);
        const records = await response.json();
        if (!Array.isArray(records)) throw new Error("manifest is not an array");
        renderProjects(records.map(normalizeProject));
      } catch (error) {
        els.empty.hidden = false;
        els.empty.textContent = "无法加载 " + MANIFEST_LABEL + ": " + error.message;
      }
    }
    void loadProjects();
  `;
}

function currentProgram(kind) {
  const html = readFileSync(new URL(`../${kind}/index.html`, import.meta.url), "utf8");
  const scripts = [...html.matchAll(/<script type="module">([\s\S]*?)<\/script>/g)];
  assert.equal(scripts.length, 1);
  return scripts[0][1];
}

class Element {
  constructor(tagName) {
    this.tagName = tagName;
    this.attributes = {};
    this.children = [];
    this.text = "";
    this.hidden = false;
    this.replacements = 0;
    this.htmlAssignments = 0;
  }
  set className(value) { this.setAttribute("class", value); }
  set href(value) { this.setAttribute("href", value); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) {
    this.replacements += 1;
    this.children = children;
    this.text = "";
  }
  set textContent(value) {
    this.text = String(value);
    this.children = [];
  }
  get textContent() { return this.text + this.children.map((child) => child.textContent).join(""); }
  set innerHTML(html) {
    this.htmlAssignments += 1;
    // The old renderer escapes every dynamic character and emits exactly one h2.
    // Ignore the surrounding whitespace-only text nodes, which are not grid items.
    const match = /^\s*<h2>([\s\S]*)<\/h2>\s*$/.exec(html);
    assert.ok(match, "legacy card should contain only its heading");
    assert.ok(!match[1].includes("<"), "legacy title should be escaped before HTML parsing");
    const entities = { amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'" };
    const heading = new Element("h2");
    heading.textContent = match[1].replace(/&(amp|lt|gt|quot|#39);/g, (_, name) => entities[name]);
    this.children = [heading];
  }
  snapshot() {
    return {
      tagName: this.tagName, attributes: this.attributes, hidden: this.hidden,
      text: this.text, children: this.children.map((child) => child.snapshot())
    };
  }
}

function harness(kind, program, fetchResponse) {
  const grid = new Element("section");
  const empty = new Element("div");
  empty.hidden = true;
  empty.textContent = `还没有登记 ${kind === "projects" ? "research" : "paper"} 项目。`;
  const requests = [];
  const context = vm.createContext({
    document: {
      getElementById: (id) => id === "project-grid" ? grid : empty,
      createElement: (tag) => new Element(tag)
    },
    fetch: (url) => { requests.push(url); return fetchResponse(url); }
  });
  assert.match(program, /void loadProjects\(\);/);
  const api = vm.runInContext(
    program.replace("void loadProjects();", "const initialLoad = loadProjects();")
      + "\n({ initialLoad, loadProjects })", context
  );
  return {
    ...api, grid, empty, requests,
    snapshot: () => ({ grid: grid.snapshot(), empty: empty.snapshot() })
  };
}

const response = (records) => ({ ok: true, json: async () => records });

for (const kind of ["projects", "papers"]) {
  test(`${kind}: real manifest and unusual titles preserve meaningful DOM, links and order`, async () => {
    const actualRecords = JSON.parse(readFileSync(new URL(`../${kind}/manifest.json`, import.meta.url), "utf8"));
    const records = [
      ...actualRecords,
      { title: "中文书签", folder: "中文/" },
      { title: "English 标题", folder: "mixed/?a=1&b=2#part" },
      { title: '<img src=x onerror="alert(1)"> & \'quoted\' </h2>', folder: "a&b/" },
      { title: "&lt; &#39; &amp; &#x3C;", folder: "../relative/" },
      { title: "第一行\nsecond line\t🙂", folder: "/absolute/" },
      { title: null, folder: null }, {},
      { title: "", folder: "" }, { title: 0, folder: 0 }, { title: false, folder: false },
      { title: ["中文", "ABC"], folder: ["a", "b"] },
      { title: { key: "value" }, folder: {} }, 42, false, "primitive", []
    ];
    const before = harness(kind, legacyProgram(kind), async () => response(records));
    const after = harness(kind, currentProgram(kind), async () => response(records));
    await Promise.all([before.initialLoad, after.initialLoad]);
    assert.deepEqual(after.snapshot(), before.snapshot());
    assert.equal(after.grid.children.length, records.length);
    assert.ok(after.grid.children.every((card) => card.htmlAssignments === 0));
    assert.deepEqual(after.requests, ["manifest.json"]);
    assert.equal(after.empty.hidden, true);
  });

  test(`${kind}: loading begins immediately and keeps the initial empty state until JSON is ready`, async () => {
    let release;
    const pending = new Promise((resolve) => { release = resolve; });
    const before = harness(kind, legacyProgram(kind), async () => pending);
    const after = harness(kind, currentProgram(kind), async () => pending);
    assert.deepEqual(after.requests, ["manifest.json"]);
    assert.deepEqual(after.snapshot(), before.snapshot());
    assert.equal(after.grid.replacements, 0);
    release(response([{ title: "标题", folder: "title/" }]));
    await Promise.all([before.initialLoad, after.initialLoad]);
    assert.deepEqual(after.snapshot(), before.snapshot());
  });

  test(`${kind}: empty lists, schema errors, malformed JSON, HTTP and network failures are unchanged`, async () => {
    const cases = [
      () => response([]),
      ...[{}, null, "not an array", 1, false].map((records) => () => response(records)),
      () => ({ ok: false, status: 403 }),
      () => ({ ok: false, status: 404 }),
      () => ({ ok: true, json: async () => { throw new SyntaxError("Unexpected token"); } }),
      () => { throw new Error("network unavailable"); }
    ];
    for (const fetchResponse of cases) {
      const before = harness(kind, legacyProgram(kind), fetchResponse);
      const after = harness(kind, currentProgram(kind), fetchResponse);
      await Promise.all([before.initialLoad, after.initialLoad]);
      assert.deepEqual(after.snapshot(), before.snapshot());
      assert.equal(after.empty.hidden, false);
      assert.equal(after.grid.children.length, 0);
      assert.deepEqual(after.requests, ["manifest.json"]);
    }
  });

  test(`${kind}: a later invalid record does not clear or partially replace previously rendered cards`, async () => {
    for (const invalid of [null, undefined, { title: { toString: null } }, { folder: { toString: null } }]) {
      let records = [{ title: "Original", folder: "original/" }];
      const before = harness(kind, legacyProgram(kind), async () => response(records));
      const after = harness(kind, currentProgram(kind), async () => response(records));
      await Promise.all([before.initialLoad, after.initialLoad]);
      records = [{ title: "Would be new", folder: "new/" }, invalid];
      await Promise.all([before.loadProjects(), after.loadProjects()]);
      assert.deepEqual(after.snapshot(), before.snapshot());
      assert.equal(after.grid.replacements, 1, "normalization must finish before clearing the existing grid");
      assert.equal(after.grid.children[0].textContent, "Original");
      assert.equal(after.empty.hidden, false);
      assert.match(after.empty.textContent, new RegExp(`^无法加载 ${kind}/manifest.json:`));
      records = [];
      await Promise.all([before.loadProjects(), after.loadProjects()]);
      assert.deepEqual(after.snapshot(), before.snapshot(), "recovery must retain existing empty/error text behavior");
      records = [{ title: "Recovered", folder: "recovered/" }];
      await Promise.all([before.loadProjects(), after.loadProjects()]);
      assert.deepEqual(after.snapshot(), before.snapshot());
    }
  });
}
