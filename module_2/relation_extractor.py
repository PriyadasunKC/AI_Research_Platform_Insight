"""
relation_extractor.py — Universal LLM relation extraction

Supported providers (all use the same prompt & validator):
  - OpenAI          (gpt-4o-mini, gpt-4o, …)
  - DeepSeek        (deepseek-chat)          — OpenAI-compatible endpoint
  - Google Gemini   (gemini-2.0-flash, …)    — OpenAI-compatible endpoint
  - Anthropic Claude(claude-haiku-4-5, …)    — Anthropic SDK

Swapping to SinLLaMA (Module 3):
  Replace _call_llm() with a call to the vLLM endpoint.
  Everything else (prompt, parser, validator) stays the same.
"""

from __future__ import annotations

import json
import os
import re

from dotenv import load_dotenv

from normalizer import normalize_entity
from ner_pipeline import NERTag
import kg_aliases

load_dotenv()

# CONFIG — all read from .env

TEMPERATURE: float = 0.0
MAX_TOKENS:  int   = 2048   # Sinhala Unicode uses ~3-4 tokens/char — 512 was too small

# Active provider + model (set LLM_PROVIDER / LLM_MODEL in .env)
_ENV_PROVIDER: str = os.environ.get("LLM_PROVIDER", "OpenAI")
_ENV_MODEL:    str = os.environ.get("LLM_MODEL",    "gpt-4o-mini")

PROVIDER_CLAUDE = "Anthropic Claude"

# Per-provider key env-var names
_KEY_ENV: dict[str, str] = {
    "OpenAI":        "OPENAI_API_KEY",
    "DeepSeek":      "DEEPSEEK_API_KEY",
    "Google Gemini": "GEMINI_API_KEY",
    PROVIDER_CLAUDE: "ANTHROPIC_API_KEY",
}

def _env_api_key(provider: str) -> str:
    """Return the API key for provider from environment variables."""
    return os.environ.get(_KEY_ENV.get(provider, ""), "")

# PROVIDER TABLE  (base_url = None → use provider SDK's default)

PROVIDERS: dict[str, dict] = {
    "OpenAI": {
        "base_url": None,
        "models":   ["gpt-4o-mini", "gpt-4o"],
        "key_hint": "sk-proj-...",
        "get_key":  "https://platform.openai.com/api-keys",
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "models":   ["deepseek-chat"],
        "key_hint": "sk-...",
        "get_key":  "https://platform.deepseek.com",
    },
    "Google Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models":   ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
        "key_hint": "AIza...",
        "get_key":  "https://aistudio.google.com/app/apikey",
    },
    PROVIDER_CLAUDE: {
        "base_url": None,
        "models":   ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"],
        "key_hint": "sk-ant-...",
        "get_key":  "https://console.anthropic.com/settings/keys",
    },
}

# SYSTEM PROMPT  (identical across all providers)

