#!/usr/bin/env python3
"""
Generate 60 clean health/medical synthetic CDEs for pipeline QC validation.

Three clinical domains with varying verbosity levels and no instrument or
temporal noise.  Designed to be combined with health_gravity_a, set1b_clinical,
and health_drift for a 360-CDE all-health evaluation set.

Usage:
    python scripts/generate_health_base.py -o data/synthetic_qc/health_base/health_base.json --pretty

Design:
    Cardiovascular Assessment         TERSE         (20 CDEs, synCRD)
    Respiratory Function Evaluation   INFORMATIONAL (20 CDEs, synRSP)
    Metabolic Health Monitoring       EXPANSIVE     (20 CDEs, synMET)

Cross-domain overlap groups (7):
    xdh:blood_pressure, xdh:lab_values, xdh:bmi, xdh:demographics,
    xdh:medication, xdh:imaging, xdh:treatment_response
"""

import argparse
import csv
import json
import os
import sys

# ---------------------------------------------------------------------------
# CDE content definitions — 20 per topic
# Each tuple: (name, question, definition)
# ---------------------------------------------------------------------------

TOPIC_CRD = [
    # --- Core cardiac parameters (0-6) ---
    (
        "Resting heart rate",
        "Heart rate measured at rest in beats per minute",
        "Number of cardiac cycles per minute measured in a resting state.",
    ),
    (
        "Systolic blood pressure",
        "Peak arterial pressure during cardiac contraction",
        "Maximum arterial blood pressure during ventricular systole in mmHg.",
    ),
    (
        "Diastolic blood pressure",
        "Minimum arterial pressure between heartbeats",
        "Lowest arterial blood pressure during ventricular diastole in mmHg.",
    ),
    (
        "Mean arterial pressure",
        "Average arterial pressure over one cardiac cycle",
        "Weighted average blood pressure throughout one complete cardiac cycle.",
    ),
    (
        "Cardiac output",
        "Volume of blood pumped by the heart per minute",
        "Total volume of blood ejected by the heart each minute in liters.",
    ),
    (
        "Left ventricular ejection fraction",
        "Percentage of blood ejected from left ventricle per beat",
        "Proportion of left ventricular blood volume pumped per contraction.",
    ),
    (
        "QT interval duration",
        "Time from QRS complex onset to T-wave end",
        "Duration of ventricular depolarization and repolarization on ECG.",
    ),
    # --- Cardiac biomarkers (7-9) ---
    (
        "Troponin I concentration",
        "Serum cardiac troponin I level",
        "Blood concentration of cardiac-specific troponin I protein marker.",
    ),
    (
        "B-type natriuretic peptide level",
        "Plasma BNP concentration",
        "Circulating plasma level of B-type natriuretic peptide hormone.",
    ),
    (
        "Total cholesterol",
        "Total serum cholesterol concentration",
        "Sum of all cholesterol fractions measured in blood serum samples.",
    ),
    # --- Lipid panel (10-12) ---
    (
        "LDL cholesterol",
        "Low-density lipoprotein cholesterol level",
        "Serum concentration of low-density lipoprotein cholesterol fraction.",
    ),
    (
        "HDL cholesterol",
        "High-density lipoprotein cholesterol level",
        "Serum concentration of high-density lipoprotein cholesterol fraction.",
    ),
    (
        "Triglyceride level",
        "Fasting serum triglyceride concentration",
        "Fasting blood level of triglyceride lipids measured in serum.",
    ),
    # --- Vascular markers (13-15) ---
    (
        "C-reactive protein",
        "High-sensitivity CRP concentration",
        "Serum level of high-sensitivity C-reactive protein inflammation marker.",
    ),
    (
        "Carotid intima-media thickness",
        "Ultrasound measurement of carotid artery wall thickness",
        "Combined thickness of carotid artery intimal and medial layers.",
    ),
    (
        "Heart rate variability",
        "Variation in time between consecutive heartbeats",
        "Standard deviation of time intervals between consecutive heartbeats.",
    ),
    # --- Cross-domain (16-19) ---
    (
        "Body mass index at cardiac assessment",
        "BMI calculated from height and weight at cardiac visit",
        "Weight in kilograms divided by height in meters squared at visit.",
    ),
    (
        "Cardiac medication adherence",
        "Self-reported adherence to prescribed cardiac medications",
        "Patient-reported compliance rate with prescribed cardiac drug regimen.",
    ),
    (
        "Age at cardiovascular screening",
        "Patient age at time of cardiac risk evaluation",
        "Age in years at the time of cardiovascular risk factor assessment.",
    ),
    (
        "Cardiac treatment response score",
        "Overall response to cardiovascular treatment regimen",
        "Clinician-rated overall response to prescribed cardiac therapy.",
    ),
]

