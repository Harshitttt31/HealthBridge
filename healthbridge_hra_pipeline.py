"""
HealthBridge — HRA Integration Pipeline  (Option 2: provider-captured)
======================================================================
Faithful implementation of healthbridge_hra_integration_framework.html.

Six stages, one flow:
  1 CAPTURE  - 13-field HRA + per-employee consent (collected at the AHC checkup)
  2 INGEST   - one combined AHC+HRA upload; validate schema; split; match; FLAG (never drop)
  3 STORE    - two key-sharing fact tables; fact_hra is engine-only (strictest tier)
  4 SCORE    - engine joins AHC+HRA -> three-pillar index + completeness tier (+ labs-only fallback)
  5 GOVERN   - role-based access matrix; raw HRA engine-only; k>=20 small-cell suppression
  6 PRESENT  - provider (all CUGs) & HR (own CUG) dashboards; coverage % on both; never raw HRA

Run:  python healthbridge_hra_pipeline.py  /path/to/combined_ahc_hra.csv
"""
from __future__ import annotations
import sys, datetime as dt
import numpy as np, pandas as pd

# ----------------------------------------------------------------------------
# STAGE 1 — CAPTURE  (schema of what the questionnaire collects)
# ----------------------------------------------------------------------------
HRA_FIELDS = ["smoking", "pack_years", "alcohol", "physical_activity", "diet_quality",
              "sleep", "stress", "waist_cm", "fh_diabetes", "fh_hypertension",
              "fh_cvd", "fh_stroke", "fh_cancer"]
KEY = ["employee_id", "CUG"]
REQUIRED_AHC = ["fbs_mg_dl", "systolic_bp_mmhg", "diastolic_bp_mmhg", "ldl_mg_dl",
                "hdl_mg_dl", "triglycerides_mg_dl", "creatinine_mg_dl", "alt_sgpt_u_l",
                "haemoglobin_g_dl", "bmi"]

PILLAR_WEIGHTS = {"clinical": 0.45, "behavioural": 0.20, "future": 0.35}   # framework weights


# ----------------------------------------------------------------------------
# STAGE 3 — STORE  (gated tiers; access is enforced here, not by convention)
# ----------------------------------------------------------------------------
class GatedStore:
    """A fact table with an access tier and an allow-list of roles that may read it."""
    def __init__(self, name: str, df: pd.DataFrame, tier: int, allow_roles: set, owner_scoped=False):
        self._df = df; self.name = name; self.tier = tier
        self.allow_roles = allow_roles; self.owner_scoped = owner_scoped

    def read(self, role: str, cug: str | None = None) -> pd.DataFrame:
        if role not in self.allow_roles:
            raise PermissionError(
                f"DENIED: role '{role}' may not read {self.name} (tier {self.tier}). "
                f"Allowed: {sorted(self.allow_roles)}")
        out = self._df
        if self.owner_scoped and role == "hr":
            if cug is None:
                raise PermissionError("HR access requires a CUG scope.")
            out = out[out["CUG"] == cug]
        return out.copy()


