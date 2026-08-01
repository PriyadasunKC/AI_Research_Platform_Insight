# Module 2 - Sinhala Historical Knowledge Graph & Essay Accuracy System
### Full Implementation Documentation

**Course:** IN4911 - Comprehensive Group Project, University of Moratuwa
**Module:** Module 2, 214161L
**Project context:** This is one of **three modules** in a larger group project. Module 3 is a separate system built by a teammate that consumes this module's output over a REST API (see [§9](#9-external-rest-api-for-other-modules)).

---

## Table of Contents
1. [What this module does](#1-what-this-module-does)
2. [High-level architecture](#2-high-level-architecture)
3. [Technology stack](#3-technology-stack)
4. [Project structure](#4-project-structure)
5. [Stage 1 - Knowledge Graph extraction pipeline](#5-stage-1--knowledge-graph-extraction-pipeline)
6. [Stage 2 - Essay Accuracy Checker](#6-stage-2--essay-accuracy-checker)
7. [Claim classification and scoring methodology](#7-claim-classification-and-scoring-methodology)
8. [Teacher-style corrective feedback](#8-teacher-style-corrective-feedback)
9. [External REST API (for other modules)](#9-external-rest-api-for-other-modules)
10. [Data persistence (MongoDB)](#10-data-persistence-mongodb)
11. [Data sources](#11-data-sources)
12. [How to run everything](#12-how-to-run-everything)
13. [Testing / verification](#13-testing--verification)
14. [Bugs found and fixed during development](#14-bugs-found-and-fixed-during-development)
15. [Known limitations and future work](#15-known-limitations-and-future-work)

---

## 1. What this module does

In plain terms: a student writes a **historical essay in Sinhala** about a Sri Lankan king. This module:

1. **Reads the essay** and figures out which king(s) it's about.
2. **Looks up everything the system already knows** about that king from a Knowledge Graph (a structured database of historical facts - dates, relationships, events - built up separately by this same module).
3. **Sends the essay and the known facts to Claude (an AI model)**, which checks every claim in the essay one by one against those facts.
4. **Produces a score** (how factually accurate the essay is) and, for anything that's factually wrong, a **corrective explanation written like a history teacher would give it** - what the student said, why it's wrong, and what the correct fact is.
5. **Saves everything** to a database and makes it available both through a web page and through an API that other modules can call programmatically.

The system is deliberately built so the AI **never relies on its own general knowledge** to judge the essay - only on facts that are actually present in the Knowledge Graph. If a claim isn't covered by the graph, it's marked "unverifiable," never silently assumed wrong.

---

## 2. High-level architecture

There are two distinct stages, built at different times, that share the same Knowledge Graph:

```
STAGE 1 - Building the Knowledge Graph (happens continuously, independent of Stage 2)

  Sinhala sentence
       │
       ▼
  XLM-RoBERTa NER model      →  finds named things in the sentence
       │                         (kings, monks, places, monuments, dates, ...)
       ▼
  LLM (Claude/GPT/Gemini/DeepSeek)  →  reads the sentence + NER tags,
       │                                 extracts (subject, relation, object) triples
       ▼
  Neo4j Knowledge Graph      →  the triple gets permanently stored as a fact
                                  e.g. (දුටුගැමුණු) -[BUILT]→ (රුවන්වැලිසෑය)


STAGE 2 - Checking a student essay against that Knowledge Graph

  Student essay (Sinhala, free text)
       │
       ▼
  Identify which king(s) the essay is about
       │        (NER on first few sentences + text-scanning against a
       │         master king-name index, incl. spelling variants/titles)
       ▼
  Pull every known fact about that king from the Knowledge Graph
       │        (including facts stored under alternate names/titles)
       ▼
  Split the essay into small batches of sentences
       │
       ▼
  Claude grades each batch: is every claim CORRECT / INCORRECT / UNVERIFIABLE
       │        against ONLY the facts just retrieved - plus, for anything
       │        editorial/opinion rather than factual, classified separately
       │        so it doesn't count against the score
       ▼
  Aggregate into a final score + a list of graded claims
       │        (with a corrective explanation for anything INCORRECT)
       ▼
  Shown in a Streamlit web page  AND/OR  returned via a REST API
       │
       ▼
  Saved to MongoDB (who submitted it, the essay, the full result)
```

**Why two stages instead of one?** Stage 1 is slow, ongoing work (it's how the Knowledge Graph gets built up in the first place, sentence by sentence, over the whole project). Stage 2 is what actually grades a finished essay, and it can only be as good as however much of the Knowledge Graph Stage 1 has built so far. A king Stage 1 hasn't covered yet will correctly show up in Stage 2 as "insufficient KG data," not a wrong score.

---

## 3. Technology stack

| Purpose | Technology |
|---|---|
| Named Entity Recognition (finding king/place/date names in Sinhala text) | XLM-RoBERTa, fine-tuned, loaded via HuggingFace `transformers` |
| Extracting facts from sentences / grading essay claims | Claude (Anthropic) - model `claude-sonnet-4-6`. Stage 1 can also use OpenAI/DeepSeek/Gemini; Stage 2 (essay grading) always uses Claude. |
| Knowledge Graph storage | Neo4j (graph database) |
| Run history / essay-check results storage | MongoDB |
| Web UI | Streamlit |
| External API (for Module 3) | FastAPI + Uvicorn |
| Interactive graph visualization | PyVis + NetworkX |
| Language | Python 3.11 |

---

## 4. Project structure

```
sinhala_kg_pipeline/
├── app.py                          # Streamlit entry point - sidebar navigation
├── pipeline.py                     # Stage 1 CLI entry point
├── api_server.py                   # Stage 2 external REST API (FastAPI)
│
├── ner_pipeline.py                  ┐
├── normalizer.py                    │  Stage 1 - KG extraction
├── relation_extractor.py            │  (see §5)
├── kg_aliases.py                    │
├── kg_store.py                      ┘
│
├── king_name_db.py                  ┐
├── kg_fact_retriever.py             │  Stage 2 - Essay Accuracy Checker
├── essay_accuracy_checker.py        │  (see §6)
│
├── mongo_store.py                   # Shared: MongoDB persistence for both stages
│
├── pages/
│   ├── extract.py                  # Stage 1 UI - Extract & Save
│   ├── kg_viewer.py                # Stage 1 UI - Interactive Graph
│   ├── kg_stats.py                 # Stage 1 UI - Statistics
│   ├── history.py                  # Stage 1 UI - Run History
│   └── essay_checker.py            # Stage 2 UI - Essay Accuracy Checker (see §6.6)
│
├── data/
│   ├── neo4j_query_table_data_2026-7-29.json   # Static KG export used by Stage 2
│   └── sri_lankan_kings_all_names.txt          # Authoritative king name list
│
├── docs/
│   ├── MODULE2_IMPLEMENTATION.md   # This file
│   ├── essay_claim_classification_report.html  # Design-rationale deep dive (see §7)
│   ├── postman_collection.json     # Ready-to-import Postman collection for the API
│   └── build_postman_body.py       # Helper: .txt file → JSON body for testing
│
├── models/xlmr_ner/                 # Trained NER model files
├── requirements.txt
├── .env / .env.example
└── දුටුගැමුණු රජතුමා.txt            # Standard test essay used throughout development
```

---

## 5. Stage 1 - Knowledge Graph extraction pipeline

*(Built before Stage 2; documented here briefly for completeness - this module's main new work this phase was Stage 2.)*

### 5.1 `ner_pipeline.py`
Loads the trained XLM-RoBERTa model from `models/xlmr_ner/` and runs Named Entity Recognition on a Sinhala sentence. Recognises 10 entity classes: `PERSON_KING`, `PERSON_MONK`, `PERSON_OTHER`, `LOCATION`, `MONUMENT`, `DYNASTY`, `BATTLE_EVENT`, `DATE_ERA`, `CHRONICLE`, `RELIC`. Returns a list of `NERTag(entity, label, start, end)`.

### 5.2 `relation_extractor.py`

Takes one sentence plus its NER tags and asks an LLM to extract `(subject, relation, object, period)` triples - these become the KG's edges once saved. This is where most of Stage 1's engineering effort went; four parts worth understanding:

**a) Provider abstraction.** `_call_llm()` supports four interchangeable providers - OpenAI, DeepSeek, Gemini, Claude - chosen via `.env` (`LLM_PROVIDER` / `LLM_MODEL`). Claude uses the Anthropic SDK; the other three all speak the OpenAI-compatible chat-completions format, so one code path serves all three. The system prompt is identical regardless of provider.

**b) The system prompt.** Not a generic "extract triples" instruction - a long, hand-built prompt doing several distinct jobs:
- **Primary directive**: the raw sentence is ground truth; NER tags are only candidates, and the model is told to use the correct entity from the raw text if a tag looks wrong.
- **A Sinhala pattern-to-relation dictionary**, organized by theme (RULED, BUILT, FAMILY, WAR, MOVEMENT, RELIGION, CHRONICLE, DYNASTY, SUCCESSION) - e.g. under FAMILY, *"ගේ පුත්"* → `SON_OF`; under WAR, *"පරාජය කළ"* → `DEFEATED`. This is what lets the model recognize a relation regardless of which of many possible Sinhala phrasings expresses it.
- **Entity extraction rules** - strip grammatical case endings (`"ශ්‍රී ලංකාවට"` → `"ශ්‍රී ලංකාව"`), never invent descriptive names.
- **An ordinal-prefix rule** - `"I වන කාශ්‍යප"` must be extracted *with* the ordinal, critical for distinguishing same-named kings (Kashyapa I vs II).
- **Direction rules with passive-voice rewriting** - Sinhala often states facts passively; the prompt requires rewriting to active voice (subject = actor, object = receiver), with worked examples.
- **A reference list of ~210 known relation types** already in the KG, to bias the model toward reusing existing names - while still allowing a new one if nothing fits.
- **An entity disambiguation rule** - if the same bare name (e.g. "මානාභරණ") is used in the source text for two different people distinguished only by an epithet ("රුහුණේ", "දෙවන", "දක්ඛිණ දේශයේ"), the epithet must be kept as part of the entity name, not stripped down to the bare name - otherwise two different historical people silently collapse into one graph node.
- **A no-abstract-nodes rule** - a single actor's single action must be extracted as a direct `subject → relation → object` triple, never routed through an intermediate event-noun node (e.g. not `king → PERFORMED → construction-event → INVOLVED → monument`).
- **Relation naming rules** - folded action+target relations for implied/generic objects (e.g. *"හින්දු ධර්මය වැලඳ ගැනීමට උනන්දු කරවීය"* → `ENCOURAGED_TO_ADOPT_HINDU_DHAMMA` with the *person* as object, not a placeholder relation pointing at "හින්දු ධර්මය"), a canonical-verb preference table to stop synonym drift (e.g. always `RULED`, never `GOVERNED`/`ADMINISTERED`), and a deduplication-awareness note for sources that restate the same fact in both a summary list and later narrative prose.
- **A speculation / disputed-facts / contested-dates rule** - the single largest behavioral gap this rewrite closed. Sinhala chronicle text routinely flags claims as legendary or uncertain ("ජනප්‍රවාදවලට අනුව", "විය හැක", "විවිධ මත පවතී"); previously these were extracted as plain, unqualified facts. Now such claims are either skipped entirely (no queryable value) or attributed to their named source via a `STATES` triple - and where two named chronicles give conflicting dates/details for the same fact, both are extracted as separate source-attributed `STATES` triples rather than one being silently discarded.
- **A chronicle-attribution rule** - when the source text names a specific chronicle or scholarly work as the source of a notable/contested claim, that source is extracted as its own subject/object (`MENTIONS`, `STATES`, `IS_PRIMARY_SOURCE_FOR`, `IS_KEY_SOURCE_FOR`) instead of being dropped.
- **26 few-shot examples** (originally 20; 6 added for this rewrite) covering the full range: basic RULED+period, passive BUILT, multi-relation sentences, alias extraction, succession chains, dynasty membership, folded relations, disputed-date dual-`STATES`, speculative-claim skip, same-name disambiguation, and chronicle attribution.

**c) Response parsing.** `_parse_response()` strips markdown fences and, if the JSON array got cut off by a token-limit truncation, `_recover_truncated()` closes it and salvages whatever parsed - the same class of fix later ported to Stage 2's `essay_accuracy_checker.py` (see §14.3).

**d) Validation** (`_validate_one_triple`, per triple):
- `_resolve_ner_entity()` matches the LLM's returned subject/object string back to an actual NER-tagged entity via five fallback strategies in order: exact match → entity plus one grammatical case suffix → NER entity is a longer form with a dropped honorific → both resolve to the same canonical form → the real entity sits at the end of a longer string the LLM prepended a *relational clause* to (e.g. "කාවන්තිස්සගේ පුත් සද්ධාතිස්ස" → "සද්ධාතිස්ස"). This last fallback is now gated on the stripped prefix actually containing a relational marker (ගේ/ගෙන්/විසින්/යටතේ), so it can't misfire on a plain disambiguating epithet like "රුහුණේ" in "රුහුණේ මානාභරණ" - without that gate, the disambiguation rule above would be silently undone by the validator. If nothing matches but the string still looks like a real name, it's accepted anyway (the "NER missed it, trust the raw text" fallback the prompt itself instructs) - this is also how a disambiguated compound name that isn't in the NER tag set survives unchanged.
- Entities are normalized twice - `normalize_entity()` (spelling/morphology) then `kg_aliases.resolve_to_canonical()` (cross-source aliasing) - so two sentences naming the same king slightly differently still produce the same graph node.
- Any triple where subject or object resolves to a `DATE_ERA` entity is rejected - dates are never nodes, only the `period` field.
- The relation string is sanitized to `UPPER_SNAKE_CASE`.

The output is a list of validated triples, handed directly to `kg_store.save_pipeline_result()` to write into Neo4j.

### 5.3 `normalizer.py`
A dictionary-based lookup for **morphological** normalization - collapsing inflected/misspelled surface forms of the *same* name to one canonical spelling (e.g. "දුටු ගැමුණු" → "දුටුගැමුණු").

### 5.4 `kg_aliases.py`
A separate dictionary for **cross-source aliasing** - genuinely *different* names used for the same person/place across different historical texts (e.g. "වළගම්බා" is also known as "වට්ටගාමිණී අභය"). Used by the storage layer before every write, and read (but not modified) by Stage 2.

### 5.5 `kg_store.py`
All Neo4j read/write operations live here - this is the only file that talks to the graph database directly. Handles entity upsert (merge-by-name-or-alias), relation upsert (with duplicate detection), and various read queries used by the Streamlit KG viewer/stats pages.

### 5.6 `pipeline.py`
CLI entry point tying NER → relation extraction → KG save together, for processing sentences outside the Streamlit UI (e.g. batch-processing a text file of sentences).

---

## 6. Stage 2 - Essay Accuracy Checker

This is the module's main deliverable this phase. Four files implement the core logic, plus a Streamlit page and API server for two different ways to use it.

### 6.1 `king_name_db.py` - King Name Knowledge Base

Builds a master lookup so the system can recognise a king mentioned in an essay under **any** spelling, title, or alternate name it knows about.

- **`KING_NAME_DB`** - a list of ~105 canonical king names, parsed at import time from `data/sri_lankan_kings_all_names.txt` (the authoritative list, which includes kings not yet covered by the Knowledge Graph).
- **`build_king_index() -> dict[str, str]`** - merges three sources into one `{name_variant: canonical_name}` lookup:
  1. Every name in `KING_NAME_DB`.
  2. Every alias in `kg_aliases.CANONICAL_ALIASES` (excluding location/monument/dynasty/chronicle entries - those aren't people, and were previously leaking into "kings found" results).
  3. Every entity linked via `ALSO_KNOWN_AS` edges in the Knowledge Graph JSON, transitively clustered (Union-Find), so a chain of aliases all resolve to one representative name.
- **`normalize_sinhala(text)`** - strips trailing royal/monastic titles (රජු, රාජ, හිමි, රැජින, etc.) for comparison purposes.
- **`find_king_in_text(text) -> list[dict]`** - scans a block of text for any known king name.
  - **Pass 1 (exact):** substring match against every name in the index, longest names first, **with a word-boundary check** (`_has_clean_boundary`) - critical, see [§14.1](#141-word-boundary-bug-in-name-matching).
  - **Pass 2 (fuzzy):** only runs if Pass 1 finds nothing at all; uses `difflib.SequenceMatcher` with a 0.85 similarity threshold to catch minor misspellings.

### 6.2 `kg_fact_retriever.py` - KG Fact Retrieval

**As of 2026-07-29, queries the live Neo4j database first**, via `kg_store.get_facts_for_entity_cluster()` / `kg_store.get_also_known_as_edges()`. The static file `data/neo4j_query_table_data_2026-7-29.json` is used only as a per-king fallback, when Neo4j is unreachable or genuinely returns zero facts for that specific king. Previously this file read exclusively from the static export with no live connection at all - that was changed because the live graph is materially larger and more current (see §11 below for the size discrepancy this used to cause).

- **`load_kg()`** - loads and caches the static-fallback JSON (a flat list of `{subject, relation, object, period, source}` triples - currently ~917 triples, ~178 relation types; only read when the live query path is unavailable).
- **`get_all_kg_names_for_king(canonical_name) -> set[str]`** - the static-export version of name-set resolution (fallback path only): starting from one canonical name, finds every other name that refers to the same king via registered aliases (`kg_aliases.get_aliases_for`) plus a transitive closure over `ALSO_KNOWN_AS` edges in the static file, in both directions, repeated until no new names are found. The live path does the equivalent transitive closure directly in Cypher (`kg_store.get_facts_for_entity_cluster`, a single query using variable-length `ALSO_KNOWN_AS*0..10` traversal).
- **`get_facts_for_king(canonical_name) -> list[dict]`** - tries the live cluster query first; falls back to `_facts_from_static_export()` only if live is unreachable (`None`) or returns nothing for this king. **Includes `ALSO_KNOWN_AS` facts** in both sources - an essay can legitimately state "he was also known as X," and the graph can confirm that; excluding these was an earlier bug (see [§14.2](#142-also_known_as-facts-hidden-from-claude)).
- **`format_facts_for_prompt(facts) -> str`** - numbered, Sinhala-readable fact list for the Claude prompt (e.g. `"5. දුටුගැමුණු - BUILT - රුවන්වැලිසෑය (කාලය: ...)"`). If a king has more than 80 facts, prioritizes the relation types most useful for fact-checking (BUILT, DEFEATED, RULED, family relations, etc.) before truncating.

### 6.3 `essay_accuracy_checker.py` - Core Pipeline

The heart of Stage 2. Key pieces:

**Data types:**
- `ClaimResult` - one graded claim: the sentence, its classification (`claim_type`), verdict, the reason if unverifiable, the matched KG fact, an explanation, and (for wrong claims) `teacher_feedback`.
- `BatchLog` - a full trace of one batch's Claude call: the exact system prompt, user message, raw response, and whether a parse retry was needed. Exists purely for transparency/debugging in the UI.
- `AccuracyResult` - the final aggregated result: subject, all kings found, score, coverage ratio, confidence level, every claim, every batch log.

**Pipeline functions, called in order by `check_essay_accuracy()`:**

1. **`identify_essay_subject(essay_text) -> (primary_king, all_kings)`**
   Runs NER on the first 5 sentences, resolves any `PERSON_KING`/`PERSON_MONK` entity to a canonical name via `king_name_db`, then separately scans the *entire* essay text for any king name NER might have missed. Ranks candidates by frequency (most-mentioned wins), tie-broken by earliest appearance, then double-checks the winner actually has at least one KG fact - falling back to the next-most-frequent candidate that does, if not.

2. **`chunk_essay(essay_text) -> list[list[str]]`**
   Splits the essay into sentences (on Sinhala/standard full stops) and groups them into batches of **at most 6 sentences** - this cap is fixed and load-bearing (bigger batches risk exceeding the Claude response token budget, see [§14.3](#143-response-truncation-on-long-batches)).

3. **`build_claude_system_prompt(primary_king, all_kings) -> str`**
   The instructions given to Claude for grading. See [§7](#7-claim-classification-and-scoring-methodology) for the full grading logic this encodes.

4. **`call_claude_batch(...)`**
   Sends one batch of sentences + the KG facts to Claude, parses the JSON response into `ClaimResult`s. Handles two failure modes gracefully:
   - **Truncated response** (Claude ran out of tokens mid-generation): salvages every claim that finished generating and pads only the genuinely-missing tail sentences, instead of discarding the whole batch.
   - **Genuinely malformed response**: retries once, then falls back to marking the batch `UNVERIFIABLE` with a clear reason.

5. **`aggregate_results(...)`**
   Combines every batch's claims into the final `AccuracyResult` and computes the score (formulas documented in code and in [§7](#7-claim-classification-and-scoring-methodology)).

### 6.4 `mongo_store.py` - Persistence

Shared between Stage 1 and Stage 2, in one MongoDB database with two collections:
- `pipeline_runs` - Stage 1 run history (unchanged, pre-existing).
- `essay_check_runs` - Stage 2 essay-check history. Every check - whether triggered from the Streamlit page or the API - is saved here via **`save_essay_check_run()`**, including:
  - The full raw essay text.
  - The complete result (score, every claim, every batch's exact Claude input/output).
  - `source` - `"streamlit_ui"` or `"api"`.
  - `caller` - which API client submitted it (resolved from the API key), `None` for the Streamlit UI.
  - `submitted_by` - an optional free-text ID the caller supplies (e.g. a student/essay ID), for their own traceability.

### 6.5 `pages/essay_checker.py` - Streamlit UI

Three tabs:
- **Input** - paste essay text or upload a `.txt` file, click Check Accuracy. Shows live progress and each batch's Claude input/output as it's processed.
- **Results** - the full breakdown: score summary card, detected kings, a dedicated **Corrections & Feedback** section (every wrong claim paired with its correction), a filterable claim-by-claim list, a summary table, a KG Gap worklist (facts the essay states that the KG doesn't cover yet - a candidate list for Stage 1 to fill in), and collapsible sections showing the raw Claude API log and the KG facts used.
- **History** - browse every past check (from MongoDB), reload any of them to see the exact same breakdown again.

All UI text is English (labels, buttons, guidance) - Sinhala is used only for content that's inherently Sinhala: the essay itself, quoted claims, king names, and KG fact text.

---

## 7. Claim classification and scoring methodology

This is the most important design decision in Stage 2, and the one most worth understanding for the thesis write-up. Full analysis: `docs/essay_claim_classification_report.html`.

### The problem it solves
A history essay naturally contains two very different kinds of sentences:
- **Factual claims** - "X built Y," "X ruled from date A to date B" - checkable against the Knowledge Graph.
- **Editorial/rhetorical sentences** - "X was the greatest king," "this marked a golden age" - value judgments that **no Knowledge Graph, however complete, could ever verify.**

Treating both the same way means an essay written in a normal, reflective style (which almost all essays are) gets penalized for "unverifiable" content that was never meant to be a checkable fact in the first place.

### The fix - two-stage grading
Every claim is classified **before** it's graded:

- **`claim_type`**: `"FACTUAL"` or `"EDITORIAL"`.
  EDITORIAL claims are always `verdict = "UNVERIFIABLE"` and excluded from every score calculation - shown to the user, but never counted against the essay.
- For FACTUAL claims that end up UNVERIFIABLE, a further **`unverifiable_reason`**: `"NOT_IN_KG"` (a real historical claim the graph simply doesn't cover yet - a genuine coverage gap, worth adding to the KG) vs `"NOT_FACTUAL"` (used defensively; in practice this only occurs on EDITORIAL claims).

**Verdict rules given to Claude:**
- **CORRECT** - the claim's central assertion matches a KG fact, *even if a secondary detail doesn't* (e.g. "built X out of grief" - the building is confirmed, the motive isn't, and that doesn't drag the verdict down).
- **INCORRECT** - *only* when a KG fact is directly contradicted (wrong date, wrong relationship, wrong person). Absence of information is never grounds for INCORRECT.
- **UNVERIFIABLE** - the claim is FACTUAL, but no KG fact confirms or contradicts it.

A defensive normalization layer (`_normalize_claim_fields`) additionally **enforces these rules in code**, not just in the prompt - because Claude's own structured verdict has, in testing, occasionally disagreed with its own explanation text. This guarantees the scoring invariants hold regardless.

### Scoring formulas

```
Factual Precision (accuracy_score) = correct / (correct + incorrect)
    "Of the claims we could verify, how many were right?" Reported as 0–100.
    None if there are zero verifiable claims.

KG Coverage Ratio = (correct + incorrect) / total_factual_claims
    "What fraction of the essay's factual claims could the KG verify at all?"
    EDITORIAL claims are excluded from this denominator, so writing style
    never depresses this number.
    coverage_warning = True if this ratio is below 30%.

Confidence Level:
    HIGH             - (correct + incorrect) >= 5
    LOW              - (correct + incorrect) is 1–4
    INSUFFICIENT_KG  - (correct + incorrect) == 0

Threshold justification (5, for HIGH): fewer than 5 verifiable claims makes
the precision figure statistically unreliable - one claim flipping verdict
swings the whole score. This is standard minimum-sample-size practice for
precision metrics (Manning & Schütze, 1999), and was empirically confirmed
against this system: a 5-sentence test essay produced only 3 verifiable
claims and was correctly rated LOW, not HIGH - the threshold catching
exactly the case it's meant to catch.
```

---

## 8. Teacher-style corrective feedback

For every claim marked `INCORRECT`, Claude additionally writes a **`teacher_feedback`** field - 2-3 sentences of natural Sinhala, in the voice of a history teacher correcting a student:
1. States what the student wrote.
2. Explains why it doesn't match the historical record (per the KG).
3. States the correct fact clearly.

Deliberately scoped to `INCORRECT` claims only (`None` for everything else) - writing this for every claim would risk the same response-truncation problem described in [§14.3](#143-response-truncation-on-long-batches), and correction only makes sense where something is actually wrong.

**Example (real output):**
> *Claim:* "දුටුගැමුණු රජු එළාර රජුගේ පුත්‍රයා විය." (Dutugämuṇu was the son of Elāra.)
> *Teacher feedback:* "ඔබ දුටුගැමුණු රජු එළාර රජුගේ පුත්‍රයා බව ලියා ඇත. නමුත් ඓතිහාසික වාර්තා අනුව දුටුගැමුණු රජුගේ පියා කාවන්තිස්ස රජු වන අතර මව විහාරමහා දේවිය වේ. ..." (You wrote X; but per the historical record, his father was actually King Kavantissa and his mother was Vihara Maha Devi. ...)

Shown in three places in the UI: individual claim cards, a dedicated "Corrections & Feedback" section (all wrong claims listed together with their corrections, or a "no factual errors found" message if there are none), and as a column in the summary table.

---

## 9. External REST API (for other modules)

`api_server.py` - a standalone FastAPI application, run separately from the Streamlit app, so Module 3 (or anything else) can call this module's pipeline over HTTP without importing any of this project's Python code.

### Running it
```powershell
uvicorn api_server:app --host 0.0.0.0 --port 8010
```
Interactive docs (test requests from the browser): `http://localhost:8010/docs`

### Authentication
Every endpoint except `/api/v1/health` requires a header:
```
X-API-Key: <key>
```
Valid keys are configured in `.env` as `ESSAY_API_KEYS=key1:CallerName,key2:OtherCaller` - a comma-separated list of `key:callername` pairs, one per client. This both gates the endpoint (each check costs real Claude API usage) and answers "who submitted this" - the resolved caller name is stored on every saved run.

### Endpoints

| Method & path | Purpose |
|---|---|
| `GET /api/v1/health` | Unauthenticated liveness check |
| `POST /api/v1/essay/check` | Submit essay as JSON: `{"essay_text": "...", "submitted_by": "optional-id"}` |
| `POST /api/v1/essay/check-file` | Submit essay as an uploaded `.txt` file (multipart form: `file` + optional `submitted_by`) |
| `GET /api/v1/essay/{request_id}` | Re-fetch a previously computed result by its ID |

Both submission endpoints share one internal function (`_run_and_save`) so they can never behave differently from each other - they just differ in how the essay text arrives.

**Response shape** (both submission endpoints return the same structure):
```json
{
  "request_id": "...",
  "caller": "Module3",
  "essay_subject": "දුටුගැමුණු",
  "all_kings_found": ["...", "..."],
  "accuracy_score": 100.0,
  "coverage_ratio": 0.6,
  "confidence_level": "LOW",
  "coverage_warning": false,
  "total_claims": 7, "total_factual_claims": 6, "editorial_claims": 1,
  "correct_claims": 3, "incorrect_claims": 0,
  "unverifiable_claims": 2, "kg_gap_claims": 2, "not_factual_claims": 1,
  "kg_facts_used": 59, "batch_count": 2, "essay_sentence_count": 5,
  "processing_seconds": 32.83,
  "claims": [
    {
      "claim_sinhala": "...", "claim_type": "FACTUAL", "verdict": "CORRECT",
      "unverifiable_reason": null,
      "matched_kg_fact": "27. දුටුගැමුණු - SON_OF - කාවන්තිස්ස රජු (...)",
      "explanation": "KG fact 27 සමඟ ගැළපේ - ...",
      "teacher_feedback": null,
      "batch_number": 1
    }
  ]
}
```

### Design notes worth knowing
- **Lenient JSON parsing**: the JSON endpoint parses the request body with `json.loads(raw_text, strict=False)` rather than FastAPI's default strict parser, so a caller pasting multi-paragraph text with real line breaks into the JSON string (the overwhelmingly common real-world case - Postman, curl, etc. don't auto-escape this) doesn't get rejected. This is a deliberate server-side fix rather than requiring every caller to pre-escape their input.
- **Batching is identical to the UI**: the API calls the exact same `check_essay_accuracy()` function the Streamlit page uses - no separate/duplicated logic, so a long essay gets split into 6-sentence batches and sent to Claude sequentially either way.
- **CORS is currently permissive** (`allow_origins=["*"]`) - appropriate for this internal, trusted multi-module project; would need tightening if ever exposed beyond the team.

### Testing aids
- `docs/postman_collection.json` - an import-ready Postman collection with all 4 endpoints pre-configured (including the file-upload one).
- `docs/build_postman_body.py` - converts a `.txt` essay file into an escaped JSON body (useful for curl; no longer strictly required for the API itself, given the lenient-parsing fix above, but still convenient).

---

## 10. Data persistence (MongoDB)

Two collections in one database (`sinhala_kg` by default):

- **`pipeline_runs`** (Stage 1) - one document per sentence processed: input text, NER tags, LLM provider/response, validated triples, whether it was saved to the KG.
- **`essay_check_runs`** (Stage 2) - one document per essay check: timestamp, `source`, `caller`, `submitted_by`, the full essay text, every computed score field, every claim (including `teacher_feedback`), and every batch's full Claude input/output trace.

Both `mongo_store.py`'s connection functions are lazy and fail gracefully - the module never raises just from being imported, and every read/write function returns `None`/`[]`/an error dict if MongoDB isn't reachable, rather than crashing the UI or API.

---

## 11. Data sources

- **`data/neo4j_query_table_data_2026-7-29.json`** - a static, flat export of the Knowledge Graph, used by Stage 2 only as a per-king fallback when live Neo4j is unreachable or has no facts for that king (see §6.2). Each entry: `{subject, subject_type, relation, object, object_type, period, source}`. ~917 triples across ~178 distinct relation types at the time of this export - periodically refreshed by re-exporting from live Neo4j; the live graph itself is larger and keeps growing as Stage 1 keeps running (991 nodes, 1,824 edges across 475 distinct relation types, queried live 2026-07-29) and is what Stage 2 now queries first.
- **`data/sri_lankan_kings_all_names.txt`** - a hand-curated, numbered list of ~105 Sri Lankan king/queen names (main chronological list + additional rulers mentioned only as relatives elsewhere), cross-referenced against the KG's `ALSO_KNOWN_AS` edges. Includes kings not yet represented in the Knowledge Graph at all.

---

## 12. How to run everything

### Prerequisites
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### `.env` configuration (copy from `.env.example`)
| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key - required for both relation extraction and essay grading |
| `NER_MODEL_PATH` | Path to the trained XLM-RoBERTa model directory |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | Neo4j connection (Stage 1) |
| `MONGO_URI` / `MONGO_DB` | MongoDB connection (both stages) |
| `ESSAY_API_KEYS` | `key:callername` pairs for the external API (Stage 2) |
| `LLM_PROVIDER` / `LLM_MODEL` | Which LLM Stage 1's relation extraction uses |

### Run the Streamlit app (Stages 1 & 2 UI)
```powershell
streamlit run app.py
```
Navigate to the **Essay Checker** page in the sidebar for Stage 2.

### Run the external API (Stage 2, for Module 3)
```powershell
uvicorn api_server:app --host 0.0.0.0 --port 8010
```
These are **two independent processes on two different ports** - running one does not start the other.

---

## 13. Testing / verification

- **Standard test fixture**: `දුටුගැමුණු රජතුමා.txt` (project root) - a short essay used throughout development to verify the pipeline end-to-end after every change.
- Verified, at various points in development:
  - `king_name_db.build_king_index()` / `find_king_in_text()` in isolation.
  - `kg_fact_retriever.get_facts_for_king()` / `get_all_kg_names_for_king()` in isolation.
  - Full `check_essay_accuracy()` end-to-end against real essays, including deliberately-wrong test essays (to confirm INCORRECT verdicts and teacher_feedback fire correctly) and long, real essays (to confirm subject identification and batching behave correctly at scale).
  - The external API - health check, both auth-failure paths (401), validation failure (422), a full successful check (200, saved to Mongo with a retrievable ID), and the file-upload variant.

---

## 14. Bugs found and fixed during development

Documented here because they reflect real methodology decisions, not just code fixes - relevant for a thesis discussion of system limitations and validation.

### 14.1 Word-boundary bug in name matching
`king_name_db.find_king_in_text()`'s substring matching had no word-boundary check: the short alias `"සිංහ"` (registered for king සිංහබාහු) matched inside the ordinary word `"සිංහල"` ("Sinhala"/the nation) every time it appeared - extremely common in Sinhala historical writing. On one real test essay, these false hits outnumbered the essay's actual mentions of its real subject and hijacked subject identification entirely (the essay was checked against the wrong king's facts). Fixed with a boundary check that rejects a match flanked by more Sinhala-script text unless that continuation is a recognised grammatical suffix (preserving legitimate inflected forms like "දුටුගැමුණුගේ").

### 14.2 `ALSO_KNOWN_AS` facts hidden from Claude
`get_facts_for_king()` originally excluded `ALSO_KNOWN_AS` triples from the fact list sent to Claude, on the reasoning that they're "just for name resolution." This meant an essay stating a king's alternate title (e.g. "he was honored with the title Pandita Vijayabahu") could never be confirmed as CORRECT, even though the KG had that exact fact. Fixed by including these facts in the prompt (their separate use for name-set resolution elsewhere was unaffected).

### 14.3 Response truncation on long batches
Claude's per-claim `explanation` text became more verbose than the prompt's terse template intended, which pushed some 6-sentence batches past the `max_tokens` budget mid-generation. The original parser treated any JSON parse failure as total loss - a batch where 5 of 6 claims had fully generated still discarded all 6. Fixed with a parser that salvages every claim object that finished generating and pads only the genuinely-missing tail sentences, plus a tightened prompt instruction demanding brevity.

### 14.4 Aggregate UI tiles not summing to the total
A side effect of the fix above: padded "truncation" claims deliberately carry no `unverifiable_reason` (a system failure isn't a real KG gap), but the UI's "Not in KG" tile only showed that specific reason's count - so the visible tiles (Correct + Incorrect + Not-in-KG + Editorial) could silently stop summing to the displayed Total Claims whenever a batch had a grading failure, with no explanation. Fixed by adding a distinct "could not be graded" display category, used consistently across summary tiles, claim cards, and the filter.

### 14.5 API body parsing too strict for real-world input
Every caller tested (Postman's raw editor, curl) pastes multi-paragraph essay text directly into the JSON body without escaping line breaks - the natural way anyone interacts with the endpoint, not an edge case. Strict JSON parsing rejected this as "Invalid control character." Fixed server-side with lenient parsing (`json.loads(..., strict=False)`) rather than requiring every caller to pre-escape their input - the server shouldn't assume how external callers format text when a one-line, standards-compatible fix removes the problem entirely.

---

## 15. Known limitations and future work

- **KG coverage is partial and growing.** Many kings in `sri_lankan_kings_all_names.txt` have zero facts in the current KG export - essays about them will correctly show `INSUFFICIENT_KG`, not a wrong score, but this is a real coverage gap, not a bug. The "KG Gap Worklist" in the UI surfaces exactly which claims from a checked essay aren't covered yet, as a candidate list for Stage 1 to fill in.
- **Short-alias collision risk.** The word-boundary fix (§14.1) fixed one specific case; other short aliases in `kg_aliases.CANONICAL_ALIASES` could in principle collide with ordinary Sinhala words the same way. Worth an audit if similar misidentifications turn up.
- **Sub-claim decomposition (not implemented).** Compound sentences that mix a verifiable fact with an unverifiable secondary detail are currently graded on their central assertion (see §7) rather than split into separate atomic claims. Full decomposition would be more precise but needs prompt, schema, and UI changes; the current approach already recovers the correct verdict for the common cases tested.
- **No live Neo4j queries in Stage 2** by design (reads only the static JSON export) - means the essay checker's view of the KG can lag behind Stage 1's latest saves until the export is regenerated.
