"""
Turns one continuous physician dictation (diagnosis + diagnostics + treatment,
all spoken in a single take) into structured fields the UI can pre-fill.

Pipeline:
1. segment_dictation() splits the raw transcript into evaluation / diagnostics /
   treatment chunks using spoken keyword markers (e.g. "diagnosis...",
   "diagnostics...", "treatment plan..."). This is a deterministic, no-AI step
   so the split is predictable and doctors can learn the cues.
2. extract_structured() sends the transcript + those chunks to OpenAI
   (chat completions, JSON mode), which maps free speech onto the app's fixed
   diagnostic-test / treatment option lists and resolves relative dates
   ("in two weeks") to ISO dates. If the API call fails, it falls back to the
   plain segmented text so the page still works (just without AI-mapped
   tests/treatments).
"""
import os
import re
import json
from datetime import datetime, timedelta

from openai import OpenAI

OPENAI_EXTRACT_MODEL = os.getenv("OPENAI_EXTRACT_MODEL", "gpt-4o-mini")
_openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Must stay in sync with frontend/src/data/mockData.js (DIAGNOSTIC_TESTS / TREATMENT_OPTIONS)
DIAGNOSTIC_TESTS = {
    "xray": "X-Ray",
    "mri": "MRI",
    "ct": "CT Scan",
    "lab": "Laboratory Tests",
    "us": "Ultrasound",
}

TREATMENT_OPTIONS = {
    "surgery": "Surgery",
    "medication": "Medication",
    "physio": "Physiotherapy",
    "injection": "Injection Therapy",
    "rest": "Rest & Monitoring",
    "rehab": "Long-term Rehab",
}

# Direct word-spotting for the two closed lists above. This runs regardless of
# whether the LLM is available — picking "x-ray" or "surgery" out of a sentence
# is a fixed-vocabulary match problem, not something that needs an LLM, and
# matching deterministically means the doctor's word always wins instead of an
# LLM's paraphrase of it.
# Arabic/French alternatives are written in *normalised* Arabic form (see
# _normalize_arabic below — alef-hamza forms collapsed to ا, ة->ه, ى->ي)
# since keyword_match() always searches the normalised haystack. English and
# French matching is plain re.I; French adds an [ée] class where accents are
# ASR-optional so it matches whether or not OpenAI transcribes the accent.
# Arabic terms use an optional `(?:و)?(?:ال)?` definite-article prefix on each noun
# — the article glues directly onto the word with no space ("الفحوصات" =
# "the" + "diagnostics" as one token), so a bare `\bفحوصات\b` would never
# match the (very common) definite form. `(?:و)?(?:ال)?` before the word keeps `\b`
# anchored at the true start (article present or not) instead.
DIAGNOSTIC_TEST_SYNONYMS = {
    "xray": [
        r"x[\s-]?ray", r"radiograph",
        r"\b(?:و)?(?:ال)?اشعه\s*(?:و)?(?:ال)?سينيه\b", r"\b(?:و)?(?:ال)?اشعه\s*(?:و)?(?:ال)?اكس\b", r"\b(?:و)?(?:ال)?رنتجن\b",
        r"\bradiographie\b", r"\brayons?\s*x\b",
    ],
    "mri": [
        r"mri", r"magnetic resonance",
        r"\b(?:و)?(?:ال)?رنين\s*(?:و)?(?:ال)?مغناطيسي\b",
        r"\birm\b", r"\bimagerie\s*par\s*r[ée]sonance\s*magn[ée]tique\b", r"\br[ée]sonance\s*magn[ée]tique\b",
    ],
    "ct": [
        r"ct\s*scan", r"cat\s*scan", r"computed tomography",
        r"\b(?:و)?(?:ال)?اشعه\s*(?:و)?(?:ال)?مقطعيه\b", r"\b(?:و)?(?:ال)?تصوير\s*(?:و)?(?:ال)?مقطعي\b",
        r"\bscanner\b", r"\btomodensitom[ée]trie\b",
    ],
    "lab": [
        r"laborator\w*", r"lab\s*tests?", r"lab\s*work", r"blood\s*(?:test|work)", r"\bcbc\b", r"\besr\b", r"\bcrp\b",
        r"\b(?:و)?(?:ال)?تحاليل\s*(?:و)?(?:ال)?مخبريه\b", r"\b(?:و)?(?:ال)?فحوصات\s*(?:و)?(?:ال)?دم\b", r"\b(?:و)?(?:ال)?تحليل\s*(?:و)?(?:ال)?دم\b",
        r"\banalyses?\s*de\s*laboratoire\b", r"\banalyses?\s*sanguines?\b", r"\bbilan\s*sanguin\b",
    ],
    "us": [
        r"ultrasound", r"sonograph\w*",
        r"\b(?:و)?(?:ال)?سونار\b", r"\b(?:و)?(?:ال)?موجات\s*فوق\s*(?:و)?(?:ال)?صوتيه\b", r"\b(?:و)?(?:ال)?ايكو\b",
        r"\b[ée]chographie\b",
    ],
}