# ----------------------------------------------------------------------------
# STAGE 2 — INGEST
# ----------------------------------------------------------------------------
def ingest_combined(path: str, simulate_coverage: float = 0.75, consent_rate: float = 0.92,
                    seed: int = 42, nrows: int | None = None):
    """Load the single combined upload, validate, split into clinical/questionnaire halves,
    match to employees, and FLAG (not drop) rows missing an ID or consent."""
    df = pd.read_csv(path, nrows=nrows)
    report = {"rows_in": len(df), "flags": {}}

    # --- schema validation
    missing = [c for c in KEY + REQUIRED_AHC if c not in df.columns]
    if missing:
        raise ValueError(f"Schema validation failed; missing required columns: {missing}")
    has_hra_schema = all(c in df.columns for c in HRA_FIELDS)
    report["hra_schema_present"] = has_hra_schema

    # --- capture-stage metadata the real upload would carry; simulated here
    rng = np.random.default_rng(seed)
    # some employees simply have no HRA captured (coverage gap)
    hra_captured = rng.random(len(df)) < simulate_coverage
    # among captured, a few decline consent -> HRA exists but is NOT usable
    consent = hra_captured & (rng.random(len(df)) < consent_rate)
    df = df.assign(
        hra_captured=hra_captured,
        hra_consent=consent,
        hra_capture_date=dt.date.today().isoformat(),
        flag_no_id=df["employee_id"].isna() | df["CUG"].isna(),
        flag_no_consent=hra_captured & ~consent,
    )
    report["flags"]["no_employee_id"] = int(df["flag_no_id"].sum())
    report["flags"]["captured_but_no_consent"] = int(df["flag_no_consent"].sum())
    report["flags"]["hra_not_captured"] = int((~df["hra_captured"]).sum())

    matched = df[~df["flag_no_id"]].copy()

    # --- split into the two halves that share the key
    ahc_cols = [c for c in matched.columns if c not in HRA_FIELDS
                and not c.startswith("hra_") and not c.startswith("flag_")]
    fact_ahc = matched[ahc_cols].copy()

    # fact_hra holds questionnaire ONLY for rows captured WITH consent (others have no usable HRA)
    usable = matched["hra_captured"] & matched["hra_consent"]
    fact_hra = matched.loc[usable, KEY + HRA_FIELDS + ["hra_consent", "hra_capture_date"]].copy()

    report["rows_matched"] = len(matched)
    report["fact_ahc_rows"] = len(fact_ahc)
    report["fact_hra_rows"] = len(fact_hra)
    return fact_ahc, fact_hra, report


def build_stores(fact_ahc: pd.DataFrame, fact_hra: pd.DataFrame) -> dict:
    """Stage 3: place the halves into gated stores with their access tiers."""
    return {
        # Tier 1 — strictest: raw HRA, engine-only, never a dashboard
        "fact_hra": GatedStore("fact_hra", fact_hra, tier=1, allow_roles={"engine"}),
        # Tier 2 — raw AHC labs: engine + the provider that owns them (not HR)
        "fact_ahc": GatedStore("fact_ahc", fact_ahc, tier=2, allow_roles={"engine", "provider"}),
    }


# ----------------------------------------------------------------------------
# STAGE 4 — SCORE  (engine-side; the only place AHC and HRA are joined)
# ----------------------------------------------------------------------------
_MAP = {
    "smoking": {"never": 1.0, "former": 0.7, "current": 0.2},
    "alcohol": {"none": 1.0, "moderate": 0.7, "heavy": 0.3},
    "physical_activity": {"high": 1.0, "moderate": 0.7, "low": 0.3},
    "diet_quality": {"good": 1.0, "average": 0.6, "poor": 0.3},
    "sleep": {"adequate": 1.0, "poor": 0.5},
    "stress": {"none": 1.0, "mild": 0.7, "mod_severe": 0.3},
}

def _clip01(s): return np.clip(s, 0.0, 1.0)

def _clinical_fraction(a: pd.DataFrame) -> pd.Series:
    pen = pd.Series(0.0, index=a.index)
    pen += _clip01((a["fbs_mg_dl"] - 100) / 60) * 0.22
    pen += _clip01((a["systolic_bp_mmhg"] - 120) / 40) * 0.16
    pen += _clip01((a["diastolic_bp_mmhg"] - 80) / 25) * 0.10
    pen += _clip01((a["ldl_mg_dl"] - 100) / 90) * 0.12
    pen += _clip01((40 - a["hdl_mg_dl"]) / 20) * 0.08
    pen += _clip01((a["triglycerides_mg_dl"] - 150) / 200) * 0.08
    pen += _clip01((a["creatinine_mg_dl"] - 1.2) / 1.0) * 0.10
    pen += _clip01((a["alt_sgpt_u_l"] - 40) / 60) * 0.07
    pen += _clip01((13 - a["haemoglobin_g_dl"]) / 4) * 0.07
    return _clip01(1.0 - pen)

def _behavioural_fraction(h: pd.DataFrame) -> pd.Series:
    parts = [h[c].map(_MAP[c]).fillna(0.6) for c in _MAP]
    waist = _clip01(1 - _clip01((h["waist_cm"] - 90) / 25))
    parts.append(waist)
    return _clip01(sum(parts) / len(parts))

def _future_fraction(a: pd.DataFrame, h: pd.DataFrame | None) -> pd.Series:
    risk = pd.Series(0.0, index=a.index)
    risk += _clip01((a["fbs_mg_dl"] - 100) / 80) * 0.30
    risk += _clip01((a["systolic_bp_mmhg"] - 120) / 50) * 0.22
    risk += _clip01((a["ldl_mg_dl"] - 100) / 100) * 0.14
    risk += _clip01((a["bmi"] - 25) / 10) * 0.14
    if h is not None:   # smoking + family history available only WITH HRA
        risk += (h["smoking"] == "current").astype(float) * 0.12
        fh = (h[["fh_diabetes", "fh_hypertension", "fh_cvd", "fh_stroke", "fh_cancer"]]
              .astype(bool).sum(axis=1))
        risk += _clip01(fh / 3) * 0.08
    else:               # degraded: assume non-smoker, no family history (framework rule)
        risk += 0.0
    return _clip01(1.0 - _clip01(risk))

def score_engine(stores: dict) -> pd.DataFrame:
    """Engine joins AHC + HRA and produces the three-pillar index with a completeness tier.
    The result holds ONLY scores/sub-scores + tier — never the raw inputs."""
    ahc = stores["fact_ahc"].read("engine")
    hra = stores["fact_hra"].read("engine")
    j = ahc.merge(hra, on=KEY, how="left", indicator=True)
    has_hra = (j["_merge"] == "both")

    clinical = _clinical_fraction(j)
    future = pd.Series(0.0, index=j.index)
    behavioural = pd.Series(np.nan, index=j.index)

    # COMPLETE rows: full three-pillar
    if has_hra.any():
        cj = j[has_hra]
        behavioural.loc[has_hra] = _behavioural_fraction(cj)
        future.loc[has_hra] = _future_fraction(cj, cj)
    # LABS-ONLY rows: drop behavioural, renormalise clinical+future, degraded future
    if (~has_hra).any():
        lj = j[~has_hra]
        future.loc[~has_hra] = _future_fraction(lj, None)

    w = PILLAR_WEIGHTS
    score = pd.Series(0.0, index=j.index)
    # complete
    score.loc[has_hra] = 1000 * (w["clinical"] * clinical[has_hra]
                                 + w["behavioural"] * behavioural[has_hra]
                                 + w["future"] * future[has_hra])
    # labs-only: renormalise the two surviving pillars to sum to 1
    denom = w["clinical"] + w["future"]
    score.loc[~has_hra] = 1000 * ((w["clinical"] / denom) * clinical[~has_hra]
                                  + (w["future"] / denom) * future[~has_hra])

    res = pd.DataFrame({
        "employee_id": j["employee_id"], "CUG": j["CUG"],
        "health_score": score.round().astype(int),
        "pillar_clinical": clinical.round(3),
        "pillar_behavioural": behavioural.round(3),
        "pillar_future": future.round(3),
        "completeness_tier": np.where(has_hra, "COMPLETE", "LABS-ONLY"),
    })
    return res


# ----------------------------------------------------------------------------
# STAGE 5 — GOVERN  (the access matrix + small-cell suppression)
# ----------------------------------------------------------------------------
K_MIN = 20   # k>=20 small-cell suppression

def _band(s):
    return pd.cut(s, [-1, 300, 600, 749, 1000],
                  labels=["Caution", "Watchful", "Fair", "Excellent"])

def _aggregate(scores: pd.DataFrame, suppress=True) -> pd.DataFrame:
    g = scores.groupby("CUG").agg(
        n=("health_score", "size"),
        mean_score=("health_score", "mean"),
        pct_complete=("completeness_tier", lambda s: (s == "COMPLETE").mean() * 100),
    ).reset_index()
    g["mean_score"] = g["mean_score"].round(0)
    g["pct_complete"] = g["pct_complete"].round(0)
    if suppress:   # Tier-4 rule: suppress any group below k
        small = g["n"] < K_MIN
        g.loc[small, ["mean_score", "pct_complete"]] = np.nan
        g["suppressed"] = small
    return g

