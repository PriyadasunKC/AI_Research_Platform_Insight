"""
tests/test_pipeline_integration.py — Integration smoke tests

These tests mock the NER model and DeepSeek API so they run offline.
They verify the full pipeline flow: NER output → extractor → validated triples.

Run with:
    pytest tests/test_pipeline_integration.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relation_extractor import _parse_response, _validate_and_normalize
from ner_pipeline import NERTag


# ─────────────────────────────────────────────────────────────────────────────
# _parse_response tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParseResponse:

    def test_clean_json_array(self):
        raw = '[{"subject":"දුටුගැමුණු","relation":"BUILT","object":"රුවන්වැලිසෑය","period":""}]'
        result = _parse_response(raw)
        assert len(result) == 1
        assert result[0]["relation"] == "BUILT"

    def test_markdown_fenced_json(self):
        raw = '```json\n[{"subject":"එළාර","relation":"RULED","object":"අනුරාධපුරය","period":""}]\n```'
        result = _parse_response(raw)
        assert len(result) == 1
        assert result[0]["subject"] == "එළාර"

    def test_empty_array(self):
        assert _parse_response("[]") == []
        assert _parse_response("[ ]") == []

    def test_single_object_wrapped(self):
        raw = '{"subject":"දේවානම්පිය","relation":"BUILT","object":"ඉශුරුමුණිය","period":""}'
        result = _parse_response(raw)
        assert len(result) == 1

    def test_empty_string(self):
        assert _parse_response("") == []

    def test_multiple_triples(self):
        raw = (
            '[{"subject":"දුටුගැමුණු","relation":"DEFEATED","object":"එළාර","period":""},'
            '{"subject":"දුටුගැමුණු","relation":"BUILT","object":"රුවන්වැලිසෑය","period":""}]'
        )
        result = _parse_response(raw)
        assert len(result) == 2


# ─────────────────────────────────────────────────────────────────────────────
# _validate_and_normalize tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateAndNormalize:

    def _make_tags(self, *pairs):
        """Helper: make NERTag list from (entity, label) pairs."""
        return [NERTag(entity=e, label=l) for e, l in pairs]

    def test_valid_triple_passes(self):
        tags = self._make_tags(
            ("දුටුගැමුණු", "PERSON_KING"),
            ("රුවන්වැලිසෑය", "MONUMENT"),
        )
        raw = [{"subject": "දුටුගැමුණු", "relation": "BUILT", "object": "රුවන්වැලිසෑය", "period": ""}]
        result = _validate_and_normalize(raw, tags)
        assert len(result) == 1
        assert result[0]["relation"] == "BUILT"

    def test_date_era_as_subject_discarded(self):
        tags = self._make_tags(
            ("ක්‍රි.පූ. 3 වන සියවස", "DATE_ERA"),
            ("අනුරාධපුරය", "LOCATION"),
        )
        raw = [{"subject": "ක්‍රි.පූ. 3 වන සියවස", "relation": "LOCATED_IN", "object": "අනුරාධපුරය", "period": ""}]
        result = _validate_and_normalize(raw, tags)
        assert result == []

    def test_date_era_goes_to_period_field(self):
        tags = self._make_tags(
            ("ක්‍රි.පූ. 2 වැනි සියවස", "DATE_ERA"),
            ("එළාර", "PERSON_KING"),
            ("අනුරාධපුරය", "LOCATION"),
        )
        raw = [{"subject": "එළාර", "relation": "RULED", "object": "අනුරාධපුරය", "period": "ක්‍රි.පූ. 2 වැනි සියවස"}]
        result = _validate_and_normalize(raw, tags)
        assert len(result) == 1
        assert result[0]["period"] == "ක්‍රි.පූ. 2 වැනි සියවස"
        assert result[0]["subject"] != "ක්‍රි.පූ. 2 වැනි සියවස"

    def test_invalid_relation_discarded(self):
        tags = self._make_tags(
            ("දුටුගැමුණු", "PERSON_KING"),
            ("රුවන්වැලිසෑය", "MONUMENT"),
        )
        raw = [{"subject": "දුටුගැමුණු", "relation": "INVENTED", "object": "රුවන්වැලිසෑය", "period": ""}]
        result = _validate_and_normalize(raw, tags)
        assert result == []

    def test_entity_not_in_ner_list_discarded(self):
        tags = self._make_tags(
            ("දුටුගැමුණු", "PERSON_KING"),
            ("රුවන්වැලිසෑය", "MONUMENT"),
        )
        # "සීගිරිය" is NOT in the NER tags
        raw = [{"subject": "දුටුගැමුණු", "relation": "BUILT", "object": "සීගිරිය", "period": ""}]
        result = _validate_and_normalize(raw, tags)
        assert result == []

    def test_lowercase_relation_normalized(self):
        tags = self._make_tags(
            ("දුටුගැමුණු", "PERSON_KING"),
            ("රුවන්වැලිසෑය", "MONUMENT"),
        )
        raw = [{"subject": "දුටුගැමුණු", "relation": "built", "object": "රුවන්වැලිසෑය", "period": ""}]
        result = _validate_and_normalize(raw, tags)
        assert len(result) == 1
        assert result[0]["relation"] == "BUILT"

    def test_alias_entity_normalized(self):
        tags = self._make_tags(
            ("දේවානම්පිය", "PERSON_KING"),   # alias form
            ("ඉශුරුමුණිය", "MONUMENT"),
        )
        raw = [{"subject": "දේවානම්පිය", "relation": "BUILT", "object": "ඉශුරුමුණිය", "period": ""}]
        result = _validate_and_normalize(raw, tags)
        assert len(result) == 1
        assert result[0]["subject"] == "දේවානම්පිය තිස්ස"

    def test_empty_raw_list(self):
        tags = self._make_tags(("දුටුගැමුණු", "PERSON_KING"), ("එළාර", "PERSON_KING"))
        assert _validate_and_normalize([], tags) == []
