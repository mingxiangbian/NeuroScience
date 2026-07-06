# Interaction Protocol

## Phase 1: Input Pack

The input pack contains exam type, target, timeline, weekly time budget, score evidence, samples, error logs, and constraints.

## Phase 2: Subagent Reports

Each subagent returns:
- Evidence used
- Weak points
- Bottleneck hypothesis
- High-impact drills
- Confidence level
- Missing evidence

## Phase 3: Cross-Agent Critique

Required critiques:
- Writing vs Speaking: grammar cleanup, fluency, and naturalness tradeoff
- Reading vs Listening: vocabulary size vs real-time synonym recognition
- Language Error Analyst vs skill specialists: cross-skill error pattern validation
- Study Load Planner vs all agents: remove work that exceeds actual weekly capacity

## Phase 4: Orchestrator Resolution

The Orchestrator resolves conflicts using scoring risk, confidence, target gap, workload feasibility, and regression risk.

## Phase 5: Weekly Review

Every weekly review updates score history, error status, completed hours, and next-week allocation.

## Conflict Table Format

| Conflict | Agents involved | Resolution | Reason |
| --- | --- | --- | --- |
|  |  |  |  |
