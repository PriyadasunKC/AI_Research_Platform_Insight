# Essay Historical Accuracy Scoring — Methodology

**Module 2, 214161L — Stage 2 (Essay Accuracy Checker)**

This document explains, end to end, how a raw Sinhala essay becomes a
numeric historical-accuracy score: how the subject king is identified, how
the specific historical facts used to check the essay are chosen, how each
individual claim in the essay is judged, and how those per-claim judgements
are combined into the final score. It is written to be read on its own (no
need to read the source code alongside it), and every rule/formula below is
taken directly from the current implementation in `essay_accuracy_checker.py`,
`kg_fact_retriever.py`, and `king_name_db.py` — not a simplified summary.

---

## 1. Pipeline overview

```
Raw essay text
   │
   ▼
① Identify the essay's subject (which king/kings it is about)
   │
   ▼
② Retrieve every Knowledge-Graph fact known about that king (and any
   other kings mentioned), including facts stored under alternate names
   │
   ▼
③ Split the essay into sentences, grouped into batches of ≤6
   │
   ▼
④ For each batch, ask Claude to:
     a. classify every claim as FACTUAL or EDITORIAL
     b. grade every FACTUAL claim as CORRECT / INCORRECT / UNVERIFIABLE
        against ONLY the KG facts retrieved in step ②
     c. write a short explanation, and (for INCORRECT claims only) a
        corrective teacher_feedback note
   │
   ▼
⑤ Aggregate every claim across all batches into:
     - Factual Precision (the headline accuracy score, 0–100)
     - KG Coverage Ratio (how much of the essay the KG could actually judge)
     - Confidence Level (how much to trust the score, given how many
       claims were actually verifiable)
```

Source: `check_essay_accuracy()` in `essay_accuracy_checker.py` (lines
700–796) is the orchestrating function that runs steps ①–⑤ in order.

---

## 2. Step ① — Identifying which king(s) the essay is about

Function: `identify_essay_subject()` (`essay_accuracy_checker.py:102-153`).

The system does **not** ask the user to specify who the essay is about — it
detects it automatically, because the essay text is the only input the API
requires (see the external API's single `essay_text` field).

1. **NER pass on the first 5 sentences.** The trained NER model
   (`ner_pipeline.run_ner`) tags `PERSON_KING` / `PERSON_MONK` entities.
   Only the first 5 sentences are scanned here — essays conventionally
   introduce their subject early, and this keeps the identification step
   fast without needing to NER-tag the whole essay.
2. **Each tagged name is resolved to a canonical king name** via
   `king_name_db.find_king_in_text()`, which looks the surface form up in a
   master name index built from three merged sources (see §2.1 below).
3. **A second, independent scan runs over the *entire* essay text**
   (`king_name_db.find_king_in_text(essay_text)`), catching any king name
   the NER model missed (NER recall is not perfect — this is a deliberate
   safety net, not redundant work).
4. **Frequency + earliest-position ranking.** Every canonical name found is
   counted. The king mentioned **most often** is ranked first; ties are
   broken by **whichever appears earliest** in the essay. This produces a
   `primary_king` and a full list `all_kings` (every king mentioned, most
   of whom may only get a couple of claims graded).
5. **KG-fact sanity check.** The top-ranked candidate is only accepted as
   `primary_king` if it actually has ≥1 fact in the Knowledge Graph
   (`kg_fact_retriever.get_facts_for_king(candidate)` returns something).
   If not, the next most-frequent candidate is tried instead. This stops
   an essay's introductory mention of an unrelated king (with zero KG
   coverage) from being picked as the subject over the king the essay is
   actually mostly about.

If no king is recognised at all, the pipeline returns immediately with an
empty result (`accuracy_score = None`, zero claims) rather than guessing.

### 2.1 The king name index (how "which king is this text about" is even possible)

Built once by `king_name_db.build_king_index()` and cached, merging:

| Source | What it contributes |
|---|---|
| `data/sri_lankan_kings_all_names.txt` | 105 authoritative king names, including kings not yet in the KG at all |
| `kg_aliases.CANONICAL_ALIASES` | Same-person alias groups also used when *writing* the KG (Stage 1), minus non-person entries (locations, monuments, dynasties, chronicles — excluded by an explicit exclusion set, since a mention of "අනුරාධපුරය" is not a king) |
| `ALSO_KNOWN_AS` edges inside the static KG export | Alternate names/titles discovered during Stage 1 extraction itself, transitively clustered (union-find) so a chain of 3+ linked aliases all resolve to one canonical name |

