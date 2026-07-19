# Interaction Protocol

## Phase 1: Input Pack

The input pack contains exam type, target, external deadlines if any, score evidence, samples, error logs, the unit ledger, calibration events, and constraints.

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
- Execution Planner vs all agents: reduce competing recommendations to one evidence-backed unit

## Phase 4: Orchestrator Resolution

The Orchestrator resolves conflicts using scoring risk, confidence, target gap, regression risk, and external deadline risk.

## Phase 5: Settlement And Trigger Update

When the active unit meets its settlement criteria, update the score event history, error status, settled-unit record, and calibration triggers. If the unit has not started, preserve `activeUnit: null`.

## Conflict Table Format

| Conflict | Agents involved | Resolution | Reason |
| --- | --- | --- | --- |
|  |  |  |  |
