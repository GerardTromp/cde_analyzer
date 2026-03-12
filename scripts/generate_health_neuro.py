#!/usr/bin/env python3
"""
Generate 60 synthetic neurology CDEs for verbosity-vs-clustering QC validation.

Unlike health_base (which confounds domain with verbosity), this dataset holds
the domain CONSTANT (neurology) and varies verbosity across all three tiers
for the SAME 20 CDE concepts.  This lets analysts measure whether verbosity
alone creates substructure or separate clusters in embedding space.

Usage:
    python scripts/generate_health_neuro.py -o data/synthetic_qc/health_neuro/health_neuro.json --pretty

Design:
    20 neurology concepts × 3 verbosity tiers = 60 CDEs
    Sub-domains: Stroke (4), Epilepsy (4), Movement Disorders (4),
                 Headache (4), Neuropathy (4)

    Each concept has terse (~60 char def), informational (~200 char def),
    and expansive (~450 char def) versions with appropriately scaled
    designations and definitions.

    concept_id in manifest links the three verbosity variants of each concept.

Cross-domain overlap groups (4):
    xdn:demographics, xdn:medication, xdn:imaging, xdn:lab_values
"""

import argparse
import csv
import json
import os

# ---------------------------------------------------------------------------
# CDE content — 20 concepts, each as (terse, informational, expansive)
# Each tier: (name, question, definition)
# ---------------------------------------------------------------------------

# --- Stroke (concepts 1-4) ---

CONCEPT_01 = {
    "sub_domain": "Cerebrovascular",
    "expected_cluster": "stroke",
    "terse": (
        "Stroke onset time",
        "Time of acute stroke symptom onset",
        "Clock time when stroke symptoms were first observed or reported.",
    ),
    "informational": (
        "Time of acute ischemic stroke symptom onset",
        "Documented clock time at which the patient or a witness first "
        "noticed neurological symptoms consistent with acute stroke",
        "The clock time at which acute stroke symptoms were first "
        "recognized by the patient or a bystander. Accurate onset time "
        "is critical for determining eligibility for thrombolytic therapy "
        "and endovascular intervention within established time windows.",
    ),
    "expansive": (
        "Time of acute ischemic stroke symptom onset documented for "
        "thrombolysis eligibility determination",
        "Precise clock time at which the patient or a reliable witness "
        "first observed focal neurological deficits consistent with "
        "acute ischemic stroke, recorded for treatment window assessment",
        "The documented clock time at which acute ischemic stroke "
        "symptoms were first recognized by the patient, a family member, "
        "or a bystander. When the exact onset is unknown, the last-known-"
        "well time is recorded as the surrogate onset time. Accurate "
        "documentation of symptom onset is essential for determining "
        "eligibility for intravenous thrombolysis within the four-and-a-"
        "half-hour window and for mechanical thrombectomy within extended "
        "time windows of up to twenty-four hours in selected patients "
        "with favorable perfusion imaging profiles.",
    ),
}

CONCEPT_02 = {
    "sub_domain": "Cerebrovascular",
    "expected_cluster": "stroke",
    "terse": (
        "NIH Stroke Scale score",
        "NIHSS total score at presentation",
        "Quantitative measure of stroke-related neurological deficit severity.",
    ),
    "informational": (
        "NIH Stroke Scale total score at initial assessment",
        "Sum of individual NIHSS item scores reflecting the severity of "
        "neurological impairment at the time of initial clinical evaluation",
        "The National Institutes of Health Stroke Scale is a 15-item "
        "standardized assessment that quantifies neurological deficit "
        "severity in acute stroke patients. Scores range from zero to "
        "forty-two, with higher values indicating more severe impairment "
        "across domains including consciousness, gaze, visual fields, "
        "facial palsy, limb strength, ataxia, sensation, language, "
        "dysarthria, and extinction.",
    ),
    "expansive": (
        "National Institutes of Health Stroke Scale total score at "
        "initial emergency department neurological assessment",
        "Composite score from the standardized 15-item NIHSS assessment "
        "performed at initial evaluation quantifying the severity of "
        "acute neurological deficits across multiple functional domains",
        "The National Institutes of Health Stroke Scale is a systematic "
        "15-item clinical examination tool that quantifies the severity "
        "of neurological impairment in patients presenting with acute "
        "stroke. Each item assesses a specific neurological function "
        "including level of consciousness, horizontal eye movement, "
        "visual fields, facial palsy, motor strength in each limb, "
        "limb ataxia, sensory function, language, dysarthria, and "
        "extinction or inattention. The total score ranges from zero "
        "indicating no measurable deficit to forty-two indicating the "
        "most severe impairment. The NIHSS score at presentation guides "
        "acute treatment decisions, predicts short-term outcomes, and "
        "serves as the primary efficacy endpoint in stroke clinical "
        "trials evaluating thrombolytic and endovascular therapies.",
    ),
}

