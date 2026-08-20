# DATA-SO-CONTEXT-RECOVERY-V2: Certified Stack Overflow Context Recovery

- Protocol ID: `DATA-SO-CONTEXT-RECOVERY-V2`
- Tier: Major data protocol
- RQ: `RQ-S2`
- Parent: [DEC-SO-CONTEXT-RECOVERY-V2](dec-so-context-recovery-v2.md) and
  [DATA-SO-TASK-V1](data-so-task-v1.md)
- Registered: 2026-08-17
- Status: `Registered only; no download, private-data access, recovery, review,
  C2 construction, model run, or test access is authorized`

## 1. Question And Stop Boundary

Can a high-precision subset of the fixed 4,800 Stack Overflow Emotion Gold rows
be linked to the correct platform entity and initial target revision, then paired
with parent-question text that existed when the target was created?

The source workbook supplies no verified platform IDs. A plausible match is not a
fact until it passes this protocol. Failure of source, license, security, precision,
temporal, quarantine, quantity, label-support, donor, or power gates stops formal
C2 construction; thresholds may not be relaxed after results are seen.

## 2. Source, Field, Resource, And License Preflight

Before any future download or extraction, an amendment must freeze:

```text
Gold source revision and SHA-256
selected SOTorrent or Stack Exchange dump release
official download URL or DOI
archive SHA-256 and download date
logical-to-physical table mapping and table versions
archive, extracted, index, temporary, and 20%-headroom byte estimates
authorized local access principals
retention deadline and verified deletion procedure for every private class
```

Available disk must cover all five byte estimates. Large extraction/index work
and every formal M3 model-load/training scope must acquire the same exclusive,
non-blocking OS advisory mutex before either process initializes mutable output:

```text
experiments/stack-overflow-emotion-gold/oof-router/private/locks/heavy-research-workload.lock
```

This is one shared mutex, not two independent check files. Both workflows use the
same canonical lexical path, reject symlink components, acquire the kernel lock
atomically, and hold it through the complete heavy scope. Owner, PID, host, stage,
and acquisition time are diagnostic metadata only; metadata does not establish
ownership without the live kernel lock. A contender fails closed without waiting
or mutating its attempt. Deleting, replacing, or overriding a live or unverifiable
lock is forbidden, and both workflow verifiers test and record the same mutex
contract.

The closed logical source allowlist is:

| Table | Allowed fields |
|---|---|
| `Posts` | `Id`, `PostTypeId`, `ParentId`, `CreationDate`, `LastEditDate`, `Title`, `Body`, `Tags`, `ContentLicense` |
| `Comments` | `Id`, `PostId`, `CreationDate`, `Text`, `ContentLicense` |
| `PostHistory` | `Id`, `PostHistoryTypeId`, `PostId`, `RevisionGUID`, `CreationDate`, `Text` |

No `Users`, `Votes`, owner/display-name, email, IP, or profile field is permitted.
If a selected source uses different physical names, the amendment may map them to
these logical fields but may not widen the allowlist silently. The main C2 task
uses Answer-to-Question relations; Comments are candidate/audit data only and do
not become a direct-parent C2 sample.

Before extraction, the source amendment must enumerate the exact
`PostHistoryTypeId` values that represent initial or edited title/body/tag content
and any required rollback representation. Every moderation, ownership, user,
comment, or other history type is rejected by default; a descriptive label alone
cannot expand this value allowlist.

For every privately retained contribution revision, record its revision and
creation times, applicable `ContentLicense` or time-derived CC BY-SA version,
canonical source URL, source entity/revision identifiers, whether an account
identifier is present in the selected dump, and the exact attribution obligation.
For this no-redistribution experiment, that private source-and-license ledger is
the attribution record; it does not require opening a `Users` table or retaining
display names. This protocol redistributes no source text or author data. Any
later text redistribution requires a new license-and-attribution protocol that
separately freezes the minimum author-attribution fields and their private/public
handling before access.

## 3. Private Storage And Review Safety

Frozen roots for a later authorized implementation are:

```text
public:  experiments/stack-overflow-emotion-gold/context-recovery/runs/data-so-context-recovery-v2
private: experiments/stack-overflow-emotion-gold/context-recovery/private/data-so-context-recovery-v2
```

Every authorized stage uses append-only attempt paths beneath those roots:

```text
<root>/<source-preflight|calibration-pilot|full-recovery|certification|c2-construction>/attempt-N
<public-root>/<stage>/selected-attempt.json
```

