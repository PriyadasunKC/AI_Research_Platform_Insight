"""pages/essay_checker.py - Essay Accuracy Checker page (Stage 2, Module 2, 214161L).

UI language convention: every label, guide, button, and status message is
English. Only content that is inherently Sinhala - the student's essay text,
quoted claims, king names, and KG facts - is rendered in Sinhala.
"""

from __future__ import annotations

import html as _html
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

_CARD_OPEN  = '<div class="kg-card">'
_CARD_CLOSE = '</div>'

# Display category - distinct from the raw `verdict` field. EDITORIAL claims
# are always verdict=UNVERIFIABLE, but need their own visual bucket so they
# read as "not scored" rather than "a KG coverage gap" (see the analysis
# report §3-§5: conflating the two was the original problem).
_CATEGORY_STYLE: dict[str, dict[str, str]] = {
    "CORRECT": {
        "bg": "rgba(67,160,71,0.10)", "border": "rgba(67,160,71,0.35)",
        "fg": "#81c784", "label": "CORRECT",
    },
    "INCORRECT": {
        "bg": "rgba(229,57,53,0.10)", "border": "rgba(229,57,53,0.35)",
        "fg": "#ef9a9a", "label": "INCORRECT",
    },
    "NOT_IN_KG": {
        "bg": "rgba(255,255,255,0.03)", "border": "rgba(255,255,255,0.12)",
        "fg": "rgba(255,255,255,0.5)", "label": "NOT IN KG",
    },
    "EDITORIAL": {
        "bg": "rgba(255,255,255,0.02)", "border": "rgba(255,183,77,0.28)",
        "fg": "#ffb74d", "label": "EDITORIAL - NOT SCORED",
    },
    "ERROR": {
        "bg": "rgba(255,255,255,0.02)", "border": "rgba(158,158,158,0.35)",
        "fg": "rgba(255,255,255,0.55)", "label": "COULD NOT BE GRADED",
    },
}

_CATEGORY_ORDER: tuple[str, ...] = ("CORRECT", "INCORRECT", "NOT_IN_KG", "EDITORIAL", "ERROR")


def _display_category(claim) -> str:
    """Map a claim's (claim_type, verdict, unverifiable_reason) onto one of
    the 5 display buckets. ERROR (unverifiable_reason is None) is distinct
    from NOT_IN_KG (unverifiable_reason == "NOT_IN_KG") - a claim the model
    genuinely couldn't find in the KG is a different thing from a claim
    that never got graded because a batch's API/response failed."""
    if getattr(claim, "claim_type", "FACTUAL") == "EDITORIAL":
        return "EDITORIAL"
    if claim.verdict == "CORRECT":
        return "CORRECT"
    if claim.verdict == "INCORRECT":
        return "INCORRECT"
    if claim.verdict == "UNVERIFIABLE" and getattr(claim, "unverifiable_reason", None) is None:
        return "ERROR"
    return "NOT_IN_KG"

_EXAMPLE_ESSAY = (
    "දුටුගැමුණු රජු ලංකා ඉතිහාසයේ අති වීරෝදාර රජෙකි. ඔහු කාවන්තිස්ස රජුගේ පුත්‍රයා විය. "
    "දුටුගැමුණු රජු එළාර රජු පරාජය කර රට එක්සත් කළේය. ඔහු රුවන්වැලිසෑය ඉදිකළේය."
)


# Helpers

def _get_api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "")


def _kings_chips_html(primary: str, all_kings: list[str]) -> str:
    chips = []
    for king in all_kings:
        if king == primary:
            chips.append(
                f'<span style="background:rgba(239,83,80,0.15);border:1.5px solid #ef5350;'
                f'color:#ff8a80;border-radius:20px;padding:6px 16px;margin:4px 6px 4px 0;'
                f'display:inline-block;font-weight:700;'
                f'font-family:\'Noto Sans Sinhala\',sans-serif;font-size:.95em">'
                f'{_html.escape(king)}</span>'
            )
        else:
            chips.append(
                f'<span style="background:rgba(66,165,245,0.12);border:1px solid rgba(66,165,245,0.35);'
                f'color:#90caf9;border-radius:20px;padding:6px 16px;margin:4px 6px 4px 0;'
                f'display:inline-block;font-weight:600;'
                f'font-family:\'Noto Sans Sinhala\',sans-serif;font-size:.9em">'
                f'{_html.escape(king)}</span>'
            )
    return "".join(chips)


