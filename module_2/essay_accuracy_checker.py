"""
essay_accuracy_checker.py — Essay Accuracy Scoring core logic (Stage 2, Module 2, 214161L)

Pipeline: Student essay → identify all kings mentioned → retrieve their KG
facts (including alternate names via ALSO_KNOWN_AS) → Claude API evaluates
each claim against those facts → aggregated, research-level accuracy score.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from dotenv import load_dotenv

import king_name_db
import kg_fact_retriever
from ner_pipeline import run_ner

load_dotenv()

CLAUDE_MODEL: str = "claude-sonnet-4-6"
# 2048 was the original budget but proved too tight for batches where several
# claims are INCORRECT (each adds a 2-3 sentence teacher_feedback on top of
# explanation) — Claude would hit the ceiling mid-batch and the remaining
# claims fell to the truncation-recovery fallback (see call_claude_batch).
# Raised to give headroom; the fallback stays in place regardless as a backstop.
MAX_TOKENS:   int = 4096
MAX_SENTENCES_PER_BATCH: int = 6
MIN_VERIFIABLE_FOR_HIGH_CONFIDENCE: int = 5
LOW_COVERAGE_THRESHOLD: float = 0.30

# Sinhala + standard full-stop sentence boundary. `\s*` (rather than `\s+`)
# means a sentence still splits correctly even with no trailing whitespace
# (e.g. the very last sentence of the essay), covering the "plus r'\.'" case.
_SENT_BOUNDARY_RE = re.compile(r"(?<=[.।。])\s*")


# DATA TYPES

@dataclass
class ClaimResult:
    claim_sinhala: str          # exact sentence or phrase from essay (Sinhala essay content)
    claim_type: str             # "FACTUAL" | "EDITORIAL" — see build_claude_system_prompt STEP 1
    verdict: str                # "CORRECT" | "INCORRECT" | "UNVERIFIABLE"
    unverifiable_reason: Optional[str]  # "NOT_IN_KG" | "NOT_FACTUAL" | None (set only when verdict == UNVERIFIABLE)
    matched_kg_fact: str        # the KG triple that supports or contradicts (Sinhala KG content)
    explanation: str            # Sinhala explanation sentence + English KG relation.
                                 # Format: "KG fact N සමඟ ගැළපේ — Subject RELATION Object (period)"
                                 # Example: "KG fact 5 සමඟ ගැළපේ — දුටුගැමුණු BUILT රුවන්වැලිසෑය (ක්‍රි.පූ. 161-137)"
    teacher_feedback: Optional[str]  # Sinhala corrective feedback in a history-teacher's voice,
                                 # set ONLY when verdict == "INCORRECT" (None otherwise — this is
                                 # intentionally scoped to wrong claims only, to keep Claude's
                                 # output bounded; see feedback_llm_response_recovery.md).
                                 # States what the student wrote, why it's wrong, and the correct
                                 # fact per the KG, in a constructive, encouraging tone.
    batch_number: int


@dataclass
class BatchLog:
    """Full input/output trace for one batch call to Claude — for UI transparency."""
    batch_number: int
    total_batches: int
    sentences: list[str]
    system_prompt: str
    user_message: str
    raw_response: str           # exact text Claude returned (last attempt, pre-parse)
    parse_retried: bool         # True if a JSON-parse retry was needed
    claim_results: list["ClaimResult"] = field(default_factory=list)


@dataclass
class AccuracyResult:
    essay_subject: str
    all_kings_found: list[str]
    accuracy_score: Optional[float]     # Factual Precision 0-100, None if no verifiable claims
    coverage_ratio: float               # (correct + incorrect) / total_factual_claims
    confidence_level: str               # "HIGH" | "LOW" | "INSUFFICIENT_KG"
    coverage_warning: bool              # True if coverage_ratio < 0.30
    total_claims: int                   # ALL claims, including EDITORIAL
    total_factual_claims: int           # FACTUAL claims only — the scoring denominator
    editorial_claims: int               # count of claim_type == EDITORIAL (not scored)
    correct_claims: int                 # FACTUAL + CORRECT
    incorrect_claims: int               # FACTUAL + INCORRECT
    unverifiable_claims: int            # FACTUAL + UNVERIFIABLE
    kg_gap_claims: int                  # count of unverifiable_reason == NOT_IN_KG
    not_factual_claims: int             # count of unverifiable_reason == NOT_FACTUAL
    kg_facts_used: int
    batch_count: int
    essay_sentence_count: int
    all_claim_results: list[ClaimResult] = field(default_factory=list)
    batch_logs: list[BatchLog] = field(default_factory=list)
    kg_facts_text: str = ""


# ESSAY SUBJECT IDENTIFICATION

def identify_essay_subject(essay_text: str) -> tuple[str, list[str]]:
    """Identify the primary king and all kings mentioned in the essay.

    Step 1: NER on the first 5 sentences.
    Step 2: Resolve each PERSON_KING/PERSON_MONK entity to a canonical name.
    Step 3: Also scan the FULL essay text for king names NER missed.
    Step 4: The king appearing earliest & most frequently is the primary
            subject; all others found are secondary.
    Step 5: Verify the primary king has >=1 KG fact — otherwise fall back to
            the next most frequent king that does have KG facts.

    Returns: (primary_canonical_name, [all_canonical_names_found])
    """
    essay_text = essay_text.strip()
    if not essay_text:
        return "", []

    sentences = [s for s in _SENT_BOUNDARY_RE.split(essay_text) if s.strip()]
    first_five = sentences[:5]

    occurrences: list[tuple[str, int]] = []  # (canonical, position/sentence-index)

    for sent_idx, sentence in enumerate(first_five):
        for tag in run_ner(sentence):
            if tag.label not in ("PERSON_KING", "PERSON_MONK"):
                continue
            for hit in king_name_db.find_king_in_text(tag.entity):
                occurrences.append((hit["canonical"], sent_idx))

    for hit in king_name_db.find_king_in_text(essay_text):
        occurrences.append((hit["canonical"], hit["position"]))

    if not occurrences:
        return "", []

    freq: dict[str, int] = {}
    earliest: dict[str, int] = {}
    for name, pos in occurrences:
        freq[name] = freq.get(name, 0) + 1
        earliest[name] = min(pos, earliest.get(name, pos))

    # Rank by frequency (desc), tie-broken by earliest appearance (asc).
    ranked = sorted(freq, key=lambda n: (-freq[n], earliest[n]))
    all_kings = sorted(freq, key=lambda n: (earliest[n], -freq[n]))

    primary = ranked[0]
    for candidate in ranked:
        if kg_fact_retriever.get_facts_for_king(candidate):
            primary = candidate
            break

    return primary, all_kings


# ESSAY CHUNKING

def chunk_essay(essay_text: str) -> list[list[str]]:
    """Split essay into sentences, grouped into batches of at most 6 sentences.

    A sentence is never split across batches.
    """
    essay_text = essay_text.strip()
    if not essay_text:
        return []

    sentences = [s.strip() for s in _SENT_BOUNDARY_RE.split(essay_text) if s.strip()]

    batches: list[list[str]] = []
    for i in range(0, len(sentences), MAX_SENTENCES_PER_BATCH):
        batches.append(sentences[i:i + MAX_SENTENCES_PER_BATCH])
    return batches


# CLAUDE PROMPTING

def build_claude_system_prompt(primary_king: str, all_kings: list[str]) -> str:
    """Build the system prompt instructing Claude how to grade the essay.

    Two-stage grading (see analysis report §3-§6): every claim is first
    classified FACTUAL vs EDITORIAL, then only FACTUAL claims are graded
    against the KG. This keeps essay-writing style (character studies,
    value judgments) from being counted as "unverifiable coverage gaps".
    """
    other_kings = [k for k in all_kings if k != primary_king]
    others_str  = ", ".join(other_kings) if other_kings else "(none)"

    return f"""\
