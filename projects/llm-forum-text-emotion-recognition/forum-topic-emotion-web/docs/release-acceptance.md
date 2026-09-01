# Phase C Release Acceptance

Date: 2026-09-01
Status: **Passed for the bounded local research release candidate**
Scope: delivery QA only; no new scientific experiment, model run, or forum request

## Acceptance basis

The release decision combines three evidence types:

1. Current automated software gates.
2. An isolated real-browser smoke using a temporary database and `start_worker=False`.
3. Frozen formal execution evidence from EXP-076, EXP-085 attempt 2, and EXP-086.

The browser smoke listened only on `127.0.0.1:8795`. It did not load M1/M3, access Stack Overflow or
Discourse, read gold labels, or reuse the formal validation databases. The three throwaway jobs and temporary
database were removed after the service stopped.

## Automated RC gates

| Gate | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests -q` | **579 passed in 36.86s** |
| `node --check static/app.js` | Passed |
| `.venv/bin/python -m pip check` | `No broken requirements found` |
| `git diff --check` | Passed |
| Current runtime files versus EXP-086 37-member frozen archive | **0 mismatches** |

The test suite covers upload parsing, both forum adapters, API authentication, task lifecycle, dashboard and
exports, M1/Research/Demo semantics, staged progress and costs, cancellation, late-write rejection, raw clearing,
deletion, store recovery, resource gates, and independent verifier failure cases. Passing tests do not replace
the formal model/source runs.

## Browser smoke

| Check | Result | Evidence |
| --- | --- | --- |
| Login and loopback page | Passed | Token login opened the authenticated workspace |
| Upload form | Passed | One 1-item Research placeholder was created, shown as queued, cancelled, and recovered after reload |
| Stack Overflow form | Passed | Source fields and bounds rendered; a zero-fetch placeholder was created and cancelled |
| Discourse form | Passed | Fixed Python Help source, bounds, population caveat, and Demo budget control rendered; a zero-fetch placeholder was created and cancelled. License metadata is covered by formal EXP-086 evidence, not this empty browser task |
| M1-only / Research / Demo selectors | Passed | All three modes and their distinct help text rendered |
| Progress and Dashboard shell | Passed | Queued progress, denominator, cost scope, diagnostics, source section, and disabled replay/raw controls rendered without model execution |
| Refresh recovery | Passed | Cancelled state persisted after page reload |
| Service restart recovery | Passed | All 3 throwaway jobs reappeared after a clean stop/start using the same temporary database |
| Responsive layout | Passed | `scrollWidth == innerWidth` at widths 1280, 720, and 390 |
| Focus visibility and semantics | Passed with bounded evidence | Task-name focus ring was visible; labelled controls, headings, tables, progressbars, and skip link were present. This is not a full assistive-technology audit |
| Browser console | Passed | 0 warning/error entries |
| Browser delete / clear-raw clicks | Not repeated | Destructive paths are covered by `test_api.py` and `test_store.py`; the smoke did not perform irreversible UI actions |

## Final checklist

| # | Release item | Status | Primary evidence |
| ---: | --- | --- | --- |
| 1 | Browser creates File Upload task | Passed | Browser smoke plus staged integration tests |
| 2 | Browser creates Stack Overflow task | Passed | Browser zero-fetch placeholder; real source chain in EXP-076 |
| 3 | Browser creates Discourse task | Passed | Browser zero-fetch placeholder; real source chain in EXP-086 |
| 4 | Page displays progress | Passed | Browser queued progress; EXP-085 282 staged progress events |
| 5 | Dashboard is viewable | Passed | Browser dashboard shell; EXP-085/086 frozen dashboard artifacts and verifier recomputation |
| 6 | Source traceability is viewable | Passed | UI/source tests; EXP-076/086 provenance verification. No usernames or raw text are copied into this checklist |
| 7 | Queued task can be cancelled | Passed | Browser smoke and API/store tests |
| 8 | Task/private data deletion works | Passed by automated destructive-path tests | Browser smoke intentionally did not click irreversible controls |
| 9 | M1-only mode runs | Passed | EXP-085 attempt 2, three complete M1-only jobs |
| 10 | Research mode runs | Passed | EXP-085 attempt 2 and EXP-086 |
| 11 | Demo budget fallback is explicit | Passed | EXP-085 attempt 2, 15 registered `m3_budget_exhausted` outcomes |
| 12 | State survives page and service restart | Passed | Browser reload/restart smoke plus store recovery tests |

## Local screenshot evidence

The PNGs are local and Git-ignored. They contain only throwaway task names and zero-result UI state.

| File | SHA-256 |
| --- | --- |
| `private/reports/release-acceptance-assets/01-desktop-discourse-cancelled.png` | `0a8b849682d472ec2f2413411ee949e14d42e41159ebdfdf1eb15b756df33c55` |
| `private/reports/release-acceptance-assets/02-layout-1280.png` | `18bdababd542e41156419157a254fa2173a48fa4a42a8e5a50f4def93537ebe9` |
| `private/reports/release-acceptance-assets/03-layout-720.png` | `eb439e9610c724cc1106e09a547447b442c416776fa2f98ffed8d7f7221ce1cf` |
| `private/reports/release-acceptance-assets/04-layout-390-focus.png` | `cdce6ce5404c65897212c671eb2249df64ed4545bc047a19dc62f36a5d50cee8` |
| `private/reports/release-acceptance-assets/05-layout-390-form.png` | `cfed70c4553670d28c456ef429604125689b7b52e9b7414439bc4a10758f25c1` |

## Acceptance boundary

This release acceptance verifies local delivery behavior and evidence presentation. It does not establish
production availability, public-network safety, multi-user behavior, a long-running SLA, external-gold accuracy,
complete forum sampling, or commercial redistribution rights. No commit, stage, push, or public deployment is
part of this acceptance.
