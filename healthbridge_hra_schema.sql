-- ============================================================================
-- HealthBridge — HRA Integration: PostgreSQL realization of the gated tiers
-- Implements Stage 3 (Store) + Stage 5 (Govern) of the integration framework.
-- The privacy rules are enforced by the database, not by application convention:
--   Tier 1  raw HRA   -> engine role only
--   Tier 2  raw AHC   -> engine + provider (owner)
--   Tier 3  score     -> provider (role-gated) + HR (own CUG via RLS)
--   Tier 4  aggregates-> open, but only through k>=20 views
-- ============================================================================

-- ---------- roles (the two-login model + the scoring engine) ----------------
DO $$ BEGIN
  CREATE ROLE hb_engine   NOLOGIN;   -- scoring engine: the only reader of raw HRA
  CREATE ROLE hb_provider NOLOGIN;   -- health provider: owns AHC, cross-company
  CREATE ROLE hb_hr       NOLOGIN;   -- company HR: own CUG only
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE SCHEMA IF NOT EXISTS raw    AUTHORIZATION hb_engine;   -- gated fact tables
CREATE SCHEMA IF NOT EXISTS scored AUTHORIZATION hb_engine;   -- scores only
CREATE SCHEMA IF NOT EXISTS pub;                              -- safe aggregate views

-- ---------- Stage 3: two fact tables sharing the key ------------------------
CREATE TABLE IF NOT EXISTS raw.fact_ahc (
    employee_id   text NOT NULL,
    cug           text NOT NULL,
    ahc_date      date,
    fbs_mg_dl numeric, systolic_bp_mmhg numeric, diastolic_bp_mmhg numeric,
    ldl_mg_dl numeric, hdl_mg_dl numeric, triglycerides_mg_dl numeric,
    creatinine_mg_dl numeric, alt_sgpt_u_l numeric, haemoglobin_g_dl numeric, bmi numeric,
    -- ... remaining clinical biomarkers ...
    PRIMARY KEY (employee_id, cug)
);

CREATE TABLE IF NOT EXISTS raw.fact_hra (         -- TIER 1: strictest
    employee_id   text NOT NULL,
    cug           text NOT NULL,
    smoking text, pack_years numeric, alcohol text, physical_activity text,
    diet_quality text, sleep text, stress text, waist_cm numeric,
    fh_diabetes boolean, fh_hypertension boolean, fh_cvd boolean,
    fh_stroke boolean, fh_cancer boolean,
    hra_consent      boolean NOT NULL DEFAULT false,   -- no consent, no scoring use
    hra_capture_date date,
    PRIMARY KEY (employee_id, cug)
);

CREATE TABLE IF NOT EXISTS scored.fact_health_score (   -- TIER 3: score only, no raw inputs
    employee_id text NOT NULL,
    cug         text NOT NULL,
    health_score      integer,
    pillar_clinical   numeric,
    pillar_behavioural numeric,
    pillar_future     numeric,
    completeness_tier text CHECK (completeness_tier IN ('COMPLETE','LABS-ONLY')),
    scored_at         timestamptz DEFAULT now(),
    PRIMARY KEY (employee_id, cug)
);

-- ---------- Stage 5: tier grants --------------------------------------------
REVOKE ALL ON ALL TABLES IN SCHEMA raw, scored FROM PUBLIC;

-- Tier 1: raw HRA is engine-only. Provider and HR are never granted.
GRANT SELECT, INSERT, UPDATE ON raw.fact_hra TO hb_engine;

-- Tier 2: raw AHC labs to engine + provider (the owner); NOT to HR.
GRANT SELECT, INSERT, UPDATE ON raw.fact_ahc TO hb_engine;
GRANT SELECT                  ON raw.fact_ahc TO hb_provider;

-- Tier 3: scores written by engine; read by provider (role-gated) and HR (RLS below).
GRANT SELECT, INSERT, UPDATE ON scored.fact_health_score TO hb_engine;
GRANT SELECT                  ON scored.fact_health_score TO hb_provider, hb_hr;

-- ---------- Stage 5: row-level security so HR sees only its own CUG ----------
ALTER TABLE scored.fact_health_score ENABLE ROW LEVEL SECURITY;

-- HR: only rows for the CUG set in the session variable app.cug
CREATE POLICY hr_own_cug ON scored.fact_health_score
    FOR SELECT TO hb_hr
    USING (cug = current_setting('app.cug', true));

-- Provider: all CUGs (role-gated to individual scores by policy presence)
CREATE POLICY provider_all ON scored.fact_health_score
    FOR SELECT TO hb_provider USING (true);

-- Engine: full access
CREATE POLICY engine_all ON scored.fact_health_score
    FOR ALL TO hb_engine USING (true) WITH CHECK (true);

-- ---------- Stage 4 helper: join is only possible for the engine -------------
-- (provider/HR cannot run this because they lack SELECT on raw.fact_hra)
CREATE OR REPLACE VIEW scored.v_scoring_input AS
SELECT a.*, h.smoking, h.alcohol, h.physical_activity, h.diet_quality, h.sleep,
       h.stress, h.waist_cm, h.fh_diabetes, h.fh_hypertension, h.fh_cvd,
       h.fh_stroke, h.fh_cancer, h.hra_consent,
       (h.employee_id IS NOT NULL AND h.hra_consent) AS has_usable_hra
FROM raw.fact_ahc a
LEFT JOIN raw.fact_hra h USING (employee_id, cug);

-- ---------- Stage 6 / Tier 4: aggregates ONLY through k>=20 views ------------
CREATE OR REPLACE VIEW pub.v_cug_aggregate AS
SELECT cug,
       count(*)                                              AS n,
       CASE WHEN count(*) >= 20 THEN round(avg(health_score)) END AS mean_score,
       CASE WHEN count(*) >= 20
            THEN round(100.0 * avg((completeness_tier='COMPLETE')::int), 0) END AS hra_coverage_pct
FROM scored.fact_health_score
GROUP BY cug
HAVING count(*) >= 20;                       -- small-cell suppression at the source

GRANT SELECT ON pub.v_cug_aggregate TO hb_provider, hb_hr;

-- HR sees its own aggregate row only (RLS-style guard on the view)
CREATE OR REPLACE VIEW pub.v_my_cug_aggregate AS
SELECT * FROM pub.v_cug_aggregate
WHERE cug = current_setting('app.cug', true);
GRANT SELECT ON pub.v_my_cug_aggregate TO hb_hr;

-- ============================================================================
-- USAGE
--   Engine load:   SET ROLE hb_engine;   INSERT INTO raw.fact_ahc / raw.fact_hra ...
--   Engine score:  INSERT INTO scored.fact_health_score SELECT ... FROM scored.v_scoring_input;
--   Provider read: SET ROLE hb_provider; SELECT * FROM pub.v_cug_aggregate;       -- all CUGs
--   HR read:       SET ROLE hb_hr; SET app.cug = 'cisco001';
--                  SELECT * FROM scored.fact_health_score;   -- only cisco001 (RLS)
--                  SELECT * FROM pub.v_my_cug_aggregate;      -- own aggregate, k>=20
--   Any attempt by hb_provider/hb_hr to read raw.fact_hra fails: permission denied.
-- ============================================================================