You are an expert Sinhala historian and language specialist evaluating a student essay about Sri Lankan kings.

You will receive:
(A) A numbered list of verified historical facts from a Knowledge Graph (KG)
(B) A portion of a student essay written in Sinhala

Primary king: {primary_king}
Other kings mentioned in the essay: {others_str}
Consider claims about ALL kings mentioned, not only the primary one.

Your ONLY source of historical truth is the provided KG facts.
Do NOT use your own historical knowledge to confirm or contradict any claim.
If a fact is not in the KG, it is UNVERIFIABLE — not incorrect.

━━━ STEP 1: CLASSIFY EACH CLAIM ━━━

For every sentence or key claim in the essay, first assign claim_type:

claim_type = "EDITORIAL" when the sentence expresses:
  - A value judgment ("ශ්‍රේෂ්ඨතම රජ", "මහාන් වීරයා")
  - A character assessment ("මෙතුමා සතු වූ උතුම් විනය")
  - Historical significance ("ඉතිහාසයේ ස්වර්ණමය සන්ධිස්ථානයක්")
  - Emotional or narrative description ("හදවතේ නොමියෙන වීරයා")
  - Any statement that NO knowledge graph could ever verify or refute
  EDITORIAL claims always get verdict = "UNVERIFIABLE"
  and unverifiable_reason = "NOT_FACTUAL"
  Do not attempt to match EDITORIAL claims against KG facts.

