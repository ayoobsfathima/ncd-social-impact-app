"""
NCD Social Impact Score — scoring engine.

This module is a direct Python translation of the validated R script
(NCD_Questionnaire__P_and_C__and_P_scoring.R), so that the score produced
by this application is mathematically identical to the one the R script
produces, given the same answers.

Design choices carried over from the R script:
  - Each item is recoded to a numeric code, then rescaled to 0-100
    using that item's known maximum.
  - A domain score is the mean of its items' 0-100 scores. If every
    item in a domain is missing, the domain score is treated as 0
    (this matches `ifelse(is.nan(domain_100), 0, domain_100)` in R).
  - The final score is a weighted sum of domain scores. The weight set
    used depends on whether the respondent has a caregiver (dom3_caregiver).
    If they do NOT have a caregiver, the caregiver domain is dropped
    from the weighted sum entirely (matches R's na.rm=TRUE behaviour
    when the weight lookup has no row for that domain).
  - Severity band cut-offs (P25 / P75) are the ones supplied by the
    statistician from the reference sample, not recomputed per upload.

Additions beyond the R script (introduced for this application, and
called out explicitly so a statistician auditing the app can see
exactly where the app diverges from the validated script):
  - Values may arrive as free-text Likert labels (e.g. "Frequently",
    "frequently ", "FREQUENTLY") or as raw numeric codes (e.g. 3).
    Both are accepted and normalised the same way.
  - Any value that cannot be matched to a known category is treated
    as missing AND is separately flagged as "unrecognised" so it is
    never silently misclassified.
  - In batch (CSV) mode only: for the general items (i.e. everything
    except the two items with a bespoke rule below), a column is
    median-imputed ONLY if fewer than 2% of its values are missing.
    At or above 2% missing, values are left missing (and the column
    is flagged) rather than imputed, since imputing a high-missingness
    column can distort the domain mean.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Item catalogue
# ---------------------------------------------------------------------------

# The 18 items that are actually scored, plus dom3_caregiver (used only to
# decide which weight set applies) and dob (used only to help impute
# dom4_reproduce). Order matters only for display purposes.

ITEM_LABELS = {
    "dom2_insurance": "Health needs covered by insurance",
    "dom2_oope": "Can afford out-of-pocket medical expenses",
    "dom2_work_fear": "Afraid of not being able to work anymore",
    "dom3_role": "Worried about role reversal with children",
    "dom3_vacation": "Unable to enjoy vacations/outings with family",
    "dom4_uncertainty": "Feels uncertain about the future",
    "dom4_reproduce": "Worried about being unable to have children",
    "dom4_stigma": "Bothered by unsympathetic reactions of others",
    "dom4_exhausted": "Worried caregiver will be exhausted",
    "dom4_overloaded": "Worried caregiver is overloaded",
    "dom5_mobility": "Mobility",
    "dom5_pain": "Pain / discomfort",
    "dom6_help_more": "Feels relative asks for more help than needed",
    "dom6_no_time": "Feels no time for self because of caregiving",
    "dom6_stressed": "Feels stressed balancing caregiving and other duties",
    "dom6_privacy": "Feels lacking privacy because of caregiving",
    "dom6_depend": "Feels relative expects only them to help",
    "dom6_unable": "Worried about being unable to continue caregiving",
}

LIKERT_ITEMS = {
    "dom2_work_fear", "dom3_role", "dom3_vacation", "dom4_uncertainty",
    "dom4_reproduce", "dom4_stigma", "dom4_exhausted", "dom4_overloaded",
    "dom6_help_more", "dom6_no_time", "dom6_stressed", "dom6_privacy",
    "dom6_depend", "dom6_unable",
}
PHYSICAL_ITEMS = {"dom5_mobility", "dom5_pain"}
YESNO_ITEMS = {"dom2_insurance", "dom2_oope"}
CAREGIVER_FLAG_ITEM = "dom3_caregiver"  # yes/no, not itself scored

ALL_SCORED_ITEMS = list(ITEM_LABELS.keys())
ALL_INPUT_ITEMS = ALL_SCORED_ITEMS + [CAREGIVER_FLAG_ITEM]

ITEM_MAX = {
    "dom2_insurance": 1, "dom2_oope": 1, "dom2_work_fear": 4,
    "dom3_role": 4, "dom3_vacation": 4,
    "dom4_uncertainty": 4, "dom4_reproduce": 4, "dom4_stigma": 4,
    "dom4_exhausted": 4, "dom4_overloaded": 4,
    "dom5_mobility": 2, "dom5_pain": 2,
    "dom6_help_more": 4, "dom6_no_time": 4, "dom6_stressed": 4,
    "dom6_privacy": 4, "dom6_depend": 4, "dom6_unable": 4,
}

DOMAIN_ITEMS = {
    "economic": ["dom2_insurance", "dom2_oope", "dom2_work_fear"],
    "social": ["dom3_role", "dom3_vacation"],
    "psych": ["dom4_uncertainty", "dom4_reproduce", "dom4_stigma",
              "dom4_exhausted", "dom4_overloaded"],
    "phys": ["dom5_mobility", "dom5_pain"],
    "caregiver": ["dom6_help_more", "dom6_no_time", "dom6_stressed",
                  "dom6_privacy", "dom6_depend", "dom6_unable"],
}

DOMAIN_LABELS = {
    "economic": "Economic", "social": "Social", "psych": "Psychological",
    "phys": "Physical", "caregiver": "Caregiver",
}

# weight sets, keyed by whether the respondent HAS a caregiver
WEIGHTS = {
    True: {  # has a caregiver -> 5 domains
        "economic": 0.0766, "social": 0.297, "psych": 0.270,
        "phys": 0.235, "caregiver": 0.122,
    },
    False: {  # no caregiver -> 4 domains, caregiver domain excluded entirely
        "economic": 0.115, "social": 0.276, "psych": 0.342, "phys": 0.266,
    },
}

# Cut-offs supplied by the statistician from the reference sample
P25_CUTOFF = 20.2
P75_CUTOFF = 39.9

MISSING_IMPUTE_THRESHOLD = 0.02  # 2%


# ---------------------------------------------------------------------------
# Value normalisation / classification
# ---------------------------------------------------------------------------

def _normalize(raw) -> str:
    s = str(raw).strip().lower()
    s = re.sub(r"[\s\-/]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _is_blank(raw) -> bool:
    if raw is None:
        return True
    try:
        import math
        if isinstance(raw, float) and math.isnan(raw):
            return True
    except Exception:
        pass
    return str(raw).strip() == ""


class Unrecognized(Exception):
    """Raised internally when a value can't be matched to any category."""


