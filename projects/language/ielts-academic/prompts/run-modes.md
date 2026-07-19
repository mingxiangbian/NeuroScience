# Run Modes

## Manual Multi-Session Mode

This is the only mode that supports real agent independence.

Use it for:
- baseline diagnosis
- a regression or error-set decision
- target calibration after comparable mocks
- final exam strategy

Process:
1. Give the same input pack to each subagent in a separate chat or isolated context.
2. Do not show one subagent another subagent's output.
3. Collect all subagent reports.
4. Give the reports to the Orchestrator for conflict resolution.

Cost:
- Baseline: eight subagent runs plus one Orchestrator run.
- Later calibration: rerun only agents whose evidence changed, then rerun Orchestrator.

## Single-Session Simulation Mode

This mode is not independent.

Use it for:
- low-stakes review
- one-sample tactical feedback when the user accepts weaker independence

Required label:

> This output uses single-session simulation mode. Cross-agent critique is simulated and should not be treated as evidence-isolated multi-agent reasoning.

## Mode Choice Rule

Choose manual multi-session mode when a decision changes the target judgment, skill priority, active unit, or exam strategy. Choose single-session simulation mode only for low-stakes tactical feedback.
