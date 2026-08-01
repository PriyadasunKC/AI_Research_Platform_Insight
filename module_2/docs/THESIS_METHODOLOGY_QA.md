# Thesis Methodology Q&A - Module 2

Answers to the 8 methodology questions, each one verified directly against the live codebase, the live Neo4j database, and a fresh test run - not recalled from earlier in the conversation. Where a question asked me to decide something, that's marked clearly as a **recommendation**, not a verified fact.

---

## Q1 - NER results

**I cannot supply an exact per-class F1 table - here is exactly why, and what I could verify instead.**

I searched this project directory and the parent `Model Training/sinhala_ner_test/` folder (where `ner_train.py`, `ner_train_3_tags.py`, `ner_xlm.py`, and the model checkpoints live) for any saved evaluation output - a log file, a `classification_report` dump, a results JSON. **None exists.** The training scripts do call `classification_report`/`f1_score`/`seqeval`-style functions, but whatever numbers they printed at training time were not saved to disk anywhere I have access to, and I don't have the interim report file itself to read the numbers back out of it. Fabricating a per-class table here would be exactly the kind of unverified claim you told me not to make.

**What I *can* confirm, factually, from the actual annotated training data** (combined across `annotated.conll`, `annotated1.conll`, `pre_annotated_full_kings.conll` - 47,286 tokens scanned):

| Entity class | Span count in training data |
|---|---|
| LOCATION | 1,729 |
| PERSON_KING | 1,613 |
| PERSON *(legacy label, pre-dates the current PERSON_KING/MONK/OTHER split)* | 407 |
| PERSON_OTHER | 398 |
| DATE_ERA | 335 |
| MONUMENT | 324 |
| DYNASTY | 120 |
| CHRONICLE | 117 |
| RELIC | 70 |
| PERSON_MONK | 51 |
| BATTLE_EVENT | 45 |
| ORGANIZATION *(legacy label, not in the current 10-class scheme)* | 29 |

This directly supports your explanation: **BATTLE_EVENT (45), PERSON_MONK (51), and RELIC (70)** are the rarest of the current official classes by a wide margin compared to LOCATION/PERSON_KING (1,600+ each) - consistent with "some classes only occur a couple of times and score much lower." This is training-data *frequency*, not F1 - it explains the mechanism, it isn't a substitute for the actual per-class score.

**What to do next, given the 3-day constraint:** either (a) pull the exact per-class numbers from wherever the interim report's evaluation was originally run/logged, or (b) if you want, I can run a proper held-out evaluation against the trained model now - but that needs a genuine train/test split (using the training data itself to "evaluate" would be circular/invalid) and will take real time, so tell me explicitly if you want me to do that rather than assuming.

---

## Q2 - Knowledge Graph current numbers

**Updated 2026-07-29** - both the static export and Stage 2's data source changed since this question was first answered. I queried both the static file and the live Neo4j database directly, just now:

| | Static JSON snapshot (`neo4j_query_table_data_2026-7-29.json`) | **Live Neo4j (current, right now)** |
|---|---|---|
| Total triples/edges | **1,824** | **1,824** |
| Distinct relation types | **475** | **475** |
| Distinct entities | 942 (distinct names appearing in a triple) | 991 nodes (includes isolated nodes with no edges) |
| `ALSO_KNOWN_AS` edges | 81 | 81 |

Live node breakdown by type: Person 228, King 185, Place 150, Monument 143, Era 122, Chronicle 46, Dynasty 42, Battle 31, Monk 19, Relic 17, Technology 7, Animal 1.

**The two previous findings on this question are both now resolved, as of 2026-07-29:**
1. The static export was regenerated from live Neo4j (hence the near-exact match above - 1,824/475 both sides; the small entity-count difference is simply isolated nodes vs. triple-participants, not staleness).
2. `essay_accuracy_checker.py` (via `kg_fact_retriever.py`) was changed to **query live Neo4j first**, per king, falling back to the static export only when Neo4j is unreachable or has zero facts for that specific king. Previously it read only the static file with no live connection at all - that was the root cause of the ~41% KG-size gap reported in the earlier version of this answer. See `docs/ACCURACY_SCORING_METHODOLOGY.md` §3 for the exact fallback logic.

**Still worth stating explicitly in the thesis:** because the KG keeps growing as Stage 1 continues running, whatever number you report should be timestamped (e.g. "991 nodes / 1,824 edges / 475 relation types, queried live on 2026-07-29") rather than reported as a fixed constant - it will already be different by the time of submission if Stage 1 work continues.

---

## Q3 - Essay Accuracy Checker verified results

**Confirmed, reproducible result** - I just re-ran the standard test essay (`දුටුගැමුණු රජතුමා.txt`, current file content, current code) live:

> *"දුටුගැමුණු රජු ලංකා ඉතිහාසයේ අති වීරෝදාර රජෙකි. ඔහු කාවන්තිස්ස රජුගේ පුත්‍රයා විය. දුටුගැමුණු රජු එළාර රජු පරාජය කර රට එක්සත් කළේය. ඔහු රුවන්වැලිසෑය ඉදිකළේය. දුටුගැමුණු රජු ක්‍රි.පූ. 137 දී මිය ගියේය."*

| Field | Value |
|---|---|
| `essay_subject` | දුටුගැමුණු |
| `all_kings_found` | දුටුගැමුණු, කාවන්තිස්ස රජු, එළාර රජු |
| `accuracy_score` | **100.0** |
| `coverage_ratio` | **0.5** (50%) |
| `confidence_level` | **LOW** |
| `coverage_warning` | False |
| `total_claims` | 7 |
| `total_factual_claims` | 6 |
| `editorial_claims` | 1 |
| `correct_claims` | 3 |
| `incorrect_claims` | 0 |
| `unverifiable_claims` | 3 |
| `kg_gap_claims` | 2 |
| `not_factual_claims` | 1 |
| `kg_facts_used` | 61 |
| `batch_count` | 2 |

Note: `unverifiable_claims` (3) is one more than `kg_gap_claims` (2) - the remaining one is a claim that couldn't be graded due to a transient API/parsing hiccup on this particular run (a known, previously-documented failure mode - see the bug log in `docs/MODULE2_IMPLEMENTATION.md` §14.3/14.4), not a "real" KG gap. **This is worth reporting honestly in the thesis as an observed system behavior**, not hidden - it demonstrates the system degrades gracefully (still produces a valid score) rather than failing outright.

**Other essays tested in this session** (for completeness, since you asked):
- An essay about **පළමුවන විමලධර්මසූරිය රජු** (Vimaladharmasuriya I) - subject correctly identified, but this king has **zero facts** in the current KG snapshot, so the result was `accuracy_score: null`, `confidence_level: INSUFFICIENT_KG`. Good example of the system correctly declining to score rather than guessing.
- An essay about **තෙවැනි වික්‍රමබාහු රජු / පළමුවැනි දප්පුල රජු** - I only have a partial capture of this result (`accuracy_score: 100.0`, `coverage_ratio: 0.5`, `total_claims: 7`, `total_factual_claims: 6`, `editorial_claims: 1`) - the full correct/incorrect breakdown wasn't fully captured in this conversation, so I won't state numbers for it I can't verify. If you want this one as a confirmed data point, I can re-run it now.

**Recommendation for the final report:** decide now how many distinct essays you'll run as your Stage-2 evaluation set, and re-run all of them fresh in one sitting (ideally right before writing up results) rather than mixing numbers from different points in development - the scoring logic changed materially several times during this build.

---

## Q4 - Human evaluators

Recorded as stated: **20 evaluators, non-experts, recruited as a convenience sample** ("random people"). Your reasoning is sound and worth stating explicitly in the thesis methodology: since evaluators are given the same Knowledge-Graph-derived fact sheet the system itself used, domain expertise isn't required to judge historical accuracy - they're checking the essay against provided facts, not against their own historical knowledge.

**Two things you still need to decide/state explicitly** (the thesis examiner will ask):
1. **How many essays does each of the 20 evaluate?** Given 3 days, I'd recommend a small, fixed set of essays (e.g. 5–8) that **every evaluator sees**, rather than splitting 20 people across many different essays 1-to-1. This is important: with only one human judgment per essay, you can't measure how much humans even agree with *each other*, which weakens any claim about how well the system agrees with "human judgment" in general. Multiple independent judgments per essay let you report both system-vs-human-average agreement *and* human-vs-human agreement (a baseline to compare the system against).
2. **State the sampling limitation plainly**: non-expert evaluators are a deliberate, defensible choice given the design (facts are provided), but say so explicitly rather than leaving it for the examiner to notice unprompted.

---

## Q5 - Evaluation instrument

**Recommendation, given the 3-day constraint:** a single **holistic 0–100 accuracy score per essay**, directly comparable to the system's own `accuracy_score`.

