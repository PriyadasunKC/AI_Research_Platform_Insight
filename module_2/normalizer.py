
from __future__ import annotations

ALLOWED_RELATIONS: frozenset[str] = frozenset({
    "RULED",        "BUILT",          "DEFEATED",      "BELONGED_TO",
    "LOCATED_IN",   "SON_OF",         "CONVERTED",     "ARRIVED_AT",
    "ORDAINED",     "CAPITAL_OF",     "BUILT_BY",      "DEDICATED_TO",
    "RULED_BY",     "DESCENDED_FROM", "FOUGHT_BY",     "FOUGHT_AT",
    "WON_BY",       "REMOVED_FROM",   "APPOINTED_AS",  "MARRIED",
    "BROTHER_OF",   "SERVED",
})

RELATION_SURFACE_MAP: dict[str, str] = {
    "ruled":            "RULED",
    "built":            "BUILT",
    "defeated":         "DEFEATED",
    "belonged_to":      "BELONGED_TO",
    "located_in":       "LOCATED_IN",
    "son_of":           "SON_OF",
    "converted":        "CONVERTED",
    "arrived_at":       "ARRIVED_AT",
    "ordained":         "ORDAINED",
    "capital_of":       "CAPITAL_OF",
    "built_by":         "BUILT_BY",
    "dedicated_to":     "DEDICATED_TO",
    "ruled_by":         "RULED_BY",
    "descended_from":   "DESCENDED_FROM",
    "fought_by":        "FOUGHT_BY",
    "fought_at":        "FOUGHT_AT",
    "won_by":           "WON_BY",
    "removed_from":     "REMOVED_FROM",
    "appointed_as":     "APPOINTED_AS",
    "married":          "MARRIED",
    "brother_of":       "BROTHER_OF",
    "served":           "SERVED",
    "governs":          "RULED",
    "governed":         "RULED",
    "reign":            "RULED",
    "reigned":          "RULED",
    "reigns_over":      "RULED",
    "rules":            "RULED",
    "rules_over":       "RULED",
    "constructed":      "BUILT",
    "construct":        "BUILT",
    "erected":          "BUILT",
    "erect":            "BUILT",
    "built_at":         "BUILT",
    "established":      "BUILT",
    "founded":          "BUILT",
    "conquered":        "DEFEATED",
    "conquer":          "DEFEATED",
    "beat":             "DEFEATED",
    "overthrew":        "DEFEATED",
    "overthrown_by":    "DEFEATED",
    "vanquished":       "DEFEATED",
    "belongs_to":       "BELONGED_TO",
    "member_of":        "BELONGED_TO",
    "part_of":          "BELONGED_TO",
    "affiliated_with":  "BELONGED_TO",
    "situated_in":      "LOCATED_IN",
    "found_in":         "LOCATED_IN",
    "is_in":            "LOCATED_IN",
    "resides_in":       "LOCATED_IN",
    "lies_in":          "LOCATED_IN",
    "child_of":         "SON_OF",
    "daughter_of":      "SON_OF",
    "offspring_of":     "SON_OF",
    "converted_by":     "CONVERTED",
    "converts":         "CONVERTED",
    "arrived":          "ARRIVED_AT",
    "visited":          "ARRIVED_AT",
    "came_to":          "ARRIVED_AT",
    "traveled_to":      "ARRIVED_AT",
    "became_monk":      "ORDAINED",
    "ordained_as":      "ORDAINED",
    "capital":          "CAPITAL_OF",
    "serves_as_capital":"CAPITAL_OF",
    "dedicated":        "DEDICATED_TO",
    "consecrated_to":   "DEDICATED_TO",
    "descend_from":     "DESCENDED_FROM",
    "descendant_of":    "DESCENDED_FROM",
    "lineage_of":       "DESCENDED_FROM",
    "fought":           "FOUGHT_BY",
    "participated_in":  "FOUGHT_BY",
    "participated":     "FOUGHT_BY",
    "won":              "WON_BY",
    "winner":           "WON_BY",
    "victory_at":       "WON_BY",
    "removed":          "REMOVED_FROM",
    "deposed":          "REMOVED_FROM",
    "expelled":         "REMOVED_FROM",
    "banished":         "REMOVED_FROM",
    "appointed":        "APPOINTED_AS",
    "named_as":         "APPOINTED_AS",
    "wed":              "MARRIED",
    "wedded":           "MARRIED",
    "spouse_of":        "MARRIED",
    "sibling_of":       "BROTHER_OF",
    "sister_of":        "BROTHER_OF",
    "brother":          "BROTHER_OF",
    "siblings":         "BROTHER_OF",
    "serve":            "SERVED",
    "serves":           "SERVED",
    "serving":          "SERVED",
    "worked_for":       "SERVED",
}