def _claim_card_html(claim) -> str:
    category = _display_category(claim)
    style = _CATEGORY_STYLE[category]
    body = (
        f'<div style="background:{style["bg"]};border:1px solid {style["border"]};'
        f'border-radius:12px;padding:14px 18px;margin:8px 0">'
        f'<div style="font-family:\'Inter\',sans-serif;font-size:.7em;font-weight:700;'
        f'letter-spacing:.06em;color:{style["fg"]};margin-bottom:8px">{style["label"]}</div>'
        f'<div style="font-family:\'Noto Sans Sinhala\',sans-serif;color:#f0f2f6;'
        f'font-size:.98em;line-height:1.7;margin-bottom:8px">{_html.escape(claim.claim_sinhala)}</div>'
    )
    if category in ("CORRECT", "INCORRECT"):
        body += (
            f'<div style="font-family:\'Inter\',sans-serif;font-size:.78em;font-weight:600;'
            f'color:rgba(255,255,255,.45);margin-bottom:6px">KG Fact: '
            f'<span style="font-weight:500;color:rgba(255,255,255,.65);'
            f'font-family:\'Noto Sans Sinhala\',sans-serif">'
            f'{_html.escape(claim.matched_kg_fact)}</span></div>'
        )
    if claim.explanation:
        # explanation is a Sinhala-templated sentence with an embedded English
        # KG relation name (e.g. "KG fact 5 සමඟ ගැළපේ - X BUILT Y") - needs
        # the Sinhala font, not the Latin-only 'Inter' used elsewhere for
        # pure-English UI chrome.
        body += (
            f'<div style="font-family:\'Noto Sans Sinhala\',sans-serif;font-size:.88em;'
            f'color:rgba(255,255,255,.6);line-height:1.6">{_html.escape(claim.explanation)}</div>'
        )
    if getattr(claim, "teacher_feedback", None):
        body += (
            f'<div style="margin-top:10px;padding:10px 14px;border-radius:8px;'
            f'background:rgba(229,57,53,0.06);border-left:3px solid rgba(229,57,53,0.4)">'
            f'<div style="font-family:\'Inter\',sans-serif;font-size:.68em;font-weight:700;'
            f'letter-spacing:.06em;text-transform:uppercase;color:rgba(255,255,255,.4);'
            f'margin-bottom:5px">Teacher\'s Correction</div>'
            f'<div style="font-family:\'Noto Sans Sinhala\',sans-serif;font-size:.92em;'
            f'color:#f0f2f6;line-height:1.7">{_html.escape(claim.teacher_feedback)}</div>'
            f'</div>'
        )
    body += '</div>'
    return body


def _render_category_filter(key_suffix: str) -> list[str]:
    """Multiselect to filter claims by display category. Returns selected category codes."""
    labels = {v: _CATEGORY_STYLE[v]["label"] for v in _CATEGORY_ORDER}
    selected = st.multiselect(
        "Filter by category",
        options=list(_CATEGORY_ORDER),
        default=list(_CATEGORY_ORDER),
        format_func=lambda v: labels.get(v, v),
        key=f"essay_category_filter_{key_suffix}",
    )
    return selected


# Section renderers

def _render_input_tab() -> None:
    st.markdown('<div class="kg-section-title">Enter Essay</div>', unsafe_allow_html=True)

    text_input = st.text_area(
        "Enter the Sinhala historical essay",
        key="essay_text_input",
        height=300,
        placeholder=_EXAMPLE_ESSAY,
        label_visibility="collapsed",
    )

    uploaded = st.file_uploader(
        "Upload .txt file (optional)",
        type=["txt"],
        key="essay_file_upload",
    )

    essay_text = text_input.strip()
    if uploaded is not None:
        essay_text = uploaded.read().decode("utf-8").strip()
        st.info(f"Extracted from file - {len(essay_text)} characters. (Text box will be ignored.)")

    api_key = _get_api_key()
    if not api_key:
        st.error("ANTHROPIC_API_KEY is not set in the .env file.")

    check_btn = st.button(
        "Check Accuracy",
        type="primary",
        disabled=(not essay_text or not api_key),
        width="content",
    )

    if check_btn and essay_text:
        _run_check(essay_text, api_key)