TOPIC_RSP = [
    # --- Core spirometry (0-4) ---
    (
        "Forced expiratory volume in one second",
        "Maximum volume of air exhaled in the first second of a forced breath",
        "The volume of air that can be forcefully expelled from the lungs in "
        "the first second of a maximal expiratory effort after full "
        "inspiration. FEV1 is the primary measure of airflow limitation.",
    ),
    (
        "Forced vital capacity",
        "Total volume of air exhaled during a complete forced expiration",
        "The maximum volume of air that can be forcefully exhaled from "
        "the lungs following a maximal inhalation. Forced vital capacity "
        "reflects total lung volume accessible during forced breathing.",
    ),
    (
        "FEV1 to FVC ratio",
        "Ratio of forced expiratory volume to forced vital capacity",
        "The proportion of forced vital capacity expelled in the first "
        "second of forced exhalation. A reduced ratio below the lower "
        "limit of normal indicates obstructive ventilatory impairment.",
    ),
    (
        "Peak expiratory flow rate",
        "Maximum airflow speed achieved during forced exhalation",
        "The highest instantaneous flow rate attained during a maximal "
        "forced expiratory maneuver. Peak flow monitoring tracks "
        "day-to-day variability in airway caliber.",
    ),
    (
        "Oxygen saturation by pulse oximetry",
        "Peripheral blood oxygen saturation measured noninvasively",
        "The percentage of arterial hemoglobin saturated with oxygen "
        "as measured by pulse oximetry at the fingertip. Values below "
        "ninety percent typically indicate clinically significant hypoxemia.",
    ),
    # --- Gas exchange and mechanics (5-8) ---
    (
        "Respiratory rate",
        "Number of breaths taken per minute at rest",
        "The frequency of breathing cycles per minute recorded at rest. "
        "Normal adult respiratory rate ranges from twelve to twenty "
        "breaths per minute; deviations suggest respiratory compromise.",
    ),
    (
        "Arterial partial pressure of oxygen",
        "Oxygen tension in arterial blood sample",
        "The partial pressure of dissolved oxygen in arterial blood "
        "measured from an arterial blood gas sample. PaO2 directly "
        "reflects the efficiency of pulmonary gas exchange.",
    ),
    (
        "Arterial partial pressure of carbon dioxide",
        "Carbon dioxide tension in arterial blood sample",
        "The partial pressure of dissolved carbon dioxide in arterial "
        "blood. Elevated PaCO2 indicates hypoventilation or impaired "
        "carbon dioxide elimination by the respiratory system.",
    ),
    (
        "Six-minute walk distance",
        "Total distance walked in six minutes on a flat corridor",
        "The maximum distance a patient can walk on a flat surface in "
        "six minutes under standardized conditions. The six-minute walk "
        "test assesses functional exercise capacity in cardiopulmonary disease.",
    ),
    # --- Additional lung function (9-13) ---
    (
        "Diffusing capacity for carbon monoxide",
        "Rate of carbon monoxide transfer across the alveolar membrane",
        "The volume of carbon monoxide absorbed from inspired gas per "
        "unit time per unit pressure gradient. DLCO evaluates the "
        "integrity of the alveolar-capillary membrane for gas exchange.",
    ),
    (
        "Tidal volume",
        "Volume of air inhaled or exhaled in a normal resting breath",
        "The volume of air moved into and out of the lungs during a "
        "single normal breathing cycle at rest. Tidal volume is a "
        "fundamental parameter in ventilatory mechanics assessment.",
    ),
    (
        "Bronchodilator response",
        "Change in FEV1 after inhaled bronchodilator administration",
        "The percentage improvement in forced expiratory volume after "
        "administration of an inhaled short-acting bronchodilator. "
        "A significant response supports the diagnosis of reversible airway obstruction.",
    ),
    (
        "Dyspnea severity score",
        "Patient-reported breathlessness severity rating",
        "A standardized numeric rating of the patient's perceived "
        "difficulty of breathing, assessed using a validated dyspnea "
        "scale. Higher scores indicate more severe breathlessness.",
    ),
    (
        "Exhaled nitric oxide concentration",
        "Fractional concentration of nitric oxide in exhaled breath",
        "The level of nitric oxide measured in exhaled breath, "
        "expressed in parts per billion. Elevated exhaled nitric oxide "
        "is a marker of eosinophilic airway inflammation.",
    ),
    # --- Cross-domain (14-19) ---
    (
        "Chest radiograph classification",
        "Diagnostic category assigned to the chest X-ray findings",
        "The radiologist's classification of chest radiograph findings "
        "into a diagnostic category. Chest imaging aids in the "
        "evaluation of pulmonary parenchymal and pleural abnormalities.",
    ),
    (
        "Blood pressure at pulmonary function visit",
        "Resting blood pressure recorded at pulmonary clinic appointment",
        "Systolic and diastolic blood pressure measured in the seated "
        "position at the pulmonary function laboratory visit. Blood "
        "pressure is a routine vital sign during respiratory assessment.",
    ),
    (
        "Body mass index at respiratory assessment",
        "BMI at the time of pulmonary function evaluation",
        "Weight in kilograms divided by height in meters squared "
        "recorded at the respiratory assessment visit. BMI influences "
        "lung volumes and respiratory mechanics in clinical evaluation.",
    ),
    (
        "Respiratory medication adherence",
        "Self-reported adherence to prescribed respiratory medications",
        "Patient-reported compliance rate with prescribed inhaler and "
        "respiratory medication regimens. Adherence affects treatment "
        "outcomes and disease control in chronic respiratory conditions.",
    ),
    (
        "Age at pulmonary function evaluation",
        "Patient age at the time of lung function testing",
        "Age in years at the time of pulmonary function testing. "
        "Age is a key determinant of predicted reference values for "
        "spirometric and diffusion capacity measurements.",
    ),
    (
        "Pulmonary treatment response rating",
        "Clinician-rated response to respiratory treatment plan",
        "Overall assessment of the patient's clinical response to the "
        "prescribed respiratory treatment regimen. Treatment response "
        "informs decisions on therapy continuation or adjustment.",
    ),
]