CONCEPT_03 = {
    "sub_domain": "Cerebrovascular",
    "expected_cluster": "stroke",
    "terse": (
        "Modified Rankin Scale score",
        "Post-stroke disability level on the mRS",
        "Ordinal scale rating global disability after stroke from 0 to 6.",
    ),
    "informational": (
        "Modified Rankin Scale score at follow-up assessment",
        "Clinician-assigned disability grade on the modified Rankin Scale "
        "assessed at the follow-up visit after acute stroke treatment",
        "The modified Rankin Scale is a seven-level ordinal outcome "
        "measure ranging from zero for no symptoms to six for death. "
        "It is the most widely used primary endpoint in acute stroke "
        "trials and captures the overall degree of disability in "
        "activities of daily living following cerebrovascular events.",
    ),
    "expansive": (
        "Modified Rankin Scale disability score assessed at ninety-day "
        "follow-up after acute ischemic stroke treatment",
        "Ordinal disability grade assigned by a trained evaluator using "
        "the modified Rankin Scale at the ninety-day post-stroke "
        "follow-up visit reflecting functional independence level",
        "The modified Rankin Scale is a clinician-rated ordinal outcome "
        "measure that grades the degree of disability or dependence in "
        "daily activities of stroke survivors. The scale ranges from "
        "zero indicating no symptoms at all through five indicating "
        "severe disability requiring constant nursing care to six "
        "indicating death. Assessment at ninety days after stroke onset "
        "is the standard time point for outcome evaluation in clinical "
        "trials. A shift analysis of the modified Rankin Scale "
        "distribution is the recommended statistical approach for "
        "detecting treatment effects across the full range of "
        "functional outcomes in acute stroke intervention studies.",
    ),
}

CONCEPT_04 = {
    "sub_domain": "Cerebrovascular",
    "expected_cluster": "xdn:imaging",
    "terse": (
        "Brain CT infarct volume",
        "Volume of ischemic infarct on brain CT",
        "Measured volume of acute ischemic tissue on non-contrast CT scan.",
    ),
    "informational": (
        "Brain CT ischemic infarct volume measurement",
        "Quantified volume of acute ischemic infarction measured on "
        "non-contrast computed tomography of the brain",
        "The volume of acute ischemic infarction measured on brain CT "
        "imaging in cubic centimeters. Infarct volume is calculated "
        "using semi-automated planimetric methods applied to axial "
        "slices and correlates with clinical severity and long-term "
        "functional outcome after ischemic stroke.",
    ),
    "expansive": (
        "Brain computed tomography ischemic infarct volume measured "
        "using semi-automated planimetric segmentation",
        "Quantified total volume of acute ischemic infarction in cubic "
        "centimeters determined from non-contrast computed tomography "
        "of the brain using semi-automated volumetric analysis software",
        "The total volume of acute ischemic infarction measured on "
        "non-contrast computed tomography of the brain using semi-"
        "automated planimetric segmentation software. Infarct volume "
        "is calculated by summing the area of hypodense ischemic "
        "tissue on each axial slice multiplied by the slice thickness. "
        "Larger infarct volumes are associated with more severe "
        "neurological deficits, higher mortality, and worse long-term "
        "functional outcomes. Infarct volume measurement is used as "
        "a secondary endpoint in acute stroke treatment trials and "
        "as a prognostic biomarker in clinical practice to guide "
        "rehabilitation planning and goals of care discussions.",
    ),
}

# --- Epilepsy (concepts 5-8) ---

CONCEPT_05 = {
    "sub_domain": "Epilepsy",
    "expected_cluster": "epilepsy",
    "terse": (
        "Seizure frequency",
        "Number of seizures per month",
        "Count of seizure episodes occurring within a calendar month.",
    ),
    "informational": (
        "Monthly seizure frequency count",
        "Total number of observed or patient-reported seizure episodes "
        "occurring within the preceding calendar month",
        "The total count of seizure episodes documented during the "
        "preceding calendar month, based on patient self-report, "
        "seizure diary entries, or caregiver observation. Seizure "
        "frequency is the primary measure of epilepsy control and "
        "the key outcome variable in antiepileptic drug trials.",
    ),
    "expansive": (
        "Monthly seizure frequency count from patient seizure diary "
        "and caregiver observation log",
        "Total number of clinically apparent seizure episodes recorded "
        "in the patient seizure diary and corroborated by caregiver "
        "observation during the preceding calendar month",
        "The total number of clinically apparent seizure episodes "
        "documented during the preceding calendar month as recorded "
        "in the patient seizure diary and corroborated when possible "
        "by caregiver observation logs. Seizure counting includes all "
        "seizure types experienced by the patient: focal aware, focal "
        "impaired awareness, focal to bilateral tonic-clonic, and "
        "generalized onset seizures. Accurate seizure frequency "
        "quantification is the cornerstone of epilepsy treatment "
        "monitoring and serves as the primary efficacy endpoint in "
        "randomized controlled trials evaluating new antiepileptic "
        "medications. A fifty percent or greater reduction in monthly "
        "seizure frequency is the conventional responder threshold.",
    ),
}