ENTITY_ALIAS_MAP: dict[str, str] = {
    "දුටු ගැමුණු":              "දුටුගැමුණු",
    "දුටුගැමුනු":               "දුටුගැමුණු",
    "දුටගැමුණු":                "දුටුගැමුණු",
    "ගැමිණි":                   "දුටුගැමුණු",
    "ගැමුණු රජු":               "දුටුගැමුණු",
    "දුටුගැමුණු රජු":           "දුටුගැමුණු",
    "දේවානම්පිය":               "දේවානම්පිය තිස්ස",
    "දේවානම්පිය රජු":           "දේවානම්පිය තිස්ස",
    "දේවනම්පිය":                "දේවානම්පිය තිස්ස",
    "දේවනම්පිය තිස්ස":          "දේවානම්පිය තිස්ස",
    "කාශ්‍යප":                  "කාශ්‍යප රජු",
    "කාශ්‍යපගේ":                "කාශ්‍යප රජු",
    "කශ්‍යප":                   "කාශ්‍යප රජු",
    "කශ්‍යපගේ":                 "කාශ්‍යප රජු",
    "එළාර":                     "එළාර රජු",
    "එළාර රාජ":                 "එළාර රජු",
    "එළාරගේ":                   "එළාර රජු",
    "කාවන්තිස්ස":               "කාවන්තිස්ස රජු",
    "කාවන්තිස්ස රාජ":           "කාවන්තිස්ස රජු",
    "කාවන්තිස්සගේ":             "කාවන්තිස්ස රජු",
    "පරාක්‍රමබාහු":             "පරාක්‍රමබාහු රජු",
    "පරාකුම්බා":                "පරාක්‍රමබාහු රජු",
    "පරාක්‍රමබාහුගේ":           "පරාක්‍රමබාහු රජු",
    "විජය රජු":                 "විජය",
    "විජයගේ":                   "විජය",
    "මිහිදු":                   "මිහිඳු හිමි",
    "මිහිඳු":                   "මිහිඳු හිමි",
    "මිහිඳු හාමුදුරුවෝ":        "මිහිඳු හිමි",
    "මිහිඳු හාමුදුරුවන්":       "මිහිඳු හිමි",
    "මිහිදු හාමුදුරුවෝ":        "මිහිඳු හිමි",
    "මිහිඳුගේ":                 "මිහිඳු හිමි",
    "සංඝමිත්තා":                "සංඝමිත්තා හිමිණිය",
    "සංගමිත්තා":                "සංඝමිත්තා හිමිණිය",
    "සංඝමිත්තාගේ":              "සංඝමිත්තා හිමිණිය",
    "විහාරමහාදේවි":             "විහාරමහාදේවී",
    "විහාරමහාදේවිගේ":           "විහාරමහාදේවී",
    "විහාරමහාදේවීගේ":           "විහාරමහාදේවී",
    "කොනප්පු බණ්ඩාර":           "ශ්‍රී වික්‍රම රාජසිංහ",
    "රාජසිංහ":                  "ශ්‍රී වික්‍රම රාජසිංහ",
    "ශ්‍රී වික්‍රම රාජසිංහගේ":  "ශ්‍රී වික්‍රම රාජසිංහ",
    "ලංකාව":                    "ශ්‍රී ලංකාව",
    "ලංකා":                     "ශ්‍රී ලංකාව",
    "පණ්ඩු කාභය":               "පණ්ඩුකාභය",
    "පණ්ඩුකාභයගේ":              "පණ්ඩුකාභය",
    "පාණ්ඩුකාභය":               "පණ්ඩුකාභය",
    "පඬුවස්දෙව්":               "පඬුවස්දෙව් රජු",
    "පඬුවස්දෙව්ගේ":             "පඬුවස්දෙව් රජු",
    "අනුරා":                    "අනුරාධපුරය",
    "අනුරාධ":                   "අනුරාධපුරය",
    "අනුරාධපුරේ":               "අනුරාධපුරය",
    "අනුරාධපුරෙහි":             "අනුරාධපුරය",
    "රුවන් වැලිසෑය":            "රුවන්වැලිසෑය",
    "රුවන්වෑලිසෑය":             "රුවන්වැලිසෑය",
    "රුවන්වැලිසෑයේ":            "රුවන්වැලිසෑය",
    "ඉශුරුමුනිය":               "ඉශුරුමුණිය",
    "ඉශුරුමුණිය වෙහෙර":         "ඉශුරුමුණිය",
    "තුපාරාමය":                 "තූපාරාමය",
    "තූපාරාමේ":                 "තූපාරාමය",
    "තූපාරාම":                  "තූපාරාමය",
    "සිගිරි":                   "සීගිරිය",
    "සිගිරිය":                  "සීගිරිය",
    "සීගිරියේ":                 "සීගිරිය",
    "පොළොන්නරු":                "පොළොන්නරුව",
    "පොළොන්නරුවේ":              "පොළොන්නරුව",
    "පොළොන්නරු නුවර":           "පොළොන්නරුව",
    "රුහුණේ":                   "රුහුණ",
    "රුහුණු":                   "රුහුණ",
    "ලම්බකර්ණ":                 "ලම්බකර්ණ රාජ වංශය",
    "ලම්බකාර්ණ":                "ලම්බකර්ණ රාජ වංශය",
    "මහාවංශ":                   "මහාවංශය",
    "මහාවංශයේ":                 "මහාවංශය",
    "දළදා":                     "දළදා මාළිගාව",
    "දළදා මාළිගා":              "දළදා මාළිගාව",
    "උපතිස්ස":                  "උපතිස්ස නුවර",
    "උපතිස්සනුවර":              "උපතිස්ස නුවර",
}

