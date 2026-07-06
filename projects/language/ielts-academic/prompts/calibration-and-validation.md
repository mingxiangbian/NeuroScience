# Calibration And Validation

## Source Anchors

- IELTS scoring detail: https://ielts.org/take-a-test/your-results/ielts-scoring-in-detail
- IELTS Writing descriptors news entry: https://ielts.org/news-and-insights/ielts-writing-band-descriptors-and-key-assessment-criteria
- British Council Writing band descriptors PDF: https://takeielts.britishcouncil.org/sites/default/files/ielts_writing_band_descriptors.pdf
- British Council Speaking band descriptors PDF: https://takeielts.britishcouncil.org/sites/default/files/ielts_speaking_band_descriptors.pdf

## Examiner Rule

An LLM-generated band estimate is advisory. It is not an official IELTS score.

## Calibration Routine

1. Use a known-score or official sample answer when available.
2. Ask the examiner prompt to score it using descriptor categories.
3. Compare the estimated score to the known score.
4. If the estimate differs by more than 0.5 band, mark that examiner as uncalibrated.
5. If the examiner cannot justify the score against descriptor categories, mark that examiner as uncalibrated.

## Writing Consistency Check

For major replanning, assess important Writing samples twice:
- first-pass examiner judgment
- second-pass consistency check

Use the score range and confidence level in the score profile.

## Speaking Evidence Check

Pronunciation and real-time fluency require audio evidence, timing notes, or a structured self-assessment. Transcript-only evidence can support grammar, vocabulary, and answer structure, but it cannot verify pronunciation.