CONCEPT_06 = {
    "sub_domain": "Epilepsy",
    "expected_cluster": "epilepsy",
    "terse": (
        "Seizure type classification",
        "ILAE classification of seizure type",
        "Categorization of seizure type per ILAE classification system.",
    ),
    "informational": (
        "Seizure type classified per ILAE 2017 framework",
        "Seizure type assigned according to the International League "
        "Against Epilepsy 2017 operational classification system",
        "The seizure type assigned using the International League "
        "Against Epilepsy 2017 classification framework, which "
        "categorizes seizures by onset as focal, generalized, or "
        "unknown, and further by level of awareness and motor or "
        "non-motor features. Accurate seizure classification guides "
        "selection of antiepileptic medication.",
    ),
    "expansive": (
        "Seizure type classified according to the International League "
        "Against Epilepsy 2017 operational classification framework",
        "Primary seizure type assigned by a neurologist according to "
        "the ILAE 2017 classification based on clinical semiology "
        "and electroencephalographic findings",
        "The primary seizure type assigned by the treating neurologist "
        "according to the International League Against Epilepsy 2017 "
        "operational classification of seizure types. This framework "
        "classifies seizures first by onset: focal onset, generalized "
        "onset, or unknown onset. Focal seizures are further "
        "subcategorized by awareness level as focal aware or focal "
        "with impaired awareness, and by predominant manifestation as "
        "motor or non-motor. Generalized seizures include tonic-clonic, "
        "absence, myoclonic, atonic, and tonic subtypes. Accurate "
        "classification based on clinical semiology and "
        "electroencephalographic findings is essential for selecting "
        "appropriate antiepileptic therapy and predicting prognosis.",
    ),
}

CONCEPT_07 = {
    "sub_domain": "Epilepsy",
    "expected_cluster": "xdn:medication",
    "terse": (
        "Antiepileptic drug name",
        "Name of current antiepileptic medication",
        "Generic name of the prescribed antiepileptic drug.",
    ),
    "informational": (
        "Current antiepileptic drug generic name",
        "Generic name of the antiepileptic medication currently "
        "prescribed for seizure control",
        "The generic pharmaceutical name of the antiepileptic drug "
        "currently prescribed as the primary agent for seizure "
        "control. Recording the specific drug name is necessary for "
        "tracking treatment response, monitoring drug-drug interactions, "
        "and identifying medication-related adverse effects.",
    ),
    "expansive": (
        "Generic name of the primary antiepileptic drug currently "
        "prescribed for ongoing seizure management",
        "International nonproprietary name of the principal "
        "antiepileptic medication prescribed for the management of "
        "the patient's epilepsy syndrome",
        "The international nonproprietary generic name of the "
        "principal antiepileptic drug prescribed for ongoing seizure "
        "management. The drug name is recorded as part of the "
        "standardized epilepsy treatment documentation and is "
        "essential for tracking individual treatment response over "
        "time, identifying potential pharmacokinetic and "
        "pharmacodynamic drug-drug interactions with concomitant "
        "medications, monitoring for known adverse effects specific "
        "to each agent, and ensuring continuity of care across "
        "clinical settings. Common agents include levetiracetam, "
        "lamotrigine, valproate, carbamazepine, and oxcarbazepine.",
    ),
}

CONCEPT_08 = {
    "sub_domain": "Epilepsy",
    "expected_cluster": "epilepsy",
    "terse": (
        "EEG finding category",
        "Primary EEG finding classification",
        "Categorical classification of the dominant EEG abnormality.",
    ),
    "informational": (
        "Primary electroencephalogram finding category",
        "Dominant abnormality classification from the routine scalp "
        "electroencephalogram recording",
        "The primary finding category from a routine scalp "
        "electroencephalogram recording classified as normal, focal "
        "epileptiform, generalized epileptiform, focal slowing, "
        "generalized slowing, or other abnormality. EEG findings "
        "support seizure classification and epilepsy syndrome diagnosis.",
    ),
    "expansive": (
        "Primary electroencephalogram finding category from routine "
        "scalp recording for epilepsy evaluation",
        "Dominant electroencephalographic abnormality classified from "
        "the routine scalp EEG recording obtained as part of the "
        "comprehensive epilepsy diagnostic evaluation",
        "The dominant finding category from a routine twenty-one-"
        "channel scalp electroencephalogram recording obtained as "
        "part of the epilepsy diagnostic evaluation. Findings are "
        "classified as normal background with no epileptiform "
        "activity, focal epileptiform discharges such as spikes or "
        "sharp waves, generalized epileptiform discharges including "
        "spike-and-wave complexes, focal non-epileptiform slowing, "
        "generalized non-epileptiform slowing, or other abnormalities "
        "including breach rhythm or medication effect. The EEG finding "
        "category informs seizure type classification, epilepsy "
        "syndrome diagnosis, and antiepileptic drug selection. Serial "
        "EEG recordings may be used to monitor treatment response.",
    ),
}

# --- Movement Disorders (concepts 9-12) ---

CONCEPT_09 = {
    "sub_domain": "Movement Disorders",
    "expected_cluster": "movement",
    "terse": (
        "Tremor severity rating",
        "Clinical tremor severity grade",
        "Ordinal rating of tremor severity from absent to severe.",
    ),
    "informational": (
        "Clinical tremor severity rating at neurological examination",
        "Ordinal severity grade assigned to the patient's tremor "
        "during the standard neurological motor examination",
        "An ordinal severity rating assigned to tremor during "
        "neurological examination, graded as absent, mild, moderate, "
        "or severe. The rating considers tremor amplitude, frequency, "
        "and impact on voluntary movement. Tremor severity tracking "
        "guides medication titration and surgical candidacy assessment.",
    ),
    "expansive": (
        "Clinical tremor severity rating assigned during standardized "
        "neurological motor examination at clinic visit",
        "Ordinal severity grade for resting and action tremor assigned "
        "by the examining neurologist based on visual assessment of "
        "amplitude, frequency, and functional impact during the "
        "standardized motor examination",
        "An ordinal severity rating assigned to both resting and "
        "action components of tremor during the standardized "
        "neurological motor examination. The rating scale grades "
        "tremor as absent, slight with barely perceptible amplitude, "
        "mild with noticeable tremor that does not interfere with "
        "function, moderate with tremor that partially interferes "
        "with daily activities, or severe with tremor that prevents "
        "normal function. The assessment considers tremor amplitude "
        "in centimeters, frequency in hertz estimated visually, "
        "constancy, and the degree of functional impairment during "
        "tasks such as pouring water, writing, and bringing a cup "
        "to the mouth. Serial tremor severity ratings track disease "
        "progression and treatment response in movement disorder "
        "clinics.",
    ),
}