Immediately before initialization, both matching public/private attempt paths and
that stage's selection record must be absent; files, empty directories, symlinks,
and redirected ancestors all fail closed. Directories and every frame, rule
manifest, review bundle, judgment, adjudication, graph, split, seal, donor map,
run, verification, and failure record are created exclusively once. Partial or
failed attempts remain immutable. A retry uses `attempt-N+1`; a verifier cannot
repair an analyzer artifact in place. Only an independent verifier may atomically
create a stage selection record, which binds the selected attempt and every input
and output hash. A rule correction after a certification frame exists requires a
new protocol version, new attempt, new frame, and new random draw; no freeze,
hash, or seal may be replaced in place.

The private root and every extraction, index, candidate, review, mapping, donor,
and row-level artifact must be covered by exact Git-ignore rules. Preflight runs
`git check-ignore` on every resolved private path, rejects symlinks or redirected
ancestors, enforces directories `0700` and files `0600`, and scans public outputs
against an aggregate-only allowlist.

Raw/cleaned text, platform IDs, revision IDs, URLs, labels, parent-target maps,
review decisions, and per-row raw/normalized text hashes are private. Public
outputs may contain only aggregate counts/distributions, recovery rates, method
counts, precision intervals, bias summaries, artifact hashes, and verifier status;
even anonymous per-row mappings are excluded.

The pre-download retention manifest covers raw archives, extracted tables,
indexes, caches, temporary files, review bundles, mappings, split/test seals,
donor maps, checkpoints, adapters, optimizer states, predictions, logits and
backups. All are private by default. Their access principals, retention deadline
and verified deletion disposition are frozen by class; publishing any class
requires a later protocol rather than an implicit exception.

Raw text, IDs, URLs, hashes, and mappings must not enter command lines, stdout,
stderr, progress bars, exception messages, telemetry, or crash dumps. They must
not be sent to external LLM, embedding, vector-search, web-search, analytics, or
logging APIs. Matching is local and deterministic.

Any review UI is local-only and reads the private review bundle. All source text
is HTML-escaped; active HTML, Markdown rendering, JavaScript, remote assets,
clickable links, URL previews, and automatic network requests are disabled. A
restrictive `default-src 'none'` content-security policy is required.

## 4. Candidate Index And Retrieval Normalization

The private candidate index stores only the allowlisted fields needed to derive:

```text
target_id and target_type
question_id, parent_question_id, host_post_id, and thread_id
target creation time
post/comment revision ID and revision time
raw, cleaned, body-only, title-plus-body, and historical-version hashes
```

The initial local candidate-retrieval transform is applied in this order:

1. HTML entity decoding;
2. HTML tag removal;
3. fenced/block code removal;
4. inline code removal;
5. URL removal;
6. Unicode NFKC;
7. quote normalization;
8. newline normalization;
9. whitespace collapse;
10. trim.

It creates question title-plus-body, question body-only, answer body, comment,
and historical-version candidates. This transform is a retrieval hypothesis, not
a claim that it reproduces the Gold authors' preprocessing. The pilot may produce
one pre-full-recovery amendment that freezes the final ordered transform, hashes,
short-text exclusions, similarity threshold, best-versus-second margin, candidate
multiplicity rule, and deterministic tie order. No rule changes are allowed after
the certification frame is frozen.

Candidate methods are:

- `normalized_exact`: one unique accepted normalized current-text match;
- `historical_exact`: one unique accepted historical-revision match;
- `fuzzy`: locally retrieved BM25/character-n-gram/containment/edit-similarity
  candidates passing the pilot-frozen score and margin.

Short generic strings and unresolved multiple candidates are rejected under the
frozen rule. Fuzzy candidates remain review-only unless fuzzy independently passes
its own certification gate.

## 5. Independent Pilot And Certification

### 5.1 Calibration pilot

The pilot contains exactly `100` candidate decisions drawn with
`PCG64(20260817)`. Its deterministic allocation balances method, target type,
score/boundary band, text-length quintile, candidate multiplicity, and creation-era
quartile using largest-remainder quotas over nonempty strata.

The pilot frame excludes:

- every old C0 test row;
- every exact/normalized duplicate component already containing old C0 test;
- any already known thread/component connected to old C0 test;
- any case reserved for certification.

