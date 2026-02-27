#!/usr/bin/env python3
"""
Generate Health Gravity A: 60 health/medical CDEs with embedded instruments.

Three clinical domains with synthetic instrument names and temporal boilerplate.
Tests "gravity" effects — shared instruments pull semantically unrelated CDEs
together in embedding space.

Usage:
    python scripts/generate_health_gravity_a.py \
        -o data/synthetic_qc/health_gravity_a/health_gravity_a.json --pretty

Design:
    Mental Health Screening            TERSE         (20 CDEs, synMHL)
    Musculoskeletal Assessment         INFORMATIONAL (20 CDEs, synMSK)
    Gastrointestinal Health Evaluation EXPANSIVE     (20 CDEs, synGIH)

Instrument families (shared across topics for gravity):
    PHI   Patient Health Inventory           3 sub-scales
    COAS  Clinical Outcome Assessment Scale  3 sub-scales

Injection distribution per 20-CDE topic:
    0-5   PHI sub-scale in name + temporal in question + anchor in definition
    6-11  COAS sub-scale in name + temporal in question + anchor in definition
    12-14 PHI instrument in definition only (weak gravity)
    15-16 Temporal phrase only (no instrument)
    17-19 Clean controls

Cross-domain concepts (xdha:*) at indices 5, 10, 12, 15, 16, 17, 18.
"""

import argparse
import csv
import json
import os
import sys

# ---------------------------------------------------------------------------
# Instrument definitions
# ---------------------------------------------------------------------------

PHI_PARENT = "Patient Health Inventory (PHI)"
PHI_SUBSCALES = {
    "MHL": "PHI Emotional Distress",
    "MSK": "PHI Physical Limitation",
    "GIH": "PHI Digestive Function",
}

COAS_PARENT = "Clinical Outcome Assessment Scale (COAS)"
COAS_SUBSCALES = {
    "MHL": "COAS Psychological Well-Being",
    "MSK": "COAS Rehabilitation Progress",
    "GIH": "COAS Somatic Symptom Burden",
}

TEMPORALS = [
    "In the past 7 days",
    "Over the past 2 weeks",
    "During the past 4 weeks",
]

# ---------------------------------------------------------------------------
# CDE content — 20 per topic, each tuple: (name, question, definition)
# Base content WITHOUT injection; injection applied by _inject_noise()
# ---------------------------------------------------------------------------

TOPIC_MHL = [
    # 0-5: PHI Emotional Distress instrument CDEs
    (
        "Depression symptom score",
        "Self-reported depression severity rating",
        "Total score on a standardized depression screening questionnaire.",
    ),
    (
        "Anxiety symptom score",
        "Self-reported generalized anxiety severity level",
        "Total score on a validated generalized anxiety screening instrument.",
    ),
    (
        "Perceived stress level",
        "Rating of overall perceived psychological stress",
        "Self-rated global stress intensity over the assessment time period.",
    ),
    (
        "Emotional regulation score",
        "Ability to manage and modulate emotional responses",
        "Rating of capacity to regulate emotional reactions under stress.",
    ),
    (
        "Suicidal ideation screen result",
        "Presence of thoughts of self-harm or suicide",
        "Binary screening result for active or passive suicidal ideation.",
    ),
    # 5: PHI + xdha:severity
    (
        "Overall psychiatric symptom severity",
        "Global rating of psychiatric symptom burden",
        "Composite severity score across all psychiatric symptom domains.",
    ),
    # 6-11: COAS Psychological Well-Being instrument CDEs
    (
        "Social functioning score",
        "Ability to engage in social interactions and relationships",
        "Rating of social engagement and interpersonal functioning level.",
    ),
    (
        "Occupational functioning rating",
        "Impact of mental health on work or school performance",
        "Degree of mental-health-related impairment in occupational roles.",
    ),
    (
        "Psychological resilience score",
        "Capacity to recover from adverse psychological experiences",
        "Rating of adaptive coping ability following stressful life events.",
    ),
    (
        "Self-efficacy assessment",
        "Belief in ability to accomplish daily tasks",
        "Self-rated confidence in managing routine activities and challenges.",
    ),
    # 10: COAS + xdha:function
    (
        "Mental health functional impairment",
        "Degree of disability caused by mental health symptoms",
        "Overall functional limitation attributable to psychiatric symptoms.",
    ),
    (
        "Trauma exposure history",
        "Prior exposure to potentially traumatic events",
        "Count of distinct traumatic events endorsed on screening checklist.",
    ),
    # 12-14: PHI definition-only CDEs
    # 12: PHI def + xdha:medication
    (
        "Psychotropic medication usage",
        "Current use of prescribed psychiatric medications",
        "Record of prescribed psychotropic medications and current dosages.",
    ),
    (
        "Psychological distress thermometer",
        "Visual analog rating of overall psychological distress",
        "Single-item distress rating on a zero-to-ten visual analog scale.",
    ),
    (
        "Substance use screening result",
        "Screening for problematic alcohol or drug use",
        "Outcome of a brief standardized substance use screening instrument.",
    ),
    # 15-16: Temporal-only CDEs
    # 15: temporal + xdha:demographics
    (
        "Age at mental health assessment",
        "Patient age at the time of psychiatric evaluation",
        "Chronological age at the date of mental health screening visit.",
    ),
    # 16: temporal + xdha:comorbidity
    (
        "Psychiatric comorbidity count",
        "Number of concurrent psychiatric diagnoses",
        "Total number of active comorbid psychiatric conditions diagnosed.",
    ),
    # 17-19: Clean controls
    # 17: clean + xdha:qol
    (
        "Mental health quality of life rating",
        "Impact of psychiatric symptoms on overall quality of life",
        "Self-reported effect of mental illness on daily well-being.",
    ),
    # 18: clean + xdha:treatment
    (
        "Psychiatric treatment response",
        "Clinical response to current mental health treatment",
        "Clinician-rated response to prescribed psychiatric intervention.",
    ),
    # 19: clean, domain-specific
    (
        "Panic attack frequency",
        "Number of panic episodes in the assessment period",
        "Count of discrete panic attacks during the assessment interval.",
    ),
]