def _render_batch_log_html(log) -> str:
    """Render one batch's full input/output trace as HTML.

    Used both live (during processing, via batch_callback) and persisted
    (in the Results tab, from result.batch_logs) - same rendering either way
    so what the user watches happen matches what they can review afterward.
    """
    retried_note = (
        ' <span style="color:#ffb74d">(JSON parse failed - retried once)</span>'
        if getattr(log, "parse_retried", False) else ""
    )
    sentences_html = "".join(
        f'<div style="padding:2px 0">{i}. {_html.escape(s)}</div>'
        for i, s in enumerate(log.sentences, start=1)
    )
    claims_html = "".join(
        _claim_card_html(c) for c in log.claim_results
    ) or '<div style="color:rgba(255,255,255,.4)">(no claims)</div>'

    return f'''
    <div style="font-family:'Inter',sans-serif;font-size:.75em;font-weight:700;
                letter-spacing:.05em;text-transform:uppercase;color:rgba(255,255,255,.4);
                margin-bottom:6px">Sentences sent{retried_note}</div>
    <div style="font-family:'Noto Sans Sinhala',sans-serif;font-size:.9em;
                color:rgba(255,255,255,.7);margin-bottom:12px">{sentences_html}</div>
    <div style="font-family:'Inter',sans-serif;font-size:.75em;font-weight:700;
                letter-spacing:.05em;text-transform:uppercase;color:rgba(255,255,255,.4);
                margin:14px 0 6px 0">Input sent to Claude (user message)</div>
    <pre style="font-family:'Fira Code',monospace;font-size:.78em;line-height:1.7;
                background:rgba(0,0,0,0.3);padding:14px 18px;border-radius:8px;
                color:#b0bec5;border:1px solid rgba(255,255,255,0.06);
                white-space:pre-wrap;word-break:break-word;max-height:320px;
                overflow-y:auto">{_html.escape(log.user_message)}</pre>
    <div style="font-family:'Inter',sans-serif;font-size:.75em;font-weight:700;
                letter-spacing:.05em;text-transform:uppercase;color:rgba(255,255,255,.4);
                margin:14px 0 6px 0">Raw response received from Claude</div>
    <pre style="font-family:'Fira Code',monospace;font-size:.78em;line-height:1.7;
                background:rgba(0,0,0,0.3);padding:14px 18px;border-radius:8px;
                color:#80cbc4;border:1px solid rgba(255,255,255,0.06);
                white-space:pre-wrap;word-break:break-word;max-height:320px;
                overflow-y:auto">{_html.escape(log.raw_response)}</pre>
    <div style="font-family:'Inter',sans-serif;font-size:.75em;font-weight:700;
                letter-spacing:.05em;text-transform:uppercase;color:rgba(255,255,255,.4);
                margin:14px 0 6px 0">Parsed claims in this batch ({len(log.claim_results)})</div>
    {claims_html}
    '''


def _run_check(essay_text: str, api_key: str) -> None:
    from essay_accuracy_checker import check_essay_accuracy

    status = st.empty()
    live_log_area = st.container()

    def _progress(msg: str) -> None:
        status.info(msg)

    def _on_batch(log) -> None:
        with live_log_area:
            with st.expander(
                f"Batch {log.batch_number}/{log.total_batches} - Input to Output",
                expanded=True,
            ):
                st.markdown(_render_batch_log_html(log), unsafe_allow_html=True)

    try:
        result = check_essay_accuracy(
            essay_text, api_key,
            progress_callback=_progress,
            batch_callback=_on_batch,
        )
        st.session_state["essay_result"] = result
        st.session_state["essay_checked_text"] = essay_text
        status.success("Complete! - View the full result in the 'Results' tab.")
    except Exception as exc:
        status.error(f"An error occurred: {exc}")
        return

    # Persist to MongoDB (non-blocking - failure is logged, not surfaced).
    try:
        import mongo_store
        run_id = mongo_store.save_essay_check_run(essay_text, result)
        st.session_state["essay_mongo_run_id"] = run_id
    except Exception:
        pass