claim_type = "FACTUAL" when the sentence describes:
  - An event (battle, construction, arrival, death)
  - A date or time period
  - A relationship (father, son, wife, ruler of)
  - A construction, building, or monument
  - An alternative name or title
  - Any proposition that a sufficiently complete KG could in principle verify

━━━ STEP 2: GRADE FACTUAL CLAIMS ONLY ━━━

For each FACTUAL claim:

CORRECT — when the claim's CENTRAL ASSERTION matches a KG fact.
  Key rule for compound sentences: if the main verb/event matches a KG
  fact, the verdict is CORRECT even if a secondary clause (motive, method,
  technique, superlative) is not in the KG.
  Example: "මානසික පීඩාව නිසා මිරිසවැටිය ඉදිකළේය" — the building event
  matches KG. The motive clause does not. Verdict = CORRECT.
  Note the uncovered secondary clause in explanation. Do not downgrade.

  Sinhala surface forms: a KG fact "දුටුගැමුණු RULED ශ්‍රී ලංකාව" may
  appear in the essay as "රජ කළේය", "රාජ්‍ය කළේ", "ලංකාව පාලනය කළේ",
  "සිංහල රටේ රජු විය" — treat all as matching the same fact.
  You are a Sinhala language expert — recognise semantic equivalence
  across surface forms.

INCORRECT — ONLY when a KG fact is DIRECTLY contradicted:
  - Wrong date (essay says ක්‍රි.පූ. 200, KG says ක්‍රි.පූ. 161)
  - Wrong relationship (essay says පුත්‍රයා, KG says සොහොයුරා)
  - Wrong person (essay says රජු A built X, KG says රජු B built X)
  An unconfirmed detail is NEVER grounds for INCORRECT.

UNVERIFIABLE with unverifiable_reason = "NOT_IN_KG" — when:
  - The claim is FACTUAL in type
  - No KG fact confirms or contradicts it
  - The claim is simply absent from the provided KG facts

━━━ STEP 3: EXPLANATION FORMAT ━━━

For every claim write explanation in this exact format:
  If CORRECT: "KG fact [N] සමඟ ගැළපේ — [Subject] [RELATION] [Object] ([period])"
  If INCORRECT: "KG fact [N] සමඟ පරස්පර — [Subject] [RELATION] [Object] ([period])"
  If UNVERIFIABLE NOT_IN_KG: "KG හි මෙම කරුණ නොමැත"
  If UNVERIFIABLE NOT_FACTUAL: "මෙය සාහිත්‍යමය/සංස්කෘතික ප්‍රකාශයකි — KG සත්‍යාපනය කළ නොහැක"

Output ONLY the template text above for explanation — do not append extra
reasoning, caveats, or additional sentences. Every claim in the batch must
receive a complete response; verbose explanations are the most common
cause of the response being cut off before all claims finish.

━━━ STEP 4: TEACHER FEEDBACK FOR INCORRECT CLAIMS ONLY ━━━