**Why this one, not sentence-by-sentence marking:** a full sentence-level correct/incorrect/unverifiable instrument (mirroring the system's own granularity) would give richer data and enable a claim-level agreement analysis, but it multiplies the evaluator's workload by however many sentences are in each essay, across 20 people × several essays - not realistic in 3 days without risking rushed, low-quality responses.

**Concrete instrument to hand evaluators** (one form per essay):
1. The essay text.
2. **The same KG fact sheet the system used** for that essay (you already have this - it's exactly what `kg_fact_retriever.format_facts_for_prompt()` produces, and it's shown in the "Raw KG Facts Used" section of the Streamlit UI, or the `kg_facts_text` field from the API/DB). Giving evaluators the *identical* reference material the system graded against is what makes the comparison fair.
3. One question: *"Based only on the facts provided above, how historically accurate is this essay, as a percentage (0–100)?"*
4. **Optional, only if time genuinely allows:** a short free-text box - "list anything that contradicts the facts provided" - costs almost nothing extra to add, and gives you qualitative examples to quote in the discussion section even if you don't analyze it quantitatively.

Keep the instrument to literally one number per essay if you're tight on the 3 days - a longer instrument you don't finish is worse than a short one you complete cleanly.

---

## Q6 - Agreement metric

**Recommendation**, since both sides of the comparison are continuous 0–100 scores (system `accuracy_score` vs. each evaluator's 0–100 rating):

**Primary:** **Pearson correlation coefficient (r)** between the system's score and the *mean* human score per essay. This is the standard way to report "does the automated score track human judgment" for two continuous variables.

**Also report, as robustness checks:**
- **Spearman's rank correlation (ρ)** alongside Pearson - with a small number of essays (likely true here given 3 days), Spearman is less sensitive to outliers/non-normality and is worth reporting side-by-side rather than instead of Pearson.
- **Mean Absolute Error (MAE)** between the system score and the mean human score, e.g. "the system's score differed from the human average by 8.2 points on average." This is often more intuitive for readers than a correlation coefficient alone, and costs nothing extra to compute.

**Do not use Cohen's Kappa** for this comparison - Kappa is for categorical agreement (e.g. two raters each choosing CORRECT/INCORRECT/UNVERIFIABLE for the same items), not for two continuous 0–100 scores. It would only become relevant if you also collect the optional sentence-level marking from Q5 and want to compare the system's per-claim verdict against a human's per-claim verdict directly - in that specific sub-analysis, Kappa (or simple percentage agreement, easier to compute and explain under time pressure) would be the right tool.

**Important caveat to state in the thesis:** correlation coefficients are unstable and easily misleading with very few data points. If you end up with fewer than ~10 essays in the comparison, say so explicitly and treat the correlation figure as indicative rather than a strong statistical claim.

---

## Q7 - Knowledge bases used

**Confirmed, with two corrections to your numbers** (I counted these directly rather than trusting the earlier estimate):

| Knowledge base | Your figure | **Verified figure** |
|---|---|---|
| `data/sri_lankan_kings_all_names.txt` | 105 king/queen names | **105 - confirmed, matches.** |
| `kg_aliases.py` (`CANONICAL_ALIASES`) | 63 canonical entries, 258 aliases | **64 canonical entries, 274 total aliases** - recount needed here, the figures had drifted. |
| `data/neo4j_query_table_data_2026-7-29.json` | 917 triples, 178 relation types | **1,824 triples, 475 relation types as of 2026-07-29** - the file was regenerated since that figure was first recorded, and now matches live Neo4j exactly (see [Q2](#q2--knowledge-graph-current-numbers)). Report the export date alongside whichever number you use, since it will drift again as Stage 1 keeps running. |

**One more resource not in your list, worth deciding whether to include:** the **trained XLM-RoBERTa NER model** (`models/xlmr_ner/`) itself. It's not a textual knowledge base like the other three, but it is the fourth distinct knowledge *asset* the system depends on - if your thesis's "knowledge bases used" section is scoped to *data sources* specifically, leave it out; if it's scoped to *all knowledge resources the system relies on*, it belongs in the list.

No other data/knowledge files exist in the project beyond these.

---

## Q8 - Scoring formula

**Confirmed - this is exactly what's in the code right now** (`essay_accuracy_checker.py`, `aggregate_results()`), no changes since our last conversation:

```
Factual Precision (accuracy_score) = correct / (correct + incorrect)
    Range 0–100. None if (correct + incorrect) == 0.

KG Coverage Ratio (coverage_ratio) = (correct + incorrect) / total_factual_claims
    EDITORIAL claims are excluded from this denominator.

Confidence Level:
    HIGH             - (correct + incorrect) >= 5
    LOW              - (correct + incorrect) is 1–4
    INSUFFICIENT_KG  - (correct + incorrect) == 0
```

**One detail your draft didn't include, worth adding for completeness:**
```
coverage_warning = True if coverage_ratio < 0.30
```
This is a separate flag (`LOW_COVERAGE_THRESHOLD = 0.30` in code) that fires independently of the confidence level - it specifically warns when fewer than 30% of an essay's factual claims could be checked at all, regardless of how many that ends up being in absolute terms.

Exact constant names in code, if you want to cite them directly: `MIN_VERIFIABLE_FOR_HIGH_CONFIDENCE = 5`, `LOW_COVERAGE_THRESHOLD = 0.30`.