def _render_summary_card(result) -> None:
    score_str = f"{result.accuracy_score:.1f} / 100" if result.accuracy_score is not None else "N/A"

    st.markdown(
        f'''
        <div class="kg-card" style="border-left:4px solid #5c6bc0">
          <div style="font-family:'Inter',sans-serif;font-size:.75em;font-weight:700;
                      letter-spacing:.06em;text-transform:uppercase;color:rgba(255,255,255,.4);
                      margin-bottom:6px">King</div>
          <div style="font-family:'Noto Sans Sinhala',sans-serif;font-size:1.3em;font-weight:700;
                      color:#f0f2f6;margin-bottom:16px">{_html.escape(result.essay_subject or "Not identified")}</div>
          <div style="font-family:'Inter',sans-serif;font-size:.8em;font-weight:600;
                      color:rgba(255,255,255,.45);margin-bottom:2px">Accuracy Score</div>
          <div style="font-family:'Inter',sans-serif;font-size:2.4em;font-weight:700;
                      color:#7986cb;margin-bottom:16px">{score_str}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    for col, val, label, color in [
        (m1, result.correct_claims,   "Correct",               "#81c784"),
        (m2, result.incorrect_claims, "Incorrect",             "#ef9a9a"),
        (m3, result.kg_gap_claims,    "Not in KG",             "rgba(255,255,255,.6)"),
        (m4, result.editorial_claims, "Editorial (not scored)", "#ffb74d"),
        (m5, result.total_claims,     "Total Claims",          "#7986cb"),
    ]:
        col.markdown(
            f'<div class="kg-metric-card">'
            f'<div class="kg-metric-value" style="color:{color}">{val}</div>'
            f'<div class="kg-metric-label">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # "Not in KG" is a strict subset of all FACTUAL+UNVERIFIABLE claims -
    # it excludes ones where a Claude API/response error prevented grading
    # (unverifiable_reason left None; see call_claude_batch). Those still
    # count in Total Claims and in KG Coverage, so surface them explicitly
    # instead of letting the visible tiles silently fail to sum to Total.
    unresolved = result.unverifiable_claims - result.kg_gap_claims
    if unresolved > 0:
        plural = "s" if unresolved != 1 else ""
        st.caption(
            f"{unresolved} claim{plural} could not be graded due to a Claude API/response "
            f"error (e.g. a truncated response) and are counted in Total Claims and KG "
            f"Coverage, but not in 'Not in KG' or 'Editorial' above - see the Claude API "
            f"Log below for details."
        )

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**KG Coverage:** {result.coverage_ratio:.1%} *(of {result.total_factual_claims} factual claims)*")
    c2.markdown(f"**Confidence:** `{result.confidence_level}`")
    c3.markdown(f"**Batches:** {result.batch_count}")

    if result.coverage_warning:
        st.warning(
            "Low KG Coverage - Less than 30% of the essay's factual claims could be "
            "verified using information in the Knowledge Graph. This score may not "
            "fully represent the essay's overall accuracy. (Editorial/interpretive "
            "claims are excluded from this figure - see the Editorial count above.)"
        )
    if result.confidence_level == "INSUFFICIENT_KG":
        st.warning(
            "No verifiable factual claims were found for this king - the score "
            "result may not be reliable."
        )


def _render_kings_section(result) -> None:
    st.markdown('<div class="kg-section-title">Detected Kings</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)
    if result.all_kings_found:
        st.markdown(_kings_chips_html(result.essay_subject, result.all_kings_found), unsafe_allow_html=True)
    else:
        st.markdown(
            '<span style="color:rgba(255,255,255,.4)">No kings could be identified.</span>',
            unsafe_allow_html=True,
        )
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


def _render_claims_section(result, selected_categories: list[str]) -> None:
    st.markdown('<div class="kg-section-title">Claim-by-Claim Analysis</div>', unsafe_allow_html=True)
    if not result.all_claim_results:
        st.info("No claims found.")
        return
    filtered = [c for c in result.all_claim_results if _display_category(c) in selected_categories]
    if not filtered:
        st.info("No claims match the selected filter.")
        return
    for claim in filtered:
        st.markdown(_claim_card_html(claim), unsafe_allow_html=True)


def _render_summary_table(result, selected_categories: list[str]) -> None:
    import pandas as pd

    st.markdown('<div class="kg-section-title">Summary Table</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    filtered = [c for c in result.all_claim_results if _display_category(c) in selected_categories]
    df = pd.DataFrame([
        {
            "#":                 i + 1,
            "Claim":             c.claim_sinhala,
            "Type":              c.claim_type,
            "Verdict":           c.verdict,
            "KG Fact":           c.matched_kg_fact,
            "Explanation":       c.explanation,
            "Teacher Feedback":  c.teacher_feedback or "",
        }
        for i, c in enumerate(filtered)
    ])
    if df.empty:
        st.info("No claims match the selected filter.")
    else:
        st.dataframe(df, width="stretch", hide_index=True)
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


def _render_kg_gap_worklist(result) -> None:
    """Claims that are FACTUAL and UNVERIFIABLE specifically because the KG
    doesn't cover them yet - a worklist of real historical statements worth
    adding to the graph, distinct from editorial/interpretive claims."""
    st.markdown('<div class="kg-section-title">KG Gap Worklist</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    gap_claims = [c for c in result.all_claim_results if c.unverifiable_reason == "NOT_IN_KG"]
    if not gap_claims:
        st.markdown(
            '<span style="color:rgba(255,255,255,.4)">No KG gaps found in this essay.</span>',
            unsafe_allow_html=True,
        )
        st.markdown(_CARD_CLOSE, unsafe_allow_html=True)
        return

    st.markdown(
        '<div style="font-family:\'Inter\',sans-serif;font-size:.85em;'
        'color:rgba(255,255,255,.55);margin-bottom:12px">'
        'Factual claims from the essay that the current Knowledge Graph does not '
        'yet cover. These may be genuine historical facts worth adding to the KG.'
        '</div>',
        unsafe_allow_html=True,
    )
    for c in gap_claims:
        st.markdown(
            f'<div style="font-family:\'Noto Sans Sinhala\',sans-serif;font-size:.92em;'
            f'color:#f0f2f6;line-height:1.7;padding:8px 0;'
            f'border-bottom:1px solid rgba(255,255,255,.06)">{_html.escape(c.claim_sinhala)}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


def _render_corrections_section(result) -> None:
    """Every INCORRECT claim, paired with its teacher_feedback correction -
    a focused, easy-to-read list of exactly what the essay got wrong and
    what the correct historical fact is, so the student can learn from it."""
    st.markdown('<div class="kg-section-title">Corrections & Feedback</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    wrong_claims = [c for c in result.all_claim_results if c.verdict == "INCORRECT"]
    if not wrong_claims:
        st.markdown(
            '<span style="color:rgba(255,255,255,.55)">No factual errors were found in this '
            'essay - well done.</span>',
            unsafe_allow_html=True,
        )
        st.markdown(_CARD_CLOSE, unsafe_allow_html=True)
        return

    st.markdown(
        '<div style="font-family:\'Inter\',sans-serif;font-size:.85em;'
        'color:rgba(255,255,255,.55);margin-bottom:12px">'
        'Sentences that contradict the Knowledge Graph, with the correct fact explained.'
        '</div>',
        unsafe_allow_html=True,
    )
    for i, c in enumerate(wrong_claims, start=1):
        st.markdown(
            f'<div style="padding:14px 0;border-bottom:1px solid rgba(255,255,255,.06)">'
            f'<div style="font-family:\'Inter\',sans-serif;font-size:.68em;font-weight:700;'
            f'letter-spacing:.06em;text-transform:uppercase;color:#ef9a9a;margin-bottom:6px">'
            f'What you wrote ({i})</div>'
            f'<div style="font-family:\'Noto Sans Sinhala\',sans-serif;font-size:.95em;'
            f'color:#f0f2f6;line-height:1.7;margin-bottom:10px">{_html.escape(c.claim_sinhala)}</div>'
            f'<div style="font-family:\'Inter\',sans-serif;font-size:.68em;font-weight:700;'
            f'letter-spacing:.06em;text-transform:uppercase;color:#81c784;margin-bottom:6px">'
            f'Correction</div>'
            f'<div style="font-family:\'Noto Sans Sinhala\',sans-serif;font-size:.95em;'
            f'color:#f0f2f6;line-height:1.7">'
            f'{_html.escape(c.teacher_feedback or c.explanation)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


def _render_raw_facts_section(result) -> None:
    with st.expander("Raw KG Facts Used", expanded=False):
        import kg_fact_retriever

        seen: set[tuple] = set()
        all_facts: list[dict] = []
        for king in result.all_kings_found:
            for fact in kg_fact_retriever.get_facts_for_king(king):
                key = (fact.get("subject"), fact.get("relation"), fact.get("object"))
                if key not in seen:
                    seen.add(key)
                    all_facts.append(fact)

        if not all_facts:
            st.markdown("(No KG facts found)")
            return

        facts_text = kg_fact_retriever.format_facts_for_prompt(all_facts)
        st.markdown(
            f'<pre style="font-family:\'Fira Code\',monospace;font-size:.82em;'
            f'line-height:1.8;background:rgba(0,0,0,0.3);padding:16px 20px;'
            f'border-radius:10px;color:#b0bec5;border:1px solid rgba(255,255,255,0.06);'
            f'white-space:pre-wrap;word-break:break-word">{_html.escape(facts_text)}</pre>',
            unsafe_allow_html=True,
        )


def _render_batch_logs_section(result) -> None:
    """Persisted, step-by-step Claude I/O - one expander per batch, in order,
    exactly as sent/received. Lets the user re-inspect after the fact what
    was shown live while processing."""
    st.markdown('<div class="kg-section-title">Claude API Log - Batch Details</div>', unsafe_allow_html=True)

    if not result.batch_logs:
        st.info("No batch log data.")
        return

    for log in result.batch_logs:
        with st.expander(
            f"Batch {log.batch_number}/{log.total_batches} - "
            f"{len(log.sentences)} sentences -> {len(log.claim_results)} claims",
            expanded=False,
        ):
            st.markdown(_render_batch_log_html(log), unsafe_allow_html=True)


def _render_complete_response_section(result) -> None:
    """The full picture once every batch is done: system prompt used, every
    batch's raw Claude response concatenated in order, and the final
    aggregated claims JSON - the "complete response" across the whole essay."""
    with st.expander("Complete Response (all batches combined)", expanded=False):
        if not result.batch_logs:
            st.markdown("(No data)")
            return

        st.markdown(
            '<div style="font-family:\'Inter\',sans-serif;font-size:.75em;font-weight:700;'
            'letter-spacing:.05em;text-transform:uppercase;color:rgba(255,255,255,.4);'
            'margin-bottom:6px">System prompt (used for every batch)</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<pre style="font-family:\'Fira Code\',monospace;font-size:.76em;line-height:1.6;'
            f'background:rgba(0,0,0,0.3);padding:14px 18px;border-radius:8px;color:#b0bec5;'
            f'border:1px solid rgba(255,255,255,0.06);white-space:pre-wrap;word-break:break-word;'
            f'max-height:260px;overflow-y:auto">{_html.escape(result.batch_logs[0].system_prompt)}</pre>',
            unsafe_allow_html=True,
        )

        combined_raw = "\n\n".join(
            f"-- Batch {log.batch_number}/{log.total_batches} raw response --\n{log.raw_response}"
            for log in result.batch_logs
        )
        st.markdown(
            '<div style="font-family:\'Inter\',sans-serif;font-size:.75em;font-weight:700;'
            'letter-spacing:.05em;text-transform:uppercase;color:rgba(255,255,255,.4);'
            'margin:16px 0 6px 0">All batch responses (concatenated, in order)</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<pre style="font-family:\'Fira Code\',monospace;font-size:.76em;line-height:1.6;'
            f'background:rgba(0,0,0,0.3);padding:14px 18px;border-radius:8px;color:#80cbc4;'
            f'border:1px solid rgba(255,255,255,0.06);white-space:pre-wrap;word-break:break-word;'
            f'max-height:400px;overflow-y:auto">{_html.escape(combined_raw)}</pre>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div style="font-family:\'Inter\',sans-serif;font-size:.75em;font-weight:700;'
            'letter-spacing:.05em;text-transform:uppercase;color:rgba(255,255,255,.4);'
            'margin:16px 0 6px 0">Final aggregated claims (JSON)</div>',
            unsafe_allow_html=True,
        )
        st.json([
            {
                "batch_number":        c.batch_number,
                "claim_sinhala":       c.claim_sinhala,
                "claim_type":          c.claim_type,
                "verdict":             c.verdict,
                "unverifiable_reason": c.unverifiable_reason,
                "matched_kg_fact":     c.matched_kg_fact,
                "explanation":         c.explanation,
                "teacher_feedback":    c.teacher_feedback,
            }
            for c in result.all_claim_results
        ])


def _render_essay_text_section(essay_text: str) -> None:
    st.markdown('<div class="kg-section-title">Essay Text</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-family:\'Noto Sans Sinhala\',sans-serif;font-size:1em;'
        f'line-height:1.9;color:#f0f2f6;white-space:pre-wrap">{_html.escape(essay_text)}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)


def _render_full_result(essay_text: str, result, key_suffix: str) -> None:
    """Raw essay followed by the complete result - shared by the live
    Results tab and the History tab so a past check looks exactly like it
    did when it was first run."""
    _render_essay_text_section(essay_text)
    st.markdown("<br>", unsafe_allow_html=True)

    _render_summary_card(result)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_kings_section(result)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_corrections_section(result)
    st.markdown("<br>", unsafe_allow_html=True)

    selected_categories = _render_category_filter(key_suffix=key_suffix)

    _render_claims_section(result, selected_categories)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_summary_table(result, selected_categories)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_kg_gap_worklist(result)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_batch_logs_section(result)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_complete_response_section(result)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_raw_facts_section(result)


def _render_results_tab() -> None:
    result = st.session_state.get("essay_result")
    if result is None:
        st.info("Enter an essay in the 'Input' tab and check it first.")
        return

    essay_text = st.session_state.get("essay_checked_text", "")
    _render_full_result(essay_text, result, key_suffix="live")


# History tab - reload past essay checks from MongoDB

def _rebuild_result_from_doc(doc: dict):
    """Reconstruct an AccuracyResult (with ClaimResult/BatchLog objects) from
    a MongoDB document saved by mongo_store.save_essay_check_run().

    Backward compatible with records saved before claim_type /
    unverifiable_reason existed: per-claim fields default to the safest
    prior assumption (claim_type="FACTUAL", reason=None), and the
    AccuracyResult-level counts fall back to their pre-taxonomy
    equivalents (total_factual_claims -> total_claims, kg_gap_claims ->
    unverifiable_claims) rather than silently zeroing out.
    """
    from essay_accuracy_checker import AccuracyResult, BatchLog, ClaimResult

    def _claim(d: dict) -> ClaimResult:
        return ClaimResult(
            claim_sinhala=d.get("claim_sinhala", ""),
            claim_type=d.get("claim_type", "FACTUAL"),
            verdict=d.get("verdict", "UNVERIFIABLE"),
            unverifiable_reason=d.get("unverifiable_reason"),
            matched_kg_fact=d.get("matched_kg_fact", "N/A"),
            explanation=d.get("explanation", ""),
            teacher_feedback=d.get("teacher_feedback"),
            batch_number=d.get("batch_number", 0),
        )

    def _batch(d: dict) -> BatchLog:
        return BatchLog(
            batch_number=d.get("batch_number", 0),
            total_batches=d.get("total_batches", 0),
            sentences=d.get("sentences", []),
            system_prompt=d.get("system_prompt", ""),
            user_message=d.get("user_message", ""),
            raw_response=d.get("raw_response", ""),
            parse_retried=d.get("parse_retried", False),
            claim_results=[_claim(c) for c in d.get("claim_results", [])],
        )

    total_claims = doc.get("total_claims", 0)
    unverifiable_claims = doc.get("unverifiable_claims", 0)

    return AccuracyResult(
        essay_subject=doc.get("essay_subject", ""),
        all_kings_found=doc.get("all_kings_found", []),
        accuracy_score=doc.get("accuracy_score"),
        coverage_ratio=doc.get("coverage_ratio", 0.0),
        confidence_level=doc.get("confidence_level", ""),
        coverage_warning=doc.get("coverage_warning", False),
        total_claims=total_claims,
        total_factual_claims=doc.get("total_factual_claims", total_claims),
        editorial_claims=doc.get("editorial_claims", 0),
        correct_claims=doc.get("correct_claims", 0),
        incorrect_claims=doc.get("incorrect_claims", 0),
        unverifiable_claims=unverifiable_claims,
        kg_gap_claims=doc.get("kg_gap_claims", unverifiable_claims),
        not_factual_claims=doc.get("not_factual_claims", 0),
        kg_facts_used=doc.get("kg_facts_used", 0),
        batch_count=doc.get("batch_count", 0),
        essay_sentence_count=doc.get("essay_sentence_count", 0),
        all_claim_results=[_claim(c) for c in doc.get("all_claim_results", [])],
        batch_logs=[_batch(b) for b in doc.get("batch_logs", [])],
        kg_facts_text=doc.get("kg_facts_text", ""),
    )


def _render_history_tab() -> None:
    try:
        import mongo_store
    except ImportError:
        st.error("pymongo is not installed. Run: pip install pymongo")
        return

    stats = mongo_store.get_essay_run_stats()
    if "error" in stats:
        st.warning(f"MongoDB not reachable: {stats['error']}")
        st.info("Set MONGO_URI and MONGO_DB in your .env and make sure MongoDB is running.")
        return

    st.markdown('<div class="kg-section-title">Overview</div>', unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    avg_score = stats.get("avg_accuracy_score")
    for col, val, label, color in [
        (m1, stats.get("total_runs", 0), "Total Checks", "#7986cb"),
        (m2, f"{avg_score:.1f}" if avg_score is not None else "N/A", "Average Score", "#81c784"),
        (m3, stats.get("total_claims", 0), "Total Claims Evaluated", "#ffb74d"),
    ]:
        col.markdown(
            f'<div class="kg-metric-card">'
            f'<div class="kg-metric-value" style="color:{color}">{val}</div>'
            f'<div class="kg-metric-label">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown("<br>", unsafe_allow_html=True)

    runs = mongo_store.get_recent_essay_runs(limit=100)
    if not runs:
        st.info("No essay checks saved yet.")
        return

    st.markdown('<div class="kg-section-title">Past Essay Checks</div>', unsafe_allow_html=True)
    st.markdown(_CARD_OPEN, unsafe_allow_html=True)

    search = st.text_input(
        "Filter by essay text or king name",
        key="essay_hist_search",
    )

    import pandas as pd

    rows = []
    for r in runs:
        text = r.get("essay_text", "")
        subj = r.get("essay_subject", "")
        if search and search.lower() not in text.lower() and search.lower() not in subj.lower():
            continue
        ts = r.get("timestamp", "")[:19].replace("T", "  ")
        score = r.get("accuracy_score")
        rows.append({
            "_id":           r["_id"],
            "Timestamp":     ts,
            "King":          subj,
            "Score":         f"{score:.1f}" if score is not None else "N/A",
            "Claims":        r.get("total_claims", 0),
            "Essay preview": (text[:70] + "...") if len(text) > 70 else text,
        })

    if not rows:
        st.info("No runs match the filter.")
        st.markdown(_CARD_CLOSE, unsafe_allow_html=True)
        return

    df = pd.DataFrame(rows)
    ids = df["_id"].tolist()
    st.dataframe(df.drop(columns=["_id"]), width="stretch", hide_index=True)

    selected_id = st.selectbox(
        "Select a run to view in full",
        options=ids,
        format_func=lambda rid: next(
            (r["Timestamp"] + "  -  " + (r["King"] or "?") for r in rows if r["_id"] == rid), rid
        ),
        key="essay_hist_selected",
    )
    st.markdown(_CARD_CLOSE, unsafe_allow_html=True)

    if not selected_id:
        return

    st.markdown("<br>", unsafe_allow_html=True)
    doc = mongo_store.get_essay_run_by_id(selected_id)
    if not doc:
        st.warning("Could not load run details.")
        return

    result = _rebuild_result_from_doc(doc)
    _render_full_result(doc.get("essay_text", ""), result, key_suffix=f"hist_{selected_id}")


# Page entry point

def render() -> None:
    st.markdown("""
    <div class="kg-page-title">Essay Accuracy Checker</div>
    <div class="kg-page-subtitle">
      Verifies a student's Sinhala historical essay against Knowledge Graph facts
      using Claude AI, and produces a structured accuracy score.
    </div>
    """, unsafe_allow_html=True)

    for k, v in [
        ("essay_result",       None),
        ("essay_checked_text", ""),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    tab_input, tab_results, tab_history = st.tabs(["Input", "Results", "History"])

    with tab_input:
        _render_input_tab()

    with tab_results:
        _render_results_tab()

    with tab_history:
        _render_history_tab()