CONCEPT_10 = {
    "sub_domain": "Movement Disorders",
    "expected_cluster": "movement",
    "terse": (
        "UPDRS motor score",
        "Unified Parkinson's Disease Rating Scale Part III total",
        "Total motor examination score from the MDS-UPDRS Part III.",
    ),
    "informational": (
        "MDS-UPDRS Part III motor examination total score",
        "Total score from the Movement Disorder Society Unified "
        "Parkinson's Disease Rating Scale Part III motor examination",
        "The total score from Part III of the MDS-UPDRS motor "
        "examination, which assesses eighteen motor items including "
        "speech, facial expression, rigidity, finger tapping, hand "
        "movements, pronation-supination, toe tapping, leg agility, "
        "arising from chair, gait, freezing, postural stability, "
        "posture, body bradykinesia, postural tremor, kinetic tremor, "
        "and rest tremor. Scores range from zero to one hundred "
        "thirty-two.",
    ),
    "expansive": (
        "Movement Disorder Society Unified Parkinson's Disease Rating "
        "Scale Part III motor examination total score",
        "Composite score from the MDS-UPDRS Part III standardized "
        "motor examination assessing eighteen items across speech, "
        "facial expression, rigidity, bradykinesia, tremor, gait, "
        "and postural stability domains",
        "The total composite score from Part III of the Movement "
        "Disorder Society revision of the Unified Parkinson's Disease "
        "Rating Scale, which is the standardized motor examination "
        "performed by a trained rater. The examination consists of "
        "eighteen items assessing speech, facial expression, rigidity "
        "in four limbs and the neck, finger tapping, hand movements, "
        "pronation-supination movements, toe tapping, leg agility, "
        "arising from a chair, gait, freezing of gait, postural "
        "stability on the pull test, posture, global spontaneity of "
        "movement reflecting body bradykinesia, postural tremor of "
        "the hands, kinetic tremor of the hands, and rest tremor "
        "amplitude in four limbs and the lip or jaw. Each item is "
        "scored from zero for normal to four for severe impairment. "
        "The total score ranges from zero to one hundred thirty-two "
        "and is the primary motor outcome in Parkinson disease "
        "clinical trials.",
    ),
}

CONCEPT_11 = {
    "sub_domain": "Movement Disorders",
    "expected_cluster": "movement",
    "terse": (
        "Gait assessment score",
        "Standardized gait evaluation rating",
        "Numeric score from standardized clinical gait assessment.",
    ),
    "informational": (
        "Standardized gait assessment composite score",
        "Composite numeric score from the standardized clinical gait "
        "evaluation performed during the movement disorder examination",
        "A composite numeric score derived from standardized clinical "
        "gait assessment evaluating stride length, cadence, arm swing, "
        "turning stability, and freezing episodes. The gait score is "
        "used to monitor progression of parkinsonian gait impairment "
        "and to evaluate response to dopaminergic medication and "
        "physical therapy interventions.",
    ),
    "expansive": (
        "Standardized gait assessment composite score from the "
        "movement disorder clinic clinical evaluation protocol",
        "Composite numeric score from the standardized gait evaluation "
        "protocol assessing stride length, cadence, arm swing symmetry, "
        "turning stability, and freezing of gait episodes during the "
        "movement disorder examination",
        "A composite numeric score derived from the standardized gait "
        "assessment protocol used in movement disorder clinics. The "
        "evaluation systematically rates stride length relative to "
        "the patient's height, walking cadence in steps per minute, "
        "symmetry and amplitude of arm swing, stability and number "
        "of steps required during turning, presence and duration of "
        "freezing episodes at gait initiation and during turns, and "
        "the degree of festination or propulsive gait tendency. Each "
        "component is rated on a five-point severity scale and summed "
        "to produce the composite score. Serial gait assessments "
        "track disease progression in neurodegenerative conditions "
        "and quantify the motor response to pharmacological "
        "interventions and deep brain stimulation therapy.",
    ),
}