TREATMENT_SYNONYMS = {
    "surgery": [
        r"surger\w*", r"surgical", r"operat\w*",
        r"\b(?:و)?(?:ال)?جراحه\b", r"\b(?:و)?(?:ال)?عمليه\s*(?:و)?(?:ال)?جراحيه\b",
        r"\bchirurgie\b", r"\bop[ée]ration\b",
    ],
    "medication": [
        r"medication\w*", r"\bmeds\b", r"prescri\w*", r"\bmedicine\b",
        r"\b(?:و)?(?:ال)?دواء\b", r"\b(?:و)?(?:ال)?ادويه\b", r"\b(?:و)?(?:ال)?علاج\s*(?:و)?(?:ال)?دوائي\b",
        r"\bm[ée]dicament\w*\b", r"\btraitement\s*m[ée]dicamenteux\b",
    ],
    "physio": [
        r"physiotherap\w*", r"physical therap\w*", r"\bphysio\b",
        r"\b(?:و)?(?:ال)?علاج\s*(?:و)?(?:ال)?طبيعي\b", r"\b(?:و)?(?:ال)?فيزيوثيرابي\b",
        r"\bkin[ée]sith[ée]rapie\b", r"\bphysioth[ée]rapie\b",
    ],
    "injection": [
        r"injection\w*", r"corticosteroid\w*", r"\bprp\b", r"steroid shot", r"cortisone",
        r"\b(?:و)?(?:ال)?حقن\b", r"\b(?:و)?(?:ال)?حقنه\b", r"\b(?:و)?(?:ال)?ابره\s*كورتيزون\b",
        r"\binfiltration\b", r"\bcorticoth[ée]rapie\b",
    ],
    "rest": [
        r"rest\s*(?:and|&)?\s*monitor\w*", r"conservative management", r"\bjust rest\b",
        r"\b(?:و)?(?:ال)?راحه\s*(?:و)?(?:ال)?متابعه\b", r"\b(?:و)?(?:ال)?راحه\s*(?:و)?(?:ال)?مراقبه\b",
        r"\brepos\s*et\s*surveillance\b", r"\brepos\s*et\s*suivi\b",
    ],
    "rehab": [
        r"rehabilitation\w*", r"long[\s-]?term rehab\w*", r"\brehab\b",
        r"\b(?:و)?(?:ال)?اعاده\s*(?:و)?(?:ال)?تاهيل\b", r"\b(?:و)?(?:ال)?تاهيل\s*(?:و)?(?:ال)?طويل\s*(?:و)?(?:ال)?امد\b", r"\b(?:و)?(?:ال)?تاهيل\b",
        r"\br[ée][ée]ducation\b", r"\br[ée]adaptation\b",
    ],
}


# Length-preserving normalisation of common Arabic letter-form variants
# (alef-hamza forms, ta-marbuta/ha, alef-maksura/ya) so the Arabic
# alternatives in the patterns below only need to spell one canonical form
# instead of enumerating every variant. Only ever used to build the
# *haystack* passed to .search()/.finditer() — never applied to text that
# gets sliced or returned, since every substitution is one codepoint for one
# codepoint, so match offsets stay valid against the original string.
_ARABIC_NORMALIZE_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا",
    "ى": "ي",
    "ة": "ه",
})


def _normalize_arabic(text: str) -> str:
    return text.translate(_ARABIC_NORMALIZE_MAP)


# Auto-detects which of the app's 3 supported languages a transcript is in,
# from the transcript text itself — used to identify the dictation's language
# from the first few words spoken (see main.py /transcribe/preview) so the
# doctor doesn't have to pick a language up front, and so the rest of the
# recording can then be transcribed with that language forced (more accurate
# than leaving every chunk unforced/auto-detected — see run_transcription).
# Arabic is unambiguous by Unicode script. English vs French (both Latin
# script) is resolved by accented characters or common French stopwords;
# English is the default when neither signal is present.
_ARABIC_SCRIPT_PATTERN = re.compile(r"[؀-ۿ]")
_LATIN_WORD_PATTERN = re.compile(r"[A-Za-z]{2,}")
_FRENCH_SIGNAL_PATTERN = re.compile(
    r"[àâäéèêëïîôöùûüÿœæç]"
    r"|\b(le|la|les|des|une|un|est|dans|avec|pour|que|qui|vous|nous|votre|nos|et|au|aux|du|ce|cette|ces|douleur|traitement)\b",
    re.I,
)


def detect_language(text: str) -> str:
    """Best-effort en/ar/fr/mixed guess from transcribed text. Falls back to
    "en" when the text is empty or carries no clear signal either way."""
    if not text or not text.strip():
        return "en"
    if _ARABIC_SCRIPT_PATTERN.search(text):
        # Arabic speech that also carries Latin-script words (English medical
        # terms said mid-sentence) is code-switched: forcing "ar" on it makes
        # the ASR translate or transliterate the English terms, so it is
        # reported as "mixed" and transcribed without a forced language.
        if len(_LATIN_WORD_PATTERN.findall(text)) >= 2:
            return "mixed"
        return "ar"
    if _FRENCH_SIGNAL_PATTERN.search(text):
        return "fr"
    return "en"


def keyword_match(text: str, synonyms: dict) -> list[str]:
    """Scan text for the first occurrence of any synonym for each known id,
    returning matched ids ordered by where they were said (earliest first)."""
    haystack = _normalize_arabic(text)
    hits = []
    for id_, patterns in synonyms.items():
        for pattern in patterns:
            m = re.search(pattern, haystack, re.I)
            if m:
                hits.append((m.start(), id_))
                break
    hits.sort(key=lambda x: x[0])
    seen, ordered = set(), []
    for _, id_ in hits:
        if id_ not in seen:
            seen.add(id_)
            ordered.append(id_)
    return ordered