TOPIC_MSK = [
    # 0-5: PHI Physical Limitation instrument CDEs
    (
        "Joint pain severity score",
        "Self-reported severity of joint pain at the most affected site",
        "A numeric rating of the patient's joint pain intensity on a "
        "validated ordinal scale. Joint pain severity is assessed at the "
        "most affected joint and guides analgesic therapy decisions.",
    ),
    (
        "Active range of motion",
        "Angular excursion of the joint during voluntary movement",
        "The maximum angular displacement achieved through voluntary "
        "muscle contraction at the specified joint, measured in degrees "
        "with a goniometer. Reduced active range indicates pathology.",
    ),
    (
        "Grip strength measurement",
        "Maximum force exerted during a hand grip dynamometry test",
        "Peak isometric grip force measured in kilograms using a "
        "calibrated hand dynamometer. Grip strength is a surrogate "
        "marker of upper-extremity musculoskeletal function.",
    ),
    (
        "Muscle weakness grading",
        "Manual muscle testing grade for the affected muscle group",
        "A clinical grade assigned to the strength of a target muscle "
        "group using the Medical Research Council scale from zero to "
        "five. Grades below four indicate clinically meaningful weakness.",
    ),
    (
        "Bone mineral density T-score",
        "Standard deviation of bone density relative to young adult reference",
        "The number of standard deviations by which the patient's bone "
        "mineral density differs from the mean of a healthy young adult "
        "reference population, measured by dual-energy X-ray absorptiometry.",
    ),
    # 5: PHI + xdha:severity
    (
        "Musculoskeletal symptom severity",
        "Global rating of musculoskeletal symptom burden",
        "A composite score reflecting the overall severity of "
        "musculoskeletal symptoms including pain, stiffness, and "
        "functional limitation assessed on a validated outcome measure.",
    ),
    # 6-11: COAS Rehabilitation Progress instrument CDEs
    (
        "Gait speed assessment",
        "Walking velocity measured over a standardized distance",
        "The patient's habitual walking speed in meters per second over "
        "a four-meter course. Gait speed is a reliable predictor of "
        "disability, falls, and mortality in older adults.",
    ),
    (
        "Fall risk score",
        "Composite assessment of the patient's risk of falling",
        "A multifactorial risk score incorporating balance, gait speed, "
        "lower-extremity strength, medication use, and prior fall "
        "history. Elevated scores guide fall prevention interventions.",
    ),
    (
        "Swollen joint count",
        "Number of joints with detectable swelling on examination",
        "The count of joints exhibiting clinically detectable "
        "soft-tissue swelling on standardized musculoskeletal "
        "examination. A core disease activity measure in arthritis.",
    ),
    (
        "Morning stiffness duration",
        "Length of time morning joint stiffness persists after waking",
        "The duration in minutes from waking to resolution of joint "
        "stiffness. Morning stiffness lasting more than thirty minutes "
        "is characteristic of inflammatory arthropathies.",
    ),
    # 10: COAS + xdha:function
    (
        "Musculoskeletal functional impairment",
        "Degree of disability in daily activities due to musculoskeletal conditions",
        "A standardized rating of the patient's functional limitation "
        "attributable to musculoskeletal disorders, covering self-care, "
        "mobility, and household activities.",
    ),
    (
        "Physical therapy response",
        "Clinical improvement following physical rehabilitation program",
        "The change in functional outcome measures after a structured "
        "physical therapy program, expressed as the percentage "
        "improvement from baseline values.",
    ),
    # 12-14: PHI definition-only CDEs
    # 12: PHI def + xdha:medication
    (
        "Musculoskeletal medication usage",
        "Current medications prescribed for musculoskeletal conditions",
        "A record of analgesic, anti-inflammatory, and disease-modifying "
        "agents prescribed for the patient's musculoskeletal condition. "
        "Medication type, dose, and frequency are documented.",
    ),
    (
        "Vertebral fracture assessment",
        "Presence and grading of vertebral compression fractures",
        "An evaluation of thoracolumbar vertebral bodies for "
        "morphometric fractures using lateral spine imaging. Vertebral "
        "fractures indicate elevated future fracture risk.",
    ),
    (
        "Disability index score",
        "Standardized disability rating for musculoskeletal conditions",
        "A patient-reported disability score derived from a validated "
        "questionnaire assessing difficulty with daily activities. "
        "The index quantifies functional impact across life domains.",
    ),
    # 15-16: Temporal-only CDEs
    # 15: temporal + xdha:demographics
    (
        "Age at musculoskeletal assessment",
        "Patient age at the time of musculoskeletal evaluation",
        "The chronological age of the patient at the date of the "
        "musculoskeletal assessment. Age is a major determinant of "
        "osteoarthritis prevalence and normative strength values.",
    ),
    # 16: temporal + xdha:comorbidity
    (
        "Musculoskeletal comorbidity count",
        "Number of concurrent conditions affecting the musculoskeletal system",
        "The total number of active comorbid conditions relevant to "
        "musculoskeletal health including osteoporosis, fibromyalgia, "
        "gout, and rheumatic diseases.",
    ),
    # 17-19: Clean controls
    # 17: clean + xdha:qol
    (
        "Musculoskeletal quality of life",
        "Impact of musculoskeletal conditions on overall quality of life",
        "A patient-reported measure of the effect of musculoskeletal "
        "disorders on physical, emotional, and social well-being "
        "beyond clinical severity measures.",
    ),
    # 18: clean + xdha:treatment
    (
        "Musculoskeletal treatment response",
        "Clinical response to musculoskeletal treatment regimen",
        "The clinician's assessment of the patient's response to "
        "prescribed musculoskeletal treatment covering pain reduction, "
        "functional improvement, and side effect burden.",
    ),
    # 19: clean, domain-specific
    (
        "Tender joint count",
        "Number of joints painful to palpation on physical examination",
        "The count of joints eliciting pain on standardized palpation "
        "during musculoskeletal examination. A core component of "
        "composite disease activity indices in arthritis.",
    ),
]