def classify_likert(raw) -> Optional[int]:
    if _is_blank(raw):
        return None
    n = _normalize(raw)
    if re.fullmatch(r"\d+(\.0+)?", n):
        v = int(float(n))
        if 0 <= v <= 4:
            return v
        raise Unrecognized(raw)
    if re.fullmatch(r"(not_at_all|never|almost_never|none)", n):
        return 0
    if re.fullmatch(r"rarely", n):
        return 1
    if re.fullmatch(r"sometimes|occasionally", n):
        return 2
    if re.fullmatch(r"frequently|often", n):
        return 3
    if re.fullmatch(r"nearly_always|almost_always|always", n):
        return 4
    if n in ("not_applicable", "na", "n_a"):
        return None
    raise Unrecognized(raw)


def classify_physical(raw) -> Optional[int]:
    if _is_blank(raw):
        return None
    n = _normalize(raw)
    if re.fullmatch(r"\d+(\.0+)?", n):
        v = int(float(n))
        if 0 <= v <= 2:
            return v
        raise Unrecognized(raw)
    if re.fullmatch(r"no_problem|no_pain", n):
        return 0
    if re.search(r"some_problem|some_pain", n):
        return 1
    if re.fullmatch(r"bed|mostly_confined_to_bed|extreme|extreme_pain", n):
        return 2
    raise Unrecognized(raw)


