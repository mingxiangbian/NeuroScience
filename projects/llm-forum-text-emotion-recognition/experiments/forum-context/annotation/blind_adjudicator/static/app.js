"use strict";

const emotionLabels = [
  "anger",
  "frustration",
  "disappointment",
  "sadness",
  "fear",
  "joy",
  "surprise",
  "confusion",
  "disgust",
  "cynicism",
  "neutral",
  "other_emotion",
];

const assessmentOptions = [
  ["", "请选择"],
  ["supported", "支持"],
  ["acceptable_but_not_primary", "可接受但非首选"],
  ["unsupported", "不支持"],
  ["undecidable", "无法判断"],
];

let csrfToken = "";
let currentState = null;
let renderedKey = "";

const elements = {
  loading: document.querySelector("#loading-state"),
  caseView: document.querySelector("#case-view"),
  sessionBreak: document.querySelector("#session-break-state"),
  complete: document.querySelector("#complete-state"),
  decisionPanel: document.querySelector("#decision-panel"),
  datasetMode: document.querySelector("#dataset-mode"),
  stageChip: document.querySelector("#stage-chip"),
  caseProgress: document.querySelector("#case-progress"),
  progressBar: document.querySelector("#progress-bar"),
  sessionCount: document.querySelector("#session-count"),
  endSession: document.querySelector("#end-session"),
  startSession: document.querySelector("#start-session"),
  notice: document.querySelector("#notice"),
  stageKicker: document.querySelector("#stage-kicker"),
  stageTitle: document.querySelector("#stage-title"),
  caseNumber: document.querySelector("#case-number"),
  phaseLock: document.querySelector("#phase-lock"),
  discussionTitle: document.querySelector("#discussion-title"),
  parentText: document.querySelector("#parent-text"),
  quotesSection: document.querySelector("#quotes-section"),
  quoteCount: document.querySelector("#quote-count"),
  quoteList: document.querySelector("#quote-list"),
  targetText: document.querySelector("#target-text"),
  phaseOneSummary: document.querySelector("#phase-one-summary"),
  summaryValues: document.querySelector("#summary-values"),
  candidateSection: document.querySelector("#candidate-section"),
  candidateList: document.querySelector("#candidate-list"),
  decisionStage: document.querySelector("#decision-stage"),
  decisionTitle: document.querySelector("#decision-title"),
  lockState: document.querySelector("#lock-state"),
  phaseOneForm: document.querySelector("#phase-one-form"),
  phaseTwoForm: document.querySelector("#phase-two-form"),
  phaseOneError: document.querySelector("#phase-one-error"),
  phaseTwoError: document.querySelector("#phase-two-error"),
  phaseOneEmotionFields: document.querySelector("#phase-one-emotion-fields"),
  phaseOneEmotion: document.querySelector("#phase-one-emotion"),
  phaseOneOtherField: document.querySelector("#phase-one-other-field"),
  phaseOneOther: document.querySelector("#phase-one-other"),
  candidateAssessmentFields: document.querySelector("#candidate-assessment-fields"),
  finalDecisionBlock: document.querySelector("#final-decision-block"),
  finalEmotionFields: document.querySelector("#final-emotion-fields"),
  finalEmotion: document.querySelector("#final-emotion"),
  finalOtherField: document.querySelector("#final-other-field"),
  finalOther: document.querySelector("#final-other"),
  primaryReason: document.querySelector("#primary-reason"),
  phaseOneNote: document.querySelector("#phase-one-note"),
  phaseTwoNote: document.querySelector("#phase-two-note"),
};

function populateEmotionSelect(select) {
  for (const label of emotionLabels) {
    const option = document.createElement("option");
    option.value = label;
    option.textContent = label;
    select.append(option);
  }
}

populateEmotionSelect(elements.phaseOneEmotion);
populateEmotionSelect(elements.finalEmotion);
document.querySelector("#mobile-glossary").append(
  document.querySelector("#label-glossary").cloneNode(true),
);

function selectedRadio(form, name) {
  return form.querySelector(`input[name="${name}"]:checked`)?.value ?? null;
}

