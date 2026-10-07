import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../papers/shared/reader.js", import.meta.url), "utf8");
const initOffset = source.lastIndexOf("\ninitReader().catch(");
assert.ok(initOffset > 0, "reader entry point must be isolated from the test DOM");
const manifest = JSON.parse(readFileSync(new URL("../papers/manifest.json", import.meta.url), "utf8"));
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function createReader(fetch, projectId = "test", query = "") {
  const context = vm.createContext({
    URL, URLSearchParams, console, fetch,
    document: {
      body: { dataset: { projectId } },
      querySelector: () => ({}),
      querySelectorAll: () => []
    },
    window: {
      location: { href: `https://example.test/papers/${projectId}/${query}`, search: query },
      history: { replaceState() {} }
    }
  });
  const api = vm.runInContext(`${source.slice(0, initOffset)}\n({
    state, loadReadingPackage, loadAllSearchItems, getHybridSearchResults,
    getLexicalScore, getSearchSnippet, highlightSearchTerms, openPaper, initReader, DOMAIN_DIMS
  })`, context);
  return { ...api, evaluate: (code) => vm.runInContext(code, context) };
}

function fixturePaper(id, hasReading = true) {
  return { id, title: "Memory agent", shortTitle: "Memory", hasReading };
}

function fixtureFile(file, id) {
  const chunk = {
    id: `${id}-chunk`, sectionId: "s", sourceText: "agent memory", zhTranslation: "智能体记忆",
    zhExplanation: "海马检索", claim: "memory claim", premise: "memory premise",
    evidence: ["memory evidence"], keywords: ["memory"]
  };
  return {
    "paper.json": { sections: [{ id: "s", title: "Memory section" }] },
    "chunks.json": { chunks: [chunk] },
    "notes.json": { notes: [] },
    "embeddings.json": { items: [{ chunkId: chunk.id, vector: [1, 0, 0] }] },
    "figures.json": { figures: [] }
  }[file];
}

function readRequest(url) {
  const parts = new URL(url).pathname.split("/");
  return { id: parts.at(-2), file: parts.at(-1) };
}

function ok(payload) {
  return { ok: true, json: async () => payload };
}

async function within(promise, ms = 150) {
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("operation did not settle")), ms); })
    ]);
  } finally {
    clearTimeout(timer);
  }
}

function silenceRendering(reader) {
  reader.evaluate(`
    stopObservingChunks = closeMobilePanels = renderReaderViewControls = renderPaperNav =
      renderPaperHeader = renderSectionRail = renderChunks = renderNoChunkPaper = () => {};
    resetReaderPosition = async () => {};
  `);
}

test("three loading workers preserve manifest order and share an in-flight quick click", async () => {
  const papers = Array.from({ length: 7 }, (_, index) => fixturePaper(`p${index}`));
  const delays = [32, 4, 18, 2, 10, 3, 1];
  const requests = new Map();
  const completed = [];
  let active = 0;
  let maximum = 0;
  const reader = createReader(async (url) => {
    const { id, file } = readRequest(url);
    requests.set(String(url), (requests.get(String(url)) ?? 0) + 1);
    maximum = Math.max(maximum, ++active);
    await pause(delays[Number(id.slice(1))]);
    active -= 1;
    if (file === "figures.json") completed.push(id);
    return ok(fixtureFile(file, id));
  });
  reader.state.papers = papers;
  silenceRendering(reader);
  const loading = reader.loadAllSearchItems();
  assert.equal(requests.size, 15, "only three packages start immediately");
  const clicks = [reader.openPaper("p0"), reader.openPaper("p0")];
  assert.equal(requests.size, 15, "opening a loading paper must reuse its requests");
  await Promise.all([loading, ...clicks]);
  assert.equal(maximum, 15, "successful package loads must not exceed 15 simultaneous JSON requests");
  assert.notDeepEqual(completed, papers.map((paper) => paper.id), "fixture must finish out of order");
  assert.deepEqual(Array.from(reader.state.searchItems, (item) => item.paper.id), papers.map((paper) => paper.id));
  assert.ok([...requests.values()].every((count) => count === 1));
  assert.equal(reader.state.pendingReadings.size, 0);
  assert.equal(reader.state.currentReading, reader.state.allReadings.get("p0"));
  assert.equal(await reader.loadReadingPackage(papers[0]), reader.state.currentReading);
  assert.equal(requests.size, 35);
});

test("non-reading papers and empty collections make no package requests", async () => {
  const reader = createReader(() => assert.fail("unexpected fetch"));
  const papers = [fixturePaper("disabled", false), { id: "missing-flag" }];
  reader.state.papers = papers;
  await reader.loadAllSearchItems();
  assert.equal(reader.state.searchItems.length, 0);
  for (const paper of papers) {
    assert.equal(await reader.loadReadingPackage(paper), null);
    assert.equal(reader.state.allReadings.has(paper.id), true);
  }
  reader.state.papers = [];
  await reader.loadAllSearchItems();
  assert.equal(reader.state.searchItems.length, 0);
});