TOPIC_MET = [
    # --- Core glucose metabolism (0-3) ---
    (
        "Fasting blood glucose concentration",
        "Blood sugar level measured after an overnight fast of at least "
        "eight hours used to screen for diabetes mellitus",
        "Fasting blood glucose is the concentration of glucose in venous "
        "plasma measured after an overnight fast of at least eight hours. "
        "The test is a primary screening tool for diabetes mellitus and "
        "prediabetes. Fasting glucose values of 100 to 125 milligrams per "
        "deciliter indicate impaired fasting glucose, while values at or "
        "above 126 milligrams per deciliter are diagnostic of diabetes when "
        "confirmed on repeat testing.",
    ),
    (
        "Hemoglobin A1c percentage",
        "Glycated hemoglobin level reflecting average blood glucose over "
        "the preceding two to three months",
        "Hemoglobin A1c measures the percentage of hemoglobin molecules "
        "that have undergone non-enzymatic glycation, providing an "
        "integrated estimate of average blood glucose concentration over "
        "the preceding two to three month lifespan of circulating red "
        "blood cells. An A1c value of 6.5 percent or higher is diagnostic "
        "of diabetes mellitus, while values between 5.7 and 6.4 percent "
        "indicate increased risk for developing diabetes.",
    ),
    (
        "Fasting insulin level",
        "Serum insulin concentration measured after overnight fasting "
        "used to evaluate insulin secretion and resistance",
        "Fasting serum insulin is the concentration of insulin in venous "
        "blood collected after an overnight fast. When interpreted "
        "alongside fasting glucose, elevated insulin levels suggest "
        "insulin resistance, a hallmark of metabolic syndrome and type 2 "
        "diabetes. Fasting insulin is also used to calculate surrogate "
        "indices of insulin resistance such as the homeostatic model "
        "assessment for insulin resistance.",
    ),
    (
        "HOMA-IR insulin resistance index",
        "Homeostatic model assessment score estimating insulin "
        "resistance from fasting glucose and fasting insulin values",
        "The homeostatic model assessment for insulin resistance is "
        "calculated as the product of fasting glucose in millimoles per "
        "liter and fasting insulin in microunits per milliliter divided "
        "by a constant of 22.5. Higher values indicate greater insulin "
        "resistance. HOMA-IR is widely used in epidemiological studies "
        "and clinical research as a practical surrogate measure of "
        "insulin sensitivity without requiring invasive dynamic tests.",
    ),
    # --- Anthropometry (4-5) ---
    (
        "Waist circumference measurement",
        "Circumferential measurement of the abdomen at the level of "
        "the iliac crest used to assess central adiposity",
        "Waist circumference is measured at the level of the iliac "
        "crest using a flexible non-stretchable tape applied "
        "horizontally around the abdomen. The measurement, recorded in "
        "centimeters, serves as a clinical indicator of central "
        "adiposity and visceral fat accumulation. Elevated waist "
        "circumference is an independent risk factor for cardiovascular "
        "disease and is one of the diagnostic criteria for metabolic "
        "syndrome.",
    ),
    (
        "Body fat percentage by bioimpedance",
        "Proportion of total body mass composed of adipose tissue "
        "estimated using bioelectrical impedance analysis",
        "Body fat percentage estimated by bioelectrical impedance "
        "analysis measures the proportion of total body weight "
        "attributable to fat mass. The method passes a low-level "
        "electrical current through the body and estimates fat-free "
        "mass based on the impedance of different tissue types. "
        "Although less precise than dual-energy X-ray absorptiometry, "
        "bioimpedance is non-invasive, portable, and suitable for "
        "repeated clinical monitoring of body composition changes.",
    ),
    # --- Lipids and liver (6-10) ---
    (
        "Total cholesterol in metabolic panel",
        "Total serum cholesterol concentration as part of the "
        "comprehensive metabolic lipid assessment",
        "Total cholesterol represents the sum of low-density lipoprotein "
        "cholesterol, high-density lipoprotein cholesterol, and "
        "triglyceride-derived cholesterol fractions in a fasting blood "
        "sample. The measurement is reported in milligrams per deciliter "
        "and serves as an initial screening value for dyslipidemia. "
        "Desirable total cholesterol is below 200 milligrams per "
        "deciliter according to current clinical guidelines.",
    ),
    (
        "Triglyceride concentration in metabolic panel",
        "Fasting serum triglyceride level measured as part of the "
        "metabolic lipid profile evaluation",
        "Serum triglycerides are measured in a fasting blood sample and "
        "reported in milligrams per deciliter. Elevated triglycerides "
        "are associated with increased cardiovascular risk and are a "
        "component of the metabolic syndrome diagnostic criteria. "
        "Triglyceride levels above 150 milligrams per deciliter are "
        "considered borderline elevated, while levels exceeding 500 "
        "milligrams per deciliter increase the risk of acute pancreatitis.",
    ),
    (
        "Uric acid level",
        "Serum uric acid concentration reflecting purine metabolism "
        "and renal excretion balance",
        "Serum uric acid is the end product of purine metabolism and is "
        "measured in milligrams per deciliter. Elevated uric acid levels "
        "indicate either overproduction or underexcretion and are "
        "associated with gout, chronic kidney disease, and metabolic "
        "syndrome. Hyperuricemia is increasingly recognized as an "
        "independent risk factor for cardiovascular events and "
        "progression of renal impairment.",
    ),
    (
        "Alanine aminotransferase activity",
        "Serum ALT enzyme level as a marker of hepatocellular injury "
        "in metabolic liver disease screening",
        "Alanine aminotransferase is a cytoplasmic enzyme concentrated "
        "in hepatocytes whose elevation in serum indicates hepatocellular "
        "damage. ALT activity is measured in units per liter and is "
        "commonly included in metabolic health panels to screen for "
        "non-alcoholic fatty liver disease. Persistent ALT elevation "
        "above the upper reference limit warrants further investigation "
        "for metabolic, viral, or toxic causes of liver injury.",
    ),
    (
        "Aspartate aminotransferase activity",
        "Serum AST enzyme level as a marker of tissue injury used "
        "alongside ALT in metabolic liver screening",
        "Aspartate aminotransferase is present in hepatocytes, cardiac "
        "myocytes, and skeletal muscle cells. Serum AST is measured "
        "in units per liter and is interpreted alongside ALT to "
        "characterize the pattern and severity of liver injury. "
        "The AST to ALT ratio provides diagnostic information, with "
        "ratios above two suggesting alcoholic liver disease and ratios "
        "below one being more typical of non-alcoholic fatty liver disease.",
    ),
    # --- Renal and endocrine (11-13) ---
    (
        "Serum creatinine concentration",
        "Blood creatinine level as a marker of kidney filtration "
        "function in metabolic health assessment",
        "Serum creatinine is a breakdown product of creatine phosphate "
        "in skeletal muscle and is freely filtered by the glomeruli. "
        "The concentration, measured in milligrams per deciliter, "
        "inversely reflects the glomerular filtration rate. Serum "
        "creatinine is used to calculate estimated glomerular filtration "
        "rate and to stage chronic kidney disease, which frequently "
        "coexists with diabetes and metabolic syndrome.",
    ),
    (
        "Estimated glomerular filtration rate",
        "Calculated measure of kidney filtration capacity derived "
        "from serum creatinine, age, sex, and race",
        "Estimated glomerular filtration rate is calculated from serum "
        "creatinine using validated equations such as the CKD-EPI "
        "formula that incorporate age, sex, and race. The result, "
        "expressed in milliliters per minute per 1.73 square meters "
        "of body surface area, classifies kidney function into stages "
        "of chronic kidney disease. An eGFR below 60 sustained for "
        "three months or more defines chronic kidney disease.",
    ),
    (
        "Thyroid-stimulating hormone level",
        "Serum TSH concentration used to evaluate thyroid function "
        "in the context of metabolic health screening",
        "Thyroid-stimulating hormone is measured in milli-international "
        "units per liter and serves as the primary screening test for "
        "thyroid dysfunction. Hypothyroidism, indicated by elevated TSH, "
        "contributes to weight gain, dyslipidemia, and impaired glucose "
        "metabolism. Conversely, suppressed TSH suggests hyperthyroidism "
        "with associated metabolic acceleration. TSH screening is "
        "included in metabolic health panels due to the bidirectional "
        "relationship between thyroid function and metabolic status.",
    ),
    # --- Cross-domain (14-19) ---
    (
        "Abdominal ultrasound for hepatic steatosis",
        "Ultrasound imaging of the liver to assess for fatty "
        "infiltration in the context of metabolic syndrome screening",
        "Abdominal ultrasound is a non-invasive imaging modality used "
        "to detect hepatic steatosis by evaluating liver echogenicity "
        "relative to the renal cortex. Increased liver echogenicity "
        "suggests fat infiltration and is graded as mild, moderate, or "
        "severe. Ultrasound screening for fatty liver is recommended "
        "in patients with obesity, insulin resistance, or elevated "
        "liver enzymes as part of comprehensive metabolic assessment.",
    ),
    (
        "Blood pressure at metabolic screening visit",
        "Resting blood pressure recorded during the metabolic health "
        "assessment appointment to evaluate cardiovascular risk",
        "Blood pressure is measured in the seated position after five "
        "minutes of rest using an automated oscillometric device during "
        "the metabolic health screening visit. The measurement records "
        "both systolic and diastolic values in millimeters of mercury. "
        "Hypertension is a core component of metabolic syndrome and "
        "an independent cardiovascular risk factor that is routinely "
        "assessed alongside glycemic and lipid parameters.",
    ),
    (
        "Body mass index at metabolic assessment",
        "BMI calculated from measured height and weight at the "
        "metabolic health evaluation visit",
        "Body mass index is calculated by dividing body weight in "
        "kilograms by the square of height in meters and is recorded "
        "at the metabolic health assessment visit. BMI provides a "
        "standardized classification of weight status: underweight "
        "below 18.5, normal weight 18.5 to 24.9, overweight 25 to "
        "29.9, and obese 30 or above. BMI is used as a screening "
        "criterion for metabolic syndrome and associated comorbidities.",
    ),
    (
        "Metabolic medication adherence",
        "Self-reported adherence to prescribed medications for "
        "metabolic conditions including diabetes and dyslipidemia",
        "Patient-reported compliance with prescribed pharmacotherapy "
        "for metabolic conditions such as type 2 diabetes, "
        "dyslipidemia, and hypertension. Adherence is assessed using "
        "standardized questionnaires and expressed as a percentage "
        "of prescribed doses taken. Poor medication adherence is a "
        "major contributor to suboptimal glycemic control, persistent "
        "dyslipidemia, and increased cardiovascular event risk.",
    ),
    (
        "Age at metabolic health screening",
        "Patient age at the time of the metabolic health assessment "
        "used as a covariate in cardiovascular risk estimation",
        "Age in years at the time of the comprehensive metabolic "
        "health screening visit. Age is a non-modifiable risk factor "
        "for metabolic syndrome, type 2 diabetes, and cardiovascular "
        "disease. Advancing age is associated with declining insulin "
        "sensitivity, increasing visceral adiposity, and progressive "
        "changes in lipid metabolism that collectively elevate "
        "cardiometabolic risk.",
    ),
    (
        "Metabolic treatment response score",
        "Composite clinical assessment of response to metabolic "
        "intervention including lifestyle and pharmacological therapy",
        "A composite score reflecting the overall clinical response "
        "to metabolic interventions including dietary modification, "
        "exercise prescription, and pharmacotherapy. The score "
        "integrates changes in fasting glucose, hemoglobin A1c, "
        "lipid profile, blood pressure, and body weight from baseline "
        "to follow-up. Favorable treatment response is defined as "
        "clinically meaningful improvement in two or more metabolic "
        "parameters over the treatment period.",
    ),
]