function setRadio(form, name, value) {
  const input = form.querySelector(`input[name="${name}"][value="${value}"]`);
  if (input) input.checked = true;
}

function setError(element, message) {
  element.textContent = message;
  element.hidden = !message;
}

function showNotice(message, tone = "neutral") {
  elements.notice.textContent = message;
  elements.notice.dataset.tone = tone;
  elements.notice.hidden = !message;
}

function normalizeDisplayText(text) {
  return text
    .replaceAll("[[QUOTE]]", "\n引用：\n")
    .replaceAll("[[/QUOTE]]", "\n回复：\n")
    .trim();
}

function formatDecision(decision) {
  if (decision.status !== "labeled") return decision.status;
  if (decision.primary_emotion === "other_emotion") {
    return `other_emotion: ${decision.other_emotion_text}`;
  }
  return decision.primary_emotion;
}

function candidateName(alias) {
  return `Candidate ${alias.slice(-1).toUpperCase()}`;
}

function hideAllStates() {
  elements.loading.hidden = true;
  elements.caseView.hidden = true;
  elements.sessionBreak.hidden = true;
  elements.complete.hidden = true;
}

function updateProgress(state) {
  const progress = state.progress ?? {
    completed: 0,
    total: 40,
    session_completed: 0,
    session_limit: 20,
  };
  elements.progressBar.max = progress.total;
  elements.progressBar.value = progress.completed;
  elements.caseProgress.textContent = `${progress.completed} / ${progress.total}`;
  elements.sessionCount.textContent = `本轮 ${progress.session_completed} / ${progress.session_limit}`;
}

function renderContent(content) {
  elements.discussionTitle.textContent = content.discussion_title;
  elements.parentText.textContent = content.direct_parent_body;
  elements.targetText.textContent = normalizeDisplayText(content.target_full_with_quotes);
  elements.quoteList.replaceChildren();
  elements.quoteCount.textContent = `${content.target_quotes.length} quotes`;
  elements.quotesSection.hidden = content.target_quotes.length === 0;
  for (const [index, quote] of content.target_quotes.entries()) {
    const block = document.createElement("blockquote");
    block.className = "quote-item";
    const label = document.createElement("span");
    label.textContent = `Quote ${index + 1}`;
    const text = document.createElement("p");
    text.textContent = quote;
    block.append(label, text);
    elements.quoteList.append(block);
  }
}

function renderPhaseOneSummary(summary) {
  elements.summaryValues.replaceChildren();
  const values = [
    ["Emotion", summary.emotion_presence],
    ["Stance", summary.stance],
    ["Unit", summary.unit_validity],
    ["Decision", formatDecision(summary.independent_decision)],
    ["Confidence", summary.confidence],
  ];
  for (const [label, value] of values) {
    const item = document.createElement("div");
    const term = document.createElement("span");
    term.textContent = label;
    const decision = document.createElement("strong");
    decision.textContent = value;
    item.append(term, decision);
    elements.summaryValues.append(item);
  }
}

function renderCandidates(candidates) {
  elements.candidateList.replaceChildren();
  elements.candidateAssessmentFields.replaceChildren();
  for (const candidate of candidates) {
    const item = document.createElement("article");
    item.className = "candidate-item";
    const heading = document.createElement("span");
    heading.className = "candidate-name";
    heading.textContent = candidateName(candidate.alias);
    const value = document.createElement("strong");
    value.textContent = formatDecision(candidate.decision);
    item.append(heading, value);
    elements.candidateList.append(item);

    const group = document.createElement("div");
    group.className = "form-group candidate-assessment";
    const label = document.createElement("label");
    label.className = "field-label";
    label.htmlFor = `assessment-${candidate.alias}`;
    label.textContent = candidateName(candidate.alias);
    const select = document.createElement("select");
    select.id = `assessment-${candidate.alias}`;
    select.name = `assessment_${candidate.alias}`;
    select.required = true;
    for (const [optionValue, optionLabel] of assessmentOptions) {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = optionLabel;
      select.append(option);
    }
    group.append(label, select);
    elements.candidateAssessmentFields.append(group);
  }
}