test("required failures and optional figure failures retain their existing cache semantics", async () => {
  for (const file of ["paper.json", "chunks.json", "notes.json", "embeddings.json", "figures.json"]) {
    for (const failure of ["http", "network", "json"]) {
      let requests = 0;
      const paper = fixturePaper("failure");
      const reader = createReader(async (url) => {
        requests += 1;
        const request = readRequest(url);
        if (request.file !== file) return ok(fixtureFile(request.file, request.id));
        if (failure === "http") return { ok: false, status: 404 };
        if (failure === "network") throw new Error("network failure");
        return { ok: true, json: async () => { throw new SyntaxError("invalid JSON"); } };
      });
      const [first, second] = await Promise.all([reader.loadReadingPackage(paper), reader.loadReadingPackage(paper)]);
      assert.equal(first, second, `${file}/${failure}: concurrent callers must share the same result`);
      if (file === "figures.json" && failure === "http") {
        assert.ok(first);
        assert.equal(first.figures.size, 0);
      } else {
        assert.equal(first, null, `${file}/${failure}`);
      }
      assert.equal(await reader.loadReadingPackage(paper), first);
      assert.equal(requests, 5, `${file}/${failure}: cached failures must not retry`);
      assert.equal(reader.state.pendingReadings.size, 0);
    }
  }
});

test("a failed required request remains fail-fast even when another request never settles", async () => {
  const failed = fixturePaper("failed");
  const reader = createReader(async (url) => {
    const { id, file } = readRequest(url);
    if (id === "failed" && file === "paper.json") return { ok: false, status: 500 };
    if (id === "failed" && file === "notes.json") return new Promise(() => {});
    return ok(fixtureFile(file, id));
  });
  assert.equal(await within(reader.loadReadingPackage(failed)), null);
  assert.equal(reader.state.pendingReadings.size, 0);
  reader.state.papers = [failed, fixturePaper("healthy")];
  await within(reader.loadAllSearchItems());
  assert.deepEqual(Array.from(reader.state.searchItems, (item) => item.paper.id), ["healthy"]);
});

test("initial reading still waits for the complete search library and preserves deep links", async () => {
  const papers = [fixturePaper("first"), fixturePaper("requested"), fixturePaper("last")];
  let releaseLast;
  const last = new Promise((resolve) => { releaseLast = resolve; });
  const reader = createReader(async (url) => {
    if (new URL(url).pathname.endsWith("/manifest.json")) return ok([{ id: "test", papers }]);
    if (new URL(url).pathname.endsWith("/research-atlas.json")) return { ok: false };
    const { id, file } = readRequest(url);
    if (id === "last") await last;
    return ok(fixtureFile(file, id));
  }, "test", "?paper=requested&chunk=requested-chunk");
  reader.evaluate(`
    globalThis.opened = [];
    loadAnnotations = () => ({});
    bindControls = renderPaperNav = () => {};
    openPaper = async (...args) => { opened.push(args); };
  `);
  const initializing = reader.initReader();
  await pause(0);
  assert.equal(reader.evaluate("opened.length"), 0, "the first view must still wait for all packages");
  releaseLast();
  await initializing;
  assert.equal(reader.evaluate("JSON.stringify(opened)"), '[["requested","requested-chunk"]]');
});

// Frozen pre-optimization scoring oracle: use raw content, not the new cached fields.
function legacyLexicalScore(item, query) {
  const terms = query.trim().split(/\s+/).filter(Boolean).map((term) => term.toLowerCase());
  const section = item.reading.paperData.sections.find((entry) => entry.id === item.chunk.sectionId);
  const fields = [
    [item.paper.title, 5], [item.paper.shortTitle, 5], [section?.titleZh ?? section?.title ?? "Section", 4],
    [item.chunk.claim, 4], [item.chunk.premise, 3], [item.chunk.sourceText, 2],
    [item.chunk.zhTranslation, 2], [item.chunk.zhExplanation, 2],
    [(item.chunk.evidence ?? []).join(" "), 3], [(item.chunk.keywords ?? []).join(" "), 3]
  ];
  let score = 0;
  for (const [field, weight] of fields) {
    for (const term of terms) {
      if (String(field ?? "").toLowerCase().includes(term)) score += weight;
    }
  }
  return score;
}