# Marks a sentence as describing a PAST result ("old MRI", "X-ray from last
# year", "previous ultrasound showed...") rather than a test being newly
# ordered now. Used to keep keyword_match_new_orders() from flagging a test
# as "ordered" just because its name appears near a stray mention of an old
# result — this can happen even when the sentence is correctly placed in the
# "evaluation" section, and especially when a spoken "Diagnosis:" cue gets
# misheard by the ASR as "Diagnostics:" and sweeps evaluation text (old
# results included) into the diagnostics-ordering chunk that this matcher
# scans (see segment_dictation's marker collision between the two).
_PRIOR_RESULT_QUALIFIER_PATTERN = re.compile(
    r"\b(?:old|previous|prior|earlier|already|last)\b"
    r"|\b\d+\s*(?:days?|weeks?|months?|years?)\s*ago\b"
    r"|\b(?:و)?(?:ال)?قديمه?\b|\b(?:و)?(?:ال)?سابقه?\b|\bمن\s*(?:و)?(?:ال)?قبل\b|\bمنذ\b"
    r"|\b(?:ancien\w*|pr[ée]c[ée]dent\w*|d[ée]j[àa])\b",
    re.I,
)

# Splits on sentence-ending punctuation (Latin and Arabic question mark) so
# a qualifier in one sentence doesn't suppress a genuinely new order stated
# in a neighboring sentence of the same section chunk.
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?؟])\s+")


def keyword_match_new_orders(text: str, synonyms: dict) -> list[str]:
    """Like keyword_match(), but drops a sentence entirely before matching if
    it carries a "prior/old/already/...ago" qualifier — a test name said in
    that sentence is describing a past result, not something to order now."""
    haystack = _normalize_arabic(text)
    kept_sentences = [
        s for s in _SENTENCE_SPLIT_PATTERN.split(haystack)
        if not _PRIOR_RESULT_QUALIFIER_PATTERN.search(s)
    ]
    return keyword_match(" ".join(kept_sentences), synonyms)

# Spoken section markers a physician uses to delimit one continuous dictation
# without touching the screen. Word-boundary regexes so "diagnosis" and
# "diagnostics" don't collide with each other. Arabic/French alternatives
# merged in via `|` rather than branching by detected language — this also
# handles a doctor code-switching mid-dictation (e.g. Arabic speech with
# English medical terms), which is realistic for a bilingual clinic. Arabic
# alternatives are written in normalised form (see _normalize_arabic above);
# matched against the normalised haystack in segment_dictation() below.
#
# Every alternative — Latin-script ones included — gets the same optional
# leading `(?:و)?(?:ال)?` already used for the Arabic terms: ASR output for
# code-switched speech commonly glues "و" (and) and/or "ال" (the) directly
# onto a borrowed English word with zero space regardless of script
# ("والTreatment plan" = و + ال + "Treatment plan", not "و Treatment plan").
# Since Arabic letters count as \w just like Latin ones, `\b` sees no
# boundary at that exact script transition and the marker silently fails to
# match — which used to make the whole rest of the dictation fall into
# whichever section came before it instead of "treatment"/etc.
_SECTION_PATTERNS = [
    ("treatment", re.compile(
        r"\b(?:و)?(?:ال)?treatment\s*plan\b|\b(?:و)?(?:ال)?treatment\b|\b(?:و)?(?:ال)?prescri(?:be|bing|ption)\b"
        r"|\b(?:و)?(?:ال)?خطه\s*(?:و)?(?:ال)?علاج\b|\b(?:و)?(?:ال)?علاج\b|\b(?:و)?(?:ال)?وصفه\s*(?:و)?(?:ال)?طبيه\b|\bصرف\s*(?:و)?(?:ال)?دواء\b"
        r"|\b(?:و)?(?:ال)?plan\s*de\s*traitement\b|\b(?:و)?(?:ال)?traitement\b|\b(?:و)?(?:ال)?prescription\b|\b(?:و)?(?:ال)?ordonnance\b",
        re.I)),
    ("diagnostics", re.compile(
        r"\b(?:و)?(?:ال)?diagnostics?\b|\b(?:و)?(?:ال)?order(?:ing)?\s+(?:tests?|imaging)\b|\b(?:و)?(?:ال)?request(?:ing)?\s+(?:tests?|imaging)\b|\b(?:و)?(?:ال)?labs?\b|\b(?:و)?(?:ال)?imaging\b"
        r"|\b(?:و)?(?:ال)?فحوصات\b|\b(?:و)?(?:ال)?تحاليل\b|\b(?:و)?(?:ال)?اشعه\b|\bطلب\s*(?:و)?(?:ال)?فحوصات\b|\b(?:و)?(?:ال)?تصوير\b"
        r"|\b(?:و)?(?:ال)?examens?\b|\b(?:و)?(?:ال)?analyses?\b|\b(?:و)?(?:ال)?imagerie\b|\b(?:و)?(?:ال)?demande\s*d.examens?\b",
        re.I)),
    ("evaluation", re.compile(
        r"\b(?:و)?(?:ال)?diagnosis\b|\b(?:و)?(?:ال)?evaluation\b|\b(?:و)?(?:ال)?assessment\b|\b(?:و)?(?:ال)?findings\b"
        r"|\b(?:و)?(?:ال)?تشخيص\b|\b(?:و)?(?:ال)?تقييم\b|\b(?:و)?(?:ال)?نتائج\b|\b(?:و)?(?:ال)?فحص\b"
        # French "diagnostic" (noun) is spelled identically to the English
        # adjective in "diagnostic tests" — the negative lookahead keeps this
        # cue for standalone French use without stealing English "diagnostic
        # tests"/"diagnostic imaging" away from the diagnostics pattern above.
        r"|\b(?:و)?(?:ال)?diagnostic\b(?!\s+(?:tests?|imaging))|\b(?:و)?(?:ال)?[ée]valuation\b|\b(?:و)?(?:ال)?r[ée]sultats\b|\b(?:و)?(?:ال)?constatations\b",
        re.I)),
]