function renderCase(state) {
  elements.caseView.hidden = false;
  elements.decisionPanel.hidden = false;
  elements.endSession.hidden = false;
  elements.caseNumber.textContent = `Blind case ${state.case_id}`;
  renderContent(state.content);

  const phaseTwo = state.stage === "phase_2";
  elements.stageKicker.textContent = phaseTwo ? "Phase 2" : "Phase 1";
  elements.stageTitle.textContent = phaseTwo
    ? "Candidate assessment"
    : "Independent diagnosis";
  elements.stageChip.textContent = phaseTwo ? "Phase 2" : "Phase 1";
  elements.stageChip.dataset.stage = phaseTwo ? "two" : "one";
  elements.phaseLock.hidden = !phaseTwo;
  elements.phaseOneSummary.hidden = !phaseTwo;
  elements.candidateSection.hidden = !phaseTwo;
  elements.phaseOneForm.hidden = phaseTwo;
  elements.phaseTwoForm.hidden = !phaseTwo;
  elements.decisionStage.textContent = phaseTwo ? "Phase 2" : "Phase 1";
  elements.decisionTitle.textContent = phaseTwo ? "匿名候选裁决" : "独立诊断";
  elements.lockState.textContent = phaseTwo ? "Phase 1 locked" : "未锁定";
  elements.lockState.dataset.locked = phaseTwo ? "true" : "false";

  const nextKey = `${state.case_id}:${state.stage}`;
  if (nextKey !== renderedKey) {
    if (phaseTwo) {
      elements.phaseTwoForm.reset();
      renderPhaseOneSummary(state.phase_1_summary);
      renderCandidates(state.candidates);
      setError(elements.phaseTwoError, "");
    } else {
      elements.phaseOneForm.reset();
      setError(elements.phaseOneError, "");
    }
    updateDecisionVisibility();
    renderedKey = nextKey;
  }
}

function renderState(state) {
  currentState = state;
  csrfToken = state.csrf_token ?? csrfToken;
  elements.datasetMode.textContent =
    state.dataset_mode === "synthetic" ? "Synthetic demo" : "Private diagnostic";
  updateProgress(state);
  hideAllStates();

  if (state.state === "case") {
    renderCase(state);
    return;
  }

  elements.decisionPanel.hidden = true;
  elements.endSession.hidden = true;
  if (state.state === "session_break") {
    elements.stageChip.textContent = "Break";
    elements.sessionBreak.hidden = false;
  } else if (state.state === "complete") {
    elements.stageChip.textContent = "Complete";
    elements.complete.hidden = false;
  } else {
    elements.loading.hidden = false;
  }
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error ?? `Request failed: ${response.status}`);
  return payload;
}

async function post(path, body) {
  return request(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Adjudication-Token": csrfToken,
    },
    body: JSON.stringify(body),
  });
}

function collectDecision(form, statusName, emotionElement, otherElement) {
  const status = selectedRadio(form, statusName);
  if (!status) throw new Error("请选择决定状态。");
  if (status !== "labeled") {
    return { status, primary_emotion: null, other_emotion_text: null };
  }
  const primaryEmotion = emotionElement.value;
  if (!primaryEmotion) throw new Error("请选择主情绪。");
  const other = otherElement.value.trim();
  if (primaryEmotion === "other_emotion" && !other) {
    throw new Error("请填写 other_emotion 的英文原子名称。");
  }
  return {
    status,
    primary_emotion: primaryEmotion,
    other_emotion_text: primaryEmotion === "other_emotion" ? other : null,
  };
}

function updateDecisionVisibility() {
  const phaseOneStatus = selectedRadio(elements.phaseOneForm, "phase_one_status");
  elements.phaseOneEmotionFields.hidden = phaseOneStatus !== "labeled";
  elements.phaseOneOtherField.hidden =
    phaseOneStatus !== "labeled" || elements.phaseOneEmotion.value !== "other_emotion";

  const resolution = selectedRadio(elements.phaseTwoForm, "resolution");
  elements.finalDecisionBlock.hidden = resolution !== "final_decision";
  const finalStatus = selectedRadio(elements.phaseTwoForm, "final_status");
  elements.finalEmotionFields.hidden =
    resolution !== "final_decision" || finalStatus !== "labeled";
  elements.finalOtherField.hidden =
    resolution !== "final_decision" ||
    finalStatus !== "labeled" ||
    elements.finalEmotion.value !== "other_emotion";
}