function legacyResults(items, query, currentPaper, dimensions) {
  const lower = String(query ?? "").toLowerCase();
  const vector = dimensions.map(([, terms], index) => {
    let score = 0;
    for (const term of terms) {
      const pattern = term.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      score += lower.match(new RegExp(pattern, "g"))?.length ?? 0;
    }
    return score + ((lower.length + index * 17) % 11) / 100;
  });
  const magnitude = Math.sqrt(vector.reduce((sum, value) => sum + value * value, 0)) || 1;
  const queryVector = vector.map((value) => value / magnitude);
  const allowSemanticOnly = dimensions.some(([, terms]) => terms.some((term) => lower.includes(term.toLowerCase())));
  return Array.from(items, (item) => {
    const lexicalScore = legacyLexicalScore(item, query);
    let dot = 0;
    let left = 0;
    let right = 0;
    for (let index = 0; index < Math.min(queryVector.length, item.vector.length); index += 1) {
      dot += queryVector[index] * item.vector[index];
      left += queryVector[index] * queryVector[index];
      right += item.vector[index] * item.vector[index];
    }
    const semanticScore = dot / ((Math.sqrt(left) || 1) * (Math.sqrt(right) || 1));
    return {
      paperId: item.paper.id, chunkId: item.chunk.id, lexicalScore, semanticScore,
      score: lexicalScore * 10 + semanticScore,
      resultType: item.paper.id === currentPaper?.id ? "chunk" : "paper"
    };
  }).filter(({ lexicalScore, semanticScore }) =>
    (lexicalScore > 0 || semanticScore >= 0.42) && (lexicalScore > 0 || allowSemanticOnly)
  ).sort((left, right) => right.score - left.score).slice(0, 8);
}

function resultRows(results) {
  return Array.from(results, ({ paper, chunk, lexicalScore, semanticScore, score, resultType }) => ({
    paperId: paper.id, chunkId: chunk.id, lexicalScore, semanticScore, score, resultType
  }));
}

test("all real reading packages match legacy search scores, fields, ordering and result types", async (t) => {
  let paperCount = 0;
  let itemCount = 0;
  let queryCount = 0;
  for (const collection of manifest) {
    const reader = createReader(async (url) => {
      const path = new URL(url).pathname.replace(/^\/papers\//, "");
      return ok(JSON.parse(readFileSync(new URL(`../papers/${path}`, import.meta.url), "utf8")));
    }, collection.id);
    reader.state.papers = collection.papers;
    await reader.loadAllSearchItems();
    const queries = new Set(["", "memory", "Memory MEMORY", " agent\t memory\n", "海马 检索", "检索检索", "formula", "café", "[unknown]+", "no_such_match_xyz"]);
    for (const item of reader.state.searchItems) {
      for (const [field] of item.lexicalFields) {
        const term = field.match(/[\p{L}\p{N}][\p{L}\p{N}_-]{1,16}/u)?.[0];
        if (term) queries.add(term);
      }
    }
    for (const query of queries) {
      const terms = query.trim().split(/\s+/).filter(Boolean).map((term) => term.toLowerCase());
      for (const item of reader.state.searchItems) {
        assert.equal(reader.getLexicalScore(item, terms), legacyLexicalScore(item, query), `${collection.id}/${item.chunk.id}/${query}`);
      }
      for (const paper of collection.papers) {
        reader.state.currentPaper = paper;
        assert.deepEqual(
          resultRows(reader.getHybridSearchResults(query)),
          legacyResults(reader.state.searchItems, query, paper, reader.DOMAIN_DIMS),
          `${collection.id}/${paper.id}/${query}`
        );
        queryCount += 1;
      }
    }
    paperCount += collection.papers.filter((paper) => paper.hasReading === true).length;
    itemCount += reader.state.searchItems.length;
  }
  assert.ok(paperCount >= 17 && itemCount >= 202, "all existing published packages must be exercised");
  t.diagnostic(`${paperCount} papers, ${itemCount} searchable chunks, ${queryCount} query/current-paper comparisons`);
});

test("duplicate query words retain their weight and equal-score results retain source order", async () => {
  const reader = createReader(async (url) => {
    const { id, file } = readRequest(url);
    return ok(fixtureFile(file, id));
  });
  reader.state.papers = Array.from({ length: 10 }, (_, index) => fixturePaper(`p${index}`));
  await reader.loadAllSearchItems();
  const item = reader.state.searchItems[0];
  assert.equal(reader.getLexicalScore(item, ["memory", "memory"]), 2 * reader.getLexicalScore(item, ["memory"]));
  assert.deepEqual(Array.from(reader.getHybridSearchResults("MEMORY memory"), (result) => result.paper.id),
    reader.state.papers.slice(0, 8).map((paper) => paper.id));
  assert.equal(reader.getSearchSnippet(item, "智能体"), "智能体记忆");
  assert.equal(reader.highlightSearchTerms("Memory & memory", "memory"),
    '<mark class="result-highlight">Memory</mark> &amp; <mark class="result-highlight">memory</mark>');
});
