#!/usr/bin/env python3
"""
Generate Set 1A: Urban/Environmental synthetic CDEs with embedded instruments.

Produces 60 CDEs across 3 urban/environmental domains with synthetic
instrument names and temporal boilerplate phrases.  Tests "gravity"
effects — shared instruments pull semantically unrelated CDEs together
in embedding space.

Usage:
    python scripts/generate_synthetic_set1a.py -o data/synthetic_qc/set1a_urban/set1a_urban.json
    python scripts/generate_synthetic_set1a.py -o data/synthetic_qc/set1a_urban/set1a_urban.json --pretty

Design:
    Topic D  Urban Heat Island Assessment   TERSE         (20 CDEs, synUHI)
    Topic E  Stormwater Runoff Monitoring   INFORMATIONAL (20 CDEs, synSRM)
    Topic F  Indoor Air Quality Evaluation  EXPANSIVE     (20 CDEs, synIAQ)

Instrument families (shared across topics for gravity):
    ESI   Environmental Stress Index         3 sub-scales
    CRAT  Community Resilience Assessment Tool  3 sub-scales

Injection distribution per 20-CDE topic:
    0-5   ESI sub-scale in name + temporal in question + anchor in definition
    6-11  CRAT sub-scale in name + temporal in question + anchor in definition
    12-14 ESI instrument in definition only (weak gravity)
    15-16 Temporal phrase only (no instrument)
    17-19 Clean controls

Cross-domain concepts (xd1a:*) at indices 5, 10, 12, 15, 16, 17, 18.
"""

import argparse
import csv
import json
import os
import sys

# ---------------------------------------------------------------------------
# Instrument definitions
# ---------------------------------------------------------------------------

ESI_PARENT = "Environmental Stress Index (ESI)"
ESI_SUBSCALES = {
    "UHI": "ESI Heat Exposure",
    "SRM": "ESI Water Stress",
    "IAQ": "ESI Air Contamination",
}

CRAT_PARENT = "Community Resilience Assessment Tool (CRAT)"
CRAT_SUBSCALES = {
    "UHI": "CRAT Infrastructure Vulnerability",
    "SRM": "CRAT Environmental Burden",
    "IAQ": "CRAT Health Impact",
}

TEMPORALS = [
    "Over the past 30 days",
    "During the last 12 months",
    "In the past 7 days",
]

# ---------------------------------------------------------------------------
# CDE content — 20 per topic, each tuple: (name, question, definition)
# Base content WITHOUT injection; injection applied by _inject_noise()
# ---------------------------------------------------------------------------