# Within the treatment section, "instructions"/"details" is itself a spoken
# cue (same idea as the section markers above) — the LLM doesn't reliably
# pick it up as free text every time, so capture everything said after it
# directly. Only used as a fallback when the AI left details empty.
_DETAILS_CUE_PATTERN = re.compile(
    r"\b(?:instructions?\s*(?:and|&)?\s*details?|details?|instructions?)\b\s*[:,]?\s*"
    r"|\bتعليمات\s*(?:و)?\s*تفاصيل\b\s*[:,]?\s*|\bتفاصيل\b\s*[:,]?\s*|\bتعليمات\b\s*[:,]?\s*|\bملاحظات\b\s*[:,]?\s*"
    r"|\binstructions?\s*(?:et)?\s*d[ée]tails?\b\s*[:,]?\s*|\bd[ée]tails?\b\s*[:,]?\s*",
    re.I)


def extract_details_cue(treatment_text: str) -> str:
    """Return whatever was said after the last "instructions"/"details" cue
    in the treatment section, or "" if the cue wasn't used."""
    haystack = _normalize_arabic(treatment_text)
    matches = list(_DETAILS_CUE_PATTERN.finditer(haystack))
    if not matches:
        return ""
    return treatment_text[matches[-1].end():].strip().rstrip(".").strip()


def _apply_details_fallback(treatments: list, fallback_details: str) -> None:
    """If the doctor used an explicit "instructions"/"details" cue but the AI
    left some treatment's details empty, fill it in directly. Applied to the
    last treatment still missing details, since that's the one the trailing
    speech most likely refers to."""
    if not fallback_details:
        return
    for entry in reversed(treatments):
        if not entry["details"]:
            entry["details"] = fallback_details
            return


# "follow-up date"/"follow up on" is itself a spoken cue, same idea as the
# details cue above — but unlike free-text details, a date said as a raw
# number sequence ("13, 12, 20, 26") is a fixed-shape value a regex can parse
# far more reliably than a small local LLM reading garbled ASR text (ASR
# commonly splits a spoken year like "twenty twenty-six" into two separate
# two-digit numbers). Deterministic parsing wins over the AI guess here, the
# same as keyword_match already does for diagnostic tests/treatment types.
_FOLLOWUP_DATE_CUE_PATTERN = re.compile(
    r"\b(?:و)?(?:ال)?follow[\s-]?up\s*(?:date|visit)?\b\s*[:,]?\s*"
    # (?:و)?(?:ال)? optional, same convention as the synonym lists above —
    # colloquial speech commonly drops the definite article and/or glues a
    # leading "و" (and) directly onto the next word with no space
    # ("وموعد متابعة" not "و موعد المتابعة").
    r"|\b(?:و)?موعد\s*(?:ال)?متابعه\b\s*[:,]?\s*|\b(?:و)?تاريخ\s*(?:ال)?متابعه\b\s*[:,]?\s*|\b(?:و)?موعد\s*(?:ال)?مراجعه\b\s*[:,]?\s*"
    r"|\b(?:و)?(?:ال)?date\s*de\s*suivi\b\s*[:,]?\s*|\b(?:و)?(?:ال)?rendez[\s-]?vous\s*de\s*suivi\b\s*[:,]?\s*|\b(?:و)?(?:ال)?date\s*de\s*contr[oô]le\b\s*[:,]?\s*",
    re.I)


def _numbers_to_iso_date(numbers: list[int], today: datetime) -> str | None:
    """Reconstruct a day/month/year date from a raw sequence of spoken
    numbers. Re-merges a split year (e.g. [20, 26] -> 2026) before assigning
    the remaining one or two numbers to day/month, preferring whichever
    ordering is actually valid (a value over 12 can only be a day)."""
    nums = list(numbers)
    year = None

    if len(nums) >= 2 and 19 <= nums[-2] <= 21 and 0 <= nums[-1] <= 99:
        year = nums[-2] * 100 + nums[-1]
        nums = nums[:-2]
    elif nums and nums[-1] >= 1000:
        year = nums[-1]
        nums = nums[:-1]
    elif nums and 0 <= nums[-1] <= 99:
        year = 2000 + nums[-1]
        nums = nums[:-1]

    if year is None or not (today.year - 1 <= year <= today.year + 5):
        return None

    if len(nums) == 2:
        a, b = nums
        if 1 <= a <= 12 and 1 <= b <= 31 and b > 12:
            month, day = a, b
        elif 1 <= b <= 12 and 1 <= a <= 31:
            day, month = a, b
        else:
            return None
    elif len(nums) == 1 and 1 <= nums[0] <= 31:
        day, month = nums[0], today.month
    else:
        return None

    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


