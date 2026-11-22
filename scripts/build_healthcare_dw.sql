-- ============================================================================
-- Healthcare Operations & 30-Day Readmission Data Warehouse (DuckDB SQL)
-- ============================================================================
-- Builds star-schema analytical tables (`dim_patients_v1`, `fact_encounters_v1`)
-- from raw MITRE Synthea synthetic EHR CSV exports (patients, encounters,
-- conditions, payers).
--
-- Key Analytical Logic:
--   1. 30-Day Inpatient Readmissions via LEAD() window function partitioned by
--      patient_id and ordered by encounter_start.
--   2. Observed / Expected (O/E) Length of Stay (LOS) using department-level
--      AVG() OVER() benchmarks, both raw and clean (excluding extreme LOS
--      outliers caused by unclosed historical encounters).
--   3. Margin Leakage & Payer Coverage financial reconciliation.
--   4. Patient Clinical Risk Tiering & Age Cohort stratification.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. DIMENSION TABLE: dim_patients_v1
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_patients_v1 AS
WITH active_conditions AS (
    SELECT
        PATIENT AS patient_id,
        COUNT(DISTINCT CODE) AS active_chronic_conditions
    FROM read_csv_auto('raw/conditions.csv')
    WHERE STOP IS NULL
    GROUP BY PATIENT
),
base_patients AS (
    SELECT
        p.Id AS patient_id,
        p.GENDER AS gender,
        p.RACE AS race,
        p.ETHNICITY AS ethnicity,
        p.CITY AS city,
        p.STATE AS state,
        p.ZIP AS zip,
        DATE_DIFF(
            'year',
            CAST(p.BIRTHDATE AS DATE),
            COALESCE(CAST(p.DEATHDATE AS DATE), DATE '2020-12-31')
        ) AS age,
        COALESCE(c.active_chronic_conditions, 0) AS active_chronic_conditions,
        CASE WHEN p.DEATHDATE IS NOT NULL THEN 1 ELSE 0 END AS is_deceased,
        ROUND(CAST(p.HEALTHCARE_EXPENSES AS DOUBLE), 2) AS lifetime_healthcare_expenses,
        ROUND(CAST(p.HEALTHCARE_COVERAGE AS DOUBLE), 2) AS lifetime_healthcare_coverage
    FROM read_csv_auto('raw/patients.csv') p
    LEFT JOIN active_conditions c
        ON p.Id = c.patient_id
)
SELECT
    patient_id,
    gender,
    race,
    ethnicity,
    city,
    state,
    zip,
    age,
    CASE
        WHEN age < 18 THEN 'Pediatric'
        WHEN age BETWEEN 18 AND 39 THEN 'Young Adult'
        WHEN age BETWEEN 40 AND 64 THEN 'Middle-Aged'
        ELSE 'Senior'
    END AS age_cohort,
    active_chronic_conditions,
    CASE
        WHEN active_chronic_conditions >= 4 OR is_deceased = 1 THEN 'High Risk'
        WHEN active_chronic_conditions BETWEEN 2 AND 3 THEN 'Moderate Risk'
        ELSE 'Low Risk'
    END AS clinical_risk_tier,
    is_deceased,
    lifetime_healthcare_expenses,
    lifetime_healthcare_coverage
FROM base_patients;