# ---------------------------------------------------------------------------
# CDE record builder
# ---------------------------------------------------------------------------

_BOILERPLATE = {
    "nihEndorsed": None,
    "elementType": "cde",
    "archived": False,
    "sources": [],
    "createdBy": None,
    "stewardOrg": {"name": "Synthetic QC"},
    "registrationState": {"registrationStatus": "Qualified"},
    "classification": [],
    "referenceDocuments": [],
    "properties": [],
    "ids": [],
    "attachments": [],
}


def _make_tiny_id(prefix: str, index: int) -> str:
    """Generate a deterministic tinyId: e.g., synCRD001, synRSP012."""
    return f"syn{prefix}{index:03d}"


def _build_record(
    tiny_id: str,
    name: str,
    question: str,
    definition: str,
    topic_tag: str,
) -> dict:
    """Build a minimal-but-valid CDE record."""
    rec = dict(_BOILERPLATE)
    rec["tinyId"] = tiny_id
    rec["designations"] = [
        {"designation": name, "sources": [], "tags": ["Preferred Question Text"]},
        {"designation": question, "sources": [], "tags": ["Alternative Question Text"]},
    ]
    rec["definitions"] = [
        {"definition": definition, "tags": [topic_tag]},
    ]
    return rec


def generate_all() -> list:
    """Return the complete list of 60 synthetic CDE records."""
    records = []

    for i, (name, question, defn) in enumerate(TOPIC_CRD, start=1):
        records.append(
            _build_record(
                _make_tiny_id("CRD", i), name, question, defn,
                "Cardiovascular Assessment",
            )
        )

    for i, (name, question, defn) in enumerate(TOPIC_RSP, start=1):
        records.append(
            _build_record(
                _make_tiny_id("RSP", i), name, question, defn,
                "Respiratory Function Evaluation",
            )
        )

    for i, (name, question, defn) in enumerate(TOPIC_MET, start=1):
        records.append(
            _build_record(
                _make_tiny_id("MET", i), name, question, defn,
                "Metabolic Health Monitoring",
            )
        )

    return records