# A follow-up cue is far more often said as a RELATIVE offset ("in 3 weeks",
# "بعد 3 أسابيع", "dans 2 semaines") than as a spelled-out calendar date — but
# _numbers_to_iso_date (below) was built for the latter and has no concept of
# units, so a lone small number like "3" gets misread as a 2-digit year
# (2003), fails the sanity-range check, and silently produces nothing. Tried
# first, before falling back to the absolute-digit-sequence parse, since a
# number immediately followed by a day/week/month word is unambiguous.
_DUAL_DURATION_DAYS = {"يومين": 2, "اسبوعين": 14, "شهرين": 60}
_DURATION_UNIT_DAYS = {
    "day": 1, "days": 1, "يوم": 1, "ايام": 1, "jour": 1, "jours": 1,
    "week": 7, "weeks": 7, "اسبوع": 7, "اسابيع": 7, "semaine": 7, "semaines": 7,
    "month": 30, "months": 30, "شهر": 30, "اشهر": 30, "mois": 30,
}
# ASR commonly spells out small counts as words ("three weeks", "ثلاثة أسابيع",
# "trois semaines") rather than digits -- without this, the count fails
# _RELATIVE_DURATION_PATTERN entirely and date resolution falls through to the
# LLM's own arithmetic, which is not reliable (observed: it once turned "three
# weeks" into a date only 2 weeks out). Arabic words are in normalised form
# (see _normalize_arabic), since matching runs on the normalised haystack.
_NUMBER_WORDS = {
    "a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
    "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
    "واحد": 1, "اثنين": 2, "اثنان": 2, "ثلاث": 3, "ثلاثه": 3, "اربع": 4, "اربعه": 4,
    "خمس": 5, "خمسه": 5, "ست": 6, "سته": 6, "سبع": 7, "سبعه": 7, "ثماني": 8, "ثمانيه": 8,
    "تسع": 9, "تسعه": 9, "عشر": 10, "عشره": 10,
}
_ENGLISH_NUMBER_WORDS = _NUMBER_WORDS  # backwards-compatible name
_COUNT_PATTERN = r"(?<!\w)(\d+|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")"
_RELATIVE_DURATION_PATTERN = re.compile(
    _COUNT_PATTERN + r"\s*(day|days|week|weeks|month|months|يوم|ايام|اسبوع|اسابيع|شهر|اشهر|jours?|semaines?|mois)\b",
    re.I)
# A bare unit after "in"/"بعد"/"dans" means one of it ("بعد شهر" = in a month).
_BARE_UNIT_PATTERN = re.compile(
    r"(?:\bin|\bafter|بعد|\bdans)\s+(?:ال)?(day|week|month|يوم|اسبوع|شهر|jour|semaine|mois)\b", re.I)
_DUAL_DURATION_PATTERN = re.compile(r"\b(يومين|اسبوعين|شهرين)\b")


def _relative_duration_to_iso_date(text: str, today: datetime) -> str | None:
    """Parses a relative offset ("in 3 weeks" / "in three weeks" / "بعد 3
    أسابيع" / "dans 2 semaines", or an Arabic dual form like "أسبوعين" with no
    digit at all) into an absolute date, or None if the text doesn't contain
    one."""
    haystack = _normalize_arabic(text)
    m = _RELATIVE_DURATION_PATTERN.search(haystack)
    if m:
        raw_count = m.group(1).lower()
        count = int(raw_count) if raw_count.isdigit() else _NUMBER_WORDS.get(raw_count)
        unit_days = _DURATION_UNIT_DAYS.get(m.group(2).lower())
        if count and unit_days:
            return (today + timedelta(days=count * unit_days)).strftime("%Y-%m-%d")
    m2 = _DUAL_DURATION_PATTERN.search(haystack)
    if m2:
        return (today + timedelta(days=_DUAL_DURATION_DAYS[m2.group(1)])).strftime("%Y-%m-%d")
    m3 = _BARE_UNIT_PATTERN.search(haystack)
    if m3:
        return (today + timedelta(days=_DURATION_UNIT_DAYS[m3.group(1).lower()])).strftime("%Y-%m-%d")
    return None


def extract_followup_date_cue(treatment_text: str, today: datetime) -> str | None:
    """Return an ISO date parsed from whatever was said after a "follow-up
    date" cue in the treatment section, or None if the cue wasn't used or
    couldn't be parsed as a date."""
    m = _FOLLOWUP_DATE_CUE_PATTERN.search(_normalize_arabic(treatment_text))
    if not m:
        return None
    tail = treatment_text[m.end():]
    cutoff = len(tail)
    details_m = _DETAILS_CUE_PATTERN.search(_normalize_arabic(tail))
    if details_m:
        cutoff = min(cutoff, details_m.start())
    period = tail.find(".")
    if period != -1:
        cutoff = min(cutoff, period)
    tail = tail[:cutoff]
    relative = _relative_duration_to_iso_date(tail, today)
    if relative:
        return relative
    numbers = [int(n) for n in re.findall(r"\d+", tail)]
    return _numbers_to_iso_date(numbers, today)


def _apply_followup_date_fallback(treatments: list, fallback_date: str | None) -> None:
    """If the doctor used an explicit "follow-up date" cue and it parsed
    cleanly, use it to fill in whichever treatment doesn't already have its
    own followUpDate (the AI should have derived that one from its own
    duration already — see the prompt's followUpDate rules). Checked from
    the end since the general follow-up mention is typically about whatever
    was said last.

    With a SINGLE treatment there's no ambiguity about which one an explicit
    follow-up cue belongs to, so the deterministically parsed date overrides
    even a value the AI already set — date arithmetic ("three weeks" -> an
    exact ISO date) is exactly the kind of fixed-format computation a regex
    gets right every time and a small/fast LLM can get wrong (observed: gpt
    turning "three weeks" into a date only 2 weeks out). With MULTIPLE
    treatments this stays a gap-filler only, never overriding an AI value —
    overriding there could clobber a treatment-specific date the AI validly
    derived from its own stated duration under the prompt's rules 1-3, which
    this single cue can't disambiguate between treatments."""
    if not fallback_date or not treatments:
        return
    if len(treatments) == 1:
        treatments[0]["followUpDate"] = fallback_date
        return
    for entry in reversed(treatments):
        if not entry.get("followUpDate"):
            entry["followUpDate"] = fallback_date
            return


