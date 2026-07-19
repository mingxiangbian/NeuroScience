function setupReadingProgress() {
  const bar = document.querySelector(".reading-progress span");
  if (!bar) return;

  let frame = 0;
  const update = () => {
    frame = 0;
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    const progress = scrollable > 0 ? Math.min(1, Math.max(0, window.scrollY / scrollable)) : 0;
    bar.style.transform = `scaleX(${progress})`;
    bar.style.width = "100%";
  };
  const schedule = () => {
    if (frame) return;
    frame = window.requestAnimationFrame(update);
  };

  update();
  window.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule, { passive: true });
}

function renderMath() {
  const renderToString = window.katex?.renderToString;
  if (typeof renderToString !== "function") return false;

  document.querySelectorAll(".math-display[data-latex], .math-inline[data-latex]").forEach((element) => {
    if (element.dataset.mathRendered === "true") return;
    try {
      element.innerHTML = renderToString(element.dataset.latex ?? "", {
        displayMode: element.classList.contains("math-display"),
        throwOnError: false,
        strict: "ignore",
        trust: false,
      });
      element.dataset.mathRendered = "true";
    } catch (error) {
      console.warn("Unable to render Zaji formula", error);
    }
  });
  return true;
}

function setupMath() {
  if (renderMath()) return;
  window.addEventListener("load", renderMath, { once: true });
}

function setupWorksPreview() {
  const items = [...document.querySelectorAll(".work-list-item[data-preview-src]")];
  const lens = document.querySelector(".work-preview-lens");
  if (!lens || items.length === 0) return;

  const image = lens.querySelector("img");
  const title = lens.querySelector(":scope > strong");
  const meta = lens.querySelector(":scope > span");
  const link = lens.querySelector(":scope > a");
  if (!image || !title || !meta || !link) return;
  let selectionVersion = 0;

  const select = (item) => {
    const requestVersion = ++selectionVersion;
    const source = item.dataset.previewSrc;
    if (!source) return;
    const commit = (replaceImage) => {
      if (requestVersion !== selectionVersion) return;
      image.style.opacity = "0";
      if (replaceImage) image.src = source;
      image.alt = item.dataset.previewAlt ?? "成果页面预览";
      title.textContent = item.dataset.previewTitle ?? "";
      meta.textContent = item.dataset.previewMeta ?? "";
      link.href = item.dataset.previewHref ?? item.href;
      items.forEach((candidate) => candidate.classList.toggle("is-current", candidate === item));
      window.requestAnimationFrame(() => {
        if (requestVersion === selectionVersion) image.style.opacity = "1";
      });
    };
    if (source === image.getAttribute("src")) {
      commit(false);
      return;
    }
    const preload = new Image();
    preload.src = source;
    if (preload.complete) commit(true);
    else preload.addEventListener("load", () => commit(true), { once: true });
  };

  for (const item of items) {
    item.addEventListener("pointerenter", () => select(item));
    item.addEventListener("focus", () => select(item));
  }
}

function setupActiveToc() {
  const links = [...document.querySelectorAll(".article-toc-list a")];
  if (links.length === 0) return;
  const byId = new Map(links.map((link) => [decodeURIComponent(link.hash.slice(1)), link]));
  const headings = [...byId.keys()].map((id) => document.getElementById(id)).filter(Boolean);
  if (headings.length === 0) return;

  let frame = 0;
  const update = () => {
    frame = 0;
    const marker = Math.min(window.innerHeight * 0.28, 180);
    let activeId = headings[0].id;
    for (const heading of headings) {
      if (heading.getBoundingClientRect().top <= marker) activeId = heading.id;
      else break;
    }
    if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 4) {
      activeId = headings.at(-1).id;
    }
    for (const [id, link] of byId) {
      const isActive = id === activeId;
      link.classList.toggle("is-active", isActive);
      if (isActive) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
  };
  const schedule = () => {
    if (frame) return;
    frame = window.requestAnimationFrame(update);
  };

  update();
  window.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule, { passive: true });
}

setupReadingProgress();
setupMath();
setupWorksPreview();
setupActiveToc();