ONLY when verdict = "INCORRECT", also write a teacher_feedback field:
2-3 sentences of natural Sinhala, in the voice of a kind but precise
history teacher (ඉතිහාස ගුරුවරයෙක්) correcting a student's essay.
Structure:
  1. Note what the student wrote (briefly, in your own words).
  2. Explain concisely why it does not match the historical record (per KG).
  3. State the correct fact clearly, so the student learns it.
Tone: constructive and encouraging, never harsh — this is feedback meant
to help the student improve, not to criticize them.

Example:
  Essay claim: "දුටුගැමුණු රජු එළාර රජු පරාජය කළේ ක්‍රි.පූ. 200 දී ය."
  KG fact: දුටුගැමුණු DEFEATED එළාර (කාලය: ක්‍රි.පූ. 161-137)
  teacher_feedback: "ඔබ මෙම සිදුවීම ක්‍රි.පූ. 200 දී සිදු වූ බව ලියා ඇත.
  නමුත් ඓතිහාසික වාර්තා අනුව දුටුගැමුණු රජු එළාර රජු පරාජය කළේ
  ක්‍රි.පූ. 161-137 කාලය තුළදීය. දිනයන් නිවැරදිව සටහන් කර ගැනීම
  ඉතිහාස රචනයේදී වැදගත් වේ."

For every other verdict (CORRECT, UNVERIFIABLE) set teacher_feedback = null
— never write feedback for a claim that isn't factually wrong. Keep this
field to 2-3 sentences maximum — the same brevity requirement as STEP 3
applies here, since it only applies to the (typically few) INCORRECT
claims, the total added length should stay small.

━━━ OUTPUT FORMAT ━━━

Return ONLY valid JSON. No preamble. No markdown fences. No explanation outside JSON.

{{
  "claims": [
    {{
      "claim_sinhala": "<sentence or key phrase from essay>",
      "claim_type": "FACTUAL" | "EDITORIAL",
      "verdict": "CORRECT" | "INCORRECT" | "UNVERIFIABLE",
      "unverifiable_reason": "NOT_IN_KG" | "NOT_FACTUAL" | null,
      "matched_kg_fact": "<KG fact number and full text, or N/A>",
      "explanation": "<Sinhala explanation + English KG relation as specified above>",
      "teacher_feedback": "<Sinhala corrective feedback in a history teacher's voice, ONLY if verdict is INCORRECT, else null>"
    }}
  ],
  "batch_correct": <int>,
  "batch_incorrect": <int>,
  "batch_unverifiable": <int>,
  "batch_editorial": <int>,
  "batch_factual": <int>
}}
"""


def _build_user_message(
    batch_sentences: list[str],
    batch_num: int,
    total_batches: int,
    primary_king: str,
    all_kings: list[str],
    kg_facts_text: str,
) -> str:
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(batch_sentences, start=1))
    all_kings_str = "، ".join(all_kings) if all_kings else primary_king
    return f"""\
ප්‍රාථමික රජු: {primary_king}
රචනාවේ සඳහන් සියලු රජවරු: {all_kings_str}

=== Knowledge Graph සත්‍ය (KG Facts) ===
{kg_facts_text}

