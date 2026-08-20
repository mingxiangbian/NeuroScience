# DEC-SO-CONTEXT-RECOVERY-V2: Context Recovery Decision Record

- Decision ID: `DEC-SO-CONTEXT-RECOVERY-V2`
- RQ: `RQ-S2`
- Parent: [DATA-SO-TASK-V1](data-so-task-v1.md)
- Registered: 2026-08-17
- Status: `Registered; data access, download, recovery, review, C2 construction,
  model training, and test access are not authorized by this document`

## Decision And Scope

Stack Overflow Emotion Gold does not contain verified platform post, revision,
parent, or thread IDs. Recovering them is therefore an independently certified
data-engineering experiment, not a deterministic enrichment of C0. It does not
block the C0 paper and cannot retroactively make C0 thread-disjoint.

Only a certified, temporally valid, leakage-controlled subset may enter a future
C2 task. Failure or insufficient yield is retained as a data result. Neither this
record nor [DATA-SO-CONTEXT-RECOVERY-V2](data-so-context-recovery-v2.md) claims
that recovery has occurred or authorizes its execution.

## Frozen Recovery Decisions

1. A 100-case calibration pilot may tune matching rules but may draw only from
   non-C0-test rows outside every duplicate component already connected to C0
   test. Pilot cases never enter certification.
2. After rules are frozen, every matching method proposed for main C2 receives
   its own fixed, independently drawn certification set of exactly 150 cases.
   Entity identity and target-revision identity are judged and gated separately;
   `uncertain` counts as an error.
3. Each method must independently attain a one-sided exact Clopper-Pearson 95%
   precision lower bound of at least `0.98` for entity, initial target revision,
   and their joint correctness. Methods that fail or lack 150 cases cannot enter
   main C2. Without a second independent reviewer, only unique normalized or
   historical exact matches may form a separately named `deterministic
   high-precision subset`; fuzzy is excluded and independent-certification claims
   are forbidden.
4. The primary temporal estimand is posting-time context: the Gold target must
   match the target's initial revision, and context must be the latest parent
   revision available no later than target creation time. Later target revisions
   are sensitivity data only.
5. C0 test rows are always excluded. Their known duplicate components are
   quarantined first; recovered thread edges expand that quarantine. Certified
   main C2 requires `100%` old-test entity recovery followed by union-component
   quarantine. Otherwise the status is only `known-link quarantine` and only a
   challenge/exploratory subset is permitted. Any component containing an old C0
   validation row is forbidden from C2 test.
6. C2 viability depends on pairs, unique threads, union-graph components,
   per-label positive components, and a pre-test power/MDE gate; raw pair count
   alone cannot pass.
7. True, target-only, and shuffled views are separately trained from clean pinned
   pretrained bases with matched fresh initializations. C0 checkpoints, adapters,
   heads, logits, or optimizer states cannot initialize a C2 model.
8. Shuffled-context temporal, split, thread/component, duplicate, information,
   reuse, and actual token-length constraints are hard and may never be relaxed.
9. The new C2 test is sealed before training and opened at most once under a
   separate explicit authorization after every configuration and checkpoint is
   frozen.
10. Every recovery stage is append-only: failed attempts remain immutable, retries
    use a new attempt, and only an independent verifier may atomically select one
    attempt while binding all input/output hashes.
11. Context recovery and formal M3 work acquire the same canonical exclusive OS
    advisory mutex before any heavy-scope mutation; check-then-act lock files are
    not accepted.
12. Per-tokenizer positive minimum actual context-token counts must be frozen in a
    no-result amendment before C2 construction; rows below either minimum cannot
    enter confirmatory comparisons.

## Security And Publication Boundary

Source tables and fields use a closed allowlist. Raw text, platform IDs, URLs,
revision IDs, user attribution, parent-target mappings, and row text hashes remain
Git-ignored and mode `0600` under mode-`0700` directories. They may not be sent to
an external LLM, embedding, search, or analytics API; logs and crash reports may
not contain them. Human-review HTML is escaped, script-free, and cannot fetch
URLs. Public outputs are aggregate allowlisted statistics and hashes only.

## Claim Boundary

If every gate later passes, the strongest permitted data claim is:

> A high-precision, time-consistent subset of recoverable Stack Overflow answer
> targets was linked to parent-question context and used to construct a newly
> frozen within-source C2 development holdout.

It is not recovery of all Stack Overflow threads, independent external-data
validation, proof that the original Gold labels are context-aware, or evidence
that context generalizes to other forums.
