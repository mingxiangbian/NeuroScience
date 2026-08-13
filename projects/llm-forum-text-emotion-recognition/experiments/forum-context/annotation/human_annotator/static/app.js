"use strict";

const elements = {
  loading: document.querySelector("#loading-state"),
  caseView: document.querySelector("#case-view"),
  breakState: document.querySelector("#session-break-state"),
  completeState: document.querySelector("#complete-state"),
  qualityStopState: document.querySelector("#quality-stop-state"),
  decisionPanel: document.querySelector("#decision-panel"),
  form: document.querySelector("#annotation-form"),
  formError: document.querySelector("#form-error"),
  submit: document.querySelector("#submit-decision"),
  endSession: document.querySelector("#end-session"),
  startSession: document.querySelector("#start-session"),
  notice: document.querySelector("#notice"),
  datasetMode: document.querySelector("#dataset-mode"),
  stageChip: document.querySelector("#stage-chip"),
  caseProgress: document.querySelector("#case-progress"),
  progressBar: document.querySelector("#progress-bar"),
  sessionCount: document.querySelector("#session-count"),
  stageKicker: document.querySelector("#stage-kicker"),
  stageTitle: document.querySelector("#stage-title"),
  caseNumber: document.querySelector("#case-number"),
  stageAView: document.querySelector("#stage-a-view"),
  stageBView: document.querySelector("#stage-b-view"),
  targetOnlyText: document.querySelector("#target-only-text"),
  discussionTitle: document.querySelector("#discussion-title"),
  parentText: document.querySelector("#parent-text"),
  quoteSection: document.querySelector("#quotes-section"),
  quoteCount: document.querySelector("#quote-count"),
  quoteList: document.querySelector("#quote-list"),
  targetFullText: document.querySelector("#target-full-text"),
  decisionStage: document.querySelector("#decision-stage"),
  lockState: document.querySelector("#lock-state"),
  emotionFields: document.querySelector("#emotion-fields"),
  primaryEmotion: document.querySelector("#primary-emotion"),
  otherEmotionField: document.querySelector("#other-emotion-field"),
  otherEmotion: document.querySelector("#other-emotion"),
  contextFields: document.querySelector("#context-fields"),
  mixedEmotion: document.querySelector("#mixed-emotion"),
  note: document.querySelector("#annotation-note"),
  noteRequirement: document.querySelector("#note-requirement"),
  mobileGlossary: document.querySelector("#mobile-glossary"),
  glossary: document.querySelector("#label-glossary"),
};

let current = null;
let csrfToken = "";
let formDirty = false;
let noticeTimer = null;

function showOnly(view) {
  const views = [
    elements.loading,
    elements.caseView,
    elements.breakState,
    elements.completeState,
    elements.qualityStopState,
  ];
  views.forEach((item) => {
    item.hidden = item !== view;
  });
}

function showNotice(message, error = false) {
  window.clearTimeout(noticeTimer);
  elements.notice.textContent = message;
  elements.notice.classList.toggle("error", error);
  elements.notice.hidden = false;
  noticeTimer = window.setTimeout(() => {
    elements.notice.hidden = true;
  }, error ? 7000 : 2800);
}

async function api(path, body = null) {
  const options = {
    method: body === null ? "GET" : "POST",
    cache: "no-store",
    headers: { Accept: "application/json" },
  };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.headers["X-Annotation-Token"] = csrfToken;
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  if (payload.csrf_token) {
    csrfToken = payload.csrf_token;
  }
  return payload;
}

function updateProgress(data) {
  const progress = data.progress || {};
  const total = progress.total || 120;
  const position = progress.position || Math.min((progress.completed || 0) + 1, total);
  elements.caseProgress.textContent = `${position} / ${total}`;
  elements.progressBar.max = total;
  elements.progressBar.value = progress.completed || 0;
  elements.progressBar.textContent = `${progress.completed || 0} / ${total}`;
  elements.sessionCount.textContent = `本轮 ${progress.session_completed || 0} / ${progress.session_limit || 40}`;
}

function resetForm() {
  elements.form.reset();
  elements.emotionFields.hidden = true;
  elements.otherEmotionField.hidden = true;
  elements.contextFields.hidden = current?.stage !== "B";
  elements.note.required = false;
  elements.noteRequirement.textContent = "可选";
  elements.formError.hidden = true;
  elements.formError.textContent = "";
  elements.submit.disabled = false;
  formDirty = false;
}