def segment_dictation(text: str) -> dict:
    """Split one continuous dictation into evaluation/diagnostics/treatment
    chunks. Anything spoken before the first marker is treated as evaluation,
    since physicians naturally lead with findings before ordering tests or
    prescribing treatment."""
    haystack = _normalize_arabic(text)
    matches = []
    for label, pattern in _SECTION_PATTERNS:
        for m in pattern.finditer(haystack):
            matches.append((m.start(), label))
    matches.sort(key=lambda x: x[0])

    sections = {"evaluation": "", "diagnostics": "", "treatment": ""}
    if not matches:
        sections["evaluation"] = text.strip()
        return sections

    pre_text = text[: matches[0][0]].strip()
    if pre_text:
        sections["evaluation"] += pre_text + " "

    for i, (start, label) in enumerate(matches):
        end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        sections[label] += text[start:end].strip() + " "

    return {k: v.strip() for k, v in sections.items()}


_SURGERY_FIELDS = ("procedurePerformed", "findings", "postoperativePlan")


def _build_surgery_prompt(transcript: str, sections: dict) -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    test_list = ", ".join(f'"{k}" ({v})' for k, v in DIAGNOSTIC_TESTS.items())
    treatment_list = ", ".join(f'"{k}" ({v})' for k, v in TREATMENT_OPTIONS.items())

    return f"""You are a clinical scribe assistant for an orthopedic surgeon dictating an
operative note in one continuous recording, covering the procedure performed,
intraoperative findings, and the postoperative plan. Extract structured data as
JSON ONLY (no markdown fences, no commentary, just the JSON object).

Today's date is {today}. Resolve relative dates ("in two weeks", "next month") to
an absolute YYYY-MM-DD date using today's date as the reference. Use null if no
date was mentioned.

Known diagnostic test ids (use ONLY these ids): {test_list}
Known treatment ids (use ONLY these ids): {treatment_list}

Full transcript:
\"\"\"{transcript}\"\"\"

Rough pre-split of the same transcript (may be incomplete/imperfect, use only as
a hint — the full transcript above is the source of truth):
- Evaluation part: \"\"\"{sections.get('evaluation', '')}\"\"\"
- Diagnostics part: \"\"\"{sections.get('diagnostics', '')}\"\"\"
- Treatment part: \"\"\"{sections.get('treatment', '')}\"\"\"

Return JSON with exactly this shape:
{{
  "diagnosis": "short preoperative/postoperative diagnosis label, e.g. Meniscus Tear, Right Knee",
  "notes": "clinical notes summarizing the procedure from the evaluation part",
  "soap": {{
    "procedurePerformed": "the surgical procedure performed, including laterality/approach if stated",
    "findings": "intraoperative findings — tissue condition, damage observed, etc.",
    "postoperativePlan": "postoperative plan — pain management, follow-up, rehab, restrictions, may restate the diagnostic tests and treatments below in sentence form"
  }},
  "diagnostic_tests": ["<ids from the known diagnostic test ids that were mentioned>"],
  "treatments": [
    {{"type": "<id from the known treatment ids>", "duration": "<e.g. 6 weeks, or null>", "details": "<instructions mentioned>", "followUpDate": "<YYYY-MM-DD or null>"}}
  ]
}}

Rules:
- If a section wasn't mentioned at all, return an empty string/array for it
  instead of guessing.
- Write every "soap" field in clear, grammatically correct clinical English —
  the surgeon is dictating out loud, so silently fix any spoken disfluency,
  filler word, or grammatical slip; never transcribe verbatim if the phrasing
  was awkward. Keep the clinical meaning exact; do not add information that
  was not said.
- Only use ids from the known lists above for diagnostic_tests and
  treatments[].type — never invent new ids.
- If the same treatment (e.g. physiotherapy) has a duration AND a follow-up
  date, put BOTH on the SAME treatment object — never create a second,
  separate treatment object just to hold a follow-up date.
- followUpDate rules (each treatment's date must reflect what was actually
  said ABOUT THAT TREATMENT, not a date meant for a different one):
  1. If a treatment has its own stated duration (e.g. "physiotherapy for 4
     weeks") and no more specific follow-up was mentioned for that same
     treatment, set that treatment's followUpDate to today's date plus its
     OWN duration — do not borrow a duration or date that was said about a
     different treatment.
  2. If the dictation separately mentions a general follow-up appointment
     that is not tied to any one specific treatment (e.g. "follow-up
     appointment in 3 weeks" said on its own, after listing the treatments),
     assign that date to whichever treatment does NOT already have a
     followUpDate from rule 1 above — never overwrite a treatment's own
     duration-derived date with this general one, and never invent a new
     treatment object just to hold it.
  3. A treatment with neither its own duration nor any applicable follow-up
     mention keeps followUpDate as null — do not guess.
- Do not wrap string values in extra quote characters; "diagnosis": "Meniscus Tear"
  is correct, "diagnosis": "'Meniscus Tear'" is NOT."""