TOPIC_GIH = [
    # 0-5: PHI Digestive Function instrument CDEs
    (
        "Abdominal pain severity score",
        "Self-reported severity of abdominal pain over the assessment period",
        "The patient's numeric rating of abdominal pain intensity on a "
        "validated ordinal scale, assessed at each visit and averaged over "
        "the assessment period. Abdominal pain is the most common "
        "presenting symptom of gastrointestinal disease and its severity "
        "guides diagnostic urgency and analgesic intervention. Pain "
        "severity is interpreted alongside location, character, and "
        "temporal pattern to narrow the differential diagnosis.",
    ),
    (
        "Stool frequency per day",
        "Average number of bowel movements per day during the recall period",
        "The mean daily number of bowel movements recorded by the patient "
        "over the assessment recall period, typically one to four weeks. "
        "Stool frequency is a primary symptom measure in both constipation "
        "and diarrhea-predominant conditions. Frequencies below three per "
        "week suggest constipation, while frequencies above three per day "
        "with loose consistency suggest diarrhea. Change in stool "
        "frequency from baseline is a key clinical trial endpoint.",
    ),
    (
        "Bristol stool form scale score",
        "Classification of stool consistency using the seven-type Bristol chart",
        "The patient's self-reported stool consistency classified according "
        "to the seven-type Bristol stool form scale, where type one "
        "represents hard separate lumps and type seven represents entirely "
        "liquid stool. Types three and four are considered normal. The "
        "Bristol scale provides a standardized, reproducible measure of "
        "colonic transit time and is widely used as an endpoint in clinical "
        "trials of gastrointestinal motility disorders.",
    ),
    (
        "Nausea severity rating",
        "Self-reported intensity of nausea symptoms during the assessment period",
        "A numeric rating of nausea intensity on a standardized visual "
        "analog or ordinal scale, recorded at each assessment. Nausea is "
        "a nonspecific gastrointestinal symptom that occurs across a wide "
        "range of conditions including gastroparesis, functional dyspepsia, "
        "and chemotherapy-induced emesis. Severity assessment captures both "
        "the peak intensity and the average daily burden of nausea and "
        "guides antiemetic prescribing decisions.",
    ),
    (
        "Gastroesophageal reflux symptom score",
        "Composite score of heartburn and regurgitation severity and frequency",
        "A composite score derived from a validated questionnaire assessing "
        "the frequency and severity of gastroesophageal reflux symptoms "
        "including heartburn, acid regurgitation, and chest discomfort. "
        "Higher scores indicate more severe and frequent reflux episodes. "
        "The GERD symptom score is used to monitor response to proton pump "
        "inhibitor therapy, identify patients requiring further endoscopic "
        "evaluation, and classify reflux disease severity.",
    ),
    # 5: PHI + xdha:severity
    (
        "Gastrointestinal symptom severity",
        "Global rating of gastrointestinal symptom burden across all domains",
        "A composite severity rating reflecting the overall burden of "
        "gastrointestinal symptoms experienced by the patient, encompassing "
        "abdominal pain, nausea, altered bowel habits, bloating, and "
        "dysphagia. The severity score is derived from a validated "
        "multi-domain gastrointestinal symptom questionnaire and provides "
        "a single summary measure of symptom impact. Global severity "
        "ratings complement individual symptom assessments by capturing "
        "cumulative burden on daily functioning.",
    ),
    # 6-11: COAS Somatic Symptom Burden instrument CDEs
    (
        "Dysphagia severity grade",
        "Grade of swallowing difficulty assessed by clinical evaluation",
        "A graded assessment of the patient's difficulty in swallowing "
        "solids, liquids, or both, classified according to a standardized "
        "severity scale. Dysphagia grading considers the consistency of "
        "foods that can be safely swallowed, the frequency of difficulty, "
        "and the presence of aspiration risk. Moderate to severe dysphagia "
        "may necessitate dietary modification, swallowing rehabilitation, "
        "or endoscopic intervention.",
    ),
    (
        "Hepatic fibrosis stage",
        "Histological or non-invasive staging of liver fibrosis severity",
        "The stage of hepatic fibrosis classified on a standardized scale "
        "from zero indicating no fibrosis to four indicating cirrhosis, "
        "determined by liver biopsy histology or validated non-invasive "
        "methods such as transient elastography or serum biomarker panels. "
        "Fibrosis staging is essential for prognostication and treatment "
        "decisions in chronic liver diseases including non-alcoholic "
        "steatohepatitis and viral hepatitis.",
    ),
    (
        "Endoscopy finding classification",
        "Standardized classification of findings during gastrointestinal endoscopy",
        "The categorical classification of mucosal and structural findings "
        "identified during upper or lower gastrointestinal endoscopy, "
        "recorded using standardized reporting terminology. Findings are "
        "classified by type including erosions, ulcers, polyps, strictures, "
        "and masses, and by location within the gastrointestinal tract. "
        "Endoscopic classification enables systematic documentation and "
        "facilitates comparison across follow-up examinations.",
    ),
    (
        "Helicobacter pylori infection status",
        "Result of diagnostic testing for Helicobacter pylori infection",
        "The result of diagnostic testing for active Helicobacter pylori "
        "infection, determined by urea breath test, stool antigen assay, "
        "or histological examination of gastric biopsy specimens. Positive "
        "status indicates current infection and guides eradication therapy "
        "with a proton pump inhibitor and antibiotic combination. H. pylori "
        "infection is causally associated with chronic gastritis, peptic "
        "ulcer disease, and gastric adenocarcinoma.",
    ),
    # 10: COAS + xdha:function
    (
        "Gastrointestinal functional impairment",
        "Degree of disability in daily activities due to gastrointestinal symptoms",
        "A composite measure of the extent to which gastrointestinal "
        "symptoms impair the patient's ability to perform daily activities "
        "including work, social participation, meal preparation, and "
        "physical exercise. Functional impairment is assessed using "
        "validated patient-reported outcome instruments that capture "
        "disability across multiple life domains. The measure complements "
        "symptom severity scores by quantifying the real-world impact of "
        "gastrointestinal disease on daily functioning.",
    ),
    (
        "Inflammatory bowel disease activity index",
        "Composite score quantifying disease activity in inflammatory bowel disease",
        "A validated composite score incorporating symptoms, laboratory "
        "markers, and endoscopic findings to quantify the current level "
        "of disease activity in Crohn's disease or ulcerative colitis. "
        "Activity indices guide treatment escalation, de-escalation, and "
        "surgical decision-making. Clinical remission is typically defined "
        "as a score below a validated threshold. Serial assessment enables "
        "objective monitoring of treatment response.",
    ),
    # 12-14: PHI definition-only CDEs
    # 12: PHI def + xdha:medication
    (
        "Gastrointestinal medication usage",
        "Current medications prescribed for gastrointestinal conditions",
        "A comprehensive record of all pharmacological agents prescribed "
        "for the patient's gastrointestinal condition, including proton "
        "pump inhibitors, antispasmodics, prokinetics, aminosalicylates, "
        "immunomodulators, and biologic agents. Medication name, dose, "
        "frequency, route, and duration of therapy are documented. The "
        "record enables assessment of treatment adherence and "
        "identification of drug interactions.",
    ),
    (
        "Celiac disease antibody titer",
        "Serum tissue transglutaminase IgA antibody level for celiac screening",
        "The serum concentration of immunoglobulin A antibodies against "
        "tissue transglutaminase, measured in units per milliliter, used "
        "as the primary serological screening test for celiac disease. "
        "Elevated titers above the laboratory-specific threshold indicate "
        "a high probability of celiac disease and warrant confirmatory "
        "small bowel biopsy. Serial monitoring assesses adherence to a "
        "gluten-free diet.",
    ),
    (
        "Nutritional status assessment score",
        "Standardized evaluation of the patient's nutritional adequacy",
        "A composite nutritional assessment score derived from "
        "anthropometric measurements, biochemical markers including serum "
        "albumin and prealbumin, dietary intake records, and clinical "
        "examination findings. The assessment identifies patients at risk "
        "of malnutrition due to gastrointestinal malabsorption, chronic "
        "inflammation, or inadequate oral intake. Nutritional screening "
        "is recommended for all patients with chronic GI disease.",
    ),
    # 15-16: Temporal-only CDEs
    # 15: temporal + xdha:demographics
    (
        "Age at gastrointestinal evaluation",
        "Patient age at the time of the gastrointestinal health assessment",
        "The chronological age of the patient at the date of the "
        "gastrointestinal health evaluation. Age is a critical determinant "
        "of disease prevalence and presentation in gastroenterology. "
        "Colorectal cancer screening guidelines are age-stratified, and "
        "the prevalence of conditions such as diverticulosis and Barrett "
        "esophagus increases with advancing age. Age-appropriate reference "
        "ranges are applied to laboratory and endoscopic findings.",
    ),
    # 16: temporal + xdha:comorbidity
    (
        "Gastrointestinal comorbidity count",
        "Number of concurrent conditions affecting the gastrointestinal system",
        "The total number of active comorbid conditions with established "
        "effects on gastrointestinal health, including diabetes mellitus, "
        "chronic kidney disease, thyroid disorders, and connective tissue "
        "diseases. The comorbidity count provides context for interpreting "
        "gastrointestinal symptoms and guides treatment selection by "
        "identifying potential drug interactions and contraindications. "
        "Higher comorbidity burden is associated with poorer outcomes.",
    ),
    # 17-19: Clean controls
    # 17: clean + xdha:qol
    (
        "Gastrointestinal quality of life",
        "Impact of gastrointestinal conditions on overall quality of life",
        "A patient-reported measure of the effect of gastrointestinal "
        "symptoms and disease on overall quality of life, encompassing "
        "physical comfort, emotional well-being, social functioning, and "
        "dietary freedom. Quality of life assessment captures the "
        "subjective burden of gastrointestinal disease that may not be "
        "reflected in objective clinical measures such as laboratory "
        "values or endoscopic scores.",
    ),
    # 18: clean + xdha:treatment
    (
        "Gastrointestinal treatment response",
        "Clinical response to prescribed gastrointestinal therapy",
        "The clinician's overall assessment of the patient's clinical "
        "response to the prescribed gastrointestinal treatment regimen, "
        "integrating changes in symptom severity, endoscopic findings, "
        "laboratory markers, and functional status from baseline to "
        "follow-up. Treatment response is classified as complete "
        "remission, partial response, stable disease, or progressive "
        "disease to guide therapy decisions.",
    ),
    # 19: clean, domain-specific
    (
        "Fecal calprotectin concentration",
        "Stool calprotectin level as a non-invasive marker of intestinal inflammation",
        "The concentration of calprotectin protein in a stool sample, "
        "measured in micrograms per gram by enzyme-linked immunosorbent "
        "assay. Fecal calprotectin is a neutrophil-derived protein that "
        "serves as a sensitive and specific non-invasive biomarker of "
        "intestinal inflammation. Elevated levels above 250 micrograms "
        "per gram strongly suggest active inflammatory bowel disease and "
        "distinguish organic from functional gastrointestinal disorders.",
    ),
]


# ---------------------------------------------------------------------------
# Noise injection
# ---------------------------------------------------------------------------

def _inject_noise(index, name, question, definition, topic_key):
    """Apply instrument/temporal noise based on 0-based CDE index within topic.

    Returns (name, question, definition, instrument_name, temporal_phrase).
    """
    instrument = ""
    temporal = ""

    if index <= 5:
        # Family 1 (PHI): full injection
        subscale = PHI_SUBSCALES[topic_key]
        instrument = subscale
        temporal = TEMPORALS[index % 3]
        name = f"{subscale} - {name}"
        question = f"{temporal}, {question[0].lower()}{question[1:]}"
        definition = f"{definition} As part of the {PHI_PARENT}."
    elif index <= 11:
        # Family 2 (COAS): full injection
        subscale = COAS_SUBSCALES[topic_key]
        instrument = subscale
        temporal = TEMPORALS[index % 3]
        name = f"{subscale} - {name}"
        question = f"{temporal}, {question[0].lower()}{question[1:]}"
        definition = f"{definition} Based on the {COAS_PARENT}."
    elif index <= 14:
        # Family 1 definition-only (weak gravity)
        instrument = PHI_SUBSCALES[topic_key]
        definition = f"{definition} A field of the {PHI_PARENT}."
    elif index <= 16:
        # Temporal phrase only
        temporal = TEMPORALS[index % 3]
        question = f"{temporal}, {question[0].lower()}{question[1:]}"
        if definition.endswith("."):
            definition = definition[:-1]
        definition = f"{definition}, assessed {temporal.lower()}."

    # indices 17-19: clean — no modification
    return name, question, definition, instrument, temporal


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
    return f"syn{prefix}{index:03d}"


def _build_record(tiny_id, name, question, definition, topic_tag):
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


# ---------------------------------------------------------------------------
# Manifest data — (sub_domain, expected_cluster) per CDE index
# ---------------------------------------------------------------------------

_MANIFEST_MHL = [
    ("Depression",          "mhl"),               # 0
    ("Anxiety",             "mhl"),               # 1
    ("Stress",              "mhl"),               # 2
    ("Emotional",           "mhl"),               # 3
    ("Risk Screening",      "mhl"),               # 4
    ("Severity",            "xdha:severity"),     # 5
    ("Social Function",     "mhl"),               # 6
    ("Occupational",        "mhl"),               # 7
    ("Resilience",          "mhl"),               # 8
    ("Self-Efficacy",       "mhl"),               # 9
    ("Function",            "xdha:function"),     # 10
    ("Trauma",              "mhl"),               # 11
    ("Medication",          "xdha:medication"),   # 12
    ("Distress",            "mhl"),               # 13
    ("Substance Use",       "mhl"),               # 14
    ("Demographics",        "xdha:demographics"), # 15
    ("Comorbidity",         "xdha:comorbidity"),  # 16
    ("Quality of Life",     "xdha:qol"),          # 17
    ("Treatment",           "xdha:treatment"),    # 18
    ("Panic Disorder",      "mhl"),               # 19
]

_MANIFEST_MSK = [
    ("Joint Pain",          "msk"),               # 0
    ("Range of Motion",     "msk"),               # 1
    ("Strength",            "msk"),               # 2
    ("Muscle Function",     "msk"),               # 3
    ("Bone Density",        "msk"),               # 4
    ("Severity",            "xdha:severity"),     # 5
    ("Gait",                "msk"),               # 6
    ("Fall Risk",           "msk"),               # 7
    ("Joint Inflammation",  "msk"),               # 8
    ("Stiffness",           "msk"),               # 9
    ("Function",            "xdha:function"),     # 10
    ("Rehabilitation",      "msk"),               # 11
    ("Medication",          "xdha:medication"),   # 12
    ("Fracture",            "msk"),               # 13
    ("Disability",          "msk"),               # 14
    ("Demographics",        "xdha:demographics"), # 15
    ("Comorbidity",         "xdha:comorbidity"),  # 16
    ("Quality of Life",     "xdha:qol"),          # 17
    ("Treatment",           "xdha:treatment"),    # 18
    ("Joint Tenderness",    "msk"),               # 19
]

_MANIFEST_GIH = [
    ("Abdominal Pain",      "gih"),               # 0
    ("Bowel Habits",         "gih"),               # 1
    ("Stool Form",           "gih"),               # 2
    ("Nausea",               "gih"),               # 3
    ("Reflux",               "gih"),               # 4
    ("Severity",             "xdha:severity"),     # 5
    ("Dysphagia",            "gih"),               # 6
    ("Liver Disease",        "gih"),               # 7
    ("Endoscopy",            "gih"),               # 8
    ("Infection",            "gih"),               # 9
    ("Function",             "xdha:function"),     # 10
    ("IBD Activity",         "gih"),               # 11
    ("Medication",           "xdha:medication"),   # 12
    ("Celiac",               "gih"),               # 13
    ("Nutrition",            "gih"),               # 14
    ("Demographics",         "xdha:demographics"), # 15
    ("Comorbidity",          "xdha:comorbidity"),  # 16
    ("Quality of Life",      "xdha:qol"),          # 17
    ("Treatment",            "xdha:treatment"),    # 18
    ("Biomarkers",           "gih"),               # 19
]