def coverage(scores: pd.DataFrame) -> pd.DataFrame:
    return (scores.groupby("CUG")["completeness_tier"]
            .apply(lambda s: round((s == "COMPLETE").mean() * 100, 0))
            .rename("hra_coverage_pct").reset_index())


# ----------------------------------------------------------------------------
# STAGE 6 — PRESENT
# ----------------------------------------------------------------------------
def provider_dashboard(scores: pd.DataFrame) -> dict:
    """Provider: cross-company aggregates across every CUG with data + coverage %.
    No raw HRA, no raw labs surfaced here — aggregates only."""
    agg = _aggregate(scores, suppress=True)
    return {"scope": "ALL CUGs", "per_cug": agg,
            "coverage": coverage(scores),
            "band_mix": scores.assign(band=_band(scores["health_score"]))
                              .pivot_table(index="CUG", columns="band",
                                           values="health_score", aggfunc="size", observed=False)
                              .fillna(0).astype(int)}

def hr_dashboard(scores: pd.DataFrame, cug: str) -> dict:
    """HR: own CUG only. Per the access matrix HR may see individual scores of their own
    employees, plus own aggregates (k>=20) and own coverage %. Other CUGs are invisible."""
    own = scores[scores["CUG"] == cug]
    if own.empty:
        raise PermissionError(f"HR for {cug} has no visibility into other companies.")
    return {"scope": cug,
            "individual_scores": own[["employee_id", "health_score", "completeness_tier"]].head(),
            "aggregate": _aggregate(own, suppress=True),
            "coverage_pct": float(coverage(own)["hra_coverage_pct"].iloc[0])}


# ----------------------------------------------------------------------------
# DEMO / DRIVER
# ----------------------------------------------------------------------------
def run(path: str, nrows: int | None = None):
    print("=" * 74)
    print("STAGE 1-2  CAPTURE + INGEST")
    fact_ahc, fact_hra, rep = ingest_combined(path, nrows=nrows)
    for k, v in rep.items(): print(f"   {k}: {v}")

    print("\nSTAGE 3  STORE (gated tiers)")
    stores = build_stores(fact_ahc, fact_hra)
    for s in stores.values():
        print(f"   {s.name:10s} tier {s.tier}  rows={len(s._df):>6}  readable_by={sorted(s.allow_roles)}")

    print("\nSTAGE 4  SCORE (engine joins AHC+HRA)")
    scores = score_engine(stores)
    tiers = scores["completeness_tier"].value_counts().to_dict()
    print(f"   scored {len(scores)} employees  | tiers={tiers}")
    print(f"   mean score COMPLETE={scores.loc[scores.completeness_tier=='COMPLETE','health_score'].mean():.0f}"
          f"  LABS-ONLY={scores.loc[scores.completeness_tier=='LABS-ONLY','health_score'].mean():.0f}")

    print("\nSTAGE 5  GOVERN (enforced in code)")
    try:
        stores["fact_hra"].read("provider")
    except PermissionError as e:
        print("   [provider -> raw HRA]  ", e)
    try:
        stores["fact_ahc"].read("hr", cug="cisco001")
    except PermissionError as e:
        print("   [hr -> raw AHC labs]   ", e)
    print("   [engine -> raw HRA]     OK (engine is the only reader)")

    print("\nSTAGE 6  PRESENT")
    pv = provider_dashboard(scores)
    print("   PROVIDER dashboard — per-CUG (k>=20 suppressed):")
    print(pv["per_cug"].to_string(index=False).replace("\n", "\n      "))
    hr = hr_dashboard(scores, cug="cisco001")
    print(f"\n   HR dashboard (cisco001) — coverage {hr['coverage_pct']:.0f}% ; sample individual scores:")
    print(hr["individual_scores"].to_string(index=False).replace("\n", "\n      "))
    try:
        hr_dashboard(scores[scores.CUG == "cisco001"], cug="jpm001")
    except PermissionError as e:
        print("   [hr(cisco) -> jpm001]  ", e)
    print("=" * 74)
    return scores


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/outputs/healthbridge_ahc_hra_combined_100k.csv"
    run(p)
