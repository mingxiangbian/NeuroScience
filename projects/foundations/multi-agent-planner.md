# Multi-Agent Interview Planner

## Purpose

这个文件是可复用的 interview planning 模板。它用于生成面向 AGI / AI / LLM / Agent system roles 的准备计划，尤其适合需要同时平衡 coding、LLM/Agent system design、research reading、mock interview 和项目包装的场景。

它不是实际路线。实际路线放在 `llm-agent-engineer-roadmap.md`。

## Inputs

每次使用 planner 前，先填写这些输入：

```yaml
target_role: "Agent / LLM Systems Engineer"
target_bar: "top AI lab / AGI team"
timeline: "30-day core, extendable to 45/60 days"
baseline: "from scattered preparation to structured interview readiness"
main_gaps:
  - coding and implementation
  - interview expression
  - deeper LLM/Agent system understanding
language_stack:
  primary:
    - Python
    - TypeScript
  optional:
    - Rust
project_preference: "interview-first, mini implementation drills, no large demo by default"
constraints:
  - daily time is variable
  - plan must support minimum / standard / stretch task levels
```

## Agents

### CTO Agent

Focus:

- scalable LLM systems
- agent runtime architecture
- RAG, memory systems, tool calling
- serving, tracing, observability
- production constraints

Output:

- practical system design priorities
- tradeoffs
- bottlenecks
- failure modes

Constraint:

- reject designs that sound impressive but cannot be shipped, tested, debugged, or operated.

### Research Agent

Focus:

- transformer and attention
- scaling laws
- reasoning models
- memory and world models
- RLHF / RLAIF / RLVR / post-training
- evals and benchmark limitations

Output:

- paper-driven concepts
- research interview questions
- conceptual frameworks

Constraint:

- cannot expand reading lists unless the material directly improves interview answers.

### Coding Interview Agent

Focus:

- LeetCode patterns
- Python implementation
- TypeScript service/interface coding
- small Agent / LLM component drills

Output:

- measurable practice schedule
- coding question set
- implementation tasks

Constraint:

- every week must have measurable coding output.

### Product / Agent Design Agent

Focus:

- AI product design
- tool orchestration
- multi-agent workflows
- memory UX
- human-in-the-loop and recovery paths

Output:

- product-style system design questions
- user workflow breakdowns
- system behavior requirements

Constraint:

- reject theory-only designs that do not explain user impact, workflow, or failure recovery.

### Interview Strategy Agent

Focus:

- interview signal maximization
- answer structure
- resume/project framing
- behavioral stories
- mock scoring

Output:

- schedule tradeoffs
- scoring rubric
- answer templates
- weak-signal warnings

Constraint:

- optimize for being perceived as strong without sacrificing accuracy or engineering rigor.

### Supervisor Agent

Role:

- orchestrates all agents
- forces disagreement
- resolves contradictions
- removes duplication
- produces final plan

Default judgment:

1. Interview usefulness beats academic completeness.
2. Coding and expression practice cannot be displaced by reading.
3. Each system design topic needs implementation evidence or failure analysis.
4. Research reading must become answer structure, not just notes.

## Step 1: Parallel Generation

Each specialist agent independently outputs:

- top priorities
- likely gaps
- recommended actions
- risks if ignored

Use this compact format:

```markdown
### Agent Name

Priorities:
- ...

Key gaps:
- ...

Recommended actions:
- ...

Risks:
- ...
```

## Step 2: Adversarial Debate

Required debates:

- CTO Agent critiques Research Agent: identify ideas that lack production realism.
- Research Agent critiques CTO Agent: identify engineering plans that miss model or eval fundamentals.
- Product / Agent Design Agent critiques Research Agent: identify abstract concepts that do not map to user-facing agent behavior.
- Coding Interview Agent critiques CTO Agent: identify architecture claims that the candidate cannot implement.
- Interview Strategy Agent critiques all agents: identify what will or will not be perceived as strong in interviews.

Each critique must include:

- claim being challenged
- why it is weak or incomplete
- revised recommendation

## Step 3: Conflict Extraction

Supervisor extracts:

- contradictions
- overlapping recommendations
- missing areas
- decisions needed

Use this table:

| Conflict | Agents involved | Resolution | Reason |
| --- | --- | --- | --- |
| Reading breadth vs coding time | Research, Coding, Strategy | Cap papers and require daily coding | Current bottleneck is coding and implementation |

## Step 4: Scoring

Each major proposal is scored:

| Proposal | Impact | Feasibility | Interview relevance | Decision |
| --- | ---: | ---: | ---: | --- |
| Daily Python coding practice | 9 | 8 | 10 | Keep |
| Full AGI reading syllabus | 6 | 3 | 4 | Cut down |

Scoring definitions:

- `impact`: how much it improves actual readiness.
- `feasibility`: whether it fits the user's time, baseline, and energy.
- `interview relevance`: whether it is likely to appear directly or indirectly in interviews.

## Step 5: Final Synthesis

Supervisor outputs one unified plan:

- structured roadmap
- weekly schedule
- prioritized knowledge graph
- coding plan
- system design plan
- reading list
- mock interview set
- project or mini-drill recommendations

The final synthesis must explicitly explain which agent recommendations were reduced, merged, or rejected.

## Output Contract

Every final plan must include:

1. Knowledge Map
2. 30/45/60-Day Plan or another timeline requested by the user
3. Coding Plan
4. System Design Plan
5. Research Reading List
6. Mock Interview Set
7. Mini Implementation Drills or Project Recommendations
8. Strategy Rubric

## Reusable Prompt Template

```text
Use the Multi-Agent Interview Planner.

Inputs:
- target_role:
- target_bar:
- timeline:
- baseline:
- main_gaps:
- language_stack:
- project_preference:
- constraints:

Run:
1. Parallel generation from CTO, Research, Coding, Product / Agent Design, and Interview Strategy agents.
2. Adversarial debate.
3. Supervisor conflict extraction.
4. Proposal scoring by impact, feasibility, and interview relevance.
5. Final synthesis.

Return:
1. Knowledge Map
2. Timeline Plan
3. Coding Plan
4. System Design Plan
5. Research Reading List
6. Mock Interview Set
7. Mini Implementation Drills / Project Recommendations
8. Strategy Rubric
```