_DOMAIN_LABELS = {
    "Mental Health Screening":            "mental_health",
    "Musculoskeletal Assessment":         "musculoskeletal",
    "Gastrointestinal Health Evaluation": "gastrointestinal",
}

_VERBOSITY = {
    "Mental Health Screening":            "terse",
    "Musculoskeletal Assessment":         "informational",
    "Gastrointestinal Health Evaluation": "expansive",
}

_TOPICS = [
    ("MHL", TOPIC_MHL, "Mental Health Screening",            _MANIFEST_MHL),
    ("MSK", TOPIC_MSK, "Musculoskeletal Assessment",         _MANIFEST_MSK),
    ("GIH", TOPIC_GIH, "Gastrointestinal Health Evaluation", _MANIFEST_GIH),
]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_all():
    """Return the complete list of 60 synthetic CDE records with injection."""
    records = []
    for prefix, topic, tag, _ in _TOPICS:
        for i, (name, question, defn) in enumerate(topic):
            name_inj, q_inj, d_inj, _, _ = _inject_noise(
                i, name, question, defn, prefix
            )
            records.append(
                _build_record(
                    _make_tiny_id(prefix, i + 1),
                    name_inj, q_inj, d_inj, tag,
                )
            )
    return records


def generate_manifest(records):
    """Build manifest rows with instrument/temporal metadata."""
    manifest_data = _MANIFEST_MHL + _MANIFEST_MSK + _MANIFEST_GIH
    all_topics = (
        [("MHL", t) for t in TOPIC_MHL]
        + [("MSK", t) for t in TOPIC_MSK]
        + [("GIH", t) for t in TOPIC_GIH]
    )
    rows = []
    for idx, (rec, (sub_domain, expected_cluster)) in enumerate(
        zip(records, manifest_data)
    ):
        topic_key, (base_name, base_q, base_d) = all_topics[idx]
        within_topic_idx = idx % 20
        _, _, _, instrument, temporal = _inject_noise(
            within_topic_idx, base_name, base_q, base_d, topic_key
        )
        domain_tag = rec["definitions"][0]["tags"][0]

        if within_topic_idx <= 11:
            site = "name+question+definition"
        elif within_topic_idx <= 14:
            site = "definition_only"
        elif within_topic_idx <= 16:
            site = "temporal_only"
        else:
            site = "clean"

        rows.append({
            "tinyId": rec["tinyId"],
            "domain": _DOMAIN_LABELS[domain_tag],
            "domain_full": domain_tag,
            "sub_domain": sub_domain,
            "verbosity": _VERBOSITY[domain_tag],
            "expected_cluster": expected_cluster,
            "name": base_name,
            "instrument": instrument,
            "temporal_phrase": temporal,
            "injection_site": site,
        })
    return rows