_TITLE_SUFFIXES: tuple[str, ...] = (
    " රජු", " රාජ", " රාජා",
    " හිමි", " හාමුදුරුවෝ", " හාමුදුරුවන්", " හිමිණිය",
    " ආචාර්ය",
    "ගේ",
    "ෙහි",
)


def normalize_entity(name: str) -> str:
    """Return canonical Sinhala entity name, or the name unchanged if not in alias dict."""
    name = name.strip()
    if not name:
        return name
    if name in ENTITY_ALIAS_MAP:
        return ENTITY_ALIAS_MAP[name]
    for suffix in _TITLE_SUFFIXES:
        candidate = name.removesuffix(suffix).strip()
        if candidate != name and candidate in ENTITY_ALIAS_MAP:
            return ENTITY_ALIAS_MAP[candidate]
    return name


def normalize_relation(rel: str) -> str | None:
    """Return canonical relation string, or None if unmappable."""
    rel = rel.strip()
    if not rel:
        return None
    if rel in ALLOWED_RELATIONS:
        return rel
    upper = rel.upper()
    if upper in ALLOWED_RELATIONS:
        return upper
    lower = rel.lower()
    if lower in RELATION_SURFACE_MAP:
        return RELATION_SURFACE_MAP[lower]
    underscore = lower.replace(" ", "_")
    if underscore in RELATION_SURFACE_MAP:
        return RELATION_SURFACE_MAP[underscore]
    return None


def normalize_triple(triple: dict) -> dict | None:
    """Normalize subject, relation and object in a raw triple dict. Returns None if invalid."""
    subject  = normalize_entity(triple.get("subject",  "").strip())
    obj      = normalize_entity(triple.get("object",   "").strip())
    relation = normalize_relation(triple.get("relation", "").strip())
    period   = triple.get("period", "").strip()
    if not subject or not obj or relation is None:
        return None
    return {"subject": subject, "relation": relation, "object": obj, "period": period}