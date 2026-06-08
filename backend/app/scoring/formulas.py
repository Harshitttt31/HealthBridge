"""Published clinical formulas for the Health Index deduction model (BRD §7).

Each domain function takes a row (pandas Series or dict) and returns the penalty
fraction in [0, 1] for that domain (renal also returns the computed eGFR). All
functions are pure and deterministic. Missing inputs yield fraction 0.0 for that
domain (never crash), so a sparse panel is penalised only where data exists.

Canonical equations used (no invented coefficients):
  - ASCVD 10-year risk: 2013 ACC/AHA Pooled Cohort Equations (non-Hispanic white
    coefficients used as the race-free default).
  - eGFR: CKD-EPI 2021 race-free creatinine equation.
  - FIB-4: (age x AST) / (platelets[10^9/L] x sqrt(ALT)).
  - Metabolic syndrome: IDF criteria (waist proxied by BMI; waist not in dataset).
  - Anaemia: WHO Hb cut-offs for non-pregnant adults.
  - VO2max fitness: ACSM-style age/sex cardiorespiratory categories.
"""

from __future__ import annotations

import math

from .deduction_config import BANDS, CHARLSON, CHARLSON_CAP, band_fraction

# Inputs not present in the dataset — documented assumptions (add later):
#   smoking status -> assumed non-smoker (TODO: capture at intake)
#   waist circumference -> proxied by BMI >= 25 in the IDF MetS count
_ASSUME_SMOKER = False


# --- safe accessors ---------------------------------------------------------
def _num(row, col) -> float:
    """Return row[col] as float, or NaN if absent/non-numeric."""
    try:
        v = row[col]
    except (KeyError, IndexError, TypeError):
        return float("nan")
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f


def _isnan(x) -> bool:
    return x is None or x != x


def _str(row, col) -> str:
    try:
        v = row[col]
    except (KeyError, IndexError, TypeError):
        return ""
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return str(v)


def _sex(row) -> str:
    """Normalised 'M'/'F' (defaults to 'M' if unknown)."""
    s = _str(row, "sex").strip().upper()
    if s.startswith("F"):
        return "F"
    return "M"


def _chronic_tokens(row) -> list[str]:
    raw = _str(row, "chronic_disease")
    return [t.strip() for t in raw.split(",") if t.strip()]


def _has_diabetes(row) -> bool:
    hba1c = _num(row, "hba1c_percent")
    if not _isnan(hba1c) and hba1c >= 6.5:
        return True
    return "Type 2 Diabetes" in _chronic_tokens(row)


# --- cardiovascular: ASCVD Pooled Cohort Equations --------------------------
# 2013 ACC/AHA PCE coefficients (non-Hispanic white). Untreated SBP, since the
# dataset has no BP-treatment flag.
_PCE = {
    "F": dict(ln_age=-29.799, ln_age_sq=4.884, ln_tc=13.540, ln_age_tc=-3.114,
              ln_hdl=-13.578, ln_age_hdl=3.149, ln_sbp=1.957,
              smoker=7.574, ln_age_smoker=-1.665, diabetes=0.661,
              s0=0.9665, mean=-29.18),
    "M": dict(ln_age=12.344, ln_age_sq=0.0, ln_tc=11.853, ln_age_tc=-2.664,
              ln_hdl=-7.990, ln_age_hdl=1.769, ln_sbp=1.764,
              smoker=7.837, ln_age_smoker=-1.795, diabetes=0.658,
              s0=0.9144, mean=61.18),
}


def _ascvd_risk_pct(age, sex, tc, hdl, sbp, diabetes, smoker=False):
    """10-year ASCVD risk percent via the Pooled Cohort Equations, or None.

    The PCE is validated for ages 40-79; ages outside are clamped to that range
    (a pragmatic in-range evaluation — a dedicated Framingham fallback is a TODO).
    """
    if any(_isnan(x) for x in (age, tc, hdl, sbp)) or tc <= 0 or hdl <= 0 or sbp <= 0:
        return None
    age = min(max(age, 40.0), 79.0)
    c = _PCE[sex]
    la, ltc, lhdl, lsbp = math.log(age), math.log(tc), math.log(hdl), math.log(sbp)
    sm = 1.0 if smoker else 0.0
    s = (c["ln_age"] * la + c["ln_age_sq"] * la * la
         + c["ln_tc"] * ltc + c["ln_age_tc"] * la * ltc
         + c["ln_hdl"] * lhdl + c["ln_age_hdl"] * la * lhdl
         + c["ln_sbp"] * lsbp
         + c["smoker"] * sm + c["ln_age_smoker"] * la * sm
         + c["diabetes"] * (1.0 if diabetes else 0.0))
    risk = 1.0 - c["s0"] ** math.exp(s - c["mean"])
    return max(0.0, min(1.0, risk)) * 100.0


