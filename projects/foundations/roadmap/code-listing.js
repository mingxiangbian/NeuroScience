const LANGUAGE_CLASS_PATTERN = /(?:^|\s)language-([a-z0-9_+-]+)(?:\s|$)/i;
const COPY_RESET_DELAY_MS = 1500;

const COPY_ICON = `
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect>
    <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path>
  </svg>
`;

const CHECK_ICON = `
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M20 6 9 17l-5-5"></path>
  </svg>
`;

export function createCodeListingModel(text, className = "") {
  const source = String(text ?? "").replace(/\r?\n$/, "");
  const language = className.match(LANGUAGE_CLASS_PATTERN)?.[1]?.toLowerCase() ?? "";
  const lineCount = source ? source.split("\n").length : 0;
  return {
    source,
    language,
    label: language ? language.toUpperCase() : "CODE",
    lineCount,
    lineNumbers: lineCount >= 4
      ? Array.from({ length: lineCount }, (_, index) => index + 1)
      : [],
  };
}

export async function copyCodeListingSource(source, clipboard) {
  if (typeof clipboard?.writeText !== "function") {
    throw new Error("Clipboard API is unavailable");
  }
  await clipboard.writeText(source);
}

function setCopyButtonState(button, state) {
  const labels = {
    error: "复制失败",
    idle: "复制代码",
    success: "已复制",
  };
  button.dataset.copyState = state;
  button.setAttribute("aria-label", labels[state]);
  button.title = labels[state];
  button.innerHTML = state === "success" ? CHECK_ICON : COPY_ICON;
}

export function enhanceCodeListings(root, {
  clipboard = globalThis.navigator?.clipboard,
  schedule = globalThis.setTimeout,
} = {}) {
  if (!root?.querySelectorAll) return;
  const ownerDocument = root.ownerDocument ?? globalThis.document;

  root.querySelectorAll("pre > code").forEach((code) => {
    if (code.classList.contains("language-mermaid")) return;
    const pre = code.parentElement;
    if (!pre || pre.closest(".code-listing")) return;

    const model = createCodeListingModel(code.textContent, code.className);
    const listing = ownerDocument.createElement("figure");
    listing.className = "code-listing";

    const header = ownerDocument.createElement("figcaption");
    header.className = "code-listing-header";
    header.dataset.annotationExclude = "true";

    const label = ownerDocument.createElement("span");
    label.className = "code-listing-language";
    label.textContent = model.label;

    const copyButton = ownerDocument.createElement("button");
    copyButton.className = "code-listing-copy";
    copyButton.type = "button";
    setCopyButtonState(copyButton, "idle");
    copyButton.addEventListener("click", async () => {
      try {
        await copyCodeListingSource(model.source, clipboard);
        setCopyButtonState(copyButton, "success");
      } catch {
        setCopyButtonState(copyButton, "error");
      }
      schedule(() => setCopyButtonState(copyButton, "idle"), COPY_RESET_DELAY_MS);
    });

    header.append(label, copyButton);

    const body = ownerDocument.createElement("div");
    body.className = "code-listing-body";
    if (model.lineNumbers.length > 0) {
      const gutter = ownerDocument.createElement("div");
      gutter.className = "code-listing-gutter";
      gutter.dataset.annotationExclude = "true";
      gutter.setAttribute("aria-hidden", "true");
      for (const lineNumber of model.lineNumbers) {
        const item = ownerDocument.createElement("span");
        item.textContent = String(lineNumber);
        gutter.append(item);
      }
      body.append(gutter);
    }

    pre.replaceWith(listing);
    body.append(pre);
    listing.append(header, body);
  });
}