def _build_prompt(transcript: str, sections: dict) -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    test_list = ", ".join(f'"{k}" ({v})' for k, v in DIAGNOSTIC_TESTS.items())
    treatment_list = ", ".join(f'"{k}" ({v})' for k, v in TREATMENT_OPTIONS.items())

    return f"""You are a clinical scribe assistant for an orthopedic clinic. A physician
dictated an entire patient visit in one continuous recording, covering diagnosis,
which tests to order, and a treatment plan. Extract structured data as JSON ONLY
(no markdown fences, no commentary, just the JSON object).

Today's date is {today}. Resolve relative dates ("in two weeks", "next month") to
an absolute YYYY-MM-DD date using today's date as the reference. Use null if no
date was mentioned.

Known diagnostic test ids (use ONLY these ids): {test_list}
Known treatment ids (use ONLY these ids): {treatment_list}

Full transcript:
\"\"\"{transcript}\"\"\"

Rough pre-split of the same transcript (may be incomplete/imperfect, use only as
a hint — the full transcript above is the source of truth):
- Evaluation part: \"\"\"{sections.get('evaluation', '')}\"\"\"
- Diagnostics part: \"\"\"{sections.get('diagnostics', '')}\"\"\"
- Treatment part: \"\"\"{sections.get('treatment', '')}\"\"\"

Return JSON with exactly this shape:
{{
  "diagnosis": "short diagnosis label, e.g. Osteoarthritis Grade 3, Right Knee",
  "notes": "clinical notes summarizing history/exam/findings from the evaluation part",
  "soap": {{
    "chiefComplaint": "the patient's presenting complaint, in their own words if stated",
    "historyOfPresentIllness": "onset, duration, character, aggravating/relieving factors of the current problem",
    "pastMedicalHistory": "relevant prior conditions, surgeries, medications mentioned — empty string if none was said",
    "examination": "physical exam findings described (inspection, palpation, range of motion, special tests, etc.)",
    "assessment": "the clinical assessment / diagnosis, same content as the top-level diagnosis field. If the dictation also mentions the RESULT of a PRIOR/EXISTING imaging or diagnostic test — e.g. an old MRI, X-ray, CT scan, ultrasound, or lab result already available, as opposed to a test being newly ordered now — append it on a new line starting with 'Imaging/Test Results: ' so it stays part of the assessment.",
    "plan": "the management plan in prose — may restate the diagnostic tests and treatments below in sentence form"
  }},
  "diagnostic_tests": ["<ids from the known diagnostic test ids that were mentioned>"],
  "treatments": [
    {{"type": "<id from the known treatment ids>", "duration": "<e.g. 6 weeks, or null>", "details": "<instructions mentioned>", "followUpDate": "<YYYY-MM-DD or null>"}}
  ]
}}

Rules:
- If a section wasn't mentioned at all, return an empty string/array for it
  instead of guessing.
- Write every "soap" field in clear, grammatically correct clinical English —
  the doctor is dictating out loud, so silently fix any spoken disfluency,
  filler word, or grammatical slip; never transcribe verbatim if the phrasing
  was awkward. Keep the clinical meaning exact; do not add information that
  was not said.
- Only use ids from the known lists above for diagnostic_tests and
  treatments[].type — never invent new ids.
- diagnostic_tests is ONLY for tests being newly ordered now. If the
  dictation instead mentions the RESULT of a test already done in the past
  (e.g. "his old MRI showed a torn meniscus", "previous X-ray revealed grade
  3 osteoarthritis", "ultrasound from last month showed a rotator cuff
  tear"), do NOT add it to diagnostic_tests — instead fold that result into
  the "assessment" soap field as described above. Never drop a mentioned
  prior result silently.
- If the same treatment (e.g. physiotherapy) has a duration AND a follow-up
  date, put BOTH on the SAME treatment object — never create a second,
  separate treatment object just to hold a follow-up date.
- followUpDate rules (each treatment's date must reflect what was actually
  said ABOUT THAT TREATMENT, not a date meant for a different one):
  1. If a treatment has its own stated duration (e.g. "physiotherapy for 4
     weeks") and no more specific follow-up was mentioned for that same
     treatment, set that treatment's followUpDate to today's date plus its
     OWN duration — do not borrow a duration or date that was said about a
     different treatment.
  2. If the dictation separately mentions a general follow-up appointment
     that is not tied to any one specific treatment (e.g. "follow-up
     appointment in 3 weeks" said on its own, after listing the treatments),
     assign that date to whichever treatment does NOT already have a
     followUpDate from rule 1 above — never overwrite a treatment's own
     duration-derived date with this general one, and never invent a new
     treatment object just to hold it.
  3. A treatment with neither its own duration nor any applicable follow-up
     mention keeps followUpDate as null — do not guess.
- Do not wrap string values in extra quote characters; "diagnosis": "Osteoarthritis"
  is correct, "diagnosis": "'Osteoarthritis'" is NOT."""