function selectedValue(name) {
  return elements.form.querySelector(`input[name="${name}"]:checked`)?.value || null;
}

function updateConditionalFields() {
  const status = selectedValue("status");
  const labeled = status === "labeled";
  const unusable = status === "unusable";
  elements.emotionFields.hidden = !labeled;
  elements.primaryEmotion.required = labeled;
  elements.otherEmotionField.hidden = !labeled || elements.primaryEmotion.value !== "other_emotion";
  elements.otherEmotion.required = labeled && elements.primaryEmotion.value === "other_emotion";

  const showContextDiagnostics = current?.stage === "B" && !unusable;
  elements.contextFields.hidden = !showContextDiagnostics;
  elements.form.querySelectorAll("input[name='sarcasm']").forEach((input) => {
    input.required = showContextDiagnostics;
  });
  elements.form.querySelectorAll("input[name='context_sufficiency']").forEach((input) => {
    input.required = showContextDiagnostics;
  });

  elements.note.required = unusable;
  elements.noteRequirement.textContent = unusable ? "必填" : "可选";
}

function createTextBlock(text, className = "text-fragment") {
  const block = document.createElement("p");
  block.className = className;
  block.textContent = text;
  return block;
}

function renderFullText(container, text) {
  container.replaceChildren();
  const pattern = /\[\[QUOTE\]\]([\s\S]*?)\[\[\/QUOTE\]\]/g;
  let cursor = 0;
  let match = pattern.exec(text);
  while (match) {
    const before = text.slice(cursor, match.index).trim();
    if (before) {
      container.append(createTextBlock(before));
    }
    const quote = document.createElement("blockquote");
    quote.className = "inline-quote";
    quote.textContent = match[1].trim();
    container.append(quote);
    cursor = pattern.lastIndex;
    match = pattern.exec(text);
  }
  const remainder = text.slice(cursor).trim();
  if (remainder) {
    container.append(createTextBlock(remainder));
  }
  if (!container.childNodes.length) {
    container.append(createTextBlock(text));
  }
}

function quoteRelationLabel(relation) {
  const labels = {
    direct_parent: "direct parent",
    same_thread_other: "same-thread post",
    external_or_unknown: "external / unresolved",
  };
  return labels[relation] || "source unresolved";
}

function renderQuotes(quotes) {
  elements.quoteList.replaceChildren();
  elements.quoteCount.textContent = `${quotes.length} quote${quotes.length === 1 ? "" : "s"}`;
  elements.quoteSection.hidden = quotes.length === 0;
  quotes.forEach((quote, index) => {
    const item = document.createElement("article");
    item.className = "quote-item";

    const meta = document.createElement("div");
    meta.className = "quote-meta";
    const number = document.createElement("span");
    number.textContent = `Quote ${index + 1}`;
    const relation = document.createElement("span");
    relation.textContent = quoteRelationLabel(quote.source_relation);
    meta.append(number, relation);
    if (quote.truncated === true) {
      const truncated = document.createElement("span");
      truncated.textContent = "truncated";
      meta.append(truncated);
    }
    if (quote.altered === true) {
      const altered = document.createElement("span");
      altered.textContent = "altered";
      meta.append(altered);
    }

    const body = document.createElement("blockquote");
    body.textContent = quote.text;
    item.append(meta, body);
    elements.quoteList.append(item);
  });
}

function renderCase(data) {
  showOnly(elements.caseView);
  elements.decisionPanel.hidden = false;
  elements.endSession.hidden = false;
  elements.datasetMode.textContent = data.dataset_mode === "synthetic" ? "Synthetic preview" : "Private pilot";
  updateProgress(data);

  elements.caseNumber.textContent = `Case ${data.case_id}`;
  elements.stageKicker.textContent = `Stage ${data.stage}`;
  elements.decisionStage.textContent = `Stage ${data.stage}`;
  elements.stageChip.textContent = data.stage === "A" ? "A · Target only" : "B · Context";
  elements.stageTitle.textContent = data.stage === "A" ? "Target only" : "Context revealed";
  elements.lockState.textContent = data.stage === "A" ? "未锁定" : "Stage A locked";
  elements.lockState.classList.toggle("locked", data.stage === "B");

  elements.stageAView.hidden = data.stage !== "A";
  elements.stageBView.hidden = data.stage !== "B";
  if (data.stage === "A") {
    elements.targetOnlyText.textContent = data.target_body;
  } else {
    elements.discussionTitle.textContent = data.context.discussion_title;
    elements.parentText.textContent = data.context.direct_parent_body;
    renderQuotes(data.context.target_quotes);
    renderFullText(elements.targetFullText, data.target_full_with_quotes);
  }

  resetForm();
  elements.submit.textContent = data.stage === "A"
    ? "锁定 Stage A 并显示上下文"
    : "保存 Stage B 并进入下一条";
  document.documentElement.dataset.stage = data.stage.toLowerCase();
  window.scrollTo({ top: 0, behavior: "auto" });
  elements.caseView.focus?.();
}