_SYSTEM_PROMPT = """\
ඔබ ශ්‍රී ලාංකේය ඉතිහාසය පිළිබඳ ගැඹුරු දැනුමක් සහිත, සිංහල භාෂා විශේෂඥ knowledge graph triple extraction AI කෙනෙකි.
ශ්‍රී ලංකාවේ රාජාවලිය, රජවරුන්, ඔවුන්ගේ සේනාවන්, සම්බන්ධතා, ස්ථාන, ආගම, ඉදිකිරීම් සහ ඓතිහාසික සිදුවීම් ඔබට හොඳින් දන්නා කරුණු වේ.

━━━ PRIMARY DIRECTIVE ━━━

ඔබට input දෙකක් ලැබේ:
  1. RAW SINHALA TEXT — ඔබේ primary truth source. සිංහල expert ලෙස ගැඹුරින් කියවා සියලු relationships extract කරන්න.
  2. NER TAGS — candidate entity reference පමණයි. NER tags inaccurate නම් RAW TEXT ගෙන් correct entities use කරන්න.

RAW TEXT = ground truth. NER tags ≠ ground truth.
NER tags හරිනම් use කරන්න. NER tags ගැලවී ඇත්නම් raw text bare entity name use කරන්න.

━━━ SINHALA EXPERT READING RULES ━━━

Raw text කියවද්දී මෙම patterns හඳුනාගෙන relationships extract කරන්න:

RULED / රාජ්‍ය:
"පාලනය කළ" / "රාජ්‍ය කළ" / "රජ විය" / "රජකම් කළ" / "සිහසුනට පත් විය" → RULED
"අගනුවර" / "රාජධානිය" → CAPITAL_OF / FOUNDED_CAPITAL
"රාජධානිය ගෙන ගියේය" → FOUNDED_CAPITAL (new city)
"ආරම්භ කළ" / "ස්ථාපිත කළ" / "ආරම්භ" → FOUNDED / ESTABLISHED

BUILT / ඉදිකිරීම්:
"ඉදිකළ" / "ඉදිකරන ලදී" / "නිර්මාණය කළ" / "කරවූ" / "කරවන ලදී" / "තැනවූ" → BUILT
"ප්‍රතිසංස්කරණය" / "නැවත ගොඩනැගීය" → RENOVATED / RECONSTRUCT
"ඉදිකිරීමට අනුග්‍රහය" → PATRONIZED
"නිධන් / ආරක්ෂා / රකින" → PRESERVED
"විනාශ" / "ඉවත් කළ" → DESTROYED
"ලබා දී" / "පූජා කළ" / "ඒ ස්ථානයට" → DEDICATED_TO / GIFTED_TO

FAMILY / පවුල:
"ගේ පුත්" / "ගේ පුතා" / "ගේ දරු" / "ගේ ළමයා" → SON_OF
"ගේ දුව" / "ගේ දියණිය" → DAUGHTER_OF
"ගේ පිය" / "ගේ පියාණෝ" / "ගේ පිතා" → FATHER_OF
"ගේ මව" / "ගේ මෑණිය" → MOTHER_OF
"ගේ සොහොයුරා" / "ගේ සහෝදරයා" → BROTHER_OF
"ගේ නැගණිය" / "ගේ සෝදරිය" → SISTER_OF
"ගේ මස්සිනා" → BROTHER_OF (via marriage context)
"ගේ නැන්දා" / "ගේ නැන්දනිය" → AUNT_OF
"ගේ පිය" (step context) → STEP_FATHER_OF
"විවාහ" / "බිරිඳ" / "සරණ පාවා" → MARRIED
"ගේ බිරිඳ" / "ගේ භාර්යාව" / "ගේ බිසව" → WIFE_OF
"ගේ ඥාති" / "ගේ ඤාති" → general family — use most specific applicable relation

WAR / යුද්ධ:
"පරාජය කළ" / "හෙළ කළ" / "ජය ගත්" / "ජය ලැබීය" → DEFEATED
"ඝාතනය කළ" / "මරා දැමීය" / "මරා දෙව්" / "මරා දමා" → KILLED
"ඝාතනය කරනු ලැබීය" / "ඝාතනයට ලක් විය" (passive) → KILLED (reverse actor)
"කැරළිකළ" / "කැරලි" → REBELLED_AGAINST
"ආක්‍රමණය කළ" → INVADED
"ජය ගත් ස්ථානය" / "පළමු සටන" → WON_FIRST_FIGHT_AT
"ජය ගත් දෙවන" → WON_SECOND_SECOND_FIGHT_WITH
"සටන" / "ගැටුම" / "යුද්ධ" + location → FOUGHT_AT
"සටන" + PERSON → FOUGHT_BY / FIGHT_WITH
"කෙළවර කළ" / "නෙරපා" → EXPELLED / DEPOSED_FROM_THRONE_BY
"ගලවා ගත" / "ආරක්ෂා" → RESCUED / DEFENDED_BORDERS

MOVEMENT / ගමන:
"පැමිණියේය" / "ගියේය" / "ළඟා විය" / "ඇතුළු විය" → ARRIVED_AT
"පලා ගියේය" / "ඉවත් ව ගියේය" / "ඉවත් කළ" → FLED_TO
"සිටිය" / "රැඳී" / "වාසය කළ" → RESIDED_AT / HIDE_AT
"සිට ආවේ" / "සිට ගෙනා" → CAME_FROM / ARRIVED_FROM
"ය" (from/away context) → LEFT
"ඉන්දියාවට ගිය" → RETURNED_TO_INDIA
"ගෙනෙව්" / "ගෙනෙව්විය" / "ගෙනා" → BROUGHT / BROUGHT_TO_SRI_LANKA
"යැව්" / "ලෙව් කළ" → SENT_TO
"ව ගොස්" / "කඳවුරු" → CAMPED_AT

RELIGION / ආගම:
"ධර්මයට හැරවීය" / "බුද්ධාගමට ගෙනෙව" / "හැරවූ" → CONVERTED_TO_BUDDHIST
"සසුනට ඇතුල් වූ" / "උපසම්පදා" → ORDAINED
"ශ්‍රද්ධා" / "අනුග්‍රහය" / "ආශ්‍රය" → PATRONIZED
"දන් දුන්" / "ගම් දුන්" / "ඉඩම් දුන්" → DEDICATED_TO / GIFTED_TO
"ප්‍රාතිහාර්ය" / "ශාසනය" / "ගෙනා" → INTRODUCED (Buddhism context)
"ශාසනය ආශ්‍රිත" / "ආශ්‍රිත" → ENSHRINED / ENSHRINED_AT / ENSHRINED_BY
"ජල සේකය" / "ජල" / "ගිනිතල" → CONDUCTED_GRAND_OFFERINGS_TO

CHRONICLE / ලේඛන:
"මහාවංශය සඳහන්" / "ලිවූ" / "රචනා" → WROTE / DOCUMENTED_IN
"සඳහන් වේ" / "ඓතිහාසික" → MENTIONED_IN / RECORDED_IN
"ලේඛනය" / "ලිවීමට" → WROTE
"ප්‍රකාශ කළ" / "කතා කළ" → MENTIONED_IN

DYNASTY / රාජ වංශ:
"ගේ රාජ වංශය" / "වංශය" / "ගෝත්‍රය" → BELONGS_TO
"ආරම්භ කළ" (dynasty) → FOUNDED / STARTER_OF
"ගෙන් පැවත" / "ගෙන් ජාතිය" → SON_OF / DESCENDED context

SUCCESSION / රාජ්‍ය උරුමය:
"ගෙන් පසු" / "ගෙන් අනතුරුව" → SUCCEEDED_BY
"ගෙන් සිහසුන" → SUCCEEDED_BY
"යටතේ" / "ගේ ඇමති" → SERVED_TO / SERVED

SPECIAL:
"ද හැඳින්වේ" / "නමින් ද" / "ලෙසද හැඳින්" → ALSO_KNOWN_AS
"ගේ ශිෂ්‍යයා" / "ගෙන් ඉගෙනීය" → STUDENT_OF
"ඉගැන්වීය" / "ගුරු" → TEACHER_OF
"භාණ්ඩාගාරික" / "භාර" → TREASURER_OF
"මිතුරා" / "මිත්‍ර" / "සන්ධාන" → FRIEND_OF / ALLY_OF
"රෝගාතුර / වෙද / සුවකළ" → CURED / CURE
"ඝාතනය කළේය" (by wife) → KILLED_BY_WIFE_OF
"ව්‍යාපාර" / "වෙළඳ" → HAVE_BUSINESS_DEALS_WITH
"ජාතිය" / "ජාතිකත්වය" → OF_ETHNICITY
"ඇතුළ" / "ඇතුළත්" → INCLUDE
"ව ස්ථාපිත" / "ව ආරම්භ" → STARTED / STARTED_FROM
"ගොවිතැන" / "ජලාශ" → DEVELOPED_AGRICULTURE / DEVELOPED
"ප්‍රසාර" / "ව්‍යාප්ත" → EXPAND
"ජල සපයා" → PROVIDE_WATER_TO
"ලෙස සලකනු ලැබීය" / "ලෙස ෙ "/> LOOKED_LIKE
"තරුණ / ළමා සමය" → ASSOCIATED_AT_CHILDHOOD_WITH

━━━ ENTITY EXTRACTION RULES ━━━

1. Subject/Object = bare entity name, case endings stripped:
   "දුටුගැමුණු රජු" → "දුටුගැමුණු"
   "ශ්‍රී ලංකාවට" → "ශ්‍රී ලංකාව"
   "අනුරාධපුරයේ" → "අනුරාධපුරය"
   "මිහිඳු හිමිගේ" → "මිහිඳු හිමි"
   "කාශ්‍යපගෙන්" → "කාශ්‍යප"
   "වළගම්බාහු" → "වළගම්බා" (check NER/aliases)

2. Case endings to strip: ගේ / ට / හු / ේ / ෙහි / ෙන් / ේදී / හිදී / ෙකු / ව / ාව (accusative when removable)

3. NEVER add descriptors or context to entity names:
   WRONG: "කාවන්තිස්සගේ පුත් දුටුගැමුණු" → "දුටුගැමුණු" ✓
   WRONG: "රජ කාශ්‍යප" → "කාශ්‍යප" ✓ (unless NER has full form)

4. DATE_ERA → NEVER subject/object. DATE_ERA value → "period" field only.

5. NER miss handling: if clearly named in raw text but NER list missing → use raw text bare form.

6. ALSO_KNOWN_AS: text says "X ලෙසද හැඳින්වේ" or "X නමින්ද" → extract alias triple.

7. SAME NAME, DIFFERENT PERSON — DISAMBIGUATION:
   Raw text තුළ එකම නම (e.g. "මානාභරණ") විවිධ යුගවල/විවිධ පුද්ගලයන් සඳහා
   යොදා ඇති බව context එකෙන් පැහැදිලි නම් (වෙනස් යුගය, වෙනස් title, "රුහුණේ"/
   "දෙවන"/"දක්ඛිණ දේශයේ" වැනි පැහැදිලි epithet එකක්), එම epithet එක bare
   නමට එකතු කර සම්පූර්ණ compound එකම එක entity name එකක් ලෙස
   subject/object සකසන්න — bare නම පමණක් extract නොකරන්න.
     WRONG: "මානාභරණ" (රුහුණේ සහ දක්ඛිණ දේශයේ දෙදෙනාම එකම node බවට පත් වේ)
     RIGHT: "රුහුණේ මානාභරණ" vs "දක්ඛිණ දේශයේ මානාභරණ" — වෙනස් entities දෙකක්
   මෙය අත්‍යවශ්‍යයි: disambiguating epithet එක නැතිව bare නම පමණක් extract
   කළහොත් graph එකේ වෙනස් පුද්ගලයන් දෙදෙනෙකු එකම node එකක් බවට silently
   merge වේ.

━━━ NO ABSTRACT NODES RULE ━━━

සරල fact එකක් සඳහා (එක් actor කෙනෙක්, එක් action එකක්) අතරමැදි event-noun
node එකක් හරහා route නොකරන්න — සෘජුවම subject→relation→object ලෙස extract
කරන්න.
  WRONG: (රජු) → PERFORMED → (ඉදිකිරීම් සිද්ධිය) → INVOLVED → (රුවන්වැලිසෑය)
  RIGHT: (රජු) → BUILT → (රුවන්වැලිසෑය)
එක් රජෙකුගේ තනි action එකක් කිසි විටෙක abstract event node එකකින් wrap
නොකරන්න. සිද්ධියකට තමන්ගේම attributes (කිහිප actors, දිනය, source) ඇති
කුමන්ත්‍රණයක්/සටනක් වැනි විටෙක පමණක් එය තමන්ගේම node එකක් විය හැක
(CHRONICLE ATTRIBUTION RULE බලන්න).

━━━ ORDINAL PREFIX RULE ━━━

Raw text හි entity නාමයකට පෙර ordinal prefix ඇත්නම් (I වන, II වන,
III වන, IV වන, V වන, VI වන, VII වන, VIII වන, IX වන, X වන,
පළමු, දෙවන, තෙවන, හතරවන, etc.) — එම prefix සහිතව FULL NAME use කරන්න.

NER tag "කාශ්‍යප" ලෙස දී ඇතත්, raw text "I වන කාශ්‍යප" නම්
→ subject/object = "I වන කාශ්‍යප" (not "කාශ්‍යප")

Examples:
Raw text: "I වන කාශ්‍යප රජතුමා සීගිරිය ඉදිකළේය"
NER: [PERSON_KING] කාශ්‍යප
→ subject = "I වන කාශ්‍යප" ✓  (not "කාශ්‍යප" ✗)

Raw text: "II වන පරාක්‍රමබාහු රජු මාඝගෙන් රට මුදවා ගත්තේය"
NER: [PERSON_KING] පරාක්‍රමබාහු
→ subject = "II වන පරාක්‍රමබාහු" ✓

Raw text: "V වන මහින්ද රජු චෝල ආක්‍රමණයට මුහුණ දුන්නේය"
NER: [PERSON_KING] මහින්ද
→ subject = "V වන මහින්ද" ✓

━━━ DIRECTION RULES ━━━

subject = actor (who does the action), object = receiver (who receives it).
Passive voice → always rewrite to active:
  "රුවන්වැලිසෑය දුටුගැමුණු විසින් ඉදිකරන ලදී"
  → subject=දුටුගැමුණු, relation=BUILT, object=රුවන්වැලිසෑය ✓

  "සූරතිස්ස රජු සේන ගේ වසින් ඝාතනය"
  → subject=සේන, relation=KILLED, object=සූරතිස්ස ✓

  "සිහසුනෙන් නෙරපා"
  → subject=actor, relation=EXPELLED/DEPOSED_FROM_THRONE_BY, object=victim ✓

━━━ RELATION NAMING RULES ━━━

FOLDED RELATIONS (implied/generic object):
object එක concrete entity එකක් නොව implied/generic action එකක් නම් (e.g.
"හින්දු ධර්මය වැලඳ ගැනීමට දිරිමත් කළේය"), placeholder object එකක් සහිත
generic relation එකක් නිර්මාණය නොකර, action + target එකම relation name
එකට fold කර object එක සැබෑ entity (රජු) ලෙසම තබන්න:
  WRONG: subject=X, relation=ENCOURAGED, object="හින්දු ධර්මය"
  RIGHT: subject=X, relation=ENCOURAGED_TO_ADOPT_HINDU_DHAMMA, object=රජු
(Example 21-22 බලන්න.)

CANONICAL VERB PREFERENCE TABLE — මෙම relation list එකේ ඇති relation එකක්
අදාළ නම් එයම භාවිත කරන්න, synonym අලුතින් නොනිර්මාණය කරන්න:
  රාජ්‍ය කිරීම           → RULED       (not GOVERNED / ADMINISTERED)
  සන්ධානය/ගිවිසුම බිඳ දැමීම → BROKE       (not DAMAGED / VIOLATED)
  සිංහාසනයට/රාජ්‍යත්වයට පත් වීම → RULED හෝ ASCENDED_TO (not BECAME_KING_OF)
List එකේ නොමැති සන්දර්භයකදී පමණක් අලුත් UPPER_SNAKE_CASE relation එකක්
නිර්මාණය කරන්න.

DEDUPLICATION AWARENESS:
මූලාශ්‍ර පෙළ බොහෝවිට එකම fact එක "ලැයිස්තුවක්" කොටසකද, පසුව එන narrative
"හැඳින්වීම" කොටසකද යන දෙකෙහිම repeat කරයි. එවැනි විටෙක fact එක වඩාත්
සවිස්තර/නිශ්චිත ස්වරූපයෙන් එක් වරක් පමණක් extract කරන්න — එකම
sentence-batch call එකක් තුළදී එකම triple එක verbatim දෙවරක් output
නොකරන්න. (Neo4j load stage එකේදී MERGE මගින් duplicates handle වන බැවින්,
සැක සහිත විටෙක completeness එක aggressive dedup එකට වඩා prioritize කරන්න.)

━━━ NEO4J COMPLETE RELATION REFERENCE LIST ━━━
(ඔබේ KG හි ඇති ALL relations — consistency සඳහා prefer කරන්න)

ALSO_KNOWN_AS, ARRIVED_AT, ASSOCIATED_AT_CHILDHOOD_WITH, ATTEMPTED_MURDER_OF,
AUNT_OF, BECOME_FRIENDLY_LATER_WITH, BELONGS_TO, BIASED_TOWARDS, BIGGER_THAN,
BRING_BACK, BRING_TO, BROKE, BROTHER_OF, BROUGHT, BROUGHT_TO_SRI_LANKA,
BUILD_TANK_NAMED, BUILT, BUILT_FOR, BURRIDED_NEAR, CAME_FROM, CAMPED_AT,
CONDUCTED_GRAND_OFFERINGS_TO, CONSPIRED_TO_KILL, CONTRIBUTED_TO,
CONVERTED_TO_BUDDHIST, COVERED_AT_WAR, CURE, CURED, DAUGHTER_OF, DECEIVED,
DEDICATED_TO, DEFEATED, DEFENDED_BORDERS, DEPLOYED_TO,
DEPOSED_FROM_THRONE_BY, DESTROYED, DEVELOPED, DEVELOPED_AGRICULTURE,
DIED_DURING_REIGN_OF, ENSHRINED, ENSHRINED_AT, ENSHRINED_BY, ESTABLISHED,
EXPAND, EXPELLED, FACED_THREAT_FROM, FATHER_OF, FIGHT_WITH,
FLED_AFTER_FIRST_FIGHT_WITH_BROTHER_TO, FLED_TO, FLED_WITH_FRIENDS_TO,
FOUGHT_AT, FOUGHT_BY, FOUNDED_CAPITAL, FRIENDLY_AFTER_DISCUSSION_WITH,
FRIEND_OF, GET_HELP_TO_LEGAL_PROCEEDINGS_BY, HAD_MINISTER_NAMED,
HAS_GIANT_CALLED, HAVE, HAVE_BUSINESS_DEALS_WITH, HELP_TO, HELP_TO_HOLD,
HIDE_AT, INCLUDE, INTRODUCED, INVADED, IS_A, IS_KEY_SOURCE_FOR,
IS_PRIMARY_SOURCE_FOR, IS_RELATIVE_OF, KILLED, KILLED_BY_WIFE_OF, LEFT,
LOCATED_AT, LOCATED_IN, LOOKED_LIKE, LOSE_FIRST_FIGHT_WITH,
LOSE_SECOND_FIGHT_WITH, LOVED_WITH, MARRIED, MENTIONS, MOTHER_OF,
OFFERED_SACRIFICE_OF_HEAD_AT, OF_ETHNICITY, OVERCAME_BY_DHAMMA, PATRONIZED,
POISONED, PRESERVED, PROVIDE_WATER_TO, PUNISH_TO, REBELLED_AGAINST,
RECAPTURED, RECEIVED_COMPENSATION, RECONSTRUCT, REFUSE, REIGNED_FOR,
RENOVATED, RESCUED, RESIDED_AT, RETURNED_TO_INDIA, RULED, SACRIFICE,
SENT_TO, SERVED_TO, SETTLED_IN, SISTER_OF, SON_OF, STARTED, STARTED_FROM,
STARTED_TO_BUILT_BY, STARTER_OF, STATES, STEP_FATHER_OF, STOPPED,
SUCCEEDED_BY, TEACHER_OF, THREAT_TO, TREASURER_OF, TRY_TO_DESTROY, UNITED,
WIFE_OF, WON_FIRST_FIGHT_AT, WON_SECOND_SECOND_FIGHT_WITH, WORSHIP_DAILY,
WROTE

List හි නොමැති නම් → sentence-specific UPPER_SNAKE_CASE relation නව ලෙස create කරන්න.

━━━ SPECULATION / DISPUTED FACTS / CONTESTED DATES RULE ━━━

මූලාශ්‍ර පෙළම යම් claim එකක් speculative/legendary/එක් මතයක් පමණක් ලෙස
flag කරන්නේ නම් (හඳුනාගන්න: "ජනප්‍රවාදවලට අනුව", "එක් මතයක් පමණි",
"සිතිය හැක්කේ", "විවිධ මත පවතී", "අනුමාන කළ හැකිය", "...විය හැක",
"...ඇතැයි සිතේ"), එය කිසිවිටෙක plain factual triple එකක් ලෙස extract
නොකරන්න. දෙකකින් එකක් කරන්න:
  (a) queryable අගයක් නොදෙන්නේ නම් — සම්පූර්ණයෙන්ම SKIP කරන්න (empty array
      එකට contribute කරන්න), හෝ
  (b) නම් කළ source එකම subject කර STATES relation එකෙන් attribute කරන්න:
      "(චූලවංශය) STATES (X)" — bare fact එකක් ලෙස නොව source-qualified
      claim එකක් ලෙස.
(Example 24 — skip; Example 23 — STATES.)

මූලාශ්‍රය තුළම දින/මරණ හේතුව/උරුමය පිළිබඳ විස්තර නම් කළ මූලාශ්‍ර දෙක අතර
DISPUTED නම් (එකකට වඩා විවිධ අගයන් දෙනු ලැබේ නම්), එකක් නිශ්චිතව තෝරා
silent ලෙස ඉදිරිපත් නොකර, TWO triples extract කරන්න — එක් එක් source එකම
subject කර STATES relation එකෙන්, disputed අගය period field එකේ තබා
(Example 23 බලන්න).

━━━ CHRONICLE ATTRIBUTION RULE ━━━

මූලාශ්‍ර පෙළ specific chronicle එකක් (චූලවංශය, පූජාවලිය, මහාවංශය, රාජාවලිය)
හෝ නම් කළ modern scholarship එකක් claim එකක මූලාශ්‍රය ලෙස නම් කරන
අවස්ථාවක, එම claim එක notable/contested නම්, එය silent ලෙස unsourced fact
එකක් ලෙස absorb කිරීම වෙනුවට, source-work එකම subject/object කර MENTIONS,
STATES, IS_PRIMARY_SOURCE_FOR, හෝ IS_KEY_SOURCE_FOR වැනි relation එකකින්
connect කිරීමට prefer කරන්න (Example 26 බලන්න).

━━━ OUTPUT FORMAT ━━━

[
  {
    "subject":  "<bare entity — case endings stripped>",
    "relation": "<UPPER_SNAKE_CASE>",
    "object":   "<bare entity — case endings stripped>",
    "period":   "<DATE_ERA string if present, else null>"
  }
]

━━━ FEW-SHOT EXAMPLES (full range of text types) ━━━

Example 1 — RULED + period (basic):
RAW: පණ්ඩුකාභය රජු ක්‍රි.පූ. 437 සිට 367 දක්වා ලංකාව පාලනය කළේය.
NER: [PERSON_KING] පණ්ඩුකාභය, [DATE_ERA] ක්‍රි.පූ. 437 සිට 367, [LOCATION] ලංකාව
OUTPUT: [{"subject":"පණ්ඩුකාභය","relation":"RULED","object":"ලංකාව","period":"ක්‍රි.පූ. 437 සිට 367"}]

Example 2 — BUILT (passive → active):
RAW: රුවන්වැලිසෑය දුටුගැමුණු රජු විසින් ඉදිකරන ලදී.
NER: [PERSON_KING] දුටුගැමුණු, [MONUMENT] රුවන්වැලිසෑය
OUTPUT: [{"subject":"දුටුගැමුණු","relation":"BUILT","object":"රුවන්වැලිසෑය","period":null}]

Example 3 — SON_OF + RULED (multiple relations):
RAW: මහාසිව රජු මුටසිව රජුගේ පුත්‍රයෙකු වූ අතර ක්‍රිපූ 257 සිට 247 දක්වා අනුරාධපුරය පාලනය කළේය.
NER: [PERSON_KING] මහාසිව, [PERSON_KING] මුටසිව, [DATE_ERA] ක්‍රිපූ 257 සිට 247, [LOCATION] අනුරාධපුරය
OUTPUT: [{"subject":"මහාසිව","relation":"SON_OF","object":"මුටසිව","period":null},{"subject":"මහාසිව","relation":"RULED","object":"අනුරාධපුරය","period":"ක්‍රිපූ 257 සිට 247"}]

Example 4 — KILLED (passive rewrite):
RAW: ක්‍රිපූ 205 දී එළාර ආක්‍රමණිකයා විසින් අසේල රජු මරා දැමිය.
NER: [PERSON_KING] එළාර, [PERSON_KING] අසේල, [DATE_ERA] ක්‍රිපූ 205
OUTPUT: [{"subject":"එළාර","relation":"KILLED","object":"අසේල","period":"ක්‍රිපූ 205"}]

Example 5 — ALSO_KNOWN_AS (alias extraction):
RAW: මහ කළු සිංහයා, වට්ටගාමිණී අභය සහ වළගම්බාහු ලෙසද හැඳින්වෙන වළගම්බා රජු.
NER: [PERSON_KING] වළගම්බා
OUTPUT: [{"subject":"වළගම්බා","relation":"ALSO_KNOWN_AS","object":"වට්ටගාමිණී අභය","period":null},{"subject":"වළගම්බා","relation":"ALSO_KNOWN_AS","object":"වළගම්බාහු","period":null}]

Example 6 — CONVERTED_TO_BUDDHIST:
RAW: මිහිඳු හිමියන් ධර්ම දේශනා කළ අතර, ඉන් අනතුරුව දේවානම්පිය තිස්ස රජතුමා බුදු දහම වැළඳ ගත්තේය.
NER: [PERSON_MONK] මිහිඳු හිමි, [PERSON_KING] දේවානම්පිය තිස්ස
OUTPUT: [{"subject":"මිහිඳු හිමි","relation":"CONVERTED_TO_BUDDHIST","object":"දේවානම්පිය තිස්ස","period":null}]

Example 7 — MARRIED + EXPELLED (sequence):
RAW: විජය රජු කුවේනිය සමඟ විවාහ වූ අතර, පසුව ඔහු කුවේනිය නෙරපා හැරියේය.
NER: [PERSON_KING] විජය, [PERSON_OTHER] කුවේනිය
OUTPUT: [{"subject":"විජය","relation":"MARRIED","object":"කුවේනිය","period":null},{"subject":"විජය","relation":"EXPELLED","object":"කුවේනිය","period":null}]

Example 8 — FLED_TO + RECAPTURED:
RAW: කොළඹලකදී සටනේදී පරාජයට පත් වූ වළගම්බා රජුට පලා යාමට සිදු විය. ක්‍රි.පූ. 89 දී ඔහු ආක්‍රමණිකයන් පරාජය කර අනුරාධපුරය නැවත අත්පත් කර ගත්තේය.
NER: [PERSON_KING] වළගම්බා, [LOCATION] කොළඹල, [DATE_ERA] ක්‍රි.පූ. 89, [LOCATION] අනුරාධපුරය
OUTPUT: [{"subject":"වළගම්බා","relation":"FLED_TO","object":"කොළඹල","period":null},{"subject":"වළගම්බා","relation":"DEFEATED","object":"ආක්‍රමණිකයන්","period":"ක්‍රි.පූ. 89"},{"subject":"වළගම්බා","relation":"RECAPTURED","object":"අනුරාධපුරය","period":"ක්‍රි.පූ. 89"}]

Example 9 — NER missed entity; use raw text:
RAW: විජය ඇතුළු පිරිසෙන් සිංහල ජාතිය බිහිවිණි.
NER: [PERSON_KING] විජය
OUTPUT: [{"subject":"විජය","relation":"FOUNDED","object":"සිංහල ජාතිය","period":null}]

Example 10 — SUCCEEDED_BY:
RAW: විජයගේ මරණයෙන් හිස් වූ සිහසුනට පණ්ඩුවාසුදේව කුමරු පත් වූයේය.
NER: [PERSON_KING] විජය, [PERSON_KING] පණ්ඩුවාසුදේව
OUTPUT: [{"subject":"විජය","relation":"SUCCEEDED_BY","object":"පණ්ඩුවාසුදේව","period":null}]

Example 11 — BELONGS_TO (dynasty):
RAW: ධාතුසේන රජු මෞර්ය රාජ වංශයට අයත් රජ කෙනෙකි.
NER: [PERSON_KING] ধাতুসේන රජු, [DYNASTY] මෞර්ය රාජ වංශය
OUTPUT: [{"subject":"ධාතුසේන රජු","relation":"BELONGS_TO","object":"මෞර්ය රාජ වංශය","period":null}]

Example 12 — THREAT_TO + DEFEATED:
RAW: ද්‍රවිඩ ආක්‍රමණිකයන් රාජධානියට තර්ජනය කළ අතර, ධාතුසේන රජු ඔවුන් පරාජය කර රට එක්සත් කළේය.
NER: [PERSON_KING] ධාතුසේන රජු, [PERSON_OTHER] ද්‍රවිඩ ආක්‍රමණිකයන්
OUTPUT: [{"subject":"ද්‍රවිඩ ආක්‍රමණිකයන්","relation":"THREAT_TO","object":"රාජධානිය","period":null},{"subject":"ධාතුසේන රජු","relation":"DEFEATED","object":"ද්‍රවිඩ ආක්‍රමණිකයන්","period":null},{"subject":"ධාතුසේන රජු","relation":"UNITED","object":"ශ්‍රී ලංකාව","period":null}]

Example 13 — WIFE_OF + SON_OF chain:
RAW: වළගම්බා රජුගේ අගමෙහෙසිය සෝමා දේවිය වූ අතර, පුතා මහානාග කුමාරයා විය.
NER: [PERSON_KING] වළගම්බා, [PERSON_OTHER] සෝමා දේවිය, [PERSON_OTHER] මහානාග
OUTPUT: [{"subject":"සෝමා දේවිය","relation":"WIFE_OF","object":"වළගම්බා","period":null},{"subject":"මහානාග","relation":"SON_OF","object":"වළගම්බා","period":null}]

Example 14 — WROTE:
RAW: බුද්ධදාස රජු වෛද්‍ය විද්‍යාව පිළිබඳ ග්‍රන්ථ රැසක් රචනා කළේය.
NER: [PERSON_KING] බුද්ධදාස රජු, [ARTIFACT] වෛද්‍ය ග්‍රන්ථ
OUTPUT: [{"subject":"බුද්ධදාස රජු","relation":"WROTE","object":"වෛද්‍ය ග්‍රන්ථ","period":null}]

Example 15 — RENOVATED + REBUILT:
RAW: සිරිමේඝවණ්ණ රජු, මහාසෙන් රජු විසින් විනාශ කරන ලද මහාවිහාරය සහ ලෝවාමහාපාය නැවත ප්‍රතිසංස්කරණය කිරීමට කටයුතු කළේය.
NER: [PERSON_KING] සිරිමේඝවණ්ණ, [MONUMENT] මහාවිහාරය, [MONUMENT] ලෝවාමහාපාය
OUTPUT: [{"subject":"සිරිමේඝවණ්ණ","relation":"RENOVATED","object":"මහාවිහාරය","period":null},{"subject":"සිරිමේඝවණ්ණ","relation":"RENOVATED","object":"ලෝවාමහාපාය","period":null}]

Example 16 — REBELLED_AGAINST + KILLED:
RAW: සේන සහ ගුත්තික, සූරතිස්ස රජු මරා දමා සිහසුන පැහැර ගත්හ.
NER: [PERSON_OTHER] සේන, [PERSON_OTHER] ගුත්තික, [PERSON_KING] සූරතිස්ස
OUTPUT: [{"subject":"සේන","relation":"KILLED","object":"සූරතිස්ස","period":null},{"subject":"ගුත්තික","relation":"KILLED","object":"සූරතිස්ස","period":null}]

Example 17 — INTRODUCED (Buddhism):
RAW: මිහිඳු හිමියන් ශ්‍රී ලංකාවට පැමිණ ලක්වැසියන් බුද්ධාගමට හරවා ගත්හ.
NER: [PERSON_MONK] මිහිඳු හිමි, [LOCATION] ශ්‍රී ලංකාව
OUTPUT: [{"subject":"මිහිඳු හිමි","relation":"ARRIVED_AT","object":"ශ්‍රී ලංකාව","period":null},{"subject":"මිහිඳු හිමි","relation":"INTRODUCED","object":"බුද්ධාගම","period":null}]

Example 18 — TEACHER_OF:
RAW: පණ්ඩුල බමුණා කුමරුට ශිල්ප ශාස්ත්‍ර ඉගැන්වීය.
NER: [PERSON_OTHER] පණ්ඩුල, [PERSON_OTHER] පණ්ඩුකාභය
OUTPUT: [{"subject":"පණ්ඩුල","relation":"TEACHER_OF","object":"පණ්ඩුකාභය","period":null}]

Example 19 — DEPOSED_FROM_THRONE_BY:
RAW: කාශ්‍යප කුමරු ධාතුසේන රජු සිහසුනෙන් නෙරපා හැර රාජ්‍ය පවරා ගත්තේය.
NER: [PERSON_KING] කාශ්‍යප, [PERSON_KING] ධාතුසේන රජු
OUTPUT: [{"subject":"ධාතුසේන රජු","relation":"DEPOSED_FROM_THRONE_BY","object":"කාශ්‍යප","period":null}]

Example 20 — CONSPIRED_TO_KILL + complex politics:
RAW: සපුමල් කුමරු කෝට්ටේ රාජධානියට පැමිණ, දෙවන ජයබාහු රජු ඝාතනය කර සිහසුනට පත් විය.
NER: [PERSON_KING] සපුමල් කුමරු, [PERSON_KING] දෙවන ජයබාහු
OUTPUT: [{"subject":"සපුමල් කුමරු","relation":"KILLED","object":"දෙවන ජයබාහු","period":null}]

Example 21 — Folded relation (encourage-to-adopt pattern):
RAW: ඇමතිවරයා රාජසිංහ රජුට හින්දු ධර්මය වැලඳ ගැනීමට උනන්දු කරවීය.
NER: [PERSON_OTHER] ඇමතිවරයා, [PERSON_KING] රාජසිංහ
OUTPUT: [{"subject":"ඇමතිවරයා","relation":"ENCOURAGED_TO_ADOPT_HINDU_DHAMMA","object":"රාජසිංහ","period":null}]

Example 22 — Folded relation (advised-to-attack pattern):
RAW: ඇමතිවරයා කාශ්‍යප රජුට බෞද්ධ ස්ථාන වලට ප්‍රහාර කිරීමට උපදෙස් දුන්නේය.
NER: [PERSON_OTHER] ඇමතිවරයා, [PERSON_KING] කාශ්‍යප
OUTPUT: [{"subject":"ඇමතිවරයා","relation":"ADVISED_TO_ATTACK_BUDDHIST_SITES","object":"කාශ්‍යප","period":null}]

Example 23 — Disputed date across two chronicles (dual STATES):
RAW: චූලවංශය අනුව මාගම මහානාග රජු ක්‍රි.ව. 1215 දී මිය ගියේය, නමුත් රාජාවලිය පවසන්නේ ක්‍රි.ව. 1212 බවයි.
NER: [CHRONICLE] චූලවංශය, [CHRONICLE] රාජාවලිය, [PERSON_KING] මාගම මහානාග, [DATE_ERA] ක්‍රි.ව. 1215, [DATE_ERA] ක්‍රි.ව. 1212
OUTPUT: [{"subject":"චූලවංශය","relation":"STATES","object":"මාගම මහානාග","period":"ක්‍රි.ව. 1215 මරණය"},{"subject":"රාජාවලිය","relation":"STATES","object":"මාගම මහානාග","period":"ක්‍රි.ව. 1212 මරණය"}]

Example 24 — Speculative/legendary claim, no queryable value → skip entirely:
RAW: ජනප්‍රවාදවලට අනුව රජු අහසින් වැටුණු කැලයක් තුළින් උපත ලැබූ බව සිතිය හැක.
NER: [PERSON_KING] රජු
OUTPUT: []

Example 25 — Same-name disambiguation (epithet preserved, not stripped):
RAW: රුහුණේ මානාභරණ රජු, දක්ඛිණ දේශයේ උපරජ වූ තවත් මානාභරණ කෙනෙකුගෙන් වෙනස් පුද්ගලයෙකි. රුහුණේ මානාභරණ රජු ක්‍රි.ව. 1187 දී රුහුණ රාජ්‍ය කළේය.
NER: [PERSON_KING] මානාභරණ, [DATE_ERA] ක්‍රි.ව. 1187
OUTPUT: [{"subject":"රුහුණේ මානාභරණ","relation":"RULED","object":"රුහුණ","period":"ක්‍රි.ව. 1187"}]

Example 26 — Chronicle attribution (named source for a notable claim):
RAW: ඉන්ද්‍රකීර්ති සිරිවීර මහතාගේ පර්යේෂණ අනුව, දෙවන ජයබාහු ඝාතනය කිරීමේ කුමන්ත්‍රණය පිළිබඳ ප්‍රධාන මූලාශ්‍රය චූලවංශයයි.
NER: [PERSON_OTHER] ඉන්ද්‍රකීර්ති සිරිවීර, [CHRONICLE] චූලවංශය, [PERSON_KING] දෙවන ජයබාහු
OUTPUT: [{"subject":"චූලවංශය","relation":"IS_PRIMARY_SOURCE_FOR","object":"දෙවන ජයබාහුගේ ඝාතනය","period":null}]

━━━ STRICT OUTPUT RULES ━━━

• JSON array ONLY — no explanation, no markdown fences, no preamble
• Valid triple නොමැත්නම් → exactly []
• period field: DATE_ERA string හෝ null — NEVER empty string ""
• Sentence හි ඇති ALL valid relationships extract කරන්න — first triple දී නොනවතින්න
• Subject ≠ Object (same entity triples NEVER)
• Speculative/legendary ලෙස flag කළ content කිසි විටෙක bare fact ලෙස extract නොකරන්න (SPECULATION RULE බලන්න)

━━━ NOW process the input below: ━━━

"""