**Matching against essay text** (`find_king_in_text()`) is two-pass:
- **Pass 1 — exact substring match**, longest names checked first (so
  "විජයබාහු" isn't shadowed by a shorter unrelated hit inside it), with a
  **word-boundary check**: a short name is only accepted as a match if it
  isn't glued to more Sinhala-script text on either side (an inflected form
  like "...ගේ" is still allowed — only an unrelated bordering word is
  rejected). This exists because, e.g., the alias "සිංහ" (short for king
  සිංහබාහු) is a literal substring of "සිංහල" ("Sinhala") — without the
  boundary check, every mention of the word "Sinhala" in an essay would
  falsely register as a mention of that king.
- **Pass 2 — fuzzy match** (only if Pass 1 finds nothing at all): each
  Sinhala word-like token in the text is compared against every name in
  the index using `difflib.SequenceMatcher`; a match is accepted only above
  a **0.85 similarity threshold**. This is the tolerance for minor spelling
  variation, not a general-purpose fuzzy search.

---

## 3. Step ② — Choosing which historical facts to check against

Function: `kg_fact_retriever.get_facts_for_king()`
(`kg_fact_retriever.py:83-99`), called once per king found in the essay
(`check_essay_accuracy`, lines 740-747).

This is the answer to *"how is a historical fact chosen"* — it is not
Claude's own historical knowledge at any point. The system prompt explicitly
instructs: **"Your ONLY source of historical truth is the provided KG
facts. Do NOT use your own historical knowledge to confirm or contradict any
claim."** (`build_claude_system_prompt`, line 199-200).

As of 2026-07-29, facts are queried from the **live Neo4j database first**
(`kg_store.get_facts_for_entity_cluster`), per king. The static export
(`data/neo4j_query_table_data_2026-7-29.json`) is used only as a fallback,
per king, in exactly two cases: Neo4j is unreachable, or Neo4j is reachable
but returns zero facts for that specific king (which can happen if the
static snapshot happens to cover a king not yet re-extracted into the live
graph). A non-empty live result is used as-is — a single run never mixes
facts from both sources for the same king. See `get_facts_for_king()` in
`kg_fact_retriever.py` for the exact logic.

1. **Name-set resolution first.** Before searching the KG, every name that
   could refer to this king is collected
   (`get_all_kg_names_for_king()`): the canonical name itself, every
   `kg_aliases` alias, and the transitive closure of `ALSO_KNOWN_AS` edges
   in the KG data (both directions, repeated until no new name is added).
   This matters because the KG itself may record facts under a title or
   alternate name (e.g. a chronicle name) that never appears as the
   "primary" name — without this step those facts would be invisible to
   the essay checker even though they genuinely describe the same person.
2. **Every triple where that king's name-set appears as subject OR
   object** is pulled in — not just triples where the king is the subject.
   This catches facts like "X was defeated **by** [this king]" as well as
   "[this king] defeated X".
3. **`ALSO_KNOWN_AS` triples are deliberately included** in the returned
   facts (not just used internally for name resolution) — an essay stating
   a king's alternate name or title as a fact ("he was also known as...")
   is itself a checkable, gradable claim, and the KG can confirm or refute
   it.
4. **Facts for every king mentioned in the essay are pooled together**
   (`check_essay_accuracy`, lines 740-747), de-duplicated by
   `(subject, relation, object)`, before being handed to Claude — so claims
   about secondary kings mentioned alongside the primary one can also be
   graded, not just claims about the primary king.
5. **Cap at 80 facts per prompt.** If a king's total fact count exceeds 80
   (`_MAX_FACTS`), the list is prioritised — `BUILT`, `DEFEATED`, `RULED`,
   `UNITED`, `FATHER_OF`, `MOTHER_OF`, `SON_OF`, `BROTHER_OF`, `MARRIED`,
   `WIFE_OF`, `BORN_IN`, `DIED_AT`, `ALSO_KNOWN_AS` first (the relation
   types judged most likely to appear as essay claims), then all other
   relation types, truncated to 80. This exists purely to keep the prompt
   within a reasonable size for a small number of unusually well-documented
   kings; it does not affect the vast majority of kings, whose fact count
   is well under 80.