# ---------------------------------------------------------------------------
# Manifest — domain, sub-domain, expected clustering
# ---------------------------------------------------------------------------

_MANIFEST_CRD = [
    # 0-6: Core cardiac
    ("Cardiac Parameters",  "cardiovascular"),      # resting heart rate
    ("Hemodynamics",        "xdh:blood_pressure"),  # systolic BP
    ("Hemodynamics",        "cardiovascular"),      # diastolic BP
    ("Hemodynamics",        "cardiovascular"),      # mean arterial pressure
    ("Cardiac Parameters",  "cardiovascular"),      # cardiac output
    ("Cardiac Parameters",  "cardiovascular"),      # ejection fraction
    ("Electrophysiology",   "cardiovascular"),      # QT interval
    # 7-9: Cardiac biomarkers
    ("Biomarkers",          "xdh:lab_values"),      # troponin I
    ("Biomarkers",          "cardiovascular"),      # BNP
    ("Lipid Panel",         "cardiovascular"),      # total cholesterol
    # 10-12: Lipid panel
    ("Lipid Panel",         "cardiovascular"),      # LDL
    ("Lipid Panel",         "cardiovascular"),      # HDL
    ("Lipid Panel",         "cardiovascular"),      # triglycerides
    # 13-15: Vascular markers
    ("Biomarkers",          "cardiovascular"),      # CRP
    ("Vascular Imaging",    "xdh:imaging"),         # carotid IMT
    ("Electrophysiology",   "cardiovascular"),      # HRV
    # 16-19: Cross-domain
    ("Anthropometry",       "xdh:bmi"),             # BMI
    ("Medication",          "xdh:medication"),      # medication adherence
    ("Demographics",        "xdh:demographics"),    # age at screening
    ("Treatment",           "xdh:treatment_response"),  # treatment response
]

