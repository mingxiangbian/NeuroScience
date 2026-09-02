# DATA-SO-CONTEXT-RECOVERY-V2 Source Preflight — Attempt 1

Status: **Blocked before download**.

## What was verified

- The fixed 4,800-row Gold workbook is present and matches SHA-256
  `29f667701227fc3f1ffc005c5d5364c30f24476005baac23fff8338dbd2f0179`.
- The workbook and current C0 derivatives have no verified Stack Overflow post,
  revision, parent, or thread identifiers.
- No local Stack Overflow `Posts` or `PostHistory` dump exists.
- The shared heavy-workload advisory mutex was available during the read-only
  check; no heavy scope was started.

## Source and storage gate

The official Internet Archive listing exposes the April 2024 Stack Overflow
archives:

- `stackoverflow.com-Posts.7z`: displayed compressed size 21.4G;
  `Posts.xml` is 103,933,385,042 bytes.
- `stackoverflow.com-PostHistory.7z`: displayed compressed size 35.2G;
  `PostHistory.xml` is 181,564,626,504 bytes.

The two extracted tables total 285,498,011,546 bytes. With only the protocol's
20% headroom, this requires 342,597,613,855 bytes before accounting for archives,
indexes, or temporary files. The workstation currently has 121,348,616,192 bytes
available. A conservative archive + extraction + headroom envelope is about
415.5 GB, so the registered full-extraction route fails the resource gate.

A streaming-only extractor could reduce disk use, but no such implementation,
archive-hash amendment, extractor validation, or bounded index estimate has been
frozen. It cannot be silently substituted for the registered route.

## Certification gate

Certified main C2 requires two independent human first-pass reviewers for every
150-case route and a third adjudicator for disagreements. No reviewers are
registered. An AI agent cannot substitute for these human judgments.

The protocol permits an exact-only deterministic fallback when a second reviewer
is unavailable, but that branch is exploratory and cannot support the certified
main-C2 claim or a confirmatory sealed-test result.

## Required resolution

Provide either:

1. at least 450 GB of free local/external storage plus two independent reviewers
   and an adjudicator-on-demand; or
2. approval of a separately frozen streaming-only resource amendment and the
   explicitly exploratory exact-only fallback.

Until then, no download, context recovery, C2 construction, or three-view model
training is permitted by the hard gates.