CONCEPT_12 = {
    "sub_domain": "Movement Disorders",
    "expected_cluster": "xdn:medication",
    "terse": (
        "Levodopa equivalent daily dose",
        "Total daily levodopa equivalent dose in milligrams",
        "Standardized total dopaminergic medication dose as levodopa equivalent.",
    ),
    "informational": (
        "Total daily levodopa equivalent dose",
        "Sum of all dopaminergic medications converted to levodopa "
        "equivalent dose in milligrams per day",
        "The total daily levodopa equivalent dose is calculated by "
        "converting all dopaminergic medications to their levodopa "
        "equivalents using standard conversion factors and summing "
        "the results. This standardized measure allows comparison "
        "of total dopaminergic load across patients receiving "
        "different medication combinations.",
    ),
    "expansive": (
        "Total daily levodopa equivalent dose calculated from all "
        "prescribed dopaminergic medications using standard "
        "conversion factors",
        "Aggregate daily dopaminergic medication burden expressed "
        "as the sum of all prescribed antiparkinsonian agents "
        "converted to levodopa milligram equivalents using "
        "published conversion ratios",
        "The total daily levodopa equivalent dose is a standardized "
        "summary measure of aggregate dopaminergic medication burden "
        "calculated by converting the daily doses of all prescribed "
        "dopaminergic agents to their levodopa equivalents using "
        "published conversion factors. Conversion factors include "
        "levodopa at a ratio of one, pramipexole at one hundred, "
        "ropinirole at twenty, rotigotine at thirty, entacapone "
        "as a one-third levodopa multiplier, and rasagiline at one "
        "hundred. The total levodopa equivalent daily dose enables "
        "comparison of dopaminergic medication intensity across "
        "patients receiving different drug combinations and is "
        "routinely reported in Parkinson disease clinical trials "
        "and observational studies as a covariate and outcome "
        "measure.",
    ),
}

# --- Headache (concepts 13-16) ---

CONCEPT_13 = {
    "sub_domain": "Headache",
    "expected_cluster": "headache",
    "terse": (
        "Headache pain intensity",
        "Current headache pain severity score",
        "Numeric rating of headache pain intensity on a 0-10 scale.",
    ),
    "informational": (
        "Headache pain intensity on numeric rating scale",
        "Patient-reported headache pain intensity on a numeric rating "
        "scale from zero for no pain to ten for worst imaginable pain",
        "The patient's self-reported headache pain intensity rated "
        "on a standard eleven-point numeric rating scale where zero "
        "represents no pain and ten represents the worst pain "
        "imaginable. The numeric rating scale is the most commonly "
        "used pain intensity measure in headache clinical trials "
        "and clinical practice.",
    ),
    "expansive": (
        "Headache pain intensity rated on the eleven-point numeric "
        "rating scale at the time of clinical assessment",
        "Patient self-reported headache pain intensity score on the "
        "standard eleven-point numeric rating scale ranging from zero "
        "for no pain to ten for the worst pain imaginable, recorded "
        "at the headache clinic evaluation",
        "The patient's self-reported headache pain intensity at the "
        "time of the headache clinic evaluation, rated on the "
        "standard eleven-point numeric rating scale. The scale "
        "anchors are zero representing no pain at all and ten "
        "representing the worst pain the patient can imagine. "
        "Patients are instructed to select the single number that "
        "best represents their current headache pain intensity. "
        "A reduction of two or more points on the numeric rating "
        "scale is generally considered a clinically meaningful "
        "improvement. The numeric pain intensity rating is "
        "recommended as a core outcome measure by the International "
        "Headache Society clinical trial guidelines and is used "
        "alongside headache frequency and disability measures to "
        "evaluate treatment efficacy in migraine and tension-type "
        "headache trials.",
    ),
}

CONCEPT_14 = {
    "sub_domain": "Headache",
    "expected_cluster": "headache",
    "terse": (
        "Migraine aura presence",
        "Whether migraine is preceded by aura",
        "Binary indicator of aura occurrence before migraine headache.",
    ),
    "informational": (
        "Migraine with aura classification",
        "Whether the patient's migraine attacks are preceded by "
        "reversible focal neurological symptoms meeting aura criteria",
        "A binary classification indicating whether the patient's "
        "migraine attacks are preceded by fully reversible focal "
        "neurological symptoms meeting the International Classification "
        "of Headache Disorders criteria for aura. Common aura types "
        "include visual, sensory, speech or language, and motor "
        "phenomena.",
    ),
    "expansive": (
        "Migraine with aura classification based on International "
        "Classification of Headache Disorders diagnostic criteria",
        "Binary classification indicating whether the patient's "
        "migraine attacks are preceded by fully reversible focal "
        "neurological symptoms meeting ICHD-3 aura diagnostic "
        "criteria including visual, sensory, or language phenomena",
        "A binary classification indicating whether the patient's "
        "migraine attacks are preceded by fully reversible focal "
        "neurological symptoms that meet the International "
        "Classification of Headache Disorders third edition criteria "
        "for migraine with aura. Aura symptoms develop gradually "
        "over five or more minutes, last between five and sixty "
        "minutes, and are followed by headache within sixty minutes. "
        "The most common aura type is visual, manifesting as "
        "scintillating scotomata, fortification spectra, or "
        "hemianopic field defects. Sensory aura presents as "
        "unilateral paresthesias, and speech or language aura "
        "presents as transient dysphasia. The distinction between "
        "migraine with and without aura is clinically relevant for "
        "treatment selection, contraceptive counseling regarding "
        "stroke risk, and stratification in clinical trials.",
    ),
}