_MANIFEST_RSP = [
    # 0-4: Core spirometry
    ("Spirometry",          "respiratory"),          # FEV1
    ("Spirometry",          "respiratory"),          # FVC
    ("Spirometry",          "respiratory"),          # FEV1/FVC ratio
    ("Spirometry",          "respiratory"),          # peak expiratory flow
    ("Oxygenation",         "respiratory"),          # SpO2
    # 5-8: Gas exchange and mechanics
    ("Ventilation",         "respiratory"),          # respiratory rate
    ("Gas Exchange",        "respiratory"),          # PaO2
    ("Gas Exchange",        "xdh:lab_values"),       # PaCO2
    ("Exercise Capacity",   "respiratory"),          # 6MWD
    # 9-13: Additional lung function
    ("Gas Exchange",        "respiratory"),          # DLCO
    ("Ventilation",         "respiratory"),          # tidal volume
    ("Spirometry",          "respiratory"),          # bronchodilator response
    ("Symptoms",            "respiratory"),          # dyspnea score
    ("Biomarkers",          "respiratory"),          # exhaled NO
    # 14-19: Cross-domain
    ("Imaging",             "xdh:imaging"),          # chest radiograph
    ("Hemodynamics",        "xdh:blood_pressure"),   # BP at visit
    ("Anthropometry",       "xdh:bmi"),              # BMI
    ("Medication",          "xdh:medication"),        # medication adherence
    ("Demographics",        "xdh:demographics"),      # age at evaluation
    ("Treatment",           "xdh:treatment_response"),  # treatment response
]