def write_manifest_tsv(rows, path):
    fields = [
        "tinyId", "domain", "domain_full", "sub_domain",
        "verbosity", "expected_cluster", "name",
        "instrument", "temporal_phrase", "injection_site",
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
        description="Generate Health Gravity A: 60 health CDEs with "
                    "embedded instruments and temporal phrases."
    )
    parser.add_argument("-o", "--output", required=True,
                        help="Output JSON file path")
    parser.add_argument("--pretty", action="store_true",
                        help="Pretty-print JSON (indented)")
    parser.add_argument("--manifest", default=None,
                        help="Output manifest TSV path")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    records = generate_all()

    indent = 2 if args.pretty else None
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        json.dump(records, f, indent=indent, ensure_ascii=False)
        f.write("\n")

    manifest_path = args.manifest
    if manifest_path is None:
        base = os.path.splitext(os.path.basename(args.output))[0]
        manifest_path = os.path.join(out_dir or ".", f"{base}_manifest.tsv")
    manifest_rows = generate_manifest(records)
    write_manifest_tsv(manifest_rows, manifest_path)

    print(f"Generated {len(records)} health-gravity-A CDEs → {args.output}")
    print(f"Manifest ({len(manifest_rows)} rows) → {manifest_path}")

    for prefix, topic, tag, _ in _TOPICS:
        avg_def = sum(len(d) for _, _, d in topic) / len(topic)
        avg_name = sum(len(n) for n, _, _ in topic) / len(topic)
        verbosity = _VERBOSITY[tag]
        print(f"  {tag} ({verbosity}): avg name {avg_name:.0f} chars, "
              f"avg def {avg_def:.0f} chars")

    inst_counts = {}
    temporal_counts = {}
    for row in manifest_rows:
        if row["instrument"]:
            inst_counts[row["instrument"]] = \
                inst_counts.get(row["instrument"], 0) + 1
        if row["temporal_phrase"]:
            temporal_counts[row["temporal_phrase"]] = \
                temporal_counts.get(row["temporal_phrase"], 0) + 1

    print(f"\nInstrument injection: {sum(inst_counts.values())} CDEs")
    for inst, count in sorted(inst_counts.items()):
        print(f"  {inst}: {count}")

    print(f"\nTemporal injection: {sum(temporal_counts.values())} CDEs")
    for tmp, count in sorted(temporal_counts.items()):
        print(f"  {tmp}: {count}")

    xd_counts = {}
    for row in manifest_rows:
        cl = row["expected_cluster"]
        if cl.startswith("xd"):
            xd_counts.setdefault(cl, []).append(row["tinyId"])
    print(f"\nCross-domain overlap: {len(xd_counts)} groups, "
          f"{sum(len(v) for v in xd_counts.values())} CDEs")
    for cl, ids in sorted(xd_counts.items()):
        print(f"  {cl}: {', '.join(ids)}")


if __name__ == "__main__":
    main()