The resulting fact list is formatted as a numbered Sinhala list (`1. X — RELATION — Y (කාලය: period)`) — this exact numbered list is what Claude cites in every `matched_kg_fact` field, so every verdict is traceable back to one specific KG line.

---

## 4. Step ④ — How each claim is judged

Function: `build_claude_system_prompt()` (`essay_accuracy_checker.py:177-315`), executed per batch by `call_claude_batch()`.

### 4.1 Classification first: FACTUAL vs EDITORIAL

Every sentence/claim is classified **before** any KG comparison happens.
This two-stage design exists specifically to stop essay-writing style
(character studies, value judgments — normal and expected in a history
essay) from being counted as "the KG failed to cover this claim":

- **EDITORIAL** — value judgments ("ශ්‍රේෂ්ඨතම රජ" / "greatest king"),
  character assessments, statements of historical significance, or
  emotional/narrative description — anything **no** knowledge graph could
  ever verify or refute in principle. Always resolves to
  `verdict = UNVERIFIABLE`, `unverifiable_reason = NOT_FACTUAL`, and is
  never compared against KG facts at all.
- **FACTUAL** — an event, date/time period, relationship (father, son,
  wife, ruler-of), a construction/monument, an alternate name/title — any
  proposition a *sufficiently complete* KG could in principle confirm or
  refute, whether or not this particular KG actually happens to cover it
  yet.

### 4.2 Grading FACTUAL claims

Only FACTUAL claims proceed to grading, against the KG fact list from §3
only:

| Verdict | Rule |
|---|---|
| **CORRECT** | The claim's *central assertion* matches a KG fact. For compound sentences, only the main verb/event needs to match — a secondary clause (motive, method, a superlative) that the KG doesn't cover is noted in the explanation but does **not** downgrade the verdict. Claude is explicitly instructed to recognise Sinhala surface-form equivalence (e.g. "රජ කළේය" / "රාජ්‍ය කළේ" / "සිංහල රටේ රජු විය" all count as matching a KG `RULED` fact) rather than requiring exact wording. |
| **INCORRECT** | Only when a KG fact is *directly contradicted* — wrong date, wrong relationship, or wrong person credited with an action. An unconfirmed detail (something merely absent from the KG) is explicitly **never** grounds for INCORRECT — that is UNVERIFIABLE instead. |
| **UNVERIFIABLE** (`unverifiable_reason = NOT_IN_KG`) | The claim is FACTUAL, but no retrieved KG fact confirms or contradicts it — it is simply outside what this KG currently records. This is a KG *coverage gap*, not a wrong claim, and is scored separately from INCORRECT (see §5). |

Every claim's `explanation` field must follow one of four fixed templates
(cites the exact KG fact number for CORRECT/INCORRECT verdicts), and for
every claim graded INCORRECT, a separate `teacher_feedback` field is
generated: 2-3 sentences of Sinhala corrective feedback in a constructive
"history teacher" voice — what the student wrote, why it contradicts the
KG, and the correct fact — used only for genuinely wrong claims.

### 4.3 Defensive normalization after Claude responds

`_normalize_claim_fields()` (`essay_accuracy_checker.py:429-473`)
re-enforces the prompt's own rules **in code** rather than trusting the
model's structured output to always be internally consistent — e.g. it was
observed in practice that Claude's `verdict` field occasionally disagreed
with its own explanation text. This step guarantees, regardless of what
Claude actually returned:
- `claim_type == EDITORIAL` always forces `verdict = UNVERIFIABLE` and
  `unverifiable_reason = NOT_FACTUAL`.
- `unverifiable_reason` is only ever set when `verdict == UNVERIFIABLE`.
- `teacher_feedback` is only ever kept when `verdict == INCORRECT`.

### 4.4 Failure handling (never silently drop a claim)

- **API error** (network/auth/etc.) → every sentence in that batch becomes
  `UNVERIFIABLE` with `unverifiable_reason = None` (a system failure is
  neither a KG gap nor an editorial finding, so it is excluded from both
  of those specific counters — see §5 — while still counting toward
  `total_claims`).