CONCEPT_15 = {
    "sub_domain": "Headache",
    "expected_cluster": "headache",
    "terse": (
        "Monthly headache days",
        "Number of headache days per month",
        "Count of days with headache in the preceding calendar month.",
    ),
    "informational": (
        "Monthly headache day frequency count",
        "Total number of calendar days on which headache of any "
        "duration occurred during the preceding month",
        "The total count of calendar days on which headache of any "
        "type or duration occurred during the preceding month, "
        "recorded from the patient headache diary. Monthly headache "
        "days is the primary frequency measure used to classify "
        "episodic versus chronic migraine and to assess preventive "
        "treatment efficacy.",
    ),
    "expansive": (
        "Monthly headache day frequency count from prospective "
        "patient headache diary for treatment monitoring",
        "Total number of unique calendar days on which headache of "
        "any type or duration occurred during the preceding month "
        "as recorded prospectively in the validated patient "
        "headache diary",
        "The total number of unique calendar days during the "
        "preceding month on which headache of any type, intensity, "
        "or duration occurred, as recorded prospectively in the "
        "patient's validated headache diary. Monthly headache days "
        "is the standard primary endpoint in migraine preventive "
        "treatment trials and is used to classify headache frequency "
        "as episodic with fewer than fifteen headache days per month "
        "or chronic with fifteen or more headache days per month for "
        "at least three consecutive months. A reduction of at least "
        "fifty percent in monthly headache days is the conventional "
        "responder definition. Accurate prospective diary recording "
        "avoids the recall bias inherent in retrospective headache "
        "frequency estimation.",
    ),
}

CONCEPT_16 = {
    "sub_domain": "Headache",
    "expected_cluster": "xdn:demographics",
    "terse": (
        "Age at headache onset",
        "Patient age when headaches first began",
        "Age in years at the time of first headache occurrence.",
    ),
    "informational": (
        "Patient age at headache disorder onset",
        "Age in years at which the patient first experienced "
        "recurrent headaches meeting diagnostic criteria",
        "The patient's age in years at the time of first onset of "
        "recurrent headaches meeting diagnostic criteria for a "
        "primary headache disorder. Age at onset is a key "
        "epidemiological variable and influences the differential "
        "diagnosis, as migraine typically begins in adolescence or "
        "early adulthood while new-onset headache after age fifty "
        "requires exclusion of secondary causes.",
    ),
    "expansive": (
        "Patient age at onset of recurrent headache disorder "
        "meeting primary headache diagnostic criteria",
        "Age in years at which the patient first experienced "
        "recurrent headache episodes meeting International "
        "Classification of Headache Disorders criteria for a "
        "primary headache disorder",
        "The patient's age in years at the time of first onset "
        "of recurrent headache episodes meeting the International "
        "Classification of Headache Disorders diagnostic criteria "
        "for a primary headache disorder such as migraine, "
        "tension-type headache, or cluster headache. Age at onset "
        "is a fundamental epidemiological and clinical variable. "
        "Migraine onset typically peaks during adolescence and "
        "early adulthood with a median age of onset around "
        "twenty-five years. Tension-type headache may begin at "
        "any age. New-onset headache after age fifty years raises "
        "concern for secondary causes including giant cell "
        "arteritis, intracranial neoplasm, or cerebrovascular "
        "disease and warrants prompt diagnostic evaluation "
        "including neuroimaging and inflammatory markers.",
    ),
}

# --- Neuropathy (concepts 17-20) ---

CONCEPT_17 = {
    "sub_domain": "Neuropathy",
    "expected_cluster": "neuropathy",
    "terse": (
        "Nerve conduction velocity",
        "Motor nerve conduction speed measurement",
        "Speed of electrical signal propagation along a peripheral nerve.",
    ),
    "informational": (
        "Motor nerve conduction velocity measurement",
        "Speed of electrical impulse propagation along a motor nerve "
        "measured during nerve conduction studies",
        "The velocity of electrical impulse propagation along a motor "
        "nerve measured in meters per second during standardized "
        "nerve conduction studies. Reduced conduction velocity below "
        "the lower limit of normal indicates demyelinating neuropathy, "
        "while preserved velocity with reduced amplitude suggests "
        "axonal neuropathy.",
    ),
    "expansive": (
        "Motor nerve conduction velocity measured during standardized "
        "electrodiagnostic nerve conduction studies",
        "Speed of electrical impulse propagation along a motor nerve "
        "segment in meters per second measured during standardized "
        "nerve conduction studies as part of the electrodiagnostic "
        "evaluation of peripheral neuropathy",
        "The velocity of electrical impulse propagation along a "
        "specified motor nerve segment measured in meters per second "
        "during standardized nerve conduction studies performed as "
        "part of the electrodiagnostic evaluation of peripheral "
        "neuropathy. Conduction velocity is calculated by dividing "
        "the distance between proximal and distal stimulation sites "
        "by the difference in onset latency. Values below the "
        "lower limit of normal for the specific nerve indicate "
        "demyelinating pathology, while preserved conduction "
        "velocity with reduced compound muscle action potential "
        "amplitude indicates primary axonal degeneration. The "
        "pattern of conduction velocity abnormalities across "
        "multiple nerves helps distinguish acquired inflammatory "
        "demyelinating neuropathies from hereditary demyelinating "
        "conditions and from axonal neuropathies of metabolic, "
        "toxic, or other etiologies.",
    ),
}