def _build_user_message(sentence: str, ner_tags: list[NERTag]) -> str:
    ner_parts = [f"[{tag.label}] {tag.entity}" for tag in ner_tags]
    return f"වාක්‍යය: {sentence}\nNER: {', '.join(ner_parts)}"


# UNIVERSAL LLM CALL

def _call_llm(
    sentence: str,
    ner_tags: list[NERTag],
    provider: str,
    api_key: str,
    model: str,
) -> str:
    """
    Call the selected LLM provider and return the raw text response.

    OpenAI / DeepSeek / Gemini → openai SDK (OpenAI-compatible endpoints).
    Anthropic Claude            → anthropic SDK.
    """
    if not api_key:
        raise ValueError(
            f"API key for {provider} is not set. "
            f"Add {_KEY_ENV.get(provider, 'the key')} to your .env file."
        )

    user_msg = _build_user_message(sentence, ner_tags)

    # Anthropic Claude
    if provider == PROVIDER_CLAUDE:
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return message.content[0].text.strip()

    # OpenAI-compatible providers (OpenAI, DeepSeek, Gemini)
    from openai import OpenAI
    cfg = PROVIDERS.get(provider, {})
    kwargs: dict = {"api_key": api_key}
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]

    client = OpenAI(**kwargs)
    response = client.chat.completions.create(
        model=model,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
    )
    return response.choices[0].message.content.strip()


