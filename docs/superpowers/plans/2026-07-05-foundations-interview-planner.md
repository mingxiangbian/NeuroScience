# Foundations Interview Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `projects/foundations/` 中生成可复用的 multi-agent planner 和一份可执行的 Agent / LLM Systems Engineer 面试准备路线。

**Architecture:** 第一版是静态 Markdown 文档加一个轻量 landing page。`README.md` 是入口，`multi-agent-planner.md` 保存可复用方法，`llm-agent-engineer-roadmap.md` 保存本次路线；`projects/foundations/index.html` 只负责把这些文件暴露给网页访问。

**Tech Stack:** Markdown, static HTML, Node-based repository requirement checks.

---

## File Structure

- Create: `projects/foundations/README.md`
  - Foundations 项目入口，说明目标、使用方式、文件说明和第一天行动。
- Create: `projects/foundations/multi-agent-planner.md`
  - 可复用 6-agent planner 模板，包含 roles、inputs、debate、scoring、output contract。
- Create: `projects/foundations/llm-agent-engineer-roadmap.md`
  - 本次面向 Agent / LLM Systems Engineer 的实际 roadmap。
- Modify: `projects/foundations/index.html`
  - 把占位说明替换为三个文档链接。
- Modify: `tests/projects-requirements.mjs`
  - 增加 Foundations 文档和 landing page 链接检查。

## Source Alignment

路线内容要显式对齐当前公开岗位信号：

- OpenAI `AI Systems Engineer, Codex Agents`：LLM applications, coding agents, evals, model deployment, inference, tool-using systems, traces, runtime constraints, Rust/Python/API layers。
- OpenAI `Applied AI Engineer, Codex Core Agent`：shipping LLM products, Python, ML tooling, model evaluation, fine-tuning, prompt design, agent UX。
- OpenAI `Software Engineer, Agent Infrastructure`：FastAPI/gRPC APIs, agentic infrastructure, research-production collaboration, scaling 0-1 to large systems。
- OpenAI `Backend Software Engineer (Evals)`：AI agents, evals, multi-agent workflows, tool use, long context, backend systems。
- Anthropic Alignment roles：empirical AI research, safety-relevant eval questions, multi-agent RL experiments, LLM-generated jailbreak eval tooling。
- Google DeepMind Research Engineer role family：engineering + ML/deep learning + research bridge, building/scaling systems to test and evaluate ideas。

### Task 1: Foundations README And Landing Page

**Files:**
- Create: `projects/foundations/README.md`
- Modify: `projects/foundations/index.html`

- [ ] **Step 1: Create README**

Write `projects/foundations/README.md` with these sections:

```markdown
# 基石

## Purpose

## Current Track

## How To Use This Folder

## Files

## First Day

## Source Alignment
```

The README must state that the first track targets Agent / LLM Systems Engineer interviews for top AI labs, with coding and interview expression as the first bottlenecks.

- [ ] **Step 2: Update landing page links**

Modify `projects/foundations/index.html` so the main content includes links to:

```text
README.md
multi-agent-planner.md
llm-agent-engineer-roadmap.md
```

Use the existing page style. Do not redesign the page.

- [ ] **Step 3: Verify README and landing links**

Run:

```bash
rg -n "multi-agent-planner|llm-agent-engineer-roadmap|README.md|Agent / LLM Systems Engineer" projects/foundations
```

Expected: output includes `README.md`, `index.html`, and all three document links.

### Task 2: Multi-Agent Planner Template

**Files:**
- Create: `projects/foundations/multi-agent-planner.md`

- [ ] **Step 1: Create planner template**

Write `projects/foundations/multi-agent-planner.md` with these sections:

```markdown
# Multi-Agent Interview Planner

## Purpose

## Inputs

## Agents

## Step 1: Parallel Generation

## Step 2: Adversarial Debate

## Step 3: Conflict Extraction

## Step 4: Scoring

## Step 5: Final Synthesis

## Output Contract

## Reusable Prompt Template
```

The template must preserve the 5 specialist agents plus 1 Supervisor structure, but remove redundant phrasing and make the Supervisor responsible for final prioritization.

- [ ] **Step 2: Verify planner coverage**

Run:

```bash
rg -n "CTO Agent|Research Agent|Coding Interview Agent|Product / Agent Design Agent|Interview Strategy Agent|Supervisor Agent|impact|feasibility|interview relevance" projects/foundations/multi-agent-planner.md
```

Expected: every agent and every scoring dimension appears.

### Task 3: LLM / Agent Engineer Roadmap

**Files:**
- Create: `projects/foundations/llm-agent-engineer-roadmap.md`

- [ ] **Step 1: Create roadmap**

Write `projects/foundations/llm-agent-engineer-roadmap.md` with these sections:

```markdown
# LLM / Agent Systems Engineer Roadmap

## Profile And Target

## Supervisor Synthesis

## 1. Knowledge Map

## 2. 30/45/60-Day Plan

## 3. Coding Plan

## 4. System Design Plan

## 5. Research Reading List

## 6. Mock Interview Set

## 7. Mini Implementation Drills

## 8. Project Recommendations

## 9. Strategy Rubric

## 10. Weekly Review Checklist
```

The roadmap must be interview-first: coding and expression are mandatory, research reading is capped and tied to system design questions, and projects are small drills unless the user later chooses to build a larger demo.

- [ ] **Step 2: Verify roadmap output contract**

Run:

```bash
rg -n "Knowledge Map|30/45/60-Day Plan|Coding Plan|System Design Plan|Research Reading List|Mock Interview Set|Mini Implementation Drills|Project Recommendations|Strategy Rubric" projects/foundations/llm-agent-engineer-roadmap.md
```

Expected: all output contract headings appear.

### Task 4: Repository Requirement Checks

**Files:**
- Modify: `tests/projects-requirements.mjs`

- [ ] **Step 1: Add Foundations checks**

Modify `tests/projects-requirements.mjs` to check:

- `projects/foundations/index.html` exists.
- `projects/foundations/README.md` exists.
- `projects/foundations/multi-agent-planner.md` exists.
- `projects/foundations/llm-agent-engineer-roadmap.md` exists.
- The Foundations landing page links to the three Markdown files.
- The roadmap contains `Agent / LLM Systems Engineer`.

- [ ] **Step 2: Run projects requirements**

Run:

```bash
node tests/projects-requirements.mjs
```

Expected: command exits 0 with no assertion output.

### Task 5: Final Verification

**Files:**
- All files from Tasks 1-4.

- [ ] **Step 1: Run full relevant tests**

Run:

```bash
node tests/projects-requirements.mjs && node tests/papers-requirements.mjs
```

Expected: command exits 0 with no assertion output.

- [ ] **Step 2: Scan for unfinished markers**

Run:

```bash
rg -n "T[B]D|T[O]DO|待[定]|以后[再]说|place[Hh]older" projects/foundations
```

Expected: no matches.

- [ ] **Step 3: Check whitespace**

Run:

```bash
git diff --check -- projects/foundations tests/projects-requirements.mjs docs/superpowers/plans/2026-07-05-foundations-interview-planner.md
```

Expected: no output and exit 0.

- [ ] **Step 4: Review changed files**

Run:

```bash
git diff --stat -- projects/foundations tests/projects-requirements.mjs docs/superpowers/plans/2026-07-05-foundations-interview-planner.md
```

Expected: changed files are limited to the plan, Foundations docs/page, and project requirements test.