=== ශිෂ්‍ය රචනාවේ කොටස {batch_num}/{total_batches} ===
{numbered}
"""


def _strip_json_fences(raw: str) -> str:
    cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
    return cleaned.rstrip("`").strip()


def _recover_truncated_claims(cleaned: str) -> dict | None:
    """Salvage complete claim objects from a response cut off mid-generation
    (hit max_tokens before the JSON could close).

    Walks the "claims" array with JSONDecoder.raw_decode, pulling out each
    fully-formed {...} object in turn and stopping at the first incomplete
    one — so a batch where e.g. 5 of 6 claims finished generating returns
    those 5 instead of failing the whole batch (see call_claude_batch,
    which pads the remainder rather than silently dropping it).
    """
    idx = cleaned.find('"claims"')
    if idx == -1:
        return None
    arr_start = cleaned.find("[", idx)
    if arr_start == -1:
        return None

    decoder = json.JSONDecoder()
    pos = arr_start + 1
    length = len(cleaned)
    claims: list = []
    while pos < length:
        while pos < length and cleaned[pos] in " \t\n\r,":
            pos += 1
        if pos >= length or cleaned[pos] == "]":
            break
        try:
            obj, end = decoder.raw_decode(cleaned, pos)
        except json.JSONDecodeError:
            break  # this object never finished generating — stop here
        claims.append(obj)
        pos = end

    return {"claims": claims} if claims else None


def _parse_claude_json(raw: str) -> dict | None:
    if not raw:
        return None
    cleaned = _strip_json_fences(raw)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return _recover_truncated_claims(cleaned)


def _unverifiable_batch(batch_sentences: list[str], batch_num: int, reason: str) -> list[ClaimResult]:
    """Fallback ClaimResults for API/parse failures.

    These are NOT a real Claude classification, so claim_type defaults to
    FACTUAL (the safer assumption — never silently drop a claim from
    scoring because of a system failure) and unverifiable_reason is left
    None: a system failure is neither a KG coverage gap (NOT_IN_KG) nor an
    editorial-content finding (NOT_FACTUAL), so it must not be counted as
    either in kg_gap_claims / not_factual_claims.
    """
    return [
        ClaimResult(
            claim_sinhala=s,
            claim_type="FACTUAL",
            verdict="UNVERIFIABLE",
            unverifiable_reason=None,
            matched_kg_fact="N/A",
            explanation=reason,
            teacher_feedback=None,
            batch_number=batch_num,
        )
        for s in batch_sentences
    ]


def _normalize_claim_fields(c: dict) -> tuple[str, str, Optional[str], Optional[str]]:
    """Validate and normalize (claim_type, verdict, unverifiable_reason,
    teacher_feedback) from one raw claim dict returned by Claude.

    Also defensively enforces the prompt's own rules in code, rather than
    trusting the model to have applied them consistently: the analysis
    report (§2) found a real case where Claude's structured verdict field
    ("INCORRECT") disagreed with its own explanation text (which argued
    for, and concluded with, "UNVERIFIABLE"). Enforcing the EDITORIAL ⇒
    UNVERIFIABLE/NOT_FACTUAL rule, clearing unverifiable_reason for
    CORRECT/INCORRECT verdicts, and clearing teacher_feedback for anything
    other than INCORRECT here guarantees these invariants hold even when
    the model's own output is inconsistent.
    """
    claim_type = str(c.get("claim_type", "FACTUAL")).strip().upper()
    if claim_type not in ("FACTUAL", "EDITORIAL"):
        claim_type = "FACTUAL"

    verdict = str(c.get("verdict", "UNVERIFIABLE")).strip().upper()
    if verdict not in ("CORRECT", "INCORRECT", "UNVERIFIABLE"):
        verdict = "UNVERIFIABLE"

    raw_reason = c.get("unverifiable_reason")
    reason = str(raw_reason).strip().upper() if raw_reason else None
    if reason not in ("NOT_IN_KG", "NOT_FACTUAL"):
        reason = None

    if claim_type == "EDITORIAL":
        verdict = "UNVERIFIABLE"
        reason = "NOT_FACTUAL"
    elif verdict != "UNVERIFIABLE":
        reason = None
    elif reason is None:
        # FACTUAL + UNVERIFIABLE but Claude omitted the reason — default to
        # the more common case (simply absent from the KG).
        reason = "NOT_IN_KG"

    # teacher_feedback is meaningful only for genuinely wrong claims — a
    # correction only makes sense when something needs correcting.
    raw_feedback = c.get("teacher_feedback")
    teacher_feedback = str(raw_feedback).strip() if raw_feedback else None
    if verdict != "INCORRECT":
        teacher_feedback = None

    return claim_type, verdict, reason, teacher_feedback


def call_claude_batch(
    batch_sentences: list[str],
    batch_num: int,
    total_batches: int,
    primary_king: str,
    all_kings: list[str],
    kg_facts_text: str,
    api_key: str,
    _debug: Optional[dict] = None,
) -> list[ClaimResult]:
    """Call Claude for one batch of essay sentences and return ClaimResults.

    On API error: all sentences in the batch become UNVERIFIABLE, error logged.
    On a truncated response (hit max_tokens mid-generation): salvages
    whichever claims completed before the cutoff and pads only the missing
    tail sentences as UNVERIFIABLE, instead of discarding the whole batch.
    On a genuinely unparseable response: retry once, then fall back to
    UNVERIFIABLE for the whole batch.

    Pass a dict as _debug to capture the exact system prompt, user message,
    raw response text, and whether a parse-retry happened:
        d = {}; call_claude_batch(..., _debug=d)
        # d["system_prompt"], d["user_message"], d["raw_response"], d["parse_retried"]
    """
    import anthropic

    system_prompt = build_claude_system_prompt(primary_king, all_kings)
    user_message  = _build_user_message(
        batch_sentences, batch_num, total_batches, primary_king, all_kings, kg_facts_text,
    )
    if _debug is not None:
        _debug["system_prompt"] = system_prompt
        _debug["user_message"]  = user_message
        _debug["raw_response"]  = ""
        _debug["parse_retried"] = False

    try:
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as exc:
        print(f"[EssayChecker] Claude client init failed: {exc}")
        if _debug is not None:
            _debug["raw_response"] = f"[client init error] {exc}"
        return _unverifiable_batch(batch_sentences, batch_num, "Could not verify — Claude API client initialization failed.")

    def _call() -> str | None:
        try:
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return message.content[0].text.strip()
        except Exception as exc:
            print(f"[EssayChecker] Claude API error (batch {batch_num}): {exc}")
            if _debug is not None:
                _debug["raw_response"] = f"[API error] {exc}"
            return None

    raw = _call()
    if raw is None:
        # Retry once on an API-level failure (network timeout, dropped
        # connection) — these are usually transient, and previously any
        # single timeout killed the whole batch with zero retry, unlike
        # the JSON-parse-failure path below which already retried.
        if _debug is not None:
            _debug["parse_retried"] = True
        raw = _call()
    if raw is None:
        return _unverifiable_batch(batch_sentences, batch_num, "Could not verify due to an API error.")
    if _debug is not None:
        _debug["raw_response"] = raw

    data = _parse_claude_json(raw)
    if data is None:
        # Retry once on JSON parse failure.
        if _debug is not None:
            _debug["parse_retried"] = True
        raw = _call()
        if raw is not None and _debug is not None:
            _debug["raw_response"] = raw
        data = _parse_claude_json(raw) if raw is not None else None

    if data is None:
        return _unverifiable_batch(batch_sentences, batch_num, "Could not parse the JSON response from Claude.")

    claims_raw = data.get("claims", [])
    if not isinstance(claims_raw, list) or not claims_raw:
        return _unverifiable_batch(batch_sentences, batch_num, "No claims found in the Claude response.")

    results: list[ClaimResult] = []
    for c in claims_raw:
        if not isinstance(c, dict):
            continue
        claim_type, verdict, unverifiable_reason, teacher_feedback = _normalize_claim_fields(c)
        results.append(ClaimResult(
            claim_sinhala=str(c.get("claim_sinhala", "")).strip(),
            claim_type=claim_type,
            verdict=verdict,
            unverifiable_reason=unverifiable_reason,
            matched_kg_fact=str(c.get("matched_kg_fact", "N/A")).strip() or "N/A",
            explanation=str(c.get("explanation", "")).strip(),
            teacher_feedback=teacher_feedback,
            batch_number=batch_num,
        ))

    if not results:
        return _unverifiable_batch(batch_sentences, batch_num, "No claims found in the Claude response.")

    if len(results) < len(batch_sentences):
        # The response likely hit max_tokens before every sentence in the
        # batch got a completed claim — _recover_truncated_claims salvages
        # whichever claims DID finish generating, in order. Claude processes
        # sentences in order too, so the missing ones are assumed to be the
        # tail of the batch; pad them rather than silently losing them from
        # the report.
        missing = batch_sentences[len(results):]
        results.extend(_unverifiable_batch(
            missing, batch_num,
            "Response was truncated before this claim could be completed (max_tokens reached).",
        ))

    return results


# AGGREGATION

def aggregate_results(
    all_claim_results: list[ClaimResult],
    essay_subject: str,
    all_kings_found: list[str],
    kg_facts_used: int,
    batch_count: int,
    essay_sentence_count: int,
    batch_logs: list[BatchLog],
    kg_facts_text: str,
) -> AccuracyResult:
    # ── Scoring methodology ────────────────────────────────────────────
    # Only FACTUAL claims participate in scoring.
    # EDITORIAL claims are displayed to the user but excluded from all
    # score denominators. This follows the claim_type classification
    # defined in the Claude prompt (see build_claude_system_prompt).
    #
    # Factual Precision = correct / (correct + incorrect)
    #   Measures how accurate the verifiable factual claims are.
    #   Range: 0.0–1.0 (reported as 0–100 in the UI).
    #   None if (correct + incorrect) == 0 (no verifiable factual claims).
    #
    # KG Coverage Ratio = (correct + incorrect) / total_factual_claims
    #   Measures what fraction of the essay's factual claims the current
    #   KG can verify or refute. Excludes EDITORIAL claims from the
    #   denominator so essay writing style does not depress coverage.
    #   coverage_warning = True when KG Coverage Ratio < 0.30.
    #
    # Confidence Level:
    #   HIGH            — (correct + incorrect) >= 5
    #   LOW             — (correct + incorrect) >= 1 and < 5
    #   INSUFFICIENT_KG — (correct + incorrect) == 0
    #
    # Threshold justification (5 for HIGH confidence):
    #   A minimum of 5 verifiable claims is required for Factual Precision
    #   to be statistically meaningful. With fewer observations the score
    #   is sensitive to a single claim changing verdict — e.g. 1 correct
    #   out of 1 gives 100% but is not informative. This threshold is
    #   consistent with minimum-sample-size practice in precision-based
    #   NLP evaluation (Manning & Schütze, 1999).
    #
    #   Empirical check against this system: the test run on the 5-sentence
    #   Dutugamunu essay (දුටුගැමුණු රජතුමා.txt) produced 3 verifiable
    #   factual claims (3 correct, 0 incorrect) out of 5 factual claims
    #   total (1 sentence was classified EDITORIAL and excluded) — below
    #   the threshold, so confidence_level was correctly LOW, not HIGH,
    #   for that essay. This is expected for a short essay; a longer or
    #   more fact-dense essay would be expected to cross the 5-claim
    #   threshold into HIGH. The LOW result on a short input is evidence
    #   the threshold is doing its job, not a defect.
    # ──────────────────────────────────────────────────────────────────
    total_claims = len(all_claim_results)
    editorial_claims = sum(1 for c in all_claim_results if c.claim_type == "EDITORIAL")
    total_factual_claims = total_claims - editorial_claims

    correct_claims = sum(
        1 for c in all_claim_results
        if c.claim_type == "FACTUAL" and c.verdict == "CORRECT"
    )
    incorrect_claims = sum(
        1 for c in all_claim_results
        if c.claim_type == "FACTUAL" and c.verdict == "INCORRECT"
    )
    unverifiable_claims = sum(
        1 for c in all_claim_results
        if c.claim_type == "FACTUAL" and c.verdict == "UNVERIFIABLE"
    )
    kg_gap_claims = sum(1 for c in all_claim_results if c.unverifiable_reason == "NOT_IN_KG")
    not_factual_claims = sum(1 for c in all_claim_results if c.unverifiable_reason == "NOT_FACTUAL")

    verifiable = correct_claims + incorrect_claims
    accuracy_score = (correct_claims / verifiable * 100) if verifiable > 0 else None
    coverage_ratio = (verifiable / total_factual_claims) if total_factual_claims > 0 else 0.0
    coverage_warning = coverage_ratio < LOW_COVERAGE_THRESHOLD
    confidence_level = (
        "HIGH" if verifiable >= MIN_VERIFIABLE_FOR_HIGH_CONFIDENCE
        else "LOW" if verifiable >= 1
        else "INSUFFICIENT_KG"
    )

    return AccuracyResult(
        essay_subject=essay_subject,
        all_kings_found=all_kings_found,
        accuracy_score=round(accuracy_score, 1) if accuracy_score is not None else None,
        coverage_ratio=coverage_ratio,
        confidence_level=confidence_level,
        coverage_warning=coverage_warning,
        total_claims=total_claims,
        total_factual_claims=total_factual_claims,
        editorial_claims=editorial_claims,
        correct_claims=correct_claims,
        incorrect_claims=incorrect_claims,
        unverifiable_claims=unverifiable_claims,
        kg_gap_claims=kg_gap_claims,
        not_factual_claims=not_factual_claims,
        kg_facts_used=kg_facts_used,
        batch_count=batch_count,
        essay_sentence_count=essay_sentence_count,
        all_claim_results=all_claim_results,
        batch_logs=batch_logs,
        kg_facts_text=kg_facts_text,
    )


# ORCHESTRATION

def check_essay_accuracy(
    essay_text: str,
    api_key: str,
    progress_callback: Optional[Callable[[str], None]] = None,
    batch_callback: Optional[Callable[["BatchLog"], None]] = None,
) -> AccuracyResult:
    """Main entry point — runs the full essay accuracy pipeline.

    progress_callback(msg) fires on each pipeline stage transition.
    batch_callback(batch_log) fires immediately after each batch's Claude
    call completes, carrying the exact input sent and response received —
    lets a caller (e.g. the Streamlit UI) show each part as it happens,
    not just the final aggregated result.

    See aggregate_results() for the full scoring methodology.
    """
    def _progress(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    essay_text = essay_text.strip()

    _progress("Identifying kings...")
    primary_king, all_kings = identify_essay_subject(essay_text)

    sentences_for_count = [s for s in _SENT_BOUNDARY_RE.split(essay_text) if s.strip()]

    if not primary_king:
        return aggregate_results(
            all_claim_results=[],
            essay_subject="",
            all_kings_found=[],
            kg_facts_used=0,
            batch_count=0,
            essay_sentence_count=len(sentences_for_count),
            batch_logs=[],
            kg_facts_text="",
        )

    _progress("Searching Knowledge Graph...")
    kg_facts_all: list[dict] = []
    seen_fact_keys: set[tuple] = set()
    for king in all_kings:
        for fact in kg_fact_retriever.get_facts_for_king(king):
            key = (fact.get("subject"), fact.get("relation"), fact.get("object"))
            if key not in seen_fact_keys:
                seen_fact_keys.add(key)
                kg_facts_all.append(fact)

    kg_facts_text = kg_fact_retriever.format_facts_for_prompt(kg_facts_all)

    batches = chunk_essay(essay_text)
    total_batches = len(batches)

    all_results: list[ClaimResult] = []
    batch_logs: list[BatchLog] = []
    for i, batch in enumerate(batches, start=1):
        _progress(f"Sending Batch {i}/{total_batches} to Claude AI...")
        _dbg: dict = {}
        batch_results = call_claude_batch(
            batch_sentences=batch,
            batch_num=i,
            total_batches=total_batches,
            primary_king=primary_king,
            all_kings=all_kings,
            kg_facts_text=kg_facts_text,
            api_key=api_key,
            _debug=_dbg,
        )
        all_results.extend(batch_results)

        log = BatchLog(
            batch_number=i,
            total_batches=total_batches,
            sentences=batch,
            system_prompt=_dbg.get("system_prompt", ""),
            user_message=_dbg.get("user_message", ""),
            raw_response=_dbg.get("raw_response", ""),
            parse_retried=_dbg.get("parse_retried", False),
            claim_results=batch_results,
        )
        batch_logs.append(log)
        if batch_callback:
            batch_callback(log)

    _progress("Complete!")

    return aggregate_results(
        all_claim_results=all_results,
        essay_subject=primary_king,
        all_kings_found=all_kings,
        kg_facts_used=len(kg_facts_all),
        batch_count=total_batches,
        essay_sentence_count=len(sentences_for_count),
        batch_logs=batch_logs,
        kg_facts_text=kg_facts_text,
    )