def cardiovascular(row) -> float:
    risk = _ascvd_risk_pct(
        _num(row, "age"), _sex(row),
        _num(row, "total_cholesterol_mg_dl"), _num(row, "hdl_mg_dl"),
        _num(row, "systolic_bp_mmhg"), _has_diabetes(row), smoker=_ASSUME_SMOKER,
    )
    if risk is None:
        return 0.0
    return band_fraction(risk, BANDS["cardiovascular_ascvd_pct"])


# --- glycaemic --------------------------------------------------------------
def glycaemic(row) -> float:
    hba1c = _num(row, "hba1c_percent")
    if _isnan(hba1c):
        fbs = _num(row, "fbs_mg_dl")
        if _isnan(fbs):
            return 0.0
        # ADAG: eAG(mg/dL) = 28.7*A1c - 46.7  ->  A1c = (eAG + 46.7) / 28.7
        hba1c = (fbs + 46.7) / 28.7
    return band_fraction(hba1c, BANDS["glycaemic_hba1c"])


# --- renal: CKD-EPI 2021 + stage -------------------------------------------
def _egfr(creat, age, sex):
    if _isnan(creat) or _isnan(age) or creat <= 0:
        return None
    female = sex == "F"
    k = 0.7 if female else 0.9
    a = -0.241 if female else -0.302
    r = creat / k
    egfr = (142.0 * (min(r, 1.0) ** a) * (max(r, 1.0) ** -1.200)
            * (0.9938 ** age) * (1.012 if female else 1.0))
    return egfr


def _egfr_stage(egfr) -> str:
    if egfr >= 90:
        return "G1"
    if egfr >= 60:
        return "G2"
    if egfr >= 45:
        return "G3a"
    if egfr >= 30:
        return "G3b"
    if egfr >= 15:
        return "G4"
    return "G5"


def renal(row) -> dict:
    egfr = _egfr(_num(row, "creatinine_mg_dl"), _num(row, "age"), _sex(row))
    if egfr is None:
        return {"fraction": 0.0, "egfr": None}
    frac = BANDS["renal_stage"][_egfr_stage(egfr)]
    return {"fraction": frac, "egfr": egfr}


# --- hepatic: FIB-4 ---------------------------------------------------------
def hepatic(row) -> float:
    age = _num(row, "age")
    ast = _num(row, "ast_sgot_u_l")
    alt = _num(row, "alt_sgpt_u_l")
    plt_lakhs = _num(row, "platelet_count_lakhs_cumm")
    if any(_isnan(x) for x in (age, ast, alt, plt_lakhs)) or alt <= 0 or plt_lakhs <= 0:
        return 0.0
    # platelets: lakhs/cumm (x10^5 per uL) -> x10^9/L is x100 (1.5 lakh/uL = 150 x10^9/L).
    plt = plt_lakhs * 100.0
    fib4 = (age * ast) / (plt * math.sqrt(alt))
    return band_fraction(fib4, BANDS["hepatic_fib4"])


# --- metabolic syndrome: IDF criteria count --------------------------------
def metabolic_syndrome(row) -> float:
    female = _sex(row) == "F"
    bmi = _num(row, "bmi")
    tg = _num(row, "triglycerides_mg_dl")
    hdl = _num(row, "hdl_mg_dl")
    sbp = _num(row, "systolic_bp_mmhg")
    dbp = _num(row, "diastolic_bp_mmhg")
    fbs = _num(row, "fbs_mg_dl")

    count = 0
    if not _isnan(bmi) and bmi >= 25:                       # central obesity (BMI proxy)
        count += 1
    if not _isnan(tg) and tg >= 150:
        count += 1
    if not _isnan(hdl) and hdl < (50 if female else 40):    # low HDL
        count += 1
    if (not _isnan(sbp) and sbp >= 130) or (not _isnan(dbp) and dbp >= 85):
        count += 1
    if not _isnan(fbs) and fbs >= 100:
        count += 1
    return BANDS["metsyn_components"][count]


# --- haematology: WHO anaemia (+ WBC/platelet nudge) ------------------------
def _anaemia_category(hb, female) -> str:
    if _isnan(hb):
        return "normal"
    if female:
        if hb >= 12:
            return "normal"
    else:
        if hb >= 13:
            return "normal"
    if hb >= 11:
        return "mild"
    if hb >= 8:
        return "moderate"
    return "severe"