CONCEPT_18 = {
    "sub_domain": "Neuropathy",
    "expected_cluster": "neuropathy",
    "terse": (
        "Neuropathic pain score",
        "Neuropathy-specific pain severity rating",
        "Numeric score reflecting severity of neuropathic pain symptoms.",
    ),
    "informational": (
        "Neuropathic pain severity score from validated questionnaire",
        "Total score from a validated neuropathic pain assessment "
        "questionnaire reflecting the severity of pain symptoms "
        "attributable to peripheral nerve damage",
        "The total score from a validated neuropathic pain assessment "
        "instrument such as the DN4, painDETECT, or Neuropathic Pain "
        "Symptom Inventory. The score quantifies the severity and "
        "character of pain symptoms attributable to peripheral nerve "
        "damage including burning, shooting, electric shock "
        "sensations, and allodynia.",
    ),
    "expansive": (
        "Neuropathic pain severity score from validated patient-"
        "reported neuropathic pain assessment questionnaire",
        "Total symptom severity score from a validated neuropathic "
        "pain questionnaire quantifying the intensity and character "
        "of pain symptoms including burning, shooting, and electric "
        "shock sensations attributable to peripheral nerve damage",
        "The total symptom severity score from a validated "
        "neuropathic pain assessment questionnaire designed to "
        "quantify the intensity and qualitative character of pain "
        "symptoms attributable to peripheral nerve damage. Common "
        "instruments include the DN4 questionnaire with a diagnostic "
        "cutoff of four out of ten, the painDETECT questionnaire "
        "with scores above nineteen indicating likely neuropathic "
        "pain, and the Neuropathic Pain Symptom Inventory which "
        "assesses five pain dimensions: burning superficial "
        "spontaneous pain, pressing deep spontaneous pain, "
        "paroxysmal pain, evoked pain including allodynia and "
        "hyperalgesia, and paresthesia or dysesthesia. The "
        "neuropathic pain score is used as a primary or secondary "
        "endpoint in clinical trials evaluating analgesic efficacy "
        "of pharmacological and interventional treatments for "
        "painful peripheral neuropathies.",
    ),
}

CONCEPT_19 = {
    "sub_domain": "Neuropathy",
    "expected_cluster": "neuropathy",
    "terse": (
        "Vibration perception threshold",
        "Quantitative vibration sense measurement",
        "Threshold of vibration detection at the great toe in micrometers.",
    ),
    "informational": (
        "Vibration perception threshold at the great toe",
        "Quantitative threshold of vibration detection at the great "
        "toe measured using a biothesiometer or similar device",
        "The vibration perception threshold measured at the dorsal "
        "surface of the great toe using a biothesiometer or "
        "equivalent quantitative sensory testing device, expressed "
        "in volts or micrometers of displacement. Elevated vibration "
        "perception threshold indicates large-fiber sensory "
        "neuropathy and is a sensitive early marker of diabetic "
        "peripheral neuropathy.",
    ),
    "expansive": (
        "Vibration perception threshold measured at the great toe "
        "using quantitative sensory testing biothesiometry",
        "Quantitative vibration detection threshold at the dorsal "
        "surface of the great toe measured using biothesiometer "
        "quantitative sensory testing expressed in micrometers of "
        "displacement or voltage units",
        "The vibration perception threshold measured at the dorsal "
        "surface of the great toe using a biothesiometer or "
        "equivalent quantitative sensory testing device. The test "
        "applies a graduated vibratory stimulus of increasing "
        "amplitude and records the lowest stimulus intensity at "
        "which the patient reliably perceives vibration, expressed "
        "in volts or micrometers of displacement. Elevated "
        "vibration perception threshold is one of the earliest "
        "quantitative markers of large-fiber sensory neuropathy "
        "and is particularly useful for screening and monitoring "
        "diabetic peripheral neuropathy. A threshold above "
        "twenty-five volts at the great toe is associated with "
        "significantly increased risk of foot ulceration. Serial "
        "vibration perception threshold measurements track "
        "neuropathy progression and are used as endpoints in "
        "clinical trials evaluating neuroprotective therapies.",
    ),
}

CONCEPT_20 = {
    "sub_domain": "Neuropathy",
    "expected_cluster": "xdn:lab_values",
    "terse": (
        "Hemoglobin A1c in neuropathy workup",
        "HbA1c level for diabetic neuropathy screening",
        "Glycated hemoglobin percentage in the neuropathy evaluation panel.",
    ),
    "informational": (
        "Hemoglobin A1c percentage in peripheral neuropathy workup",
        "Glycated hemoglobin level measured as part of the laboratory "
        "evaluation for suspected diabetic peripheral neuropathy",
        "The hemoglobin A1c percentage measured as part of the "
        "standard laboratory workup for peripheral neuropathy to "
        "assess glycemic control as a potential etiological factor. "
        "Diabetes mellitus and prediabetes are the most common "
        "identifiable causes of distal symmetric polyneuropathy, "
        "making A1c an essential component of the neuropathy "
        "diagnostic evaluation.",
    ),
    "expansive": (
        "Hemoglobin A1c percentage measured as part of the "
        "comprehensive laboratory evaluation for peripheral "
        "neuropathy etiology determination",
        "Glycated hemoglobin percentage measured in the comprehensive "
        "laboratory panel for peripheral neuropathy etiological "
        "evaluation to assess glycemic status as a contributing "
        "factor to nerve damage",
        "The hemoglobin A1c percentage measured as part of the "
        "comprehensive laboratory evaluation panel for peripheral "
        "neuropathy etiology determination. Diabetes mellitus is "
        "the most common identifiable cause of distal symmetric "
        "polyneuropathy in developed countries, and prediabetic "
        "glycemic dysregulation is increasingly recognized as a "
        "cause of small-fiber neuropathy. An A1c value at or "
        "above 6.5 percent is diagnostic of diabetes, while "
        "values between 5.7 and 6.4 percent indicate prediabetes. "
        "Glycemic control as reflected by A1c correlates with "
        "neuropathy severity and progression rate. The A1c value "
        "guides treatment decisions for glycemic optimization as "
        "a cornerstone of diabetic neuropathy management and is "
        "included alongside vitamin B12, thyroid function, serum "
        "protein electrophoresis, and other tests in the standard "
        "neuropathy laboratory evaluation panel.",
    ),
}