TOPIC_D_UHI = [
    # 0-5: ESI Heat Exposure instrument CDEs
    (
        "Surface temperature anomaly",
        "Observed deviation from baseline surface temperature",
        "Difference between local surface temperature and surrounding rural baseline.",
    ),
    (
        "Heat wave intensity index",
        "Severity score for prolonged heat events",
        "Composite measure of heat wave duration and peak temperature.",
    ),
    (
        "Impervious surface fraction",
        "Proportion of land covered by sealed surfaces",
        "Percentage of land area covered by pavement, buildings, and other impervious materials.",
    ),
    (
        "Building albedo value",
        "Solar reflectivity of building exterior materials",
        "Ratio of reflected to incident solar radiation on building facades.",
    ),
    (
        "Anthropogenic heat flux",
        "Rate of heat released by human activities",
        "Thermal energy per unit area emitted by vehicles, buildings, and industry.",
    ),
    # 5: ESI + xd1a:health_impact
    (
        "Heat-related health impact score",
        "Composite health burden from elevated urban temperatures",
        "Aggregate score of heat-related hospital admissions and mortality.",
    ),
    # 6-11: CRAT instrument CDEs
    (
        "Infrastructure thermal stress rating",
        "Risk level of thermal damage to built structures",
        "Rating of cumulative heat stress on roads, bridges, and utilities.",
    ),
    (
        "Pavement surface temperature",
        "Temperature of road and sidewalk surfaces",
        "Measured temperature of asphalt or concrete pavement under solar load.",
    ),
    (
        "Green roof coverage area",
        "Extent of rooftop vegetation installations",
        "Total area of building rooftops with installed vegetated cover.",
    ),
    (
        "Urban tree canopy extent",
        "Proportion of overhead tree cover in the urban area",
        "Percentage of urban land area shaded by tree canopy.",
    ),
    # 10: CRAT + xd1a:temperature
    (
        "Surface temperature at monitoring point",
        "Ground-level temperature recorded at the station",
        "Temperature reading from a calibrated sensor at the measurement site.",
    ),
    (
        "Pedestrian thermal comfort index",
        "Perceived heat stress for outdoor pedestrians",
        "Index combining air temperature, humidity, wind, and radiation exposure.",
    ),
    # 12-14: ESI definition-only CDEs
    # 12: ESI def + xd1a:particulates
    (
        "Airborne particulate concentration",
        "Fine particle mass per unit volume of outdoor air",
        "Mass concentration of suspended particulate matter in the urban atmosphere.",
    ),
    (
        "Heat island spatial extent",
        "Geographic area exhibiting elevated temperatures",
        "Mapped area where surface temperature exceeds the regional average.",
    ),
    (
        "Microclimate zone classification",
        "Local climate type within the urban environment",
        "Assignment of sub-areas to local climate zone categories.",
    ),
    # 15-16: Temporal-only CDEs
    # 15: temporal + xd1a:coordinates
    (
        "Monitoring station coordinates",
        "Geographic position of the measurement station",
        "Latitude and longitude of the urban heat monitoring location.",
    ),
    # 16: temporal + xd1a:seasonal
    (
        "Seasonal urban heat pattern",
        "Recurring annual cycle of heat island intensity",
        "Variation in urban heat island magnitude across seasons.",
    ),
    # 17-19: Clean controls
    # 17: clean + xd1a:regulatory
    (
        "Heat threshold exceedance count",
        "Days exceeding the regulatory heat limit",
        "Number of days the temperature exceeded the regulatory action level.",
    ),
    # 18: clean + xd1a:sampling
    (
        "Thermal sampling methodology",
        "Procedure for collecting temperature measurements",
        "Standardized method for obtaining representative thermal readings.",
    ),
    # 19: clean, domain-specific
    (
        "Cool pavement adoption rate",
        "Proportion of streets using reflective paving materials",
        "Fraction of roadway area resurfaced with high-albedo pavement.",
    ),
]

TOPIC_E_SRM = [
    # 0-5: ESI Water Stress instrument CDEs
    (
        "Peak discharge volume",
        "Maximum volume of stormwater flowing from the catchment during a storm event",
        "The highest instantaneous flow volume recorded at the outfall during a "
        "single storm event, measured in cubic meters per second. Peak discharge "
        "determines channel capacity requirements and downstream flood risk.",
    ),
    (
        "Runoff coefficient",
        "Ratio of runoff to total precipitation over the catchment area",
        "The dimensionless ratio of surface runoff volume to total rainfall "
        "volume for a defined catchment. Higher coefficients indicate greater "
        "impervious coverage and reduced infiltration capacity.",
    ),
    (
        "First flush pollutant concentration",
        "Contaminant level in the initial volume of stormwater runoff",
        "The concentration of suspended solids and dissolved pollutants in the "
        "first portion of runoff, which typically carries the highest pollutant "
        "load accumulated during the antecedent dry period.",
    ),
    (
        "Total suspended solids in runoff",
        "Mass of particulate matter carried by stormwater flow",
        "The total mass of undissolved solid particles per unit volume of "
        "stormwater, measured by filtering and weighing. Suspended solids "
        "transport adsorbed pollutants and impair receiving water quality.",
    ),
    (
        "Pollutant loading rate",
        "Mass of contaminants delivered per unit time during a storm event",
        "The rate at which pollutant mass is transported by stormwater flow, "
        "expressed in kilograms per hour. Loading rates quantify the "
        "contribution of urban runoff to downstream water quality degradation.",
    ),
    # 5: ESI + xd1a:health_impact
    (
        "Runoff public health risk score",
        "Health hazard rating from contaminated stormwater exposure",
        "Composite score reflecting the likelihood of adverse health outcomes "
        "from contact with or ingestion of contaminated stormwater runoff. "
        "Integrates pathogen counts, heavy metal concentrations, and exposure duration.",
    ),
    # 6-11: CRAT Environmental Burden instrument CDEs
    (
        "Storm drain network capacity",
        "Maximum throughput of the underground stormwater conveyance system",
        "The design flow capacity of the stormwater drainage network, expressed "
        "in cubic meters per second. Capacity shortfalls lead to surface "
        "flooding during high-intensity rainfall events.",
    ),
    (
        "Impervious area ratio",
        "Fraction of the sub-catchment covered by non-permeable surfaces",
        "The proportion of the drainage area occupied by roads, rooftops, and "
        "other sealed surfaces that prevent rainfall infiltration. Higher ratios "
        "increase runoff volume and reduce groundwater recharge.",
    ),
    (
        "Green infrastructure retention volume",
        "Stormwater volume retained by bioretention and permeable features",
        "The volume of stormwater captured and held by green infrastructure "
        "elements such as bioswales, rain gardens, and permeable pavements "
        "before gradual release or infiltration into the soil.",
    ),
    (
        "Bioswale infiltration rate",
        "Rate at which stormwater percolates through the bioswale soil medium",
        "The volume of water passing through the engineered soil profile of a "
        "bioswale per unit time and area, measured in centimeters per hour. "
        "Infiltration rate determines the system's capacity to handle runoff.",
    ),
    # 10: CRAT + xd1a:temperature
    (
        "Runoff water temperature",
        "Thermal state of stormwater at the point of discharge",
        "Temperature of stormwater measured at the outfall, expressed in degrees "
        "Celsius. Elevated runoff temperatures from heated impervious surfaces "
        "can cause thermal pollution in receiving streams.",
    ),
    (
        "Curb inlet hydraulic efficiency",
        "Proportion of gutter flow captured by the curb inlet",
        "The fraction of approaching gutter flow that enters the storm drain "
        "through the curb opening. Efficiency depends on inlet geometry, gutter "
        "slope, and flow depth relative to the opening dimensions.",
    ),
    # 12-14: ESI definition-only CDEs
    # 12: ESI def + xd1a:particulates
    (
        "Suspended sediment concentration in runoff",
        "Mass of eroded soil particles carried per unit volume of stormwater",
        "The concentration of mineral sediment particles suspended in stormwater "
        "flow, reported in milligrams per liter. Sediment loading reflects "
        "upstream erosion rates and land disturbance.",
    ),
    (
        "Rainfall intensity-duration curve",
        "Relationship between rainfall rate and storm duration for design events",
        "A mathematical function describing how maximum rainfall intensity "
        "decreases as storm duration increases for a given return period. "
        "Used to size stormwater infrastructure.",
    ),
    (
        "Watershed delineation boundary",
        "Topographic boundary defining the contributing drainage area",
        "The hydrologic boundary enclosing all land area that drains to a "
        "common outlet point. Delineated from elevation data using flow "
        "accumulation algorithms.",
    ),
    # 15-16: Temporal-only CDEs
    # 15: temporal + xd1a:coordinates
    (
        "Outfall monitoring coordinates",
        "Geographic position of the stormwater discharge monitoring point",
        "Latitude and longitude of the stormwater outfall where flow and water "
        "quality measurements are collected. Coordinates enable spatial "
        "analysis of discharge impacts.",
    ),
    # 16: temporal + xd1a:seasonal
    (
        "Seasonal rainfall-runoff pattern",
        "Recurring annual cycle of stormwater generation and quality variation",
        "The characteristic seasonal pattern of stormwater volume and pollutant "
        "loading that reflects the combined influence of precipitation frequency, "
        "antecedent moisture, and vegetation cover throughout the year.",
    ),
    # 17-19: Clean controls
    # 17: clean + xd1a:regulatory
    (
        "Discharge permit compliance status",
        "Whether stormwater discharge meets regulatory permit conditions",
        "An indicator of whether monitored stormwater quality and quantity "
        "parameters satisfy the conditions specified in the discharge permit. "
        "Non-compliance triggers corrective action requirements.",
    ),
    # 18: clean + xd1a:sampling
    (
        "Stormwater sampling protocol",
        "Standardized procedure for collecting representative runoff samples",
        "The documented method for obtaining stormwater samples during a storm "
        "event, including timing, container preparation, preservation, and "
        "chain-of-custody procedures.",
    ),
    # 19: clean, domain-specific
    (
        "Combined sewer overflow frequency",
        "Number of overflow events from the combined sewer system per year",
        "The annual count of events in which the combined sewer system "
        "discharges untreated mixed stormwater and sewage to receiving waters "
        "because inflow exceeds treatment plant capacity.",
    ),
]

TOPIC_F_IAQ = [
    # 0-5: ESI Air Contamination instrument CDEs
    (
        "Indoor carbon dioxide concentration",
        "Level of CO2 measured in the occupied indoor space",
        "The concentration of carbon dioxide in the indoor air of an occupied "
        "building, measured in parts per million using a non-dispersive infrared "
        "sensor. Carbon dioxide accumulates from human respiration and "
        "combustion sources and serves as a primary indicator of ventilation "
        "adequacy. Concentrations exceeding one thousand parts per million "
        "are associated with occupant complaints of stuffiness, impaired "
        "concentration, and reduced cognitive performance.",
    ),
    (
        "Formaldehyde emission level",
        "Concentration of formaldehyde released from building materials",
        "The airborne concentration of formaldehyde in an indoor environment, "
        "reported in micrograms per cubic meter. Formaldehyde is emitted by "
        "pressed-wood products, adhesives, insulation materials, and some "
        "textiles. Chronic exposure at elevated concentrations is associated "
        "with respiratory irritation, sensitization, and is classified as a "
        "known human carcinogen by the International Agency for Research on "
        "Cancer.",
    ),
    (
        "Indoor radon activity concentration",
        "Radioactivity level from radon gas accumulated in the enclosed space",
        "The activity concentration of radon-222 in indoor air, measured in "
        "becquerels per cubic meter using continuous radon monitors or charcoal "
        "canisters. Radon enters buildings through cracks in foundations and "
        "accumulates in poorly ventilated basements. Prolonged exposure to "
        "elevated radon concentrations is the second leading cause of lung "
        "cancer after tobacco smoking, and mitigation is recommended when "
        "levels exceed the national action level.",
    ),
    (
        "Viable mold spore count",
        "Number of culturable airborne mold spores per unit volume of indoor air",
        "The concentration of viable fungal spores recovered from indoor air "
        "samples using volumetric impaction on culture media, expressed as "
        "colony-forming units per cubic meter. Elevated mold spore counts "
        "indicate moisture intrusion, inadequate ventilation, or microbial "
        "amplification on building materials. Mold exposure is associated "
        "with allergic rhinitis, asthma exacerbation, and hypersensitivity "
        "pneumonitis in susceptible occupants.",
    ),
    (
        "Indoor PM2.5 mass concentration",
        "Fine particulate matter level in the indoor air of the building",
        "The mass concentration of airborne particles with aerodynamic diameter "
        "less than 2.5 micrometers, measured in micrograms per cubic meter "
        "using a gravimetric or optical particle counter. Indoor PM2.5 "
        "originates from cooking, tobacco smoke, candle burning, and "
        "infiltration of outdoor air. Chronic exposure to elevated indoor "
        "PM2.5 is associated with cardiovascular disease, respiratory "
        "illness, and premature mortality.",
    ),
    # 5: ESI + xd1a:health_impact
    (
        "Occupant health symptom prevalence",
        "Proportion of building occupants reporting health symptoms",
        "The percentage of building occupants who report experiencing one or "
        "more health symptoms attributable to the indoor environment, including "
        "headache, eye irritation, respiratory discomfort, and fatigue. "
        "Symptom prevalence is assessed using standardized occupant surveys "
        "and serves as an indicator of overall indoor environmental quality. "
        "Elevated symptom rates may indicate inadequate ventilation, chemical "
        "off-gassing, or microbial contamination.",
    ),
    # 6-11: CRAT Health Impact instrument CDEs
    (
        "Mechanical ventilation rate",
        "Volume of outdoor air delivered to the indoor space per unit time",
        "The flow rate of outdoor air supplied to the occupied zone by the "
        "mechanical ventilation system, expressed in liters per second per "
        "person or air changes per hour. Adequate ventilation dilutes indoor "
        "pollutants generated by occupants, materials, and processes. "
        "Ventilation rates below the minimum recommended by applicable "
        "standards are associated with increased sick building syndrome "
        "symptoms and reduced occupant productivity.",
    ),
    (
        "Total volatile organic compound mixture",
        "Sum of all measured volatile organic compounds in the indoor air",
        "The aggregate concentration of volatile organic compounds detected "
        "in the indoor air, reported in micrograms per cubic meter. The total "
        "VOC metric represents the combined contribution of individual "
        "compounds emitted by paints, solvents, cleaning products, furnishings, "
        "and building materials. While no single compound may exceed its "
        "individual guideline, the total mixture may still cause sensory "
        "irritation and comfort complaints.",
    ),
    (
        "Occupant pollutant exposure duration",
        "Cumulative time the occupant is exposed to indoor contaminants",
        "The total time, expressed in hours, during which the building "
        "occupant is present in an indoor environment with measurable "
        "pollutant concentrations. Exposure duration is a key variable in "
        "dose-response models and risk assessments. Longer exposure periods "
        "at low concentrations may pose comparable health risks to shorter "
        "exposures at higher concentrations, depending on the specific "
        "pollutant and its toxicological profile.",
    ),
    (
        "Air change rate per hour",
        "Number of complete indoor air volume replacements per hour",
        "The rate at which the total volume of indoor air is replaced with "
        "outdoor or filtered air, expressed as the number of complete volume "
        "exchanges per hour. Air change rate integrates contributions from "
        "mechanical ventilation, natural ventilation through openings, and "
        "uncontrolled infiltration through the building envelope. Higher air "
        "change rates generally reduce indoor pollutant concentrations but "
        "increase energy consumption for heating or cooling.",
    ),
    # 10: CRAT + xd1a:temperature
    (
        "Indoor air temperature",
        "Dry-bulb temperature of the air inside the occupied space",
        "The temperature of the indoor air measured at occupant breathing "
        "height using a calibrated dry-bulb thermometer or thermocouple, "
        "reported in degrees Celsius. Indoor temperature is a primary "
        "determinant of thermal comfort and influences the emission rates "
        "of volatile organic compounds from building materials. Maintaining "
        "temperature within the recommended comfort range reduces occupant "
        "complaints and supports cognitive performance.",
    ),
    (
        "Relative humidity control effectiveness",
        "Ability of the HVAC system to maintain target indoor humidity levels",
        "An assessment of the building's heating, ventilation, and air "
        "conditioning system's capacity to maintain indoor relative humidity "
        "within the target range, typically forty to sixty percent. "
        "Inadequate humidity control promotes mold growth at high humidity "
        "and causes respiratory tract irritation and static electricity "
        "buildup at low humidity. Effectiveness is evaluated by comparing "
        "measured humidity profiles against the design specification.",
    ),
    # 12-14: ESI definition-only CDEs
    # 12: ESI def + xd1a:particulates
    (
        "Respirable dust concentration indoors",
        "Mass of inhalable dust particles per unit volume of indoor air",
        "The concentration of respirable particulate matter in the indoor "
        "environment, defined as particles that penetrate the unciliated "
        "airways and gas-exchange region of the lung. Measured using size-"
        "selective sampling with a cyclone or impactor at the respirable "
        "fraction cut point of four micrometers aerodynamic diameter. "
        "Sources include construction dust, carpet fibers, paper handling, "
        "and infiltration of outdoor dust through the building envelope.",
    ),
    (
        "HVAC filter particulate removal efficiency",
        "Fraction of airborne particles captured by the air handling filter",
        "The percentage of airborne particles removed from the supply airstream "
        "as it passes through the HVAC filtration system. Efficiency is "
        "characterized by the Minimum Efficiency Reporting Value rating, "
        "which ranges from 1 to 20 for progressively finer particle capture. "
        "Higher-rated filters reduce occupant exposure to particulate matter "
        "but increase system pressure drop and energy consumption.",
    ),
    (
        "Pollutant source identification category",
        "Classification of the primary indoor pollution source",
        "The categorical assignment of the dominant pollutant source in the "
        "indoor environment, such as combustion appliances, building "
        "materials, cleaning products, occupant activities, or outdoor air "
        "infiltration. Source identification guides the selection of control "
        "strategies including source removal, increased ventilation, or air "
        "purification. The assessment is based on pollutant fingerprinting "
        "and temporal correlation analysis.",
    ),
    # 15-16: Temporal-only CDEs
    # 15: temporal + xd1a:coordinates
    (
        "Indoor monitoring sensor location",
        "Position of the air quality sensor within the building",
        "The geographic coordinates and floor level of the indoor air quality "
        "monitoring sensor, recorded to enable spatial mapping of pollutant "
        "gradients within the building. Sensor placement follows guidelines "
        "specifying breathing-zone height, minimum distance from walls and "
        "windows, and avoidance of direct airflow from supply diffusers. "
        "Accurate location metadata supports reproducibility and comparison "
        "across monitoring campaigns.",
    ),
    # 16: temporal + xd1a:seasonal
    (
        "Seasonal indoor air quality variation",
        "Recurring annual cycle of indoor pollutant concentrations",
        "The characteristic seasonal pattern of indoor air pollutant levels "
        "driven by changes in ventilation behavior, outdoor air quality, "
        "and building operation mode. Indoor pollutant concentrations "
        "typically peak during winter months when reduced ventilation "
        "and increased use of heating appliances coincide with lower "
        "outdoor air exchange. Summer peaks may occur in buildings with "
        "elevated cooling loads that recirculate indoor air.",
    ),
    # 17-19: Clean controls
    # 17: clean + xd1a:regulatory
    (
        "Indoor air standard compliance",
        "Whether measured pollutant levels meet applicable indoor air guidelines",
        "An assessment of whether the measured concentrations of regulated "
        "indoor air pollutants fall within the exposure limits established "
        "by occupational health authorities or building performance standards. "
        "Compliance is evaluated against both short-term exposure limits for "
        "acute effects and long-term reference concentrations for chronic "
        "health protection. Non-compliance triggers investigation of sources, "
        "ventilation adequacy, and remediation measures.",
    ),
    # 18: clean + xd1a:sampling
    (
        "Indoor air sampling protocol",
        "Standardized method for collecting representative indoor air samples",
        "The documented procedure for obtaining indoor air samples, including "
        "the selection of sampling locations, timing relative to occupancy "
        "and HVAC operation, sample collection media, flow rates, and "
        "duration. Standardized protocols ensure comparability of results "
        "across buildings, seasons, and investigations. The protocol "
        "specifies quality assurance measures including field blanks, "
        "duplicate samples, and chain-of-custody documentation.",
    ),
    # 19: clean, domain-specific
    (
        "Building envelope airtightness",
        "Rate of uncontrolled air leakage through the building shell",
        "The air permeability of the building envelope, measured by "
        "pressurizing the building to a standard reference pressure and "
        "recording the airflow required to maintain that pressure. Results "
        "are expressed as air changes per hour at fifty pascals or as "
        "equivalent leakage area per unit envelope area. Airtightness "
        "determines the rate of uncontrolled infiltration, which affects "
        "energy consumption, moisture transport, and the ingress of "
        "outdoor pollutants.",
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
        # Family 1 (ESI): full injection
        subscale = ESI_SUBSCALES[topic_key]
        instrument = subscale
        temporal = TEMPORALS[index % 3]
        name = f"{subscale} - {name}"
        question = f"{temporal}, {question[0].lower()}{question[1:]}"
        definition = f"{definition} As part of the {ESI_PARENT}."
    elif index <= 11:
        # Family 2 (CRAT): full injection
        subscale = CRAT_SUBSCALES[topic_key]
        instrument = subscale
        temporal = TEMPORALS[index % 3]
        name = f"{subscale} - {name}"
        question = f"{temporal}, {question[0].lower()}{question[1:]}"
        definition = f"{definition} Based on the {CRAT_PARENT}."
    elif index <= 14:
        # Family 1 definition-only (weak gravity)
        instrument = ESI_SUBSCALES[topic_key]
        definition = f"{definition} A field of the {ESI_PARENT}."
    elif index <= 16:
        # Temporal phrase only
        temporal = TEMPORALS[index % 3]
        question = f"{temporal}, {question[0].lower()}{question[1:]}"
        # Append temporal clause to definition
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

_MANIFEST_UHI = [
    ("Heat Metrics",       "uhi"),               # 0
    ("Heat Metrics",       "uhi"),               # 1
    ("Land Cover",         "uhi"),               # 2
    ("Building Properties", "uhi"),              # 3
    ("Energy Balance",     "uhi"),               # 4
    ("Health Impact",      "xd1a:health_impact"), # 5
    ("Infrastructure",     "uhi"),               # 6
    ("Infrastructure",     "uhi"),               # 7
    ("Green Infrastructure", "uhi"),             # 8
    ("Vegetation",         "uhi"),               # 9
    ("Temperature",        "xd1a:temperature"),   # 10
    ("Thermal Comfort",    "uhi"),               # 11
    ("Particulates",       "xd1a:particulates"),  # 12
    ("Remote Sensing",     "uhi"),               # 13
    ("Climate Zones",      "uhi"),               # 14
    ("Monitoring",         "xd1a:coordinates"),   # 15
    ("Seasonal Patterns",  "xd1a:seasonal"),      # 16
    ("Compliance",         "xd1a:regulatory"),    # 17
    ("Sampling",           "xd1a:sampling"),      # 18
    ("Mitigation",         "uhi"),               # 19
]

_MANIFEST_SRM = [
    ("Discharge",          "srm"),               # 0
    ("Hydrology",          "srm"),               # 1
    ("Water Quality",      "srm"),               # 2
    ("Water Quality",      "srm"),               # 3
    ("Pollutant Loading",  "srm"),               # 4
    ("Health Impact",      "xd1a:health_impact"), # 5
    ("Infrastructure",     "srm"),               # 6
    ("Land Cover",         "srm"),               # 7
    ("Green Infrastructure", "srm"),             # 8
    ("Green Infrastructure", "srm"),             # 9
    ("Temperature",        "xd1a:temperature"),   # 10
    ("Infrastructure",     "srm"),               # 11
    ("Particulates",       "xd1a:particulates"),  # 12
    ("Design Storms",      "srm"),               # 13
    ("Watershed",          "srm"),               # 14
    ("Monitoring",         "xd1a:coordinates"),   # 15
    ("Seasonal Patterns",  "xd1a:seasonal"),      # 16
    ("Compliance",         "xd1a:regulatory"),    # 17
    ("Sampling",           "xd1a:sampling"),      # 18
    ("Overflow",           "srm"),               # 19
]

_MANIFEST_IAQ = [
    ("Chemical Agents",    "iaq"),               # 0
    ("Chemical Agents",    "iaq"),               # 1
    ("Radiological",       "iaq"),               # 2
    ("Biological Agents",  "iaq"),               # 3
    ("Particulates",       "iaq"),               # 4
    ("Health Impact",      "xd1a:health_impact"), # 5
    ("Ventilation",        "iaq"),               # 6
    ("Chemical Agents",    "iaq"),               # 7
    ("Exposure",           "iaq"),               # 8
    ("Ventilation",        "iaq"),               # 9
    ("Temperature",        "xd1a:temperature"),   # 10
    ("Humidity",           "iaq"),               # 11
    ("Particulates",       "xd1a:particulates"),  # 12
    ("Filtration",         "iaq"),               # 13
    ("Source Assessment",  "iaq"),               # 14
    ("Monitoring",         "xd1a:coordinates"),   # 15
    ("Seasonal Patterns",  "xd1a:seasonal"),      # 16
    ("Compliance",         "xd1a:regulatory"),    # 17
    ("Sampling",           "xd1a:sampling"),      # 18
    ("Building Envelope",  "iaq"),               # 19
]

_DOMAIN_LABELS = {
    "Urban Heat Island Assessment":   "urban_heat_island",
    "Stormwater Runoff Monitoring":   "stormwater_runoff",
    "Indoor Air Quality Evaluation":  "indoor_air_quality",
}

_VERBOSITY = {
    "Urban Heat Island Assessment":   "terse",
    "Stormwater Runoff Monitoring":   "informational",
    "Indoor Air Quality Evaluation":  "expansive",
}

_TOPICS = [
    ("UHI", TOPIC_D_UHI, "Urban Heat Island Assessment", _MANIFEST_UHI),
    ("SRM", TOPIC_E_SRM, "Stormwater Runoff Monitoring", _MANIFEST_SRM),
    ("IAQ", TOPIC_F_IAQ, "Indoor Air Quality Evaluation", _MANIFEST_IAQ),
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
    manifest_data = _MANIFEST_UHI + _MANIFEST_SRM + _MANIFEST_IAQ
    all_topics = (
        [("UHI", t) for t in TOPIC_D_UHI]
        + [("SRM", t) for t in TOPIC_E_SRM]
        + [("IAQ", t) for t in TOPIC_F_IAQ]
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

        # Determine injection site label
        if within_topic_idx <= 5:
            site = "name+question+definition"
        elif within_topic_idx <= 11:
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
        description="Generate Set 1A: Urban/Environmental synthetic CDEs "
                    "with embedded instruments and temporal phrases."
    )
    parser.add_argument("-o", "--output", required=True,
                        help="Output JSON file path")
    parser.add_argument("--pretty", action="store_true",
                        help="Pretty-print JSON (indented)")
    parser.add_argument("--manifest", default=None,
                        help="Output manifest TSV path")
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
        manifest_path = os.path.join(
            out_dir or ".", "set1a_urban_manifest.tsv"
        )
    manifest_rows = generate_manifest(records)
    write_manifest_tsv(manifest_rows, manifest_path)

    # Summary
    print(f"Generated {len(records)} synthetic CDEs → {args.output}")
    print(f"Manifest ({len(manifest_rows)} rows) → {manifest_path}")

    for prefix, topic, tag, _ in _TOPICS:
        avg_def = sum(len(d) for _, _, d in topic) / len(topic)
        avg_name = sum(len(n) for n, _, _ in topic) / len(topic)
        verbosity = _VERBOSITY[tag]
        print(f"  {tag} ({verbosity}): avg name {avg_name:.0f} chars, "
              f"avg def {avg_def:.0f} chars")

    # Instrument distribution
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

    # Cross-domain summary
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