_MANIFEST_MET = [
    # 0-3: Glucose metabolism
    ("Glycemic",            "metabolic"),            # fasting glucose
    ("Glycemic",            "metabolic"),            # HbA1c
    ("Glycemic",            "metabolic"),            # fasting insulin
    ("Glycemic",            "metabolic"),            # HOMA-IR
    # 4-5: Anthropometry
    ("Anthropometry",       "metabolic"),            # waist circumference
    ("Anthropometry",       "metabolic"),            # body fat %
    # 6-10: Lipids and liver
    ("Lipid Panel",         "metabolic"),            # total cholesterol
    ("Lipid Panel",         "xdh:lab_values"),       # triglycerides
    ("Renal/Metabolic",     "metabolic"),            # uric acid
    ("Hepatic",             "metabolic"),            # ALT
    ("Hepatic",             "metabolic"),            # AST
    # 11-13: Renal and endocrine
    ("Renal/Metabolic",     "metabolic"),            # creatinine
    ("Renal/Metabolic",     "metabolic"),            # eGFR
    ("Endocrine",           "metabolic"),            # TSH
    # 14-19: Cross-domain
    ("Imaging",             "xdh:imaging"),          # abdominal ultrasound
    ("Hemodynamics",        "xdh:blood_pressure"),   # BP at screening
    ("Anthropometry",       "xdh:bmi"),              # BMI
    ("Medication",          "xdh:medication"),        # medication adherence
    ("Demographics",        "xdh:demographics"),      # age at screening
    ("Treatment",           "xdh:treatment_response"),  # treatment response
]