-- ----------------------------------------------------------------------------
-- 2. FACT TABLE: fact_encounters_v1
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE fact_encounters_v1 AS
WITH acute_encounters AS (
    SELECT
        e.Id AS encounter_id,
        e.PATIENT AS patient_id,
        COALESCE(py.NAME, 'NO_INSURANCE') AS payer_name,
        CASE
            WHEN COALESCE(py.NAME, 'NO_INSURANCE') = 'NO_INSURANCE'
                THEN 'Self-Pay / Uncompensated Care'
            ELSE 'Insured Payer'
        END AS payer_group,
        CASE
            WHEN COALESCE(py.NAME, 'NO_INSURANCE') = 'NO_INSURANCE'
                THEN 'Self-Pay / Uncompensated Care'
            ELSE py.NAME
        END AS payer_display,
        LOWER(e.ENCOUNTERCLASS) AS encounter_class,
        CASE
            WHEN LOWER(COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, '')) LIKE '%lung%'
              OR LOWER(COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, '')) LIKE '%asthma%'
              OR LOWER(COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, '')) LIKE '%pneumonia%'
                THEN 'Pulmonology'
            WHEN LOWER(COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, '')) LIKE '%cardiac%'
              OR LOWER(COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, '')) LIKE '%myocardial%'
              OR LOWER(COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, '')) LIKE '%heart%'
                THEN 'Cardiology'
            WHEN LOWER(COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, '')) LIKE '%pregnan%'
              OR LOWER(COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, '')) LIKE '%obstetric%'
                THEN 'Obstetrics'
            WHEN LOWER(COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, '')) LIKE '%fracture%'
              OR LOWER(COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, '')) LIKE '%joint%'
                THEN 'Orthopedics'
            ELSE 'General Medicine'
        END AS clinical_service_line,
        COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, 'Unspecified') AS clinical_reason,
        COALESCE(e.REASONDESCRIPTION, e.DESCRIPTION, 'Unspecified') AS primary_clinical_driver,
        CAST(e.START AS TIMESTAMP) AS encounter_start,
        CAST(e.STOP AS TIMESTAMP) AS encounter_stop,
        EXTRACT(YEAR FROM CAST(e.START AS TIMESTAMP)) AS encounter_year,
        CASE
            WHEN EXTRACT(YEAR FROM CAST(e.START AS TIMESTAMP)) < 2011 THEN '<2011'
            ELSE CAST(EXTRACT(YEAR FROM CAST(e.START AS TIMESTAMP)) AS VARCHAR)
        END AS year_bucket,
        CASE
            WHEN EXTRACT(YEAR FROM CAST(e.START AS TIMESTAMP)) BETWEEN 2011 AND 2020 THEN 1
            ELSE 0
        END AS is_operational_window_2011_2020,
        ROUND(
            DATE_DIFF('minute', CAST(e.START AS TIMESTAMP), CAST(e.STOP AS TIMESTAMP)) / 1440.0,
            4
        ) AS actual_los_days,
        CASE WHEN LOWER(e.ENCOUNTERCLASS) = 'inpatient' THEN 1 ELSE 0 END AS is_inpatient,
        ROUND(CAST(e.BASE_ENCOUNTER_COST AS DOUBLE), 2) AS base_encounter_cost,
        ROUND(CAST(e.TOTAL_CLAIM_COST AS DOUBLE), 2) AS total_claim_cost,
        ROUND(CAST(e.PAYER_COVERAGE AS DOUBLE), 2) AS payer_coverage,
        ROUND(
            GREATEST(CAST(e.TOTAL_CLAIM_COST AS DOUBLE) - CAST(e.PAYER_COVERAGE AS DOUBLE), 0.0),
            2
        ) AS margin_leakage
    FROM read_csv_auto('raw/encounters.csv') e
    LEFT JOIN read_csv_auto('raw/payers.csv') py
        ON e.PAYER = py.Id
    WHERE LOWER(e.ENCOUNTERCLASS) IN ('inpatient', 'emergency', 'urgentcare')
),
-- Flag extreme LOS outliers (> 30 days) caused by unclosed historical encounters
los_flagged AS (
    SELECT
        *,
        CASE WHEN actual_los_days > 30.0 THEN 1 ELSE 0 END AS is_los_outlier
    FROM acute_encounters
),
-- Compute department-level Expected LOS (raw & clean) using window functions
los_benchmarked AS (
    SELECT
        *,
        ROUND(
            AVG(actual_los_days) OVER (
                PARTITION BY clinical_service_line, encounter_class
            ),
            4
        ) AS expected_los_days_raw,
        ROUND(
            AVG(CASE WHEN is_los_outlier = 0 THEN actual_los_days END) OVER (
                PARTITION BY clinical_service_line, encounter_class
            ),
            4
        ) AS expected_los_days_clean
    FROM los_flagged
),
-- Compute 30-day inpatient readmission flag via LEAD() over inpatient stays
inpatient_sequence AS (
    SELECT
        encounter_id,
        LEAD(encounter_start) OVER (
            PARTITION BY patient_id
            ORDER BY encounter_start, encounter_id
        ) AS next_inpatient_start
    FROM los_benchmarked
    WHERE is_inpatient = 1
)
SELECT
    b.encounter_id,
    b.patient_id,
    b.payer_name,
    b.payer_group,
    b.payer_display,
    b.encounter_class,
    b.clinical_service_line,
    b.clinical_reason,
    b.primary_clinical_driver,
    b.encounter_start,
    b.encounter_stop,
    b.encounter_year,
    b.year_bucket,
    b.is_operational_window_2011_2020,
    b.actual_los_days,
    b.expected_los_days_raw,
    ROUND(b.actual_los_days / NULLIF(b.expected_los_days_raw, 0), 4) AS oe_los_ratio_raw,
    b.is_los_outlier,
    b.expected_los_days_clean,
    ROUND(b.actual_los_days / NULLIF(b.expected_los_days_clean, 0), 4) AS oe_los_ratio_clean,
    b.is_inpatient,
    CASE
        WHEN b.is_inpatient = 1
         AND s.next_inpatient_start IS NOT NULL
         AND DATE_DIFF('day', b.encounter_stop, s.next_inpatient_start) BETWEEN 0 AND 30
        THEN 1
        ELSE 0
    END AS is_30d_readmission,
    b.base_encounter_cost,
    b.total_claim_cost,
    b.payer_coverage,
    b.margin_leakage
FROM los_benchmarked b
LEFT JOIN inpatient_sequence s
    ON b.encounter_id = s.encounter_id;

-- Export analytical tables for Tableau / BI consumption
COPY dim_patients_v1 TO 'data/dim_patients_v1.csv' (HEADER, DELIMITER ',');
COPY fact_encounters_v1 TO 'data/fact_encounters_v1.csv' (HEADER, DELIMITER ',');
