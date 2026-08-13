# Stage A Model Annotation Contract V1

- Protocol: `DATA-FCTX-LABEL-V1`
- Input schema: `stage-a-model-input-v1`
- Output schema: `stage-a-model-output-v1`
- Input file: `stage-a-inputs-v1.jsonl`
- Output file: `stage-a-model-annotations-v1.jsonl`
- Expected input rows: `120`
- Frozen input SHA-256: `99341ea453164587c4cf46a02c5e203d634ce1bf823d067a73ea609c15f41047`
- Execution boundary: local model only; do not upload IAC text to an external API

## 1. Task

For every input row, identify the single most prominent emotion communicated by
the author in `target_body`. Judge only the observable emotion conveyed by the
target text. Do not claim to infer the author's private internal state.

This is Stage A. No discussion title, parent post, quoted text, later reply,
sampling lane, existing IAC score or human label may be used.

## 2. Input reading rules

The input is UTF-8 JSONL: one complete JSON object per line. Process lines in
ascending `annotation_order`. Every input object has exactly these fields:

```json
{
  "schema_version": "stage-a-model-input-v1",
  "protocol_id": "DATA-FCTX-LABEL-V1",
  "annotation_order": 1,
  "sample_uid": "smp_<64 lowercase hexadecimal characters>",
  "view_sha256": "<64 lowercase hexadecimal characters>",
  "target_body": "<target author's text>"
}
```

Rules:

1. Use only `target_body` as semantic evidence.
2. Treat `[[QUOTE]]` as "quoted text omitted". It is not an emotion token and
   does not reveal the content or emotion of the quotation.
3. Do not search for missing context or reconstruct omitted quotations.
4. Do not use IDs, hashes or line position as predictive features.
5. Do not skip, duplicate, reorder or merge rows.
6. Copy `annotation_order`, `sample_uid` and `view_sha256` exactly into the
   corresponding output row.

## 3. Candidate labels

Choose at most one primary label.

| Label | Operational definition |
| --- | --- |
| `anger` | Explicit anger, condemnation, hostility or forceful confrontation directed at a person or event. Do not use for ordinary disagreement. |
| `frustration` | Emotion caused by blocked goals, repeated failure, ineffective communication or inability to make progress. |
| `disappointment` | A prior expectation, promise or hoped-for outcome was not met. |
| `sadness` | Sadness, distress or low mood associated with loss, suffering or misfortune. |
| `fear` | Fear of a threat, danger or possible harm. Do not use for general uncertainty. |
| `joy` | Clear pleasure, happiness or enjoyment. Politeness and agreement alone are not joy. |
| `surprise` | Reaction to an unexpected or expectation-violating event. |
| `confusion` | Explicit inability to understand, resolve or explain something. A rhetorical question alone is not confusion. |
| `disgust` | Moral, social or physical revulsion and rejection. Ordinary disagreement is not disgust. |
| `cynicism` | Mocking or distrustful disbelief about another person's sincerity, motives or likely outcome. Sarcastic wording alone is not necessarily cynicism. |
| `neutral` | No candidate emotion is clearly communicated. Factual statements and position disagreement may be neutral. |
| `other_emotion` | A clear, atomic emotion exists but is absent from the candidate list. Supply its short English name in `other_emotion_text`. |

## 4. Decision rules

1. Label the target author's own communicated emotion, not an emotion merely
   mentioned, quoted, denied or attributed to another person.
2. Select the most prominent emotion in the target's current communicative act.
3. If several emotions are present but one is clearly dominant, select that one.
   Stage A does not output a secondary label or a mixed-emotion field.
4. If several emotions are plausible and no stable primary emotion can be
   selected, use `status="unclear"`; do not choose arbitrarily.
5. Use `neutral` only when the text is interpretable but no candidate emotion is
   clearly communicated. `neutral` is a label under `status="labeled"`.
6. Use `unusable` only for a data-quality failure such as corrupted text,
   effectively empty content or text that cannot be annotated in the target
   language. Shortness or emotional ambiguity alone is not unusable.
7. Do not infer a label from keywords alone. Account for negation, reported
   speech, rhetorical questions and possible nonliteral language using only the
   visible target text.
8. Do not output emotion intensity, sarcasm, mixed emotion, context sufficiency,
   rationale or chain-of-thought.

## 5. Confidence

`confidence` describes confidence in the decision, not emotion intensity:

- `high`: the decision is well supported and alternatives are clearly weaker;
- `medium`: a primary decision is possible, but a reasonable alternative exists;
- `low`: the decision is tentative and should receive review.

Model-reported confidence is not a calibrated probability.

## 6. Output format

Write UTF-8 JSONL with exactly one output object for every input line. Preserve
the input order. Do not wrap the output in a JSON array. Do not add Markdown code
fences, headings, comments, summaries or prose.

Every output line must contain exactly these outer fields:

```json
{
  "schema_version": "stage-a-model-output-v1",
  "protocol_id": "DATA-FCTX-LABEL-V1",
  "annotation_order": 1,
  "sample_uid": "smp_<copied unchanged from input>",
  "view_sha256": "<copied unchanged from input>",
  "decision": {
    "status": "labeled",
    "primary_emotion": "frustration",
    "other_emotion_text": null,
    "confidence": "medium",
    "note": null
  }
}
```

The `decision` object must contain exactly five fields:

```text
status
primary_emotion
other_emotion_text
confidence
note
```

Do not add any other field.

## 7. Conditional output constraints

### `status="labeled"`

- `primary_emotion` must be one candidate label.
- `confidence` must be `low`, `medium` or `high`.
- If `primary_emotion="other_emotion"`, `other_emotion_text` must be a short,
  atomic English emotion name of 1--64 characters.
- Otherwise `other_emotion_text` must be JSON `null`.
- `note` must normally be JSON `null`.

### `status="unclear"`

- `primary_emotion` must be JSON `null`.
- `other_emotion_text` must be JSON `null`.
- `confidence` must be `low`, `medium` or `high`.
- `note` must normally be JSON `null`.

### `status="unusable"`

- `primary_emotion` must be JSON `null`.
- `other_emotion_text` must be JSON `null`.
- `confidence` must be `low`, `medium` or `high`.
- `note` must be a concise reason for the data-quality failure, with no more
  than 1000 characters.

`status="unlabeled"` is forbidden in completed model output.

## 8. Completion checks

Before finishing, verify all of the following:

1. Output row count equals input row count.
2. Output orders are exactly `1` through `120`.
3. Every input `sample_uid` appears exactly once.
4. Every `sample_uid` and `view_sha256` matches its input row exactly.
5. Every line parses independently as one JSON object.
6. No output contains Stage B fields or additional keys.
7. No prose appears before, after or between JSONL rows.