_DOMAIN_LABELS = {
    "Cardiovascular Assessment":        "cardiovascular",
    "Respiratory Function Evaluation":  "respiratory",
    "Metabolic Health Monitoring":      "metabolic",
}

_VERBOSITY = {
    "Cardiovascular Assessment":        "terse",
    "Respiratory Function Evaluation":  "informational",
    "Metabolic Health Monitoring":      "expansive",
}


def generate_manifest(records: list) -> list[dict]:
    """Build manifest rows aligned to generate_all() output order."""
    manifest_data = _MANIFEST_CRD + _MANIFEST_RSP + _MANIFEST_MET
    rows = []
    for rec, (sub_domain, expected_cluster) in zip(records, manifest_data):
        domain_tag = rec["definitions"][0]["tags"][0]
        rows.append({
            "tinyId": rec["tinyId"],
            "domain": _DOMAIN_LABELS[domain_tag],
            "domain_full": domain_tag,
            "sub_domain": sub_domain,
            "verbosity": _VERBOSITY[domain_tag],
            "expected_cluster": expected_cluster,
            "name": rec["designations"][0]["designation"],
        })
    return rows


def write_manifest_tsv(rows: list[dict], path: str) -> None:
    """Write manifest as TSV."""
    fields = [
        "tinyId", "domain", "domain_full", "sub_domain",
        "verbosity", "expected_cluster", "name",
    ]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate 60 clean health/medical synthetic CDEs."
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON (indented)",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Output manifest TSV path (default: auto alongside JSON)",
    )
    args = parser.parse_args()

    # Ensure output directory exists
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    records = generate_all()

    # Write CDE JSON
    indent = 2 if args.pretty else None
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        json.dump(records, f, indent=indent, ensure_ascii=False)
        f.write("\n")

    # Write manifest TSV
    manifest_path = args.manifest
    if manifest_path is None:
        base = os.path.splitext(os.path.basename(args.output))[0]
        manifest_path = os.path.join(out_dir or ".", f"{base}_manifest.tsv")
    manifest_rows = generate_manifest(records)
    write_manifest_tsv(manifest_rows, manifest_path)

    # Summary
    topic_counts = {}
    for rec in records:
        tag = rec["definitions"][0]["tags"][0]
        topic_counts[tag] = topic_counts.get(tag, 0) + 1

    print(f"Generated {len(records)} health-base CDEs → {args.output}")
    print(f"Manifest ({len(manifest_rows)} rows) → {manifest_path}")
    for tag, count in topic_counts.items():
        print(f"  {tag}: {count} CDEs")

    # Cross-domain cluster summary
    xd_counts = {}
    for row in manifest_rows:
        cl = row["expected_cluster"]
        if cl.startswith("xdh:"):
            xd_counts.setdefault(cl, []).append(row["tinyId"])
    print(f"\nCross-domain overlap: {len(xd_counts)} groups, "
          f"{sum(len(v) for v in xd_counts.values())} CDEs")
    for cl, ids in sorted(xd_counts.items()):
        print(f"  {cl}: {', '.join(ids)}")

    # Verbosity stats
    for label, topic in [
        ("Cardiovascular (terse)", TOPIC_CRD),
        ("Respiratory (informational)", TOPIC_RSP),
        ("Metabolic (expansive)", TOPIC_MET),
    ]:
        avg_def = sum(len(d) for _, _, d in topic) / len(topic)
        avg_name = sum(len(n) for n, _, _ in topic) / len(topic)
        print(f"  {label}: avg name {avg_name:.0f} chars, avg def {avg_def:.0f} chars")


if __name__ == "__main__":
    main()
