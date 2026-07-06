# Run Modes

## Manual Multi-Session Mode

This is the only mode that supports real agent independence.

Use it for:
- Week 1 baseline
- Week 4 target checkpoint
- Week 6 correction checkpoint
- final exam strategy

Process:
1. Give the same input pack to each subagent in a separate chat or isolated context.
2. Do not show one subagent another subagent's output.
3. Collect all subagent reports.
4. Give the reports to the Orchestrator for conflict resolution.

Cost:
- Baseline: eight subagent runs plus one Orchestrator run.
- Weekly major replanning: rerun only agents whose evidence changed, then rerun Orchestrator.

## Single-Session Simulation Mode

This mode is not independent.

Use it for:
- quick daily adjustment
- low-stakes review
- rough planning when the user accepts weaker independence

Required label:

> This output uses single-session simulation mode. Cross-agent critique is simulated and should not be treated as evidence-isolated multi-agent reasoning.

## Mode Choice Rule

Choose manual multi-session mode when the decision changes the 8-week strategy, the target feasibility judgment, or the skill priority ranking. Choose single-session simulation mode only when the user needs a fast tactical update.