def classify_yesno(raw) -> Optional[int]:
    """Matches the R script's yesno_map: yes -> 0, no -> 1."""
    if _is_blank(raw):
        return None
    n = _normalize(raw)
    if n in ("0",):
        return 0
    if n in ("1",):
        return 1
    if re.fullmatch(r"y|yes|true", n):
        return 0
    if re.fullmatch(r"n|no|false", n):
        return 1
    raise Unrecognized(raw)


def classify_item(item: str, raw):
    """Returns numeric code (or None if blank). Raises Unrecognized if the
    value is present but unmatched to any known category."""
    if item in LIKERT_ITEMS:
        return classify_likert(raw)
    if item in PHYSICAL_ITEMS:
        return classify_physical(raw)
    if item in YESNO_ITEMS or item == CAREGIVER_FLAG_ITEM:
        return classify_yesno(raw)
    raise KeyError(f"Unknown item: {item}")


# ---------------------------------------------------------------------------
# Age helpers
# ---------------------------------------------------------------------------

def parse_dob(raw) -> Optional[date]:
    if _is_blank(raw):
        return None
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def compute_age(dob: Optional[date], as_of: Optional[date] = None) -> Optional[int]:
    if dob is None:
        return None
    as_of = as_of or date.today()
    return int((as_of - dob).days // 365.25)


def age_group(age: Optional[int]) -> Optional[str]:
    if age is None:
        return None
    if age < 25:
        return "<25"
    if age <= 35:
        return "25-35"
    if age <= 44:
        return "36-44"
    if age <= 49:
        return "45-49"
    return "50+"


# ---------------------------------------------------------------------------
# Result objects
# ---------------------------------------------------------------------------

@dataclass
class RowFlag:
    row_id: str
    field: str
    issue: str
    detail: str = ""


@dataclass
class ScoreResult:
    total_score: Optional[float]
    severity: Optional[str]
    domain_scores: dict = field(default_factory=dict)
    has_caregiver: Optional[bool] = None
    age: Optional[int] = None
    flags: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def severity_band(score: float) -> str:
    if score <= P25_CUTOFF:
        return "Low"
    if score <= P75_CUTOFF:
        return "Moderate"
    return "High"


def score_from_codes(codes: dict, has_caregiver: Optional[bool]) -> tuple[Optional[float], Optional[str], dict]:
    """codes: {item: numeric_code_or_None}. Returns (total, severity, domain_scores)."""
    domain_scores = {}
    for domain, items in DOMAIN_ITEMS.items():
        vals = []
        for it in items:
            v = codes.get(it)
            if v is not None:
                vals.append((v / ITEM_MAX[it]) * 100)
        domain_scores[domain] = round(sum(vals) / len(vals), 2) if vals else 0.0

    if has_caregiver is None:
        has_caregiver = False  # conservative default; caller should flag this

    weights = WEIGHTS[has_caregiver]
    total = sum(domain_scores.get(d, 0.0) * w for d, w in weights.items())
    total = round(total, 1)
    severity = severity_band(total)
    return total, severity, domain_scores


# ---------------------------------------------------------------------------
# Single-patient scoring (clinician mode)
# ---------------------------------------------------------------------------

def score_single(answers: dict, dob_raw=None, as_of: Optional[date] = None) -> ScoreResult:
    """
    answers: dict mapping item name -> raw value (label or numeric code).
             Must include dom3_caregiver. May omit any scored item (treated
             as missing -> excluded from that domain's mean).
    dob_raw: raw date-of-birth string/date, used only for the
             dom4_reproduce bespoke imputation rule.
    """
    flags: list[RowFlag] = []
    notes: list[str] = []
    codes = {}

    for item in ALL_INPUT_ITEMS:
        raw = answers.get(item)
        try:
            codes[item] = classify_item(item, raw)
        except Unrecognized:
            codes[item] = None
            flags.append(RowFlag("patient", item, "unrecognized_value", str(raw)))

    dob = parse_dob(dob_raw)
    age = compute_age(dob, as_of)
    if dob_raw and dob is None:
        flags.append(RowFlag("patient", "dob", "unparseable_date", str(dob_raw)))

    # Bespoke rule: dom4_reproduce
    if codes.get("dom4_reproduce") is None:
        if age is not None and age >= 49:
            codes["dom4_reproduce"] = 0
            notes.append("dom4_reproduce imputed to 0 (age >= 49).")
        else:
            notes.append(
                "dom4_reproduce left missing: no reference dataset available "
                "in single-patient mode to impute an age-group median."
            )

    # Bespoke rule: caregiver-burden worry items default to 0 if missing
    for it in ("dom4_exhausted", "dom4_overloaded"):
        if codes.get(it) is None:
            codes[it] = 0
            notes.append(f"{it} imputed to 0 (assumption: no reported worry if unanswered).")

    caregiver_code = codes.get(CAREGIVER_FLAG_ITEM)
    has_caregiver = None
    if caregiver_code is not None:
        has_caregiver = (caregiver_code == 0)
    else:
        flags.append(RowFlag("patient", CAREGIVER_FLAG_ITEM, "missing",
                              "Caregiver status unknown; defaulted to 'no caregiver' weighting. Verify with the patient."))

    total, severity, domain_scores = score_from_codes(codes, has_caregiver)

    return ScoreResult(
        total_score=total, severity=severity, domain_scores=domain_scores,
        has_caregiver=has_caregiver, age=age, flags=flags, notes=notes,
    )


# ---------------------------------------------------------------------------
# Batch scoring (researcher / CSV mode)
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = ["id", "dob"] + ALL_INPUT_ITEMS


def validate_columns(columns: list[str]) -> list[str]:
    """Returns a list of human-readable column errors (empty if OK)."""
    errors = []
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    extra = [c for c in columns if c not in REQUIRED_COLUMNS]
    if missing:
        errors.append(
            "Missing required column(s): " + ", ".join(missing) +
            ". Please use the provided template and do not rename columns."
        )
    if extra:
        errors.append(
            "Unexpected column(s) found: " + ", ".join(extra) +
            ". Only the columns in the template are accepted; remove extra columns and re-upload."
        )
    return errors


def score_batch(rows: list[dict]) -> tuple[list[dict], list[RowFlag], dict]:
    """
    rows: list of dicts, one per respondent, raw values keyed by column name
          (must include 'id', 'dob', and all items in ALL_INPUT_ITEMS).

    Returns (result_rows, flags, column_summary)
      result_rows: original row + total_score, severity, domain columns
      flags: list of RowFlag
      column_summary: {item: {"missing_pct": float, "imputed": bool}}
    """
    flags: list[RowFlag] = []
    n = len(rows)

    # Pass 1: classify every cell, collect codes matrix
    codes_matrix: list[dict] = []
    ages: list[Optional[int]] = []
    for row in rows:
        rid = str(row.get("id", "")) or "?"
        row_codes = {}
        for item in ALL_INPUT_ITEMS:
            raw = row.get(item)
            try:
                row_codes[item] = classify_item(item, raw)
            except Unrecognized:
                row_codes[item] = None
                flags.append(RowFlag(rid, item, "unrecognized_value", str(raw)))
        dob = parse_dob(row.get("dob"))
        if row.get("dob") and dob is None:
            flags.append(RowFlag(rid, "dob", "unparseable_date", str(row.get("dob"))))
        age = compute_age(dob)
        ages.append(age)
        codes_matrix.append(row_codes)

    # Pass 2: column-level missingness + conditional median imputation
    column_summary = {}
    general_items = [it for it in ALL_INPUT_ITEMS
                      if it not in ("dom4_reproduce", "dom4_exhausted", "dom4_overloaded")]
    for item in general_items:
        values = [rc[item] for rc in codes_matrix]
        missing_n = sum(1 for v in values if v is None)
        missing_pct = missing_n / n if n else 0.0
        imputed = False
        if 0 < missing_n < n and missing_pct < MISSING_IMPUTE_THRESHOLD:
            present = [v for v in values if v is not None]
            med = round(statistics.median(present))
            for rc in codes_matrix:
                if rc[item] is None:
                    rc[item] = med
            imputed = True
        elif missing_pct >= MISSING_IMPUTE_THRESHOLD and missing_n > 0:
            flags.append(RowFlag(
                "(column)", item, "high_missingness",
                f"{missing_pct:.1%} missing - left unimputed; item excluded from that "
                f"domain's average wherever missing.",
            ))
        column_summary[item] = {"missing_pct": round(missing_pct * 100, 2), "imputed": imputed}

    # Pass 3: bespoke imputation for dom4_reproduce (age-based, then age-group median)
    still_missing_idx = []
    for i, rc in enumerate(codes_matrix):
        if rc.get("dom4_reproduce") is None:
            age = ages[i]
            if age is not None and age >= 49:
                rc["dom4_reproduce"] = 0
            else:
                still_missing_idx.append(i)

    if still_missing_idx:
        # age-group-wise median from rows that DO have a value
        group_values: dict[str, list[int]] = {}
        for i, rc in enumerate(codes_matrix):
            v = rc.get("dom4_reproduce")
            if v is not None:
                g = age_group(ages[i])
                group_values.setdefault(g, []).append(v)
        for i in still_missing_idx:
            g = age_group(ages[i])
            vals = group_values.get(g)
            rid = str(rows[i].get("id", "")) or "?"
            if vals:
                codes_matrix[i]["dom4_reproduce"] = round(statistics.median(vals))
            else:
                flags.append(RowFlag(
                    rid, "dom4_reproduce", "insufficient_data_to_impute",
                    "No age-group reference values available in this upload; left missing.",
                ))

    missing_n = sum(1 for rc in codes_matrix if rc.get("dom4_reproduce") is None)
    column_summary["dom4_reproduce"] = {
        "missing_pct": round(missing_n / n * 100, 2) if n else 0.0,
        "imputed": "age-rule + age-group median (bespoke)",
    }

    # Pass 4: dom4_exhausted / dom4_overloaded -> 0 if missing
    for it in ("dom4_exhausted", "dom4_overloaded"):
        for rc in codes_matrix:
            if rc.get(it) is None:
                rc[it] = 0
        column_summary[it] = {"missing_pct": 0.0, "imputed": "defaulted to 0 (bespoke rule)"}

    # Pass 5: compute scores
    result_rows = []
    for i, row in enumerate(rows):
        rid = str(row.get("id", "")) or "?"
        rc = codes_matrix[i]
        caregiver_code = rc.get(CAREGIVER_FLAG_ITEM)
        has_caregiver = None
        if caregiver_code is not None:
            has_caregiver = (caregiver_code == 0)
        else:
            flags.append(RowFlag(rid, CAREGIVER_FLAG_ITEM, "missing",
                                  "Caregiver status unknown; defaulted to 'no caregiver' weighting."))
        total, severity, domain_scores = score_from_codes(rc, has_caregiver)

        out = dict(row)
        out["age"] = ages[i]
        out["has_caregiver"] = has_caregiver
        for d in DOMAIN_ITEMS:
            out[f"domain_{d}_score"] = domain_scores.get(d, 0.0)
        out["Total_Social_Impact"] = total
        out["Severity"] = severity
        result_rows.append(out)

    return result_rows, flags, column_summary
