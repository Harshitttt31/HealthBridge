"""Clinical reference ranges for the Health Index (Indian-adjusted baseline).

Each scored biomarker maps to a 4-point band:
    (hard_low, soft_low, soft_high, hard_high)

Interpretation, by `direction` (from weights.csv):
  - up_bad   : only the high side matters. Full score up to `soft_high`,
               declining linearly to 0 at `hard_high`. (lows are None)
  - down_bad : only the low side matters. Full score at/above `soft_low`,
               declining to 0 at `hard_low`. (highs are None)
  - band     : full score within [soft_low, soft_high], declining to 0 at
               `hard_low` below and `hard_high` above.

These are a calibratable baseline — tune without touching engine code.
`None` marks a side that does not penalise the score.
"""

REFERENCE_RANGES = {
    # column: (hard_low, soft_low, soft_high, hard_high)
    # --- Glycaemic / Metabolic (up_bad) ---
    "hba1c_percent": (None, None, 5.7, 10.0),
    "fbs_mg_dl": (None, None, 100, 300),
    "ppbs_mg_dl": (None, None, 140, 300),
    # --- Blood Pressure (up_bad) ---
    "systolic_bp_mmhg": (None, None, 120, 180),
    "diastolic_bp_mmhg": (None, None, 80, 120),
    # --- Lipids ---
    "ldl_mg_dl": (None, None, 100, 250),          # up_bad
    "hdl_mg_dl": (20, 40, None, None),            # down_bad
    "triglycerides_mg_dl": (None, None, 150, 500),
    "cho_hdl_ratio": (None, None, 4.5, 8.0),
    "tgl_hdl_ratio": (None, None, 3.0, 8.0),
    # --- Renal (up_bad) ---
    "creatinine_mg_dl": (None, None, 1.2, 5.0),
    "bun_mg_dl": (None, None, 20, 60),
    # --- Hepatic ---
    "alt_sgpt_u_l": (None, None, 40, 200),
    "ast_sgot_u_l": (None, None, 40, 200),
    "ggt_u_l": (None, None, 50, 300),
    "alp_u_l": (None, None, 120, 400),
    "bilirubin_total_mg_dl": (None, None, 1.2, 5.0),
    "albumin_g_dl": (2.5, 3.5, None, None),       # down_bad
    "total_protein_g_dl": (5.0, 6.0, 8.3, 9.5),   # band
    "globulin_g_dl": (1.5, 2.0, 3.5, 4.5),        # band
    # --- Anthropometric (band) ---
    "bmi": (16.0, 18.5, 24.9, 35.0),
    # --- Haematology ---
    "haemoglobin_g_dl": (7.0, 12.0, None, None),  # down_bad
    "total_wbc_cells_cumm": (2500, 4000, 11000, 20000),
    "platelet_count_lakhs_cumm": (0.5, 1.5, 4.1, 6.0),
    "rdw_cv_percent": (None, None, 14.5, 25.0),   # up_bad
    "mcv_fl": (70, 80, 100, 110),
    "rbc_million_cmm": (3.5, 4.2, 5.9, 7.0),
    "neutrophils_percent": (30, 40, 75, 85),
    "lymphocytes_percent": (10, 20, 45, 55),
    # --- Fitness ---
    "vo2_max_ml_kg_min": (15, 35, None, None),    # down_bad
    "duke_treadmill_score": (-11, 5, None, None), # down_bad (Duke -25..+15)
    "resting_hr_bpm": (None, None, 80, 130),      # up_bad
    # --- Inflammatory (up_bad) ---
    "crp_mg_l": (None, None, 3.0, 50.0),
    "esr_mm_hr": (None, None, 20, 80),
    "uric_acid_mg_dl": (None, None, 6.0, 12.0),
    "ra_factor_iu_ml": (None, None, 15, 100),
    # --- Thyroid (band) ---
    "tsh_uiu_ml": (0.1, 0.4, 4.5, 10.0),
    "total_t4_ug_dl": (3.0, 4.5, 12.0, 15.0),
    "total_t3_ng_dl": (40, 80, 200, 250),
    # --- Nutrition ---
    "vitamin_d_ng_ml": (10, 30, None, None),      # down_bad
    "vitamin_b12_pg_ml": (100, 200, None, None),  # down_bad
    "ferritin_ng_ml": (10, 30, 300, 500),         # band
    # --- ECG (up_bad) ---
    "qtcb_ms": (None, None, 440, 500),
    # --- Urine ---
    "urine_pus_cells_hpf": (None, None, 5, 30),
    "urine_rbc_hpf": (None, None, 2, 20),
    "urine_specific_gravity": (1.000, 1.005, 1.030, 1.035),
    "urine_ph": (4.5, 5.0, 8.0, 9.0),
}

# Hard danger thresholds. If ANY is breached, the final Health Index is capped
# (see CRITICAL_CAP) so one severe condition can't be averaged away (BRD §7.2.3).
CRITICAL_RULES = {
    "creatinine_mg_dl": ("gt", 5.0),
    "fbs_mg_dl": ("gt", 300),
    "hba1c_percent": ("gt", 10.0),
    "haemoglobin_g_dl": ("lt", 7.0),
    "systolic_bp_mmhg": ("gt", 180),
    "diastolic_bp_mmhg": ("gt", 120),
    "alt_sgpt_u_l": ("gt", 200),
}

CRITICAL_CAP = 300  # max Health Index when any critical rule fires