Reviewers are blinded to emotion labels, M1/M3 predictions, router outputs, and C0
split. Method name, similarity score, threshold, candidate rank, and the automatic
accept/reject decision are also hidden while the reviewer judges the displayed
candidate pair. Hiding the split is not the safety mechanism: test cases are
absent from the frame. Pilot judgments may change only the matching-rule manifest
described above; pilot rows never estimate precision and never re-enter
certification.

### 5.2 Frozen certification frames

After full matching with frozen rules, create an accepted frame hash before any
certification judgment. For every `(matching method, target type)` route proposed
for main C2, draw exactly `150` non-pilot cases without replacement using
`PCG64(20260818)` by simple random sampling within that route. The sampling
manifest freezes the complete frame hash, ordered frame, RNG state, selected row
positions, and inclusion probability. This makes the ordinary binomial precision
and Clopper-Pearson interval the registered primary estimator. There is no optional
stopping, replacement, post-hoc sample increase, or reuse of a failed set.

A separate challenge audit may deliberately oversample score boundaries, short
texts, long texts, multiple candidates, rare eras, and other failure-prone strata.
It is reported by stratum and cannot be pooled into, replace, or tune the primary
simple-random certification set.

Two reviewers independently label two separate questions for every case:

```text
entity_match: same / not_same / uncertain
initial_target_revision_match: same / not_same / uncertain
```

Disagreements are adjudicated by a third reviewer who has not seen model results.
If no third reviewer is available, the final label remains `uncertain`. Every final
`uncertain` counts as an error, as does any unresolved or missing judgment.
Agreement and disagreement rates remain visible regardless of adjudication.
Review bundles hide method, score, threshold, candidate rank, automatic decision,
emotion labels, model outputs, C0 split, and future C2 split.
Candidate presentation order is independently randomized for each reviewer from
`PCG64(20260822)` and cannot reveal the retrieval rank.

For each method/target-type route, compute separate and joint precision counts for:

1. correct entity;
2. correct initial target revision;
3. both correct on the same row.

Each endpoint must have a one-sided exact Clopper-Pearson 95% lower bound at least
`0.98`. With fixed `n=150`, this ordinarily requires `150/150` correct. Every route
that fails, has fewer than 150 accepted cases, or lacks two independent first-pass
reviews is excluded from main C2 and retained only as exploratory recovery evidence.
Changing a rule after certification requires a new protocol version, new frame,
new RNG draw, and new reviewers' bundle.

If a second independent reviewer truly cannot be obtained, the V2 fallback is a
separately named `deterministic high-precision subset`: only unique
`normalized_exact` and unique `historical_exact` matches may enter it, fuzzy is
excluded, and no `98% independent precision certification` claim may be made.
That exact-only branch may support separately labeled exploratory C2 development
under a later protocol, but it does not satisfy the certified main-C2 gate or
authorize a confirmatory sealed-test claim.

## 6. Temporal Identity And Context Construction

Entity identity and revision identity remain separate fields. Every accepted row
stores privately:

```text
target_id, target_initial_revision_id, target_initial_revision_time
target_creation_time, matched_gold_revision_id, matched_gold_revision_time
context_id, context_revision_id, context_revision_time, context_creation_time
entity_certification_status, target_revision_certification_status
temporal_snapshot_status
```

Primary `posting_time` rows require:

- the Gold target matches the target's initial revision;
- the temporal anchor is `target_creation_time`;
- the parent question already existed at that anchor;
- context is the latest parent-question revision satisfying
  `context_revision_time <= target_creation_time`.

Rows whose Gold text matches only a later target revision are excluded from the
primary C2 estimand. They may enter a separately labeled
`later_revision_annotation_snapshot` sensitivity set, whose context is restricted
to revisions available by that later target-revision time. `latest_only_unverified`,
missing revisions, edited-after-anchor context, and future information never enter
primary true context.

Main C2 includes only verified Answer targets with their referentially linked
Question parent. Comment-to-host records remain auxiliary and cannot be described
as direct parent context.

## 7. C0 Test Quarantine And C2 Split

Quarantine is constructed before C2 allocation:

1. exclude all old C0 test rows and their existing exact/normalized duplicate
   components;
2. under a separately authorized quarantine-only matcher, recover old test
   entities and add thread edges;
3. take connected components over duplicate plus recovered thread edges;
4. exclude every component containing any old test row from C2 train, dev, test,
   and shuffled-donor pools.