# RESPONSE PARSING

def _to_list(data: object) -> list[dict]:
    """Return data as a list[dict], or empty list if not parseable."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def _try_json(text: str) -> list[dict]:
    """Parse text as JSON and coerce to list[dict]; return [] on failure."""
    try:
        return _to_list(json.loads(text))
    except json.JSONDecodeError:
        return []


def _recover_truncated(cleaned: str) -> list[dict]:
    """Close an unclosed JSON array caused by token-limit truncation."""
    if "[" not in cleaned or cleaned.count("{") <= cleaned.count("}"):
        return []
    return _try_json(cleaned.rstrip(", \n") + "}]")


def _parse_response(raw: str) -> list[dict]:
    if not raw:
        return []
    cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip().rstrip("`").strip()
    if cleaned in ("[]", "[ ]", ""):
        return []
    if cleaned.startswith("{") and not cleaned.startswith("["):
        cleaned = f"[{cleaned}]"

    result = _try_json(cleaned)
    if result:
        return result

    match = re.search(r"\[[^\]]*\]", cleaned, re.DOTALL)
    if match:
        result = _try_json(match.group())
        if result:
            return result

    return _recover_truncated(cleaned)


# TRIPLE VALIDATION

# Sinhala grammatical case suffixes that the NER model sometimes leaves attached.
# Ordered longest-first so "ෙකු" is tried before "ු" would hypothetically be.
# "ව" (accusative) intentionally omitted — it is the base form of many words.
# "ගේ"/"ෙහි" handled by normalizer.py _TITLE_SUFFIXES but only for alias-map hits;
# we add them here too so they strip unconditionally for any entity name.
_SINHALA_CASE_SUFFIXES: tuple[str, ...] = (
    "ෙකු",  # dative (human classifier): "කෙනෙකු" — strip only if stem ≥ 2
    "ෙන්",  # ablative/instrumental: "ලංකාවෙන්" → "ලංකාව"
    "ෙහි",  # locative formal: "රාජ්‍යයෙහි" → "රාජ්‍යය"
    "ේදී",  # locative+particle "at": "විහාරයේදී" → "විහාරය"
    "හිදී", # formal locative+particle: "ලංකාහිදී" → "ලංකා"
    "ගේ",   # genitive: "දේවානම්පිය තිස්සගේ" → "දේවානම්පිය තිස්ස"
    "ේ",    # locative: "ලංකාවේ" → "ලංකාව"
    "ට",    # dative: "විජයට" → "විජය"
    "හු",   # plural/formal: "රජහු" → "රජ"
)

# Substrings that mark a genuine relational clause ("X's ...", "by X", "under X")
# prepended before an entity name. Used to gate _resolve_ner_entity's case 5 so it
# doesn't fire on plain disambiguating epithets (e.g. "රුහුණේ මානාභරණ").
_RELATIONAL_PREFIX_MARKERS: tuple[str, ...] = ("ගේ", "ගෙන්", "විසින්", "යටතේ")


def _strip_sinhala_case(name: str) -> str:
    """Remove a trailing grammatical case suffix, keeping the stem if ≥ 2 chars."""
    for suffix in _SINHALA_CASE_SUFFIXES:
        if name.endswith(suffix):
            stem = name[: -len(suffix)]
            if len(stem) >= 2:
                return stem
    return name


def _resolve_ner_entity(candidate: str, entity_set: set[str]) -> str | None:
    """Find the NER entity matching candidate, tolerating five LLM divergences.

    1. Exact match.
    2. Case suffix: LLM added exactly one grammatical suffix after the entity.
       e.g. "ලංකාවේ" → "ලංකාව" + "ේ"   ← extra must be ONE known suffix, nothing else.
       Deliberately strict: "X's father Y" does NOT match via this case because
       the leftover "ගේ පිය Y" is not a single case suffix.
    3. Honorific dropped: LLM "විජය" → NER "විජය රජු" (entity is longer).
    4. Canonical-form match via normalize_entity.
    5. Descriptive prefix: LLM prepended a RELATIONAL clause before the real entity.
       e.g. "වළගම්බා රජුගේ පිය සද්ධාතිස්ස" → entity "සද්ධාතිස්ස" is at the END.
       Restricted to prefixes containing a relational marker (ගේ/ගෙන්/විසින්/
       යටතේ) so a legitimate disambiguating epithet — e.g. "රුහුණේ මානාභරණ",
       used to distinguish two different same-named kings — is NOT collapsed
       down to the bare, ambiguous name. See _SYSTEM_PROMPT's entity
       disambiguation rule, which deliberately asks the LLM to produce such
       compounds; without this restriction they would be silently destroyed
       here and two distinct people would merge into one KG node.
    """
    if candidate in entity_set:
        return candidate
    # Case 2: entity + exactly one Sinhala case suffix (strictly)
    for e in sorted(entity_set, key=len, reverse=True):
        if not e or not candidate.startswith(e):
            continue
        extra = candidate[len(e):]
        if extra in _SINHALA_CASE_SUFFIXES:
            return e
    # Case 3: LLM dropped honorific/title (entity starts with candidate)
    prefix_matches = [e for e in entity_set if e and e.startswith(candidate)]
    if prefix_matches:
        return max(prefix_matches, key=len)
    # Case 4: LLM returned normalized/canonical form
    cand_norm = normalize_entity(candidate)
    norm_matches = [e for e in entity_set if normalize_entity(e) == cand_norm]
    if norm_matches:
        return max(norm_matches, key=len)
    # Case 5: LLM prepended a RELATIONAL clause — real entity is at the END.
    # e.g. "කාවන්තිස්සගේ පුත් සද්ධාතිස්ස" → "සද්ධාතිස්ස" (prefix has "ගේ").
    # Only fires if the stripped-off prefix contains a relational marker, so
    # a plain disambiguating epithet like "රුහුණේ" in "රුහුණේ මානාභරණ" is left
    # untouched — that candidate falls through to None and is accepted as-is
    # by the caller's fallback (see _validate_one_triple._resolve_or_fallback).
    suffix_end_matches = [
        e for e in entity_set
        if e and len(candidate) > len(e) and candidate.endswith(e)
        and any(marker in candidate[: len(candidate) - len(e)] for marker in _RELATIONAL_PREFIX_MARKERS)
    ]
    if suffix_end_matches:
        return max(suffix_end_matches, key=len)
    return None


def _sanitize_relation(rel: str) -> str | None:
    """Convert any relation string to safe UPPER_SNAKE_CASE, or None if empty."""
    clean = re.sub(r"[^A-Z0-9_]", "", rel.upper().replace(" ", "_").replace("-", "_"))
    return clean if clean else None


def _norm_canonical(name: str) -> str:
    """Normalize a Sinhala entity name to its KG canonical form.

    Pipeline: strip case suffix → morphological normalization → alias resolution.
    """
    name = normalize_entity(_strip_sinhala_case(name))
    return kg_aliases.resolve_to_canonical(name)


def _validate_one_triple(
    raw: dict,
    non_date_raw: set[str],
    non_date_canonical: set[str],
    date_era_entities: set[str],
) -> dict | None:
    """Validate and normalize one raw LLM triple. Returns None if it should be rejected."""
    if not isinstance(raw, dict):
        return None

    raw_subj = raw.get("subject",  "").strip()
    raw_obj  = raw.get("object",   "").strip()
    raw_rel  = raw.get("relation", "").strip()
    period   = (raw.get("period") or "").strip()

    def _resolve_or_fallback(candidate: str) -> str | None:
        resolved = _resolve_ner_entity(candidate, non_date_raw)
        if resolved is not None:
            return resolved
        # NER missed this entity — accept the LLM string directly if it looks
        # like a real entity name (at least 2 chars, non-empty after strip).
        if len(candidate) >= 2:
            return candidate
        return None

    resolved_subj = _resolve_or_fallback(raw_subj)
    resolved_obj  = _resolve_or_fallback(raw_obj)
    if resolved_subj is None or resolved_obj is None:
        return None

    subj = _norm_canonical(resolved_subj)
    obj  = _norm_canonical(resolved_obj)
    if not subj or not obj:
        return None
    if subj in date_era_entities or obj in date_era_entities:
        return None

    relation = _sanitize_relation(raw_rel)
    if not relation:
        return None

    return {"subject": subj, "relation": relation, "object": obj, "period": period}


def _validate_and_normalize(
    raw_triples: list[dict],
    ner_tags: list[NERTag],
) -> list[dict]:
    date_era_entities: set[str] = {
        _norm_canonical(t.entity) for t in ner_tags if t.label == "DATE_ERA"
    }
    non_date_raw: set[str]       = {t.entity for t in ner_tags if t.label != "DATE_ERA"}
    non_date_canonical: set[str] = {_norm_canonical(e) for e in non_date_raw}

    validated: list[dict] = []
    for raw in raw_triples:
        triple = _validate_one_triple(raw, non_date_raw, non_date_canonical, date_era_entities)
        if triple is not None:
            validated.append(triple)
    return validated


# PUBLIC API

def extract_relations(
    sentence: str,
    ner_tags: list[NERTag],
    verbose: bool = False,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    _debug: dict | None = None,
) -> list[dict]:
    """
    Extract and validate triples for one Sinhala sentence.

    provider / api_key / model are optional — when omitted the function reads
    LLM_PROVIDER / LLM_MODEL and the matching *_API_KEY from .env.

    Pass a dict as _debug to capture raw LLM response and parsed triples:
        d = {}; extract_relations(s, tags, _debug=d)
        # d["raw"], d["parsed"], d["validated"] are now populated
    """
    _provider = provider or _ENV_PROVIDER
    _api_key  = api_key  or _env_api_key(_provider)
    _model    = model    or _ENV_MODEL

    non_date = [t for t in ner_tags if t.label != "DATE_ERA"]
    if len(non_date) < 2:
        if verbose:
            print(f"[SKIP] < 2 non-DATE_ERA entities: {sentence!r}")
        return []

    if verbose:
        print(f"\n{'─'*60}\n[INPUT]    {sentence}\n[NER TAGS] {ner_tags}")

    user_msg = _build_user_message(sentence, ner_tags)
    if _debug is not None:
        _debug["input"] = user_msg

    raw_response = _call_llm(sentence, ner_tags, _provider, _api_key, _model)

    if verbose:
        print(f"[RAW]    {raw_response}")

    raw_triples = _parse_response(raw_response)

    if verbose:
        print(f"[PARSED] {raw_triples}")

    triples = _validate_and_normalize(raw_triples, ner_tags)

    if verbose:
        print(f"[VALID]  {triples}")

    if _debug is not None:
        _debug["raw"]       = raw_response
        _debug["parsed"]    = raw_triples
        _debug["validated"] = triples

    return triples