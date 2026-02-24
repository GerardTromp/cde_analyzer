#!/usr/bin/env python3
"""
Generate Set 1B: Clinical synthetic CDEs with embedded instruments.

Produces 60 CDEs across 3 clinical domains with synthetic clinical
instrument names and temporal boilerplate phrases.  Tests "gravity"
effects — shared instruments pull semantically unrelated CDEs together
in embedding space.

Usage:
    python scripts/generate_synthetic_set1b.py -o data/synthetic_qc/set1b_clinical/set1b_clinical.json
    python scripts/generate_synthetic_set1b.py -o data/synthetic_qc/set1b_clinical/set1b_clinical.json --pretty

Design:
    Topic G  Pain Assessment               TERSE         (20 CDEs, synPAN)
    Topic H  Cognitive Function Evaluation  INFORMATIONAL (20 CDEs, synCOG)
    Topic I  Sleep Quality Measurement      EXPANSIVE     (20 CDEs, synSLP)

Instrument families (shared across topics for gravity):
    SSS   Symptom Severity Scale             3 sub-scales
    FAB   Functional Assessment Battery      3 sub-scales

Injection distribution per 20-CDE topic:
    0-5   SSS sub-scale in name + temporal in question + anchor in definition
    6-11  FAB sub-scale in name + temporal in question + anchor in definition
    12-14 SSS instrument in definition only (weak gravity)
    15-16 Temporal phrase only (no instrument)
    17-19 Clean controls

Cross-domain concepts (xd1b:*) at indices 5, 10, 12, 15, 16, 17, 18.
"""

import argparse
import csv
import json
import os
import sys

# ---------------------------------------------------------------------------
# Instrument definitions
# ---------------------------------------------------------------------------

SSS_PARENT = "Symptom Severity Scale (SSS)"
SSS_SUBSCALES = {
    "PAN": "SSS Pain Interference",
    "COG": "SSS Cognitive Difficulty",
    "SLP": "SSS Sleep Disturbance",
}

FAB_PARENT = "Functional Assessment Battery (FAB)"
FAB_SUBSCALES = {
    "PAN": "FAB Physical Function",
    "COG": "FAB Daily Living Activities",
    "SLP": "FAB Emotional Well-Being",
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

TOPIC_G_PAIN = [
    # 0-5: SSS Pain Interference instrument CDEs
    (
        "Pain intensity numeric rating",
        "How would you rate your current pain level",
        "Self-reported pain severity on a zero-to-ten numeric scale.",
    ),
    (
        "Pain location body region",
        "Primary body area where pain is experienced",
        "Anatomical region identified as the principal site of pain.",
    ),
    (
        "Pain episode frequency",
        "How often pain episodes occur",
        "Count of distinct pain episodes within the assessment period.",
    ),
    (
        "Pain onset timing",
        "When did the current pain episode begin",
        "Date or interval since the onset of the present pain complaint.",
    ),
    (
        "Pain duration per episode",
        "How long each pain episode typically lasts",
        "Average duration of a single pain episode in hours or minutes.",
    ),
    # 5: SSS + xd1b:severity
    (
        "Overall symptom severity rating",
        "Global rating of symptom burden experienced by the subject",
        "Composite severity score across all reported symptoms.",
    ),
    # 6-11: FAB Physical Function instrument CDEs
    (
        "Grip strength measurement",
        "Maximum force exerted by the hand during a grip test",
        "Peak isometric grip force measured with a hand dynamometer.",
    ),
    (
        "Walking distance achieved",
        "Maximum distance walked during a timed test",
        "Total distance covered in a standardized timed walking assessment.",
    ),
    (
        "Stair climbing ability",
        "Number of stairs ascended without assistance",
        "Count of steps climbed independently during functional testing.",
    ),
    (
        "Lifting capacity assessment",
        "Maximum weight safely lifted from floor to waist height",
        "Heaviest load successfully lifted during a standardized lift test.",
    ),
    # 10: FAB + xd1b:function
    (
        "Functional impairment score",
        "Degree of limitation in daily physical activities",
        "Rating of the subject's functional limitation on a standardized scale.",
    ),
    (
        "Joint range of motion",
        "Angular excursion of the affected joint",
        "Goniometric measurement of active range of motion in degrees.",
    ),
    # 12-14: SSS definition-only CDEs
    # 12: SSS def + xd1b:medication
    (
        "Analgesic medication usage",
        "Type and dose of pain medication currently taken",
        "Record of analgesic agents administered and their dosage.",
    ),
    (
        "Pain catastrophizing score",
        "Tendency to magnify or ruminate on pain sensations",
        "Score on a questionnaire measuring negative cognitive responses to pain.",
    ),
    (
        "Pain trigger identification",
        "Activities or conditions that provoke pain episodes",
        "Classification of stimuli that reliably elicit or worsen pain.",
    ),
    # 15-16: Temporal-only CDEs
    # 15: temporal + xd1b:demographics
    (
        "Age at assessment",
        "Subject's age at the time of the clinical evaluation",
        "Chronological age of the participant at the assessment date.",
    ),
    # 16: temporal + xd1b:comorbidity
    (
        "Comorbidity count",
        "Number of concurrent medical conditions reported",
        "Total number of diagnosed comorbid conditions at the time of assessment.",
    ),
    # 17-19: Clean controls
    # 17: clean + xd1b:qol
    (
        "Quality of life impact rating",
        "Effect of pain on overall quality of life",
        "Self-rated impact of the condition on daily well-being.",
    ),
    # 18: clean + xd1b:treatment
    (
        "Treatment response classification",
        "Category of response to the current treatment regimen",
        "Classification of the subject's response to prescribed treatment.",
    ),
    # 19: clean, domain-specific
    (
        "Referred pain distribution",
        "Pattern of pain radiation from the primary site",
        "Body regions to which pain is referred from the primary source.",
    ),
]

TOPIC_H_COG = [
    # 0-5: SSS Cognitive Difficulty instrument CDEs
    (
        "Working memory span score",
        "Number of items correctly recalled in sequence",
        "The maximum number of stimulus items the subject can maintain and "
        "reproduce in correct order during a standardized working memory task. "
        "Working memory capacity predicts performance on complex cognitive "
        "operations and declines with age and neurological impairment.",
    ),
    (
        "Sustained attention duration",
        "Length of time the subject maintains focused attention on the task",
        "The continuous period during which the subject correctly detects "
        "target stimuli in a vigilance task, measured in minutes. Sustained "
        "attention is a prerequisite for higher-order cognitive processing "
        "and is sensitive to fatigue and medication effects.",
    ),
    (
        "Processing speed index",
        "Rate at which simple cognitive operations are completed",
        "The number of correct responses per unit time on a symbol-coding "
        "or pattern-matching task. Processing speed reflects the efficiency "
        "of neural transmission and is one of the earliest cognitive domains "
        "to show age-related decline.",
    ),
    (
        "Verbal fluency word count",
        "Number of words generated within a time-limited category task",
        "The total count of unique words produced by the subject within "
        "sixty seconds for a given phonemic or semantic category. Verbal "
        "fluency draws on lexical retrieval, executive search strategies, "
        "and language production networks.",
    ),
    (
        "Executive function composite rating",
        "Overall score on tests of planning, inhibition, and cognitive flexibility",
        "A composite score derived from multiple executive function subtests "
        "including trail-making, card sorting, and inhibition tasks. The "
        "composite reflects the integrity of prefrontal cortical networks "
        "that coordinate goal-directed behavior.",
    ),
    # 5: SSS + xd1b:severity
    (
        "Cognitive symptom severity level",
        "Self-reported severity of cognitive complaints",
        "The subject's rating of the overall severity of cognitive "
        "difficulties experienced during the assessment period, recorded on "
        "a standardized ordinal scale. Self-reported severity complements "
        "objective test scores and captures the subjective burden of "
        "cognitive symptoms.",
    ),
    # 6-11: FAB Daily Living Activities instrument CDEs
    (
        "Task completion time",
        "Duration required to complete a standardized functional task",
        "The elapsed time from initiation to successful completion of a "
        "defined daily-living task, measured in seconds. Prolonged task "
        "completion times indicate motor or cognitive impairment that "
        "interferes with independent functioning.",
    ),
    (
        "Instrumental activities score",
        "Performance rating on complex daily living activities",
        "A composite score reflecting the subject's ability to perform "
        "instrumental activities of daily living such as managing finances, "
        "preparing meals, using transportation, and managing medications. "
        "Lower scores indicate greater dependence on caregiver assistance.",
    ),
    (
        "Social participation frequency",
        "Number of social activities engaged in during the assessment period",
        "The count of social interactions and community activities in which "
        "the subject participates, recorded over a defined time frame. "
        "Reduced social participation is associated with cognitive decline "
        "and depressive symptoms.",
    ),
    (
        "Communication effectiveness rating",
        "Ability to convey and comprehend information in conversation",
        "A clinician-rated assessment of the subject's functional "
        "communication ability, including speech production, comprehension, "
        "and pragmatic language use. Communication effectiveness influences "
        "social participation and treatment adherence.",
    ),
    # 10: FAB + xd1b:function
    (
        "Daily functional independence level",
        "Degree of independence in performing routine daily tasks",
        "A composite rating of the subject's ability to independently "
        "perform basic and instrumental activities of daily living without "
        "assistance. Functional independence is the primary outcome measure "
        "for rehabilitation interventions and long-term care planning.",
    ),
    (
        "Problem solving accuracy",
        "Proportion of novel problems correctly solved",
        "The percentage of standardized novel reasoning problems that the "
        "subject solves correctly within the allotted time. Problem solving "
        "accuracy reflects fluid intelligence and the capacity to adapt "
        "to unfamiliar situations.",
    ),
    # 12-14: SSS definition-only CDEs
    # 12: SSS def + xd1b:medication
    (
        "Cognitive medication usage",
        "Pharmacological agents prescribed for cognitive symptoms",
        "Record of medications prescribed to manage cognitive symptoms, "
        "including cholinesterase inhibitors, memantine, and stimulant "
        "agents. Medication type and dosage are documented to assess "
        "potential effects on cognitive test performance.",
    ),
    (
        "Cognitive decline trajectory",
        "Rate and pattern of change in cognitive test scores over time",
        "The longitudinal trend in cognitive assessment scores across "
        "multiple evaluation time points, characterized as stable, gradual "
        "decline, or accelerated decline. Trajectory classification informs "
        "prognosis and treatment decisions.",
    ),
    (
        "Neuropsychological battery composite",
        "Aggregated score across a standardized battery of cognitive tests",
        "A single composite score derived by combining age-adjusted standard "
        "scores from multiple cognitive domains including memory, attention, "
        "language, visuospatial, and executive function subtests. The "
        "composite provides a global index of cognitive ability.",
    ),
    # 15-16: Temporal-only CDEs
    # 15: temporal + xd1b:demographics
    (
        "Participant age at evaluation",
        "Age of the participant at the time of cognitive testing",
        "The chronological age of the research participant at the date of "
        "the cognitive evaluation session. Age is the strongest demographic "
        "predictor of cognitive performance and is required for computing "
        "age-adjusted normative scores.",
    ),
    # 16: temporal + xd1b:comorbidity
    (
        "Concurrent medical condition count",
        "Number of active medical diagnoses at the time of evaluation",
        "The total number of active comorbid medical conditions documented "
        "in the participant's medical record at the evaluation date. "
        "Comorbidity burden affects cognitive performance through "
        "vascular, metabolic, and pharmacological pathways.",
    ),
    # 17-19: Clean controls
    # 17: clean + xd1b:qol
    (
        "Cognitive quality of life impact",
        "Effect of cognitive difficulties on daily quality of life",
        "The self-reported impact of cognitive limitations on the "
        "participant's overall quality of life, including social "
        "relationships, occupational functioning, and personal autonomy. "
        "Quality of life impact may not correlate with objective test "
        "scores due to individual differences in coping and compensation.",
    ),
    # 18: clean + xd1b:treatment
    (
        "Cognitive treatment response rating",
        "Clinical assessment of response to cognitive intervention",
        "The clinician's global impression of the participant's response "
        "to cognitive rehabilitation or pharmacological intervention, rated "
        "on a standardized scale from marked improvement to marked "
        "deterioration. Treatment response guides decisions about "
        "continuation, modification, or cessation of therapy.",
    ),
    # 19: clean, domain-specific
    (
        "Digit span forward and backward",
        "Number of digits correctly recalled in forward and reverse order",
        "The maximum sequence length of digits the subject reproduces "
        "correctly in both forward and backward conditions. Forward span "
        "assesses auditory attention and short-term memory, while backward "
        "span additionally engages working memory and mental manipulation.",
    ),
]

TOPIC_I_SLEEP = [
    # 0-5: SSS Sleep Disturbance instrument CDEs
    (
        "Sleep onset latency",
        "Time elapsed from lights-out to the onset of sleep",
        "The duration in minutes from the time the subject attempts to "
        "initiate sleep to the first epoch of polysomnographically defined "
        "sleep or the subjectively reported moment of falling asleep. "
        "Prolonged sleep onset latency is a cardinal feature of insomnia "
        "disorder and may reflect heightened cognitive or physiological "
        "arousal at bedtime. Latency greater than thirty minutes on most "
        "nights is considered clinically significant.",
    ),
    (
        "Sleep efficiency percentage",
        "Proportion of time in bed actually spent sleeping",
        "The ratio of total sleep time to total time spent in bed, expressed "
        "as a percentage. Sleep efficiency is calculated from sleep diary "
        "entries or actigraphy recordings and is a primary outcome in "
        "cognitive behavioral therapy for insomnia. Efficiency below eighty-"
        "five percent is considered indicative of sleep disturbance. "
        "Factors that reduce efficiency include prolonged latency, frequent "
        "awakenings, and early morning arousal.",
    ),
    (
        "Total sleep time",
        "Cumulative duration of sleep obtained during the sleep period",
        "The total number of minutes of sleep recorded between sleep onset "
        "and final morning awakening, excluding periods of wakefulness. "
        "Total sleep time is derived from polysomnography, actigraphy, or "
        "sleep diary and is the most commonly reported sleep duration "
        "metric. Both short sleep duration of less than six hours and long "
        "sleep duration exceeding nine hours are associated with adverse "
        "health outcomes including cardiovascular disease and mortality.",
    ),
    (
        "Number of nocturnal awakenings",
        "Count of discrete awakenings occurring during the sleep period",
        "The number of times the subject transitions from sleep to "
        "wakefulness during the nocturnal sleep period, as determined by "
        "polysomnography or self-report. Frequent awakenings fragment "
        "sleep architecture, reduce the proportion of restorative slow-wave "
        "and rapid-eye-movement sleep, and contribute to daytime fatigue "
        "and cognitive impairment. Awakening frequency is elevated in "
        "insomnia, sleep apnea, and periodic limb movement disorder.",
    ),
    (
        "Sleep stage distribution",
        "Percentage of total sleep time spent in each sleep stage",
        "The proportion of total sleep time occupied by each of the "
        "recognized sleep stages: non-rapid-eye-movement stages one, two, "
        "and three, and rapid-eye-movement sleep. Stage distribution is "
        "determined by visual or automated scoring of polysomnographic "
        "recordings according to standardized criteria. Alterations in "
        "sleep architecture, such as reduced slow-wave sleep or increased "
        "stage-one sleep, may indicate neurodegenerative disease, "
        "medication effects, or chronic sleep disruption.",
    ),
    # 5: SSS + xd1b:severity
    (
        "Sleep disturbance severity rating",
        "Overall severity of the subject's sleep complaints",
        "A global rating of the severity of sleep disturbance experienced "
        "by the subject, based on standardized self-report or clinician "
        "assessment. Severity encompasses difficulty initiating sleep, "
        "maintaining sleep, and achieving restorative sleep. The rating "
        "captures both the frequency and the impact of sleep complaints "
        "on daytime functioning and subjective well-being. Higher severity "
        "ratings are associated with greater functional impairment and "
        "increased utilization of healthcare resources.",
    ),
    # 6-11: FAB Emotional Well-Being instrument CDEs
    (
        "Daytime sleepiness score",
        "Propensity to fall asleep during normal waking activities",
        "A self-reported measure of the subject's tendency to doze or fall "
        "asleep during routine daytime situations such as reading, watching "
        "television, or sitting quietly. Excessive daytime sleepiness is "
        "quantified using standardized questionnaires that assess sleepiness "
        "across multiple situational contexts. Elevated scores indicate "
        "insufficient sleep, poor sleep quality, or underlying sleep "
        "disorders such as obstructive sleep apnea or narcolepsy.",
    ),
    (
        "Fatigue impact level",
        "Degree to which fatigue interferes with daily activities",
        "A self-reported rating of the extent to which persistent fatigue "
        "limits the subject's physical, cognitive, and social functioning. "
        "Fatigue impact is assessed using validated multi-dimensional "
        "scales that distinguish between physical exhaustion, cognitive "
        "weariness, and motivational depletion. High fatigue impact "
        "scores are common in sleep disorders, depression, and chronic "
        "medical conditions and predict reduced quality of life.",
    ),
    (
        "Napping frequency and duration",
        "Number and length of daytime sleep episodes during the recall period",
        "The count and total duration of intentional or unintentional "
        "daytime sleep episodes, reported as the number of naps and "
        "average nap duration in minutes. Napping may be compensatory "
        "for insufficient nocturnal sleep or may reflect excessive "
        "daytime sleepiness from an underlying sleep disorder. Frequent "
        "long naps can disrupt the circadian sleep-wake cycle and delay "
        "nocturnal sleep onset.",
    ),
    (
        "Bedtime regularity index",
        "Consistency of the subject's habitual bedtime across nights",
        "A measure of the variability in the subject's self-selected "
        "bedtime over the assessment period, expressed as the standard "
        "deviation of bedtime in minutes. Greater bedtime irregularity "
        "is associated with circadian misalignment, reduced sleep "
        "efficiency, and poorer academic and occupational performance. "
        "Regularity is a modifiable behavioral target in sleep "
        "hygiene interventions.",
    ),
    # 10: FAB + xd1b:function
    (
        "Sleep-related functional impairment",
        "Impact of poor sleep on the subject's daily functioning",
        "A composite measure of the degree to which sleep disturbance "
        "impairs the subject's performance in occupational, social, and "
        "domestic domains. Functional impairment is assessed through "
        "self-report questionnaires and clinician observation. Sleep-"
        "related impairment mediates the relationship between sleep "
        "disturbance and quality of life and is a key outcome in sleep "
        "medicine clinical trials.",
    ),
    (
        "Sleep environment adequacy rating",
        "Suitability of the bedroom environment for restorative sleep",
        "An assessment of the physical attributes of the sleep environment, "
        "including ambient noise level, light exposure, room temperature, "
        "mattress comfort, and bed partner disturbance. Suboptimal sleep "
        "environment is a common modifiable contributor to sleep onset "
        "difficulty and sleep fragmentation. Environmental assessment "
        "guides targeted recommendations in behavioral sleep medicine.",
    ),
    # 12-14: SSS definition-only CDEs
    # 12: SSS def + xd1b:medication
    (
        "Sleep medication usage record",
        "Prescription and over-the-counter sleep aids currently used",
        "A record of all pharmacological agents used by the subject to "
        "facilitate sleep, including prescription hypnotics, over-the-"
        "counter antihistamines, melatonin supplements, and herbal "
        "preparations. Medication type, dose, frequency, and duration "
        "of use are documented. Chronic use of certain hypnotic agents "
        "is associated with tolerance, dependence, and rebound insomnia "
        "upon discontinuation.",
    ),
    (
        "Polysomnography apnea-hypopnea index",
        "Number of apnea and hypopnea events per hour of sleep",
        "The frequency of obstructive, central, and mixed apneas and "
        "hypopneas recorded per hour of sleep during overnight "
        "polysomnography. The apnea-hypopnea index is the primary "
        "diagnostic metric for sleep-disordered breathing. Values "
        "above five events per hour indicate mild sleep apnea, above "
        "fifteen indicate moderate, and above thirty indicate severe "
        "obstructive sleep apnea requiring treatment.",
    ),
    (
        "Circadian rhythm phase marker",
        "Timing of the endogenous circadian rhythm relative to clock time",
        "The clock time of a physiological marker of the endogenous "
        "circadian pacemaker, such as the dim light melatonin onset or "
        "the core body temperature nadir. Phase markers indicate whether "
        "the individual's biological clock is advanced, delayed, or "
        "aligned with the desired sleep-wake schedule. Circadian "
        "misalignment is a feature of shift work disorder, jet lag, "
        "and delayed or advanced sleep-wake phase disorders.",
    ),
    # 15-16: Temporal-only CDEs
    # 15: temporal + xd1b:demographics
    (
        "Subject age at sleep assessment",
        "Age of the participant at the time of the sleep evaluation",
        "The chronological age of the participant at the date of the "
        "sleep assessment. Age influences sleep architecture, with "
        "progressive reductions in slow-wave sleep and increases in "
        "nocturnal wakefulness across the lifespan. Age-adjusted "
        "normative data are required for interpreting sleep study "
        "results, particularly the apnea-hypopnea index and sleep "
        "efficiency thresholds.",
    ),
    # 16: temporal + xd1b:comorbidity
    (
        "Sleep-relevant comorbidity count",
        "Number of medical conditions known to affect sleep quality",
        "The count of active comorbid conditions that have established "
        "associations with sleep disturbance, including chronic pain, "
        "depression, anxiety, heart failure, chronic obstructive "
        "pulmonary disease, and gastroesophageal reflux. The presence "
        "and number of sleep-affecting comorbidities guide the "
        "differential diagnosis of sleep complaints and influence "
        "treatment selection.",
    ),
    # 17-19: Clean controls
    # 17: clean + xd1b:qol
    (
        "Sleep-related quality of life",
        "Impact of sleep quality on the subject's overall quality of life",
        "A self-reported measure of the degree to which sleep disturbance "
        "affects the subject's perceived quality of life across physical, "
        "emotional, and social domains. Sleep-related quality of life "
        "captures the subjective consequences of poor sleep that may "
        "not be evident from objective sleep metrics alone. Higher "
        "scores indicate greater negative impact on well-being and "
        "daily satisfaction.",
    ),
    # 18: clean + xd1b:treatment
    (
        "Sleep intervention response rating",
        "Assessment of the subject's response to sleep treatment",
        "The clinician's global assessment of the subject's response to "
        "the prescribed sleep intervention, whether pharmacological, "
        "behavioral, or device-based. Response is rated on a "
        "standardized scale and considers changes in sleep onset latency, "
        "sleep efficiency, total sleep time, and daytime functioning. "
        "Responder classification informs decisions about treatment "
        "continuation, augmentation, or switching.",
    ),
    # 19: clean, domain-specific
    (
        "Restless leg symptom severity",
        "Intensity and frequency of restless leg syndrome symptoms",
        "A severity rating for the sensory and motor symptoms of "
        "restless leg syndrome, including the urge to move the legs, "
        "uncomfortable sensations in the lower extremities, symptom "
        "worsening at rest and in the evening, and relief with movement. "
        "Severity is assessed using validated rating scales and guides "
        "decisions about pharmacological treatment with dopaminergic "
        "agents or alpha-2-delta ligands.",
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
        # Family 1 (SSS): full injection
        subscale = SSS_SUBSCALES[topic_key]
        instrument = subscale
        temporal = TEMPORALS[index % 3]
        name = f"{subscale} - {name}"
        question = f"{temporal}, {question[0].lower()}{question[1:]}"
        definition = f"{definition} As part of the {SSS_PARENT}."
    elif index <= 11:
        # Family 2 (FAB): full injection
        subscale = FAB_SUBSCALES[topic_key]
        instrument = subscale
        temporal = TEMPORALS[index % 3]
        name = f"{subscale} - {name}"
        question = f"{temporal}, {question[0].lower()}{question[1:]}"
        definition = f"{definition} Based on the {FAB_PARENT}."
    elif index <= 14:
        # Family 1 definition-only (weak gravity)
        instrument = SSS_SUBSCALES[topic_key]
        definition = f"{definition} A field of the {SSS_PARENT}."
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
# CDE record builder (copied from generate_synthetic_cdes.py)
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

_MANIFEST_PAN = [
    ("Pain Intensity",     "pan"),               # 0
    ("Pain Location",      "pan"),               # 1
    ("Pain Frequency",     "pan"),               # 2
    ("Pain Timing",        "pan"),               # 3
    ("Pain Duration",      "pan"),               # 4
    ("Severity",           "xd1b:severity"),     # 5
    ("Physical Function",  "pan"),               # 6
    ("Physical Function",  "pan"),               # 7
    ("Physical Function",  "pan"),               # 8
    ("Physical Function",  "pan"),               # 9
    ("Function",           "xd1b:function"),     # 10
    ("Physical Function",  "pan"),               # 11
    ("Medication",         "xd1b:medication"),   # 12
    ("Psychological",      "pan"),               # 13
    ("Triggers",           "pan"),               # 14
    ("Demographics",       "xd1b:demographics"), # 15
    ("Comorbidity",        "xd1b:comorbidity"),  # 16
    ("Quality of Life",    "xd1b:qol"),          # 17
    ("Treatment",          "xd1b:treatment"),    # 18
    ("Pain Characteristics", "pan"),             # 19
]

_MANIFEST_COG = [
    ("Memory",             "cog"),               # 0
    ("Attention",          "cog"),               # 1
    ("Processing Speed",   "cog"),               # 2
    ("Language",           "cog"),               # 3
    ("Executive Function", "cog"),               # 4
    ("Severity",           "xd1b:severity"),     # 5
    ("Daily Function",     "cog"),               # 6
    ("Daily Function",     "cog"),               # 7
    ("Social Function",    "cog"),               # 8
    ("Communication",      "cog"),               # 9
    ("Function",           "xd1b:function"),     # 10
    ("Reasoning",          "cog"),               # 11
    ("Medication",         "xd1b:medication"),   # 12
    ("Longitudinal",       "cog"),               # 13
    ("Assessment",         "cog"),               # 14
    ("Demographics",       "xd1b:demographics"), # 15
    ("Comorbidity",        "xd1b:comorbidity"),  # 16
    ("Quality of Life",    "xd1b:qol"),          # 17
    ("Treatment",          "xd1b:treatment"),    # 18
    ("Memory Subtests",    "cog"),               # 19
]

_MANIFEST_SLP = [
    ("Sleep Initiation",   "slp"),               # 0
    ("Sleep Efficiency",   "slp"),               # 1
    ("Sleep Duration",     "slp"),               # 2
    ("Sleep Continuity",   "slp"),               # 3
    ("Sleep Architecture", "slp"),               # 4
    ("Severity",           "xd1b:severity"),     # 5
    ("Daytime Impact",     "slp"),               # 6
    ("Daytime Impact",     "slp"),               # 7
    ("Sleep Behavior",     "slp"),               # 8
    ("Sleep Behavior",     "slp"),               # 9
    ("Function",           "xd1b:function"),     # 10
    ("Sleep Environment",  "slp"),               # 11
    ("Medication",         "xd1b:medication"),   # 12
    ("Diagnostics",        "slp"),               # 13
    ("Circadian",          "slp"),               # 14
    ("Demographics",       "xd1b:demographics"), # 15
    ("Comorbidity",        "xd1b:comorbidity"),  # 16
    ("Quality of Life",    "xd1b:qol"),          # 17
    ("Treatment",          "xd1b:treatment"),    # 18
    ("Movement Disorders", "slp"),               # 19
]

_DOMAIN_LABELS = {
    "Pain Assessment":               "pain_assessment",
    "Cognitive Function Evaluation":  "cognitive_function",
    "Sleep Quality Measurement":      "sleep_quality",
}

_VERBOSITY = {
    "Pain Assessment":               "terse",
    "Cognitive Function Evaluation":  "informational",
    "Sleep Quality Measurement":      "expansive",
}

_TOPICS = [
    ("PAN", TOPIC_G_PAIN,  "Pain Assessment",              _MANIFEST_PAN),
    ("COG", TOPIC_H_COG,   "Cognitive Function Evaluation", _MANIFEST_COG),
    ("SLP", TOPIC_I_SLEEP, "Sleep Quality Measurement",     _MANIFEST_SLP),
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
    manifest_data = _MANIFEST_PAN + _MANIFEST_COG + _MANIFEST_SLP
    all_topics = (
        [("PAN", t) for t in TOPIC_G_PAIN]
        + [("COG", t) for t in TOPIC_H_COG]
        + [("SLP", t) for t in TOPIC_I_SLEEP]
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
        description="Generate Set 1B: Clinical synthetic CDEs "
                    "with embedded instruments and temporal phrases."
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
        manifest_path = os.path.join(
            out_dir or ".", "set1b_clinical_manifest.tsv"
        )
    manifest_rows = generate_manifest(records)
    write_manifest_tsv(manifest_rows, manifest_path)

    print(f"Generated {len(records)} synthetic CDEs → {args.output}")
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