The protocol reports old-test entity recovery coverage. Only `100%` permits the
term `complete recovered-thread quarantine`. Any lower coverage must be labeled
`known-link quarantine`; it cannot imply that unknown old-test thread links were
excluded. `100%` old-test entity recovery followed by union-component quarantine
is a hard gate for certified main C2. At lower coverage, only a separately labeled
challenge/exploratory subset may be built; no formal C2 split, confirmatory model
selection, or C2 test seal is authorized. Pilot and certification never draw from
the old-test quarantine.

For the remaining primary pairs, form the union graph of exact, normalized,
pilot-frozen near-duplicate, and Stack Overflow thread edges. Connected components
are indivisible. A deterministic `70/15/15` train/dev/test allocation with seed
`20260819` balances rows, components, labels, neutral status, target length,
matching method, era, and duplicate/conflict slices. Any component containing an
old C0 validation row **must not** enter C2 test; it may enter C2 train/dev only.
Every row exposed in pilot, certification, adjudication, or challenge review is
marked `review_exposed=true`; its entire union-graph component may enter C2
train/dev only and is forbidden from C2 test and the test donor pool. Reviewers
and model developers therefore cannot inspect a future test row or a graph-linked
proxy before the test seal.

Before any context-model training, freeze and hash the component graph, split,
labels, tokenizer/rendering rules, donor map, source-order map, and private/public
manifests. The new C2 test labels are separated and sealed. Only the data verifier
may inspect them during construction; training, checkpoint selection, threshold
selection, donor selection, and dev analysis cannot.

Because the eligible pool is derived from former C0 train/validation rows, target
texts may have participated in earlier C0 development even though the C2 relation,
views and split are newly frozen. The sealed partition must therefore be called a
`within-source newly frozen C2 development holdout`, never an independent or
previously unseen-text test.

## 8. Viability, Support, Bias, And Power Gates

All counts are recomputed after certification, temporal filtering, C0 quarantine,
component splitting, donor construction, and zero-context-budget exclusion.

Structural formal-three-view gates:

```text
primary answer-question pairs >= 500
unique Stack Overflow threads >= 300
union-graph connected components >= 300
```

At least `1,000` pairs and `600` threads/components are required before a later
learned context-gate proposal. `300-499` pairs are development/challenge only;
fewer than `300` stop the quantitative context branch.

A label-specific or Macro-F1 result is eligible for stable secondary interpretation
only when the label has at least `20` positive union components overall and at
least `5` positive components in each train/dev/test split. Five-label Macro-F1 is
secondary/sensitivity evidence, not a confirmatory primary endpoint, unless a
later amendment supplies its own power and stronger per-label support gate.
`surprise` is descriptive under the same rule; report TP/FP/FN and F1 without
letting it drive a context claim.

Before C2 test access, each model family must pass a dev-only design-power gate.
The unique confirmatory primary endpoint is paired Hamming-loss improvement. Using
paired dev loss differences, planned sealed-test component counts, `10,000`
component-resampling simulations, and seed `20260820`, estimate the smallest
detectable absolute improvement with at least `80%` power. Family-wise one-sided
alpha `0.05` is Bonferroni-controlled across exactly four confirmatory tests
(`2` model families times `2` contrasts: true versus target-only and true versus
shuffled), so every test uses alpha `0.0125`. A family is confirmatory only if both
of its contrasts have MDE at most `0.005`; otherwise its test remains sealed and
its analysis exploratory. No test labels or outcomes may enter this calculation.

The viability report also compares recovered versus unmatched Gold rows on text
length, six-label prevalence, Group/Set, and duplicate-component size. Absolute
standardized differences above `0.25` do not silently fail the dataset, but force
the claim wording `recoverable Stack Overflow answer subset`. Unobservable era or
target-type properties are marked not comparable, never inferred balanced.

## 9. Hard Shuffled-Context Contract

Each primary target receives one frozen shuffled-question donor. These constraints
are hard and may never be relaxed:

- donor is in the same C2 split but a different thread and union component;
- donor is outside every old-test quarantine and old-validation-to-test conflict;
- the selected donor revision existed by the target's primary temporal anchor;
- donor is not an exact, normalized, or pilot-frozen near duplicate of true context
  or target;
- emotion labels, model predictions, representations, errors, and context results
  are not used;
- one donor is used by at most `3` targets within a split;
- after tokenization and truncation, shuffled and true context contribute exactly
  the same actual number of context tokens for both M1 and M3.

