import assert from "node:assert/strict";
import {
  copyCodeListingSource,
  createCodeListingModel,
} from "../projects/foundations/roadmap/code-listing.js";

assert.deepEqual(
  createCodeListingModel("one\ntwo\nthree\n", "language-python hljs"),
  {
    source: "one\ntwo\nthree",
    language: "python",
    label: "PYTHON",
    lineCount: 3,
    lineNumbers: [],
  },
);

assert.deepEqual(
  createCodeListingModel("one\ntwo\nthree\nfour\n", "hljs language-typescript"),
  {
    source: "one\ntwo\nthree\nfour",
    language: "typescript",
    label: "TYPESCRIPT",
    lineCount: 4,
    lineNumbers: [1, 2, 3, 4],
  },
);

assert.equal(createCodeListingModel("value", "").label, "CODE");
assert.equal(createCodeListingModel("", "language-json").lineCount, 0);

let copied = "";
await copyCodeListingSource("print('ok')", {
  async writeText(value) {
    copied = value;
  },
});
assert.equal(copied, "print('ok')");

await assert.rejects(
  copyCodeListingSource("value", null),
  /Clipboard API is unavailable/,
);