function renderTerminal(data, view, chipText) {
  showOnly(view);
  elements.decisionPanel.hidden = true;
  elements.endSession.hidden = true;
  elements.stageChip.textContent = chipText;
  updateProgress(data);
}

function render(data) {
  current = data;
  if (data.state === "case") {
    renderCase(data);
  } else if (data.state === "session_break") {
    renderTerminal(data, elements.breakState, "Session break");
  } else if (data.state === "complete") {
    renderTerminal(data, elements.completeState, "Complete");
  } else if (data.state === "quality_stop") {
    renderTerminal(data, elements.qualityStopState, "Quality gate");
  } else {
    throw new Error("Unknown annotator state");
  }
}

function decisionFromForm() {
  const status = selectedValue("status");
  const decision = {
    status,
    primary_emotion: status === "labeled" ? elements.primaryEmotion.value : null,
    other_emotion_text:
      status === "labeled" && elements.primaryEmotion.value === "other_emotion"
        ? elements.otherEmotion.value.trim()
        : null,
    confidence: selectedValue("confidence"),
    note: elements.note.value.trim() || null,
  };
  if (current.stage === "B") {
    const unusable = status === "unusable";
    decision.sarcasm = unusable ? null : selectedValue("sarcasm");
    decision.mixed_emotion = unusable ? null : elements.mixedEmotion.checked;
    decision.context_sufficiency = unusable ? null : selectedValue("context_sufficiency");
  }
  return decision;
}

elements.form.addEventListener("input", () => {
  formDirty = true;
  updateConditionalFields();
  elements.formError.hidden = true;
});

elements.primaryEmotion.addEventListener("change", updateConditionalFields);

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  updateConditionalFields();
  if (!elements.form.checkValidity()) {
    elements.form.reportValidity();
    return;
  }
  if (!current || current.state !== "case") {
    return;
  }

  elements.submit.disabled = true;
  const originalText = elements.submit.textContent;
  elements.submit.textContent = "保存中...";
  try {
    const endpoint = current.stage === "A" ? "/api/stage-a" : "/api/stage-b";
    const data = await api(endpoint, {
      case_id: current.case_id,
      decision: decisionFromForm(),
    });
    formDirty = false;
    render(data);
    showNotice(current?.stage === "B" ? "Stage A 已锁定" : "记录已安全保存");
  } catch (error) {
    elements.formError.textContent = error.message;
    elements.formError.hidden = false;
    showNotice(error.message, true);
    elements.submit.disabled = false;
    elements.submit.textContent = originalText;
  }
});

elements.endSession.addEventListener("click", async () => {
  try {
    const data = await api("/api/session/end", {});
    formDirty = false;
    render(data);
  } catch (error) {
    showNotice(error.message, true);
  }
});

elements.startSession.addEventListener("click", async () => {
  try {
    const data = await api("/api/session/start", {});
    render(data);
  } catch (error) {
    showNotice(error.message, true);
  }
});

window.addEventListener("beforeunload", (event) => {
  if (!formDirty) {
    return;
  }
  event.preventDefault();
  event.returnValue = "";
});

async function initialize() {
  const mobileGlossary = elements.glossary.cloneNode(true);
  mobileGlossary.removeAttribute("id");
  elements.mobileGlossary.append(mobileGlossary);
  try {
    const data = await api("/api/current");
    render(data);
  } catch (error) {
    elements.loading.replaceChildren(createTextBlock(`标注器无法启动：${error.message}`));
    showNotice(error.message, true);
  }
}

initialize();
