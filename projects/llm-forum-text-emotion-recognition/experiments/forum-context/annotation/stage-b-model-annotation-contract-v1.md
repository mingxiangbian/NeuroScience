# Stage B Model Annotation Contract V1

- Protocol: `DATA-FCTX-LABEL-V1`
- Input schema: `stage-b-model-input-v1`
- Output schema: `stage-b-model-output-v1`
- Input file: `stage-b-inputs-v1.jsonl`
- Output file: `stage-b-model-annotations-v1.jsonl`
- Expected input rows: `120`
- Frozen input SHA-256: `e7dc51c2053db37ad6639b50c553c261b23b2e514072c17d8b70f5deac13ba15`
- Execution boundary: local model only; do not upload IAC text to an external API

## 1. Independence requirement

Run Stage B as an independent contextual annotation pass. Read only this
contract and `stage-b-inputs-v1.jsonl`.

Do not read or use:

- Stage A model outputs;
- human annotations;
- another model's outputs;
- sampling lanes or existing IAC scores;
- conversation history containing an earlier prediction for the sample.

This prevents the Stage B decision from being anchored to a prior label.

## 2. Task

For every input row, identify the single most prominent emotion communicated by
the target author. Use the visible discussion title, direct parent and target
quotations only to interpret the target author's response. Do not label the
emotion of the parent, quoted author, whole discussion or annotator.

The target is observable communicated emotion, not the author's inaccessible
private internal state.

## 3. Input reading rules

The input is UTF-8 JSONL: one complete JSON object per line. Process lines in
ascending `annotation_order`. Every input object has exactly this structure:

```json
{
  "schema_version": "stage-b-model-input-v1",
  "protocol_id": "DATA-FCTX-LABEL-V1",
  "annotation_order": 1,
  "sample_uid": "smp_<64 lowercase hexadecimal characters>",
  "view_sha256": "<64 lowercase hexadecimal characters>",
  "context": {
    "discussion_title": "<cleaned discussion title>",
    "direct_parent_body": "<direct parent text>",
    "target_quotes": [
      {
        "quote_index": 0,
        "text": "<quoted text>",
        "source_relation": "direct_parent",
        "truncated": false,
        "altered": false
      }
    ]
  },
  "target": {
    "body": "<target author's body with quote placeholders>",
    "full_with_quotes": "<target body with bounded quote text>"
  }
}
```

Rules:

1. `target.body` identifies the target author's own text. `[[QUOTE]]` marks an
   omitted quotation at that position.
2. `target.full_with_quotes` reconstructs quotations between `[[QUOTE]]` and
   `[[/QUOTE]]`. Text inside those boundaries belongs to the quoted source, not
   automatically to the target author.
3. `discussion_title`, `direct_parent_body` and `target_quotes` are context for
   interpreting the target response. Their emotion must not be copied to the
   target without evidence in the target's communicative act.
4. `source_relation` may be `direct_parent`, `same_thread_other` or
   `external_or_unknown`. It describes provenance, not emotion.
5. `truncated` or `altered` may be `true`, `false` or `null`. Do not reconstruct
   missing text.
6. Do not search for the original forum, omitted ancestors, root post, future
   replies or any other context.
7. Do not use IDs, hashes or line position as predictive features.
8. Do not skip, duplicate, reorder or merge rows.
9. Copy `annotation_order`, `sample_uid` and `view_sha256` exactly into the
   corresponding output row.

## 4. Candidate labels

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

## 5. Primary decision rules

1. Select the most prominent emotion in the target's current communicative act.
2. If multiple emotions are present and one is dominant, select it and set
   `mixed_emotion=true`.
3. If multiple emotions have no stable primary, use `status="unclear"` and set
   `mixed_emotion=true`.
4. Use `neutral` only when the text is interpretable but no candidate emotion is
   clearly communicated. `neutral` is a label under `status="labeled"`.
5. Use `unusable` only for data-quality failure such as corrupted text,
   effectively empty content or text that cannot be annotated in the target
   language. Emotional ambiguity is `unclear`, not unusable.
6. Do not infer a label from keywords alone. Account for negation, attribution,
   reported speech, rhetorical questions and nonliteral language.
7. Do not output a secondary label or emotion intensity.

## 6. Sarcasm

Sarcasm or irony is a separate rhetorical attribute, not an emotion label:

- `present`: context supports nonliteral, ironic or mocking expression;
- `absent`: no such phenomenon is supported;
- `uncertain`: sarcasm is plausible but evidence is insufficient.

Still label the emotion communicated through the sarcasm. Do not map every
sarcastic utterance to `cynicism`.

## 7. Mixed emotion

`mixed_emotion` is a boolean:

- `true`: more than one emotion is communicated, whether or not one dominates;
- `false`: the evidence does not support multiple communicated emotions.

It is not a secondary-label container.

## 8. Context sufficiency

- `sufficient`: the provided title, parent, quotes and target are adequate for
  the contextual decision;
- `insufficient`: omitted context could materially change interpretation;
- `uncertain`: it is unclear whether additional context is required.

`context_sufficiency="insufficient"` does not automatically force `unclear`.
Make the best valid decision from visible evidence and express uncertainty with
the status and confidence fields.

## 9. Confidence

`confidence` describes confidence in the decision, not emotion intensity:

- `high`: context and target support the decision and alternatives are weaker;
- `medium`: a decision is possible, but a reasonable alternative exists;
- `low`: the decision is tentative and should receive review.

Model-reported confidence is not a calibrated probability.

## 10. Output format

Write UTF-8 JSONL with exactly one output object for every input line. Preserve
the input order. Do not wrap the output in a JSON array. Do not add Markdown code
fences, headings, comments, summaries or prose.

Every output line must contain exactly these outer fields:

```json
{
  "schema_version": "stage-b-model-output-v1",
  "protocol_id": "DATA-FCTX-LABEL-V1",
  "annotation_order": 1,
  "sample_uid": "smp_<copied unchanged from input>",
  "view_sha256": "<copied unchanged from input>",
  "decision": {
    "status": "labeled",
    "primary_emotion": "frustration",
    "other_emotion_text": null,
    "confidence": "high",
    "sarcasm": "absent",
    "mixed_emotion": false,
    "context_sufficiency": "sufficient",
    "note": null
  }
}
```

The `decision` object must contain exactly eight fields:

```text
status
primary_emotion
other_emotion_text
confidence
sarcasm
mixed_emotion
context_sufficiency
note
```

Do not add any other field. Do not output rationale or chain-of-thought. A note
is a concise annotation note, not a reasoning transcript.

## 11. Conditional output constraints

### `status="labeled"`

- `primary_emotion` must be one candidate label.
- `confidence` must be `low`, `medium` or `high`.
- `sarcasm` must be `present`, `absent` or `uncertain`.
- `mixed_emotion` must be JSON `true` or `false`.
- `context_sufficiency` must be `sufficient`, `insufficient` or `uncertain`.
- If `primary_emotion="other_emotion"`, `other_emotion_text` must be a short,
  atomic English emotion name of 1--64 characters.
- Otherwise `other_emotion_text` must be JSON `null`.
- `note` should normally be JSON `null`; when necessary, use a concise note of
  no more than 1000 characters.

### `status="unclear"`

- `primary_emotion` must be JSON `null`.
- `other_emotion_text` must be JSON `null`.
- `confidence` must be `low`, `medium` or `high`.
- `sarcasm` must be `present`, `absent` or `uncertain`.
- `mixed_emotion` must be JSON `true` or `false`.
- `context_sufficiency` must be `sufficient`, `insufficient` or `uncertain`.
- `note` should normally be JSON `null`; when necessary, use a concise note of
  no more than 1000 characters.

### `status="unusable"`

- `primary_emotion` must be JSON `null`.
- `other_emotion_text` must be JSON `null`.
- `confidence` must be `low`, `medium` or `high`.
- `sarcasm`, `mixed_emotion` and `context_sufficiency` must all be JSON `null`.
- `note` must be a concise reason for the data-quality failure, with no more
  than 1000 characters.

`status="unlabeled"` is forbidden in completed model output.

## 12. Completion checks

Before finishing, verify all of the following:

1. Output row count equals input row count.
2. Output orders are exactly `1` through `120`.
3. Every input `sample_uid` appears exactly once.
4. Every `sample_uid` and `view_sha256` matches its input row exactly.
5. Every line parses independently as one JSON object.
6. No output contains Stage A decisions, derived label-change fields, sampling
   metadata or additional keys.
7. No prose appears before, after or between JSONL rows.