ALL_CONCEPTS = [
    CONCEPT_01, CONCEPT_02, CONCEPT_03, CONCEPT_04,
    CONCEPT_05, CONCEPT_06, CONCEPT_07, CONCEPT_08,
    CONCEPT_09, CONCEPT_10, CONCEPT_11, CONCEPT_12,
    CONCEPT_13, CONCEPT_14, CONCEPT_15, CONCEPT_16,
    CONCEPT_17, CONCEPT_18, CONCEPT_19, CONCEPT_20,
]

VERBOSITY_TIERS = ["terse", "informational", "expansive"]

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

_TIER_SUFFIX = {"terse": "T", "informational": "I", "expansive": "E"}


def _make_tiny_id(concept_num: int, tier: str) -> str:
    """Generate tinyId: synNR01T, synNR01I, synNR01E."""
    return f"synNR{concept_num:02d}{_TIER_SUFFIX[tier]}"


def _build_record(
    tiny_id: str,
    name: str,
    question: str,
    definition: str,
) -> dict:
    rec = dict(_BOILERPLATE)
    rec["tinyId"] = tiny_id
    rec["designations"] = [
        {"designation": name, "sources": [], "tags": ["Preferred Question Text"]},
        {"designation": question, "sources": [], "tags": ["Alternative Question Text"]},
    ]
    rec["definitions"] = [
        {"definition": definition, "tags": ["Neurology Assessment"]},
    ]
    return rec


def generate_all() -> list:
    """Return the complete list of 60 synthetic CDE records."""
    records = []
    for concept_num, concept in enumerate(ALL_CONCEPTS, start=1):
        for tier in VERBOSITY_TIERS:
            name, question, definition = concept[tier]
            tiny_id = _make_tiny_id(concept_num, tier)
            records.append(_build_record(tiny_id, name, question, definition))
    return records


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def generate_manifest(records: list) -> list[dict]:
    """Build manifest rows aligned to generate_all() output order."""
    rows = []
    for concept_num, concept in enumerate(ALL_CONCEPTS, start=1):
        for tier in VERBOSITY_TIERS:
            tiny_id = _make_tiny_id(concept_num, tier)
            name = concept[tier][0]
            rows.append({
                "tinyId": tiny_id,
                "domain": "neurology",
                "domain_full": "Neurology Assessment",
                "sub_domain": concept["sub_domain"],
                "verbosity": tier,
                "concept_id": f"NR{concept_num:02d}",
                "expected_cluster": concept["expected_cluster"],
                "name": name,
            })
    return rows


def write_manifest_tsv(rows: list[dict], path: str) -> None:
    fields = [
        "tinyId", "domain", "domain_full", "sub_domain",
        "verbosity", "concept_id", "expected_cluster", "name",
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
        description="Generate 60 neurology CDEs (20 concepts × 3 verbosity tiers)."
    )
    parser.add_argument("-o", "--output", required=True, help="Output JSON file path")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    parser.add_argument("--manifest", default=None, help="Manifest TSV path (default: auto)")
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

    # Summary
    print(f"Generated {len(records)} neurology CDEs -> {args.output}")
    print(f"Manifest ({len(manifest_rows)} rows) -> {manifest_path}")
    print(f"\n  20 concepts × 3 verbosity tiers = {len(records)} CDEs")
    print(f"  Domain: neurology (constant)")
    print(f"  Sub-domains: {', '.join(sorted(set(c['sub_domain'] for c in ALL_CONCEPTS)))}")

    # Verbosity char stats
    for tier in VERBOSITY_TIERS:
        defs = [c[tier][2] for c in ALL_CONCEPTS]
        avg_len = sum(len(d) for d in defs) / len(defs)
        min_len = min(len(d) for d in defs)
        max_len = max(len(d) for d in defs)
        print(f"  {tier:15s}: avg {avg_len:.0f} chars (range {min_len}-{max_len})")

    # Cross-domain groups
    xd = {}
    for c_num, c in enumerate(ALL_CONCEPTS, 1):
        if c["expected_cluster"].startswith("xdn:"):
            xd.setdefault(c["expected_cluster"], []).append(f"NR{c_num:02d}")
    print(f"\nCross-domain groups: {len(xd)}")
    for cl, ids in sorted(xd.items()):
        print(f"  {cl}: {', '.join(ids)}")


if __name__ == "__main__":
    main()