Soft matching priority is tag/topic cluster, creation-era bin, question-length
decile, then code-token-ratio bin. Only these soft properties may relax in the
pre-frozen order, with the level recorded; the maximum permitted relaxation level
is `2`, and hard constraints remain outside this numbering. Before the donor map
is sealed, one-hot topic/era indicators and numeric question-length/code-ratio
covariates must each have absolute standardized difference at most `0.10` between
true and shuffled contexts in every split. This `0.10` value is a pre-registered
engineering balance gate, not a literature-derived universal threshold. A donor
revision is the latest revision available by the target anchor. If no donor
satisfies every hard constraint, the relaxation cap, the balance gate, and exact
token-count matching, that target is excluded from the confirmatory paired set
rather than accepting a weaker donor. If the retained set no longer passes the
viability and power gates, the shuffled contrast is exploratory and C2 test access
remains blocked.

The private donor map is deterministically generated from seed `20260821`, frozen
before model training, and invariant to labels and results. Test donors cannot be
changed after any test access.

## 10. Three Views And Clean Matched Training

For each model tokenizer, target tokens are computed once and reused byte-for-byte
across views:

```text
C1 = target only
C2 = true point-in-time parent question + target
C3 = matched shuffled point-in-time question + target
```

M1 retains max length `256`; M3 retains max length `384`. Target is fully preserved
before context uses remaining capacity. True and shuffled use the same rendering,
truncation direction, and exact actual context-token count. Rows where target alone
fills the budget are flagged `zero-context-budget` and excluded from confirmatory
paired comparisons.

Before donor construction, splitting, viability counting, or any context-model
training, a no-result rendering amendment must freeze positive integer
`minimum_actual_context_tokens_m1` and `minimum_actual_context_tokens_m3` values
using only tokenizer mechanics and pre-outcome length feasibility. The values
cannot be chosen from model results. A row below either registered minimum is
flagged `insufficient-context-budget` and excluded from the confirmatory paired
set; viability, support, balance, and power gates are then recomputed. Missing
values block C2 construction rather than defaulting to zero.

For canonical seed 42, train three separate M1 runs and three separate M3 runs,
one per view. Every run starts from the original pinned clean pretrained
RoBERTa/Qwen base with a fresh matched classifier head and, for M3, fresh matched
LoRA tensors. C0/EXP-051/053/058 checkpoints, adapters, heads, optimizer states,
logits, and representations are forbidden initializers.

Within a model family, the three runs have identical initialization hashes,
train/dev/test rows, batch order, optimizer, schedule, epochs, hyperparameters,
checkpoint-selection rule, threshold-selection procedure, and evaluation code;
only the registered input view differs. Any fitted threshold is selected
separately under that identical pre-frozen procedure using train/dev only; no
numeric threshold is shared merely to force equality across different prediction
distributions. Checkpoints are selected on C2 dev only. The sealed test is
opened once, for the frozen six-run comparison, only after a separate experiment
protocol, power gate, independent preflight, and explicit user authorization pass.
Seeds 43/44 and a learned context gate require later protocols and cannot rescue a
failed seed-42 three-view result.

The confirmatory primary metric is Hamming loss. Five-label Macro-F1, six-label
Macro-F1, and per-label F1 are secondary/sensitivity metrics under the support
rules above. True context must be reported against both target-only and shuffled
context. Longer input alone cannot support a semantic-context claim.

## 11. Verification, Test Seal, And Outputs

An independent verifier must reproduce source/field allowlisting, hashes,
normalization-rule identity, pilot/certification separation, fixed RNG draws,
Clopper-Pearson bounds, temporal anchors, revision selection, test/validation
quarantine, union components, split, support/quantity/power gates, donor hard
constraints, exact per-model token counts, clean initialization, permissions,
Git-ignore coverage, public allowlist, and split-access audit.

Any mismatch leaves status `Failed/Unverified`. The C2 test seal may be opened at
most once; a crash before any label/result read is retained and independently
audited, while any partial result access consumes the one-shot gate and forbids a
silent retry.

Private outputs include sources, indexes, row-level hashes/IDs/text, reviews,
entity/revision mappings, snapshots, quarantine graph, C2 rows/labels, donor map,
and sealed test. Public outputs contain only aggregate construction, certification,
viability, bias, power, resource, license, and verification reports plus hashes.

## 12. Claim Boundary

Passing recovery and C2 construction supports a certified recoverable-subset data
claim. A later passed one-shot test supports only a newly frozen within-source C2
development-holdout result under the recovered subset and selected source
snapshot. Neither
supports complete Stack Overflow recovery, external-domain generalization,
context-aware original labels, production deployment, or a universal context
benefit.
