"""
tests/test_normalizer.py — Unit tests for normalizer.py

Run with:
    pytest tests/test_normalizer.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from normalizer import (
    ALLOWED_RELATIONS,
    normalize_entity,
    normalize_relation,
    normalize_triple,
)


# ─────────────────────────────────────────────────────────────────────────────
# Entity normalization tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeEntity:

    def test_canonical_form_unchanged(self):
        assert normalize_entity("දුටුගැමුණු") == "දුටුගැමුණු"

    def test_alias_short_form(self):
        assert normalize_entity("දේවානම්පිය") == "දේවානම්පිය තිස්ස"

    def test_alias_with_title_suffix(self):
        # "දේවානම්පිය රජු" → strip " රජු" → "දේවානම්පිය" → lookup → canonical
        assert normalize_entity("දේවානම්පිය රජු") == "දේවානම්පිය තිස්ස"

    def test_alias_monk(self):
        assert normalize_entity("මිහිදු") == "මිහිඳු හිමි"

    def test_alias_english(self):
        assert normalize_entity("Dutugamunu") == "දුටුගැමුණු"

    def test_unknown_entity_returned_as_is(self):
        assert normalize_entity("නිශ්ශංකමල්ල") == "නිශ්ශංකමල්ල"

    def test_empty_string(self):
        assert normalize_entity("") == ""

    def test_whitespace_trimmed(self):
        assert normalize_entity("  දේවානම්පිය  ") == "දේවානම්පිය තිස්ස"

    def test_kashyapa_inflected(self):
        assert normalize_entity("කාශ්‍යපගේ") == "කාශ්‍යප රජු"


# ─────────────────────────────────────────────────────────────────────────────
# Relation normalization tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeRelation:

    def test_canonical_relation_unchanged(self):
        for rel in ALLOWED_RELATIONS:
            assert normalize_relation(rel) == rel

    def test_lowercase_variant(self):
        assert normalize_relation("built") == "BUILT"
        assert normalize_relation("ruled") == "RULED"
        assert normalize_relation("defeated") == "DEFEATED"

    def test_english_synonym(self):
        assert normalize_relation("conquered") == "DEFEATED"
        assert normalize_relation("constructed") == "BUILT"
        assert normalize_relation("governs") == "RULED"
        assert normalize_relation("deposed") == "REMOVED_FROM"

    def test_underscore_case_insensitive(self):
        assert normalize_relation("belonged_to") == "BELONGED_TO"
        assert normalize_relation("BELONGED_TO") == "BELONGED_TO"

    def test_unknown_relation_returns_none(self):
        assert normalize_relation("INVENTED") is None
        assert normalize_relation("unknown_relation") is None
        assert normalize_relation("") is None

    def test_surface_form_with_space(self):
        # "won by" → "won_by" → WON_BY
        assert normalize_relation("won by") == "WON_BY"


# ─────────────────────────────────────────────────────────────────────────────
# normalize_triple tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeTriple:

    def test_valid_triple(self):
        raw = {
            "subject":  "දුටුගැමුණු",
            "relation": "BUILT",
            "object":   "රුවන්වැලිසෑය",
            "period":   "",
        }
        result = normalize_triple(raw)
        assert result is not None
        assert result["subject"]  == "දුටුගැමුණු"
        assert result["relation"] == "BUILT"
        assert result["object"]   == "රුවන්වැලිසෑය"

    def test_alias_entity_normalized(self):
        raw = {
            "subject":  "දේවානම්පිය",    # alias
            "relation": "built",         # lowercase variant
            "object":   "ඉශුරුමුණිය",
            "period":   "",
        }
        result = normalize_triple(raw)
        assert result is not None
        assert result["subject"]  == "දේවානම්පිය තිස්ස"
        assert result["relation"] == "BUILT"

    def test_invalid_relation_returns_none(self):
        raw = {
            "subject":  "දුටුගැමුණු",
            "relation": "INVENTED",
            "object":   "රුවන්වැලිසෑය",
            "period":   "",
        }
        assert normalize_triple(raw) is None

    def test_empty_subject_returns_none(self):
        raw = {"subject": "", "relation": "BUILT", "object": "රුවන්වැලිසෑය", "period": ""}
        assert normalize_triple(raw) is None

    def test_period_field_preserved(self):
        raw = {
            "subject":  "එළාර",
            "relation": "RULED",
            "object":   "අනුරාධපුරය",
            "period":   "ක්‍රි.පූ. 2 වැනි සියවස",
        }
        result = normalize_triple(raw)
        assert result is not None
        assert result["period"] == "ක්‍රි.පූ. 2 වැනි සියවස"

    def test_missing_period_defaults_to_empty(self):
        raw = {"subject": "දුටුගැමුණු", "relation": "BUILT", "object": "රුවන්වැලිසෑය"}
        result = normalize_triple(raw)
        assert result is not None
        assert result["period"] == ""