def _clean_str(value) -> str:
    """Strip stray wrapping quotes some smaller models add around string
    values despite the prompt's JSON shape (e.g. "'Osteoarthritis'"), and
    normalise the literal text "null"/"none" some models write instead of an
    actual JSON null when a field wasn't mentioned."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    while len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()
    if value.lower() in ("null", "none", "n/a"):
        return ""
    return value


def _clean_date(value):
    cleaned = _clean_str(value)
    return cleaned or None


_SOAP_FIELDS = (
    "chiefComplaint", "historyOfPresentIllness", "pastMedicalHistory",
    "examination", "assessment", "plan",
)


def _clean_note(raw, fields: tuple) -> dict:
    """Normalises the LLM's `soap` object to always carry every field in
    `fields` as a plain string, regardless of whether the model included
    every key."""
    raw = raw if isinstance(raw, dict) else {}
    return {field: _clean_str(raw.get(field)) for field in fields}


def call_openai_extract(prompt: str) -> dict | None:
    try:
        resp = _openai_client.chat.completions.create(
            model=OPENAI_EXTRACT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
        return json.loads(raw)
    except Exception as e:
        print(f"⚠️ OpenAI extraction unavailable, falling back to plain text ({e})")
        return None


def extract_structured(transcript: str, note_type: str = "physician") -> dict:
    """Best-effort structuring of a raw dictation transcript.

    `note_type` selects which prompt/field-shape to structure the "soap" note
    into — "physician" (chief complaint / HPI / PMH / exam / assessment /
    plan, for a clinic visit) or "surgery" (procedure performed / findings /
    postoperative plan, for an operative note). Diagnostic-test and
    treatment-type extraction is identical either way — both note types can
    order follow-up imaging/treatment.

    Diagnostic tests and treatment types are matched by keyword regardless of
    whether the LLM is available — those two fields are picks from a small
    fixed list, so direct word-spotting in the diagnostics/treatment sections
    is both faster and more reliable than waiting on an LLM guess. The LLM is
    only relied on for the genuinely free-text parts: the diagnosis label,
    clinical notes, and resolving things like "duration" / follow-up dates.
    """
    is_surgery = note_type == "surgery"
    fields = _SURGERY_FIELDS if is_surgery else _SOAP_FIELDS
    build_prompt = _build_surgery_prompt if is_surgery else _build_prompt
    # The one field a deterministic fallback CAN populate when the LLM call
    # fails — the free-text field closest to the raw "evaluation" chunk for
    # each note type.
    fallback_field = "findings" if is_surgery else "historyOfPresentIllness"

    today = datetime.utcnow()
    sections = segment_dictation(transcript)
    keyword_tests = keyword_match_new_orders(sections["diagnostics"], DIAGNOSTIC_TEST_SYNONYMS)
    keyword_treatment_types = keyword_match(sections["treatment"], TREATMENT_SYNONYMS)
    fallback_details = extract_details_cue(sections["treatment"])
    fallback_followup_date = extract_followup_date_cue(sections["treatment"], today)

    if not transcript.strip():
        return {
            "diagnosis": "", "notes": "", "soap": _clean_note(None, fields),
            "diagnostic_tests": [], "treatments": [],
            "sections": sections, "ai_structured": False,
        }

    parsed = call_openai_extract(build_prompt(transcript, sections))

    if parsed is None:
        # Extraction call failed: still honor the keyword-matched
        # tests/treatments so voice selection works even with the API down —
        # just without an AI-written diagnosis/notes/soap/duration/follow-up
        # date.
        treatments = [
            {"type": t, "duration": "", "details": "", "followUpDate": None}
            for t in keyword_treatment_types
        ]
        _apply_details_fallback(treatments, fallback_details)
        _apply_followup_date_fallback(treatments, fallback_followup_date)
        fallback_soap = _clean_note(None, fields)
        fallback_soap[fallback_field] = sections["evaluation"]
        return {
            "diagnosis": "",
            "notes": sections["evaluation"] or transcript,
            "soap": fallback_soap,
            "diagnostic_tests": keyword_tests,
            "treatments": treatments,
            "sections": sections,
            "ai_structured": False,
        }

    ai_tests = [t for t in parsed.get("diagnostic_tests", []) or [] if t in DIAGNOSTIC_TESTS]
    diagnostic_tests = list(keyword_tests)
    for t in ai_tests:
        if t not in diagnostic_tests:
            diagnostic_tests.append(t)

    # Smaller/faster models occasionally split one treatment's duration and
    # follow-up date into two separate objects of the same type despite being
    # told not to — merge same-type entries back together defensively.
    treatments_by_type: dict[str, dict] = {}
    for t in keyword_treatment_types:
        treatments_by_type[t] = {"type": t, "duration": "", "details": "", "followUpDate": None}
    for t in parsed.get("treatments", []) or []:
        if not isinstance(t, dict) or t.get("type") not in TREATMENT_OPTIONS:
            continue
        entry = treatments_by_type.setdefault(t["type"], {
            "type": t["type"], "duration": "", "details": "", "followUpDate": None,
        })
        entry["duration"] = entry["duration"] or _clean_str(t.get("duration"))
        entry["details"] = entry["details"] or _clean_str(t.get("details"))
        entry["followUpDate"] = entry["followUpDate"] or _clean_date(t.get("followUpDate"))

    treatments = list(treatments_by_type.values())
    _apply_details_fallback(treatments, fallback_details)
    _apply_followup_date_fallback(treatments, fallback_followup_date)

    return {
        "diagnosis": _clean_str(parsed.get("diagnosis")),
        "notes": _clean_str(parsed.get("notes")) or sections["evaluation"],
        "soap": _clean_note(parsed.get("soap"), fields),
        "diagnostic_tests": diagnostic_tests,
        "treatments": treatments,
        "sections": sections,
        "ai_structured": True,
    }
