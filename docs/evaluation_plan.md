# Evaluation Plan

This project should be evaluated with two separate controlled experiments, because the coursework requires algorithm evaluation and user interface evaluation to isolate different variables.

## 1. Algorithm Evaluation

Goal: test whether the enhanced recommendation algorithm improves recommendation accuracy.

Controlled variable:
- UI stays the same.
- Recommendation explanation stays off.
- Only `algorithm` changes.
- Ask participants to use manual genre selection instead of natural-language parsing, or reuse the same parsed genres, so the LLM preference parser does not add noise.

Conditions:
- Control: `/?algorithm=baseline&explain=false`
- Treatment: `/?algorithm=enhanced&explain=false`

Participants:
- At least 6 participants.
- These participants must not be reused in the UI evaluation.

Suggested measurements:
- Top-N satisfaction: average rating from 1 to 5 for the recommendation list.
- Precision-like score: percentage of recommended movies marked as "interested" or "would watch".
- Mean relevance rating per recommended movie.

Suggested statistical test:
- Use an independent-samples t-test if different users are assigned to control and treatment.
- Use a paired t-test only if the same participant evaluates both algorithm conditions in a counterbalanced order.

Report wording:
- Baseline algorithm: course demo style User-based KNN collaborative filtering.
- Enhanced algorithm: course collaborative filtering with a rating-weight enhancement using timestamp decay.
- TF-IDF + cosine similarity content filtering is used for feedback refinement after users like movies.

## 2. User Interface Evaluation

Goal: test whether the enhanced interface improves user satisfaction and perceived usefulness.

Controlled variable:
- Algorithm stays the same.
- Only UI/explanation features change.

Conditions:
- Control: `/?algorithm=enhanced&explain=false`
- Treatment: `/?algorithm=enhanced&explain=true`

If the original course demo UI is available, a stronger UI evaluation is:
- Control: original demo UI using the same algorithm.
- Treatment: this enhanced UI using the same algorithm.

If the original UI is not available, the explanation toggle above can be reported as a focused UI ablation study.

Participants:
- At least 6 participants.
- These participants must be different from the algorithm evaluation participants.

Suggested measurements:
- Ease of use, 1 to 5 Likert scale.
- Clarity of recommendation results, 1 to 5 Likert scale.
- Helpfulness of explanation, 1 to 5 Likert scale.
- Overall satisfaction, 1 to 5 Likert scale.

Suggested statistical test:
- Use an independent-samples t-test if different users are assigned to each UI condition.
- Use a paired t-test only if the same participant evaluates both UI conditions in a counterbalanced order.

## 3. GenAI Scope

Qwen is not part of the core ranking algorithm. It is used for:
- natural-language preference parsing;
- generating recommendation explanations.

If the Qwen API fails, the system falls back gracefully by returning empty explanations or default parsed genres. The recommendation ranking still works.

## 4. Report Checklist

- Cover page.
- System overview and screenshots.
- One novelty sentence for each UI screenshot.
- Algorithm evaluation design, measurements, results, and statistical test.
- UI evaluation design, measurements, results, and statistical test.
- Participant demographic information.
- Evidence of participation.
- Individual reflection from each group member.
- GenAI usage disclosure.
- References.
- Signed participation form.