elements.phaseOneForm.addEventListener("change", updateDecisionVisibility);
elements.phaseTwoForm.addEventListener("change", updateDecisionVisibility);
elements.phaseOneEmotion.addEventListener("change", updateDecisionVisibility);
elements.finalEmotion.addEventListener("change", updateDecisionVisibility);

elements.phaseOneForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setError(elements.phaseOneError, "");
  try {
    const emotionPresence = selectedRadio(elements.phaseOneForm, "emotion_presence");
    const stance = selectedRadio(elements.phaseOneForm, "stance");
    const unitValidity = document.querySelector("#unit-validity").value;
    const confidence = selectedRadio(elements.phaseOneForm, "confidence");
    const decision = collectDecision(
      elements.phaseOneForm,
      "phase_one_status",
      elements.phaseOneEmotion,
      elements.phaseOneOther,
    );
    if (!emotionPresence || !stance || !unitValidity || !confidence) {
      throw new Error("请完成情绪存在、立场、标注单位和信心判断。");
    }
    if ((unitValidity === "unusable") !== (decision.status === "unusable")) {
      throw new Error("标注单位与决定必须同时选择“不可用”。");
    }
    const judgment = {
      emotion_presence: emotionPresence,
      stance,
      unit_validity: unitValidity,
      independent_decision: decision,
      confidence,
      note: elements.phaseOneNote.value.trim() || null,
    };
    if (!window.confirm("锁定 Phase 1 后将不能修改，并会显示匿名候选。确认提交？")) {
      return;
    }
    const state = await post("/api/phase-1", {
      case_id: currentState.case_id,
      judgment,
    });
    showNotice("Phase 1 已锁定。", "success");
    renderState(state);
  } catch (error) {
    setError(elements.phaseOneError, error.message);
  }
});

elements.phaseTwoForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setError(elements.phaseTwoError, "");
  try {
    const assessments = {};
    for (const candidate of currentState.candidates) {
      const value = document.querySelector(`#assessment-${candidate.alias}`).value;
      if (!value) throw new Error("请判断三个匿名候选。");
      assessments[candidate.alias] = value;
    }
    const resolution = selectedRadio(elements.phaseTwoForm, "resolution");
    if (!resolution) throw new Error("请选择裁决结果。");
    const finalDecision =
      resolution === "final_decision"
        ? collectDecision(
            elements.phaseTwoForm,
            "final_status",
            elements.finalEmotion,
            elements.finalOther,
          )
        : null;
    if (!elements.primaryReason.value) throw new Error("请选择主要原因。");
    const judgment = {
      candidate_assessments: assessments,
      resolution,
      final_decision: finalDecision,
      primary_reason: elements.primaryReason.value,
      note: elements.phaseTwoNote.value.trim() || null,
    };
    if (!window.confirm("锁定后本案例不能修改。确认提交裁决？")) return;
    const state = await post("/api/phase-2", {
      case_id: currentState.case_id,
      judgment,
    });
    showNotice("案例裁决已安全保存。", "success");
    renderState(state);
  } catch (error) {
    setError(elements.phaseTwoError, error.message);
  }
});

elements.endSession.addEventListener("click", async () => {
  if (!window.confirm("结束本轮？已锁定内容会保留。")) return;
  try {
    renderState(await post("/api/session/end", {}));
  } catch (error) {
    showNotice(error.message, "error");
  }
});

elements.startSession.addEventListener("click", async () => {
  try {
    renderedKey = "";
    renderState(await post("/api/session/start", {}));
  } catch (error) {
    showNotice(error.message, "error");
  }
});

request("/api/current")
  .then(renderState)
  .catch((error) => {
    elements.loading.hidden = true;
    elements.decisionPanel.hidden = true;
    showNotice(`载入失败：${error.message}`, "error");
  });