def haematology(row) -> float:
    hb = _num(row, "haemoglobin_g_dl")
    frac = BANDS["haematology_anaemia"][_anaemia_category(hb, _sex(row) == "F")]
    # Small additive nudge for out-of-range WBC / platelets (cap at 1.0).
    wbc = _num(row, "total_wbc_cells_cumm")
    plt = _num(row, "platelet_count_lakhs_cumm")
    if not _isnan(wbc) and (wbc < 4000 or wbc > 11000):
        frac += 0.10
    if not _isnan(plt) and (plt < 1.5 or plt > 4.1):
        frac += 0.10
    return min(frac, 1.0)


# --- fitness: ACSM VO2max categories ---------------------------------------
# Per (sex, age-bracket): (excellent, good, fair, poor) lower bounds in ml/kg/min;
# vo2 >= excellent -> excellent; >= good -> good; ...; below poor -> very_poor.
_VO2 = {
    "M": [(29, (53, 49, 44, 39)), (39, (49, 45, 40, 35)), (49, (45, 41, 36, 31)),
          (59, (43, 39, 34, 29)), (200, (41, 37, 32, 27))],
    "F": [(29, (49, 44, 39, 34)), (39, (45, 40, 35, 30)), (49, (42, 37, 32, 27)),
          (59, (40, 35, 30, 25)), (200, (37, 32, 27, 22))],
}


def _vo2_category(vo2, age, sex) -> str:
    if _isnan(vo2):
        return "excellent"  # absent -> no penalty (fraction 0)
    if _isnan(age):
        age = 40.0
    table = _VO2[sex]
    cuts = next(c for upper, c in table if age <= upper)
    exc, good, fair, poor = cuts
    if vo2 >= exc:
        return "excellent"
    if vo2 >= good:
        return "good"
    if vo2 >= fair:
        return "fair"
    if vo2 >= poor:
        return "poor"
    return "very_poor"


def fitness(row) -> float:
    vo2 = _num(row, "vo2_max_ml_kg_min")
    if _isnan(vo2):
        return 0.0
    cat = _vo2_category(vo2, _num(row, "age"), _sex(row))
    return BANDS["fitness_vo2_cat"][cat]


# --- thyroid ----------------------------------------------------------------
def thyroid(row) -> float:
    tsh = _num(row, "tsh_uiu_ml")
    if _isnan(tsh):
        return 0.0
    if tsh > 10 or tsh < 0.1:
        cat = "overt"
    elif tsh > 4.0 or tsh < 0.4:
        cat = "subclinical"
    else:
        cat = "euthyroid"
    return BANDS["thyroid_tsh"][cat]


# --- inflammatory -----------------------------------------------------------
def inflammatory(row) -> float:
    crp = _num(row, "crp_mg_l")
    frac = band_fraction(crp, BANDS["inflammatory_crp"]) if not _isnan(crp) else 0.0
    uric = _num(row, "uric_acid_mg_dl")
    esr = _num(row, "esr_mm_hr")
    if not _isnan(uric) and uric > 7.0:
        frac += 0.10
    if not _isnan(esr) and esr > 20:
        frac += 0.10
    return min(frac, 1.0)


# --- nutrition --------------------------------------------------------------
def _vitd_status(v):
    if _isnan(v):
        return None
    if v >= 30:
        return "sufficient"
    if v >= 20:
        return "insufficient"
    return "deficient"


def _b12_status(v):
    if _isnan(v):
        return None
    if v >= 300:
        return "sufficient"
    if v >= 200:
        return "insufficient"
    return "deficient"


def _ferritin_status(v):
    if _isnan(v):
        return None
    if v >= 30:
        return "sufficient"
    if v >= 15:
        return "insufficient"
    return "deficient"


def nutrition(row) -> float:
    statuses = [
        _vitd_status(_num(row, "vitamin_d_ng_ml")),
        _b12_status(_num(row, "vitamin_b12_pg_ml")),
        _ferritin_status(_num(row, "ferritin_ng_ml")),
    ]
    present = [s for s in statuses if s is not None]
    if not present:
        return 0.0
    worst = max(present, key=lambda s: BANDS["nutrition_status"][s])
    return BANDS["nutrition_status"][worst]


# --- chronic disease: Charlson burden --------------------------------------
def chronic_burden(row) -> float:
    burden = sum(CHARLSON.get(tok, 0.0) for tok in _chronic_tokens(row))
    return min(burden / CHARLSON_CAP, 1.0)