- **Unparseable JSON response** → one retry; if it still fails, the whole
  batch falls back to the same UNVERIFIABLE treatment.
- **Response cut off mid-generation** (hit the model's token budget before
  finishing every claim in the batch) → whichever claims *did* finish
  generating are salvaged and kept as real graded claims
  (`_recover_truncated_claims`); only the genuinely-missing tail sentences
  are padded as UNVERIFIABLE. See `feedback_llm_response_recovery.md` for
  the incident this was built to fix, and the 2026-07-29 token-budget
  increase (2048→4096) that reduced how often this path is hit at all.

---

## 5. Step ⑤ — How the final score is calculated

Function: `aggregate_results()` (`essay_accuracy_checker.py:595-696`).
This is the exact, current scoring methodology — reproduced from the
function's own methodology comment block, which is the canonical source.

**Only FACTUAL claims participate in scoring.** EDITORIAL claims are shown
to the user in the results UI but are excluded from every score
denominator below — this is what stops normal essay-writing style from
depressing the accuracy score.

```
verifiable          = correct_claims + incorrect_claims

Factual Precision   = correct_claims / verifiable            (× 100 for display)
                       None if verifiable == 0 (no claims the KG could judge either way)

KG Coverage Ratio    = verifiable / total_factual_claims
                       0.0 if total_factual_claims == 0
                       coverage_warning = True if this ratio < 0.30

Confidence Level:
    HIGH             if verifiable >= 5
    LOW              if 1 <= verifiable < 5
    INSUFFICIENT_KG  if verifiable == 0
```

- **Factual Precision** answers *"of the claims the KG could actually
  check, how many were right?"* — this is the headline "historical
  accuracy" percentage.
- **KG Coverage Ratio** answers a different question: *"what fraction of
  the essay's factual claims could this KG check at all?"* A low coverage
  ratio (< 30%) does **not** mean the essay is inaccurate — it means the
  KG is too sparse for this particular king/topic to say much either way,
  and the UI surfaces a coverage warning so the score isn't
  over-interpreted.
- **Confidence Level** exists because Factual Precision is a plain
  proportion, and a proportion computed from very few observations is
  unreliable (e.g. 1/1 correct reads as "100% accurate" but is not
  informative). The threshold of **5** verifiable claims for HIGH
  confidence follows standard minimum-sample-size practice for
  precision-style NLP evaluation metrics (Manning & Schütze, 1999).

### Worked example (real run, not illustrative)

From the standard end-to-end test essay (`දුටුගැමුණු රජතුමා.txt`, 5
sentences): 5 FACTUAL claims were identified (1 sentence was classified
EDITORIAL and excluded), of which 3 were CORRECT and 0 were INCORRECT, with
the remaining being UNVERIFIABLE/NOT_IN_KG.

```
verifiable        = 3 + 0 = 3
Factual Precision = 3 / 3 = 100%          (of what the KG could judge, all correct)
KG Coverage Ratio = 3 / 5 = 0.60           (60% of factual claims were checkable)
Confidence Level  = LOW                    (verifiable = 3, below the 5-claim HIGH threshold)
```

This is a realistic outcome for a short essay: a perfect precision score
paired with LOW confidence correctly signals "what we could check was all
correct, but we only checked 3 claims — don't over-trust this as a
complete accuracy judgement." A longer or more fact-dense essay would be
expected to cross the 5-claim threshold into HIGH confidence.

---

## 6. What this methodology deliberately does NOT do

For thesis-methodology transparency:

- **It never uses Claude's own historical knowledge** to grade a claim —
  only the retrieved KG facts. A true historical claim that happens to be
  entirely absent from the current KG is graded UNVERIFIABLE, not CORRECT.
- **It does not penalize claims the KG cannot check.** UNVERIFIABLE claims
  affect the *coverage ratio*, never the *accuracy score* itself.
- **It does not treat "unconfirmed" as "wrong."** INCORRECT is reserved
  strictly for direct contradiction of a specific KG fact.
- **The accuracy score is about the KG's ability to verify claims, not an
  absolute measure of historical truth** — the KG's own completeness is a
  separate, documented limitation (see `THESIS_METHODOLOGY_QA.md` for the
  live-vs-static KG size discrepancy and current entity/relation counts).
