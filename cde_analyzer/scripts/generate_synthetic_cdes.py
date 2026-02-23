#!/usr/bin/env python3
"""
Generate synthetic CDE JSON for pipeline QC validation.

Produces 60 CDEs across 3 environmental-science domains with varying
verbosity levels.  The output conforms to the CDEItem Pydantic model and
can be processed directly through the cde-analyzer pipeline.

Usage:
    python scripts/generate_synthetic_cdes.py -o synthetic_cdes.json
    python scripts/generate_synthetic_cdes.py -o synthetic_cdes.json --pretty

Design:
    Topic A  Air Quality Monitoring     TERSE        (20 CDEs)
    Topic B  Water Quality Assessment   INFORMATIONAL (20 CDEs)
    Topic C  Soil Composition Analysis  EXPANSIVE     (20 CDEs)

    Cross-cutting concepts (present in all 3 domains):
    pH, temperature, concentration, sampling method, geographic location,
    regulatory threshold, heavy metals, seasonal variation
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

TOPIC_A_AIR = [
    # --- Core air pollutants ---
    (
        "PM2.5 concentration",
        "Measured PM2.5 level",
        "Mass of fine particulate matter per cubic meter of air.",
    ),
    (
        "PM10 concentration",
        "Measured PM10 level",
        "Mass of coarse particulate matter per cubic meter.",
    ),
    (
        "Ground-level ozone",
        "Ozone reading at surface",
        "Tropospheric ozone concentration at ground level.",
    ),
    (
        "Nitrogen dioxide level",
        "Ambient NO2 concentration",
        "Nitrogen dioxide in ambient air.",
    ),
    (
        "Sulfur dioxide level",
        "Ambient SO2 concentration",
        "Sulfur dioxide detected at the monitoring station.",
    ),
    (
        "Carbon monoxide level",
        "Ambient CO concentration",
        "Carbon monoxide in ambient air.",
    ),
    (
        "Air Quality Index",
        "Composite AQI score",
        "Aggregate index summarizing overall air quality.",
    ),
    (
        "Airborne lead concentration",
        "Lead in ambient air",
        "Lead particulate mass per cubic meter.",
    ),
    (
        "Benzene level",
        "Ambient benzene concentration",
        "Benzene vapor detected at the monitoring site.",
    ),
    (
        "VOC concentration",
        "Total volatile organics",
        "Sum of volatile organic compounds in air.",
    ),
    # --- Meteorological / context ---
    (
        "Ambient temperature",
        "Air temperature at site",
        "Temperature recorded at the monitoring station.",
    ),
    (
        "Relative humidity",
        "Humidity percentage",
        "Water vapor saturation ratio of ambient air.",
    ),
    (
        "Wind speed",
        "Wind velocity at station",
        "Horizontal wind speed at sensor height.",
    ),
    (
        "Atmospheric pressure",
        "Barometric pressure reading",
        "Station-level atmospheric pressure.",
    ),
    (
        "Visibility distance",
        "Optical visibility range",
        "Maximum distance at which objects are visible.",
    ),
    # --- Sampling and compliance ---
    (
        "Sampling frequency",
        "Measurement interval",
        "Time interval between consecutive air samples.",
    ),
    (
        "Station coordinates",
        "Geographic location of station",
        "Latitude and longitude of the air monitoring site.",
    ),
    (
        "Exceedance day count",
        "Days exceeding threshold",
        "Number of days the pollutant exceeded the regulatory limit.",
    ),
    (
        "Acidity of precipitation",
        "Rainwater pH value",
        "pH of collected precipitation samples.",
    ),
    (
        "Seasonal pollutant trend",
        "Seasonal concentration pattern",
        "Directional change in pollutant levels across seasons.",
    ),
]

TOPIC_B_WATER = [
    # --- Core water quality parameters ---
    (
        "Dissolved oxygen concentration",
        "Amount of oxygen dissolved in the water sample",
        "The concentration of molecular oxygen present in the water column, "
        "measured in milligrams per liter. Dissolved oxygen is essential for "
        "aquatic organism respiration and serves as an indicator of ecosystem health.",
    ),
    (
        "Water pH measurement",
        "Acidity or alkalinity of the water sample",
        "The hydrogen ion activity in the water expressed on a logarithmic scale "
        "from 0 to 14. Values below 7 indicate acidic conditions, values above 7 "
        "indicate alkaline conditions.",
    ),
    (
        "Turbidity of water sample",
        "Clarity of the water measured by light scattering",
        "A measure of water clarity determined by the amount of light scattered by "
        "suspended particles. Reported in nephelometric turbidity units and used to "
        "assess sediment load and treatment effectiveness.",
    ),
    (
        "Nitrate concentration in water",
        "Dissolved nitrate level in the sample",
        "The concentration of nitrate ions present in the water, typically reported "
        "in milligrams of nitrogen per liter. Elevated nitrate often indicates "
        "agricultural runoff or wastewater influence.",
    ),
    (
        "Phosphate level in water",
        "Dissolved phosphate concentration in the sample",
        "The amount of orthophosphate dissolved in the water column, measured in "
        "milligrams per liter. Excessive phosphate promotes algal blooms and "
        "contributes to eutrophication of surface waters.",
    ),
    (
        "Escherichia coli count",
        "Number of E. coli colonies per volume of water",
        "The enumeration of Escherichia coli bacteria in a water sample, expressed "
        "as colony-forming units per 100 milliliters. E. coli serves as an "
        "indicator of fecal contamination.",
    ),
    (
        "Total coliform bacteria count",
        "Total coliform colonies detected in the water sample",
        "The number of coliform bacteria per unit volume of water, used as a "
        "general indicator of sanitary quality. Includes both fecal and "
        "environmental coliform species.",
    ),
    (
        "Electrical conductivity of water",
        "Ability of the water sample to conduct an electric current",
        "A measure of the ionic content of water, reflecting the total "
        "concentration of dissolved salts. Higher conductivity indicates greater "
        "dissolved mineral content.",
    ),
    (
        "Water temperature at sampling point",
        "Temperature of the water at the time and location of collection",
        "The thermal state of the water body at the point of sample collection, "
        "measured in degrees Celsius. Temperature influences dissolved oxygen "
        "levels, chemical reaction rates, and biological activity.",
    ),
    (
        "Biochemical oxygen demand",
        "Oxygen consumed by microorganisms decomposing organic matter",
        "The amount of dissolved oxygen required by aerobic microorganisms to "
        "decompose organic material in a water sample over a standard incubation "
        "period. A key indicator of organic pollution load.",
    ),
    # --- Additional parameters ---
    (
        "Chemical oxygen demand",
        "Oxygen equivalent of chemically oxidizable matter in the sample",
        "The quantity of oxygen required to chemically oxidize organic and "
        "inorganic substances in water. Chemical oxygen demand provides a broader "
        "measure of pollution than biochemical oxygen demand alone.",
    ),
    (
        "Lead concentration in water",
        "Dissolved lead level in the water sample",
        "The mass of dissolved lead per unit volume of water, typically reported "
        "in micrograms per liter. Lead is a regulated heavy metal due to its "
        "neurotoxic effects at low concentrations.",
    ),
    (
        "Mercury level in water",
        "Dissolved mercury concentration in the sample",
        "The concentration of total mercury in the water column, measured in "
        "nanograms per liter. Mercury bioaccumulates in aquatic food webs and "
        "poses risks to both wildlife and human health.",
    ),
    (
        "Chlorophyll-a concentration",
        "Photosynthetic pigment level indicating algal abundance",
        "The concentration of chlorophyll-a extracted from filtered water samples, "
        "measured in micrograms per liter. Chlorophyll-a provides an estimate of "
        "phytoplankton biomass and trophic state.",
    ),
    (
        "Total dissolved solids",
        "Combined content of all dissolved substances in the water",
        "The total mass of dissolved inorganic and organic substances present in "
        "the water, measured in milligrams per liter. Includes minerals, salts, "
        "metals, and organic matter that pass through a standard filter.",
    ),
    # --- Sampling and compliance ---
    (
        "Water sampling method",
        "Technique used to collect the water sample",
        "The standardized procedure employed to obtain a representative water "
        "sample from the target water body. Includes grab sampling, composite "
        "sampling, and depth-integrated collection methods.",
    ),
    (
        "Sampling site geographic coordinates",
        "Latitude and longitude of the water sampling location",
        "The geographic position of the water sampling point, expressed as "
        "decimal degrees of latitude and longitude. Coordinates enable spatial "
        "analysis and comparison across monitoring networks.",
    ),
    (
        "Regulatory threshold exceedance",
        "Whether the measured parameter exceeds the applicable regulatory limit",
        "An indicator of whether the measured concentration or count exceeds the "
        "regulatory standard established for the parameter. Exceedance triggers "
        "reporting requirements and may necessitate remedial action.",
    ),
    (
        "Salinity measurement",
        "Salt content of the water expressed as practical salinity units",
        "The concentration of dissolved salts in the water sample, reported in "
        "practical salinity units or parts per thousand. Salinity affects water "
        "density, aquatic species distribution, and irrigation suitability.",
    ),
    (
        "Seasonal water quality variation",
        "Pattern of water quality change associated with seasonal cycles",
        "The recurring pattern of change in water quality parameters that "
        "corresponds to seasonal environmental cycles. Seasonal variation reflects "
        "the combined influence of temperature, precipitation, runoff, and "
        "biological activity on water chemistry.",
    ),
]

TOPIC_C_SOIL = [
    # --- Core composition parameters ---
    (
        "Soil organic matter content by weight",
        "Proportion of organic material present in the soil sample expressed "
        "as a percentage of total dry weight",
        "Soil organic matter encompasses all living and dead biological material "
        "within the soil matrix, including decomposed plant residues, animal "
        "remains, microbial biomass, and humic substances. The organic matter "
        "fraction is determined by loss-on-ignition or wet oxidation methods and "
        "reported as a percentage of oven-dried soil mass. Organic matter content "
        "governs nutrient cycling, water retention capacity, and soil structure.",
    ),
    (
        "Total nitrogen content of the soil sample",
        "Combined mass of all nitrogen forms present in the soil including "
        "organic nitrogen, ammonium, and nitrate fractions",
        "Total nitrogen represents the sum of organic nitrogen bound in humus and "
        "biological residues plus inorganic nitrogen species including ammonium "
        "and nitrate. The measurement is performed using Kjeldahl digestion or "
        "combustion analysis and reported in milligrams of nitrogen per kilogram "
        "of dry soil. Nitrogen availability is a primary determinant of plant "
        "productivity and microbial community composition.",
    ),
    (
        "Plant-available phosphorus concentration in soil",
        "Amount of phosphorus in the soil that is accessible for uptake by "
        "plant root systems under standard extraction conditions",
        "Plant-available phosphorus is the fraction of total soil phosphorus that "
        "can be extracted by standard chemical procedures such as the Olsen or "
        "Bray methods and is considered accessible for plant absorption. The "
        "concentration is reported in milligrams per kilogram and varies with soil "
        "pH, clay content, and organic matter. Phosphorus availability limits "
        "plant growth in many terrestrial ecosystems and influences fertilizer "
        "management decisions.",
    ),
    (
        "Exchangeable potassium in the soil matrix",
        "Concentration of potassium ions adsorbed onto soil particle surfaces "
        "that are available for exchange with the soil solution",
        "Exchangeable potassium refers to potassium ions held on the cation "
        "exchange sites of clay minerals and organic matter that can be displaced "
        "by other cations in the soil solution. This fraction is extracted using "
        "ammonium acetate and measured by flame photometry or atomic absorption "
        "spectroscopy. Exchangeable potassium is the primary reservoir supplying "
        "potassium to plant roots and is a key parameter in soil fertility "
        "assessment.",
    ),
    (
        "Soil pH measured in aqueous suspension",
        "Acidity or alkalinity of the soil determined by measuring the hydrogen "
        "ion activity in a standardized soil-water mixture",
        "Soil pH is measured by suspending a known mass of air-dried soil in "
        "deionized water at a standard ratio, typically one part soil to two parts "
        "water, and recording the hydrogen ion activity with a calibrated glass "
        "electrode. The pH value influences nutrient solubility, microbial "
        "activity, and the bioavailability of both essential elements and "
        "potentially toxic metals. Soil pH ranges from strongly acidic values "
        "below 4.5 to strongly alkaline values above 8.5.",
    ),
    (
        "Cation exchange capacity of the soil",
        "Total capacity of the soil to retain and exchange positively charged "
        "nutrient ions on its particle surfaces",
        "Cation exchange capacity quantifies the total negative charge available "
        "on soil colloid surfaces for adsorbing cations such as calcium, "
        "magnesium, potassium, and sodium. The measurement is performed by "
        "saturating exchange sites with a standard index cation and then "
        "displacing and quantifying it. Cation exchange capacity is expressed in "
        "centimoles of charge per kilogram and reflects the combined contribution "
        "of clay minerals and organic matter to the soil's nutrient-holding "
        "ability.",
    ),
    (
        "Soil bulk density at the sampling location",
        "Mass of oven-dried soil per unit volume of undisturbed soil collected "
        "using a core sampling device at the designated depth interval",
        "Bulk density is determined by extracting an intact cylindrical soil core "
        "of known volume, drying it at 105 degrees Celsius to constant weight, "
        "and dividing the dry mass by the core volume. The result, expressed in "
        "grams per cubic centimeter, reflects the degree of soil compaction and "
        "the proportion of pore space. Bulk density affects root penetration, "
        "water infiltration, and gas exchange within the soil profile.",
    ),
    (
        "Gravimetric soil moisture content",
        "Mass of water contained in the soil sample expressed as a proportion "
        "of the oven-dry soil mass at the time of collection",
        "Gravimetric moisture content is calculated by weighing a field-moist "
        "soil sample, drying it at 105 degrees Celsius until the mass stabilizes, "
        "and expressing the mass of water lost as a percentage of the dry soil "
        "mass. This measurement captures the water available for plant uptake and "
        "microbial processes at the moment of sampling. Moisture content varies "
        "with recent precipitation, soil texture, organic matter content, and "
        "landscape position.",
    ),
    (
        "Microbial biomass carbon in the soil",
        "Mass of carbon contained within the living microbial community of the "
        "soil sample expressed per unit dry weight of soil",
        "Microbial biomass carbon is estimated using the chloroform fumigation "
        "extraction method, in which paired fumigated and unfumigated soil "
        "subsamples are extracted with potassium sulfate and the difference in "
        "extractable organic carbon is converted to biomass carbon using an "
        "empirical factor. The result, reported in milligrams of carbon per "
        "kilogram of dry soil, provides an index of the size and metabolic "
        "potential of the soil microbial community.",
    ),
    (
        "Lead concentration in the soil sample",
        "Total mass of lead present per unit dry weight of soil as determined "
        "by acid digestion and instrumental analysis",
        "Total lead concentration is measured by digesting a dried and ground "
        "soil sample in concentrated acid, filtering the digest, and analyzing "
        "the filtrate by inductively coupled plasma mass spectrometry or atomic "
        "absorption spectroscopy. The concentration is reported in milligrams per "
        "kilogram. Lead is a persistent heavy metal contaminant whose "
        "accumulation in soil poses risks to human health through direct contact, "
        "dust inhalation, and uptake into food crops.",
    ),
    # --- Additional parameters ---
    (
        "Cadmium contamination level in the soil",
        "Total cadmium content of the soil sample measured after complete acid "
        "digestion of the dried and homogenized material",
        "Cadmium concentration in soil is determined by total acid digestion "
        "followed by instrumental quantification using inductively coupled plasma "
        "optical emission spectrometry. The result, expressed in milligrams per "
        "kilogram, reflects both natural geochemical background and anthropogenic "
        "inputs from phosphate fertilizers, sewage sludge, and industrial "
        "emissions. Cadmium is readily taken up by crops and is subject to "
        "regulatory soil screening levels due to its carcinogenic properties.",
    ),
    (
        "Soil texture classification based on particle size distribution",
        "Categorization of the soil into a textural class determined by the "
        "relative proportions of sand, silt, and clay-sized particles",
        "Soil texture classification assigns the sample to one of the standard "
        "textural classes defined by the proportions of sand, silt, and clay "
        "fractions as plotted on the soil texture triangle. Particle size "
        "fractions are determined by sieve and hydrometer analysis following "
        "organic matter removal and chemical dispersion. Texture governs water "
        "retention, drainage, aeration, and nutrient-holding capacity and is "
        "considered the most stable physical property of the soil.",
    ),
    (
        "Soil temperature profile at the sampling depth",
        "Temperature of the soil measured at the designated depth below the "
        "surface at the time of sample collection",
        "Soil temperature is recorded using a calibrated thermocouple or "
        "thermistor probe inserted to the specified sampling depth. The "
        "measurement, reported in degrees Celsius, reflects the thermal regime "
        "at that depth and influences the rates of organic matter decomposition, "
        "nutrient mineralization, seed germination, and root growth. Soil "
        "temperature varies with depth, time of day, season, vegetation cover, "
        "and soil moisture status.",
    ),
    (
        "Electrical conductivity of the soil saturation extract",
        "Ability of the soil saturation paste extract to conduct electrical "
        "current as an indicator of total soluble salt concentration",
        "Electrical conductivity is measured on a saturation paste extract "
        "prepared by adding deionized water to the soil until a glistening paste "
        "is formed, extracting the solution under vacuum, and measuring "
        "conductivity with a calibrated electrode. The result, expressed in "
        "decisiemens per meter, indicates the total concentration of soluble "
        "salts and is the primary criterion for classifying soils as saline. "
        "Elevated conductivity restricts plant water uptake through osmotic "
        "stress.",
    ),
    (
        "Depth of soil sample collection below the surface",
        "Vertical distance from the soil surface to the midpoint of the "
        "sampling interval from which the soil core or grab sample was obtained",
        "Sampling depth is recorded as the depth interval in centimeters below "
        "the mineral soil surface from which the sample was extracted. Standard "
        "depths include the surface horizon, typically zero to fifteen "
        "centimeters, and one or more subsurface horizons extending to the depth "
        "of interest. Accurate depth recording is essential for interpreting "
        "vertical gradients in chemical and biological soil properties.",
    ),
    (
        "Geographic coordinates of the soil sampling point",
        "Latitude and longitude of the exact location from which the soil "
        "sample was collected recorded using a global positioning system",
        "The geographic position of the sampling point is recorded in decimal "
        "degrees of latitude and longitude using a survey-grade or consumer-grade "
        "global positioning system receiver. Positional accuracy should be "
        "reported alongside the coordinates. Georeferenced sampling locations "
        "enable spatial interpolation, geostatistical analysis, and integration "
        "with remote sensing data for landscape-scale soil mapping.",
    ),
    (
        "Regulatory contamination threshold exceedance for the soil sample",
        "Whether the measured concentration of a regulated contaminant in the "
        "soil exceeds the applicable screening level or action level",
        "Regulatory threshold exceedance is determined by comparing the measured "
        "contaminant concentration to the screening level or maximum allowable "
        "concentration established by the governing environmental authority. "
        "Exceedance of the threshold triggers further investigation, risk "
        "assessment, and potentially remediation under applicable environmental "
        "regulations. The applicable threshold varies by jurisdiction, land use "
        "classification, and the specific contaminant.",
    ),
    (
        "Seasonal variation in soil organic matter content",
        "Pattern of change in the soil organic matter fraction that corresponds "
        "to annual cycles of plant growth, decomposition, and temperature",
        "Seasonal variation in organic matter reflects the balance between fresh "
        "organic inputs from root exudates, leaf litter, and crop residues and "
        "losses through microbial decomposition, leaching, and erosion. Organic "
        "matter content typically peaks following the main growing season when "
        "fresh residues are incorporated and declines during warm periods of "
        "accelerated decomposition. Quantifying seasonal dynamics requires "
        "repeated sampling at consistent depths and locations throughout the "
        "annual cycle.",
    ),
    (
        "Carbon-to-nitrogen ratio of the soil organic fraction",
        "Ratio of the mass of organic carbon to the mass of total nitrogen in "
        "the soil sample indicating the decomposition status of organic matter",
        "The carbon-to-nitrogen ratio is calculated by dividing the total organic "
        "carbon concentration by the total nitrogen concentration of the same "
        "soil sample. A ratio below twenty generally indicates that nitrogen "
        "mineralization exceeds immobilization, making inorganic nitrogen "
        "available to plants, while a ratio above thirty suggests net nitrogen "
        "immobilization. The ratio provides insight into the quality and "
        "decomposability of soil organic matter and guides fertilizer management.",
    ),
    (
        "Aggregate stability of the soil structure",
        "Resistance of soil aggregates to disintegration when subjected to the "
        "disruptive forces of water and mechanical stress",
        "Aggregate stability is assessed by wet-sieving a set of air-dried soil "
        "aggregates through a stack of sieves under standardized wetting and "
        "agitation conditions and expressing the mass of water-stable aggregates "
        "as a percentage of the initial sample mass. Stable aggregates protect "
        "organic matter from rapid decomposition, maintain pore continuity for "
        "water infiltration and root growth, and resist erosion. Aggregate "
        "stability integrates the effects of organic matter, clay mineralogy, "
        "biological activity, and management practices on soil physical quality.",
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
    """Generate a deterministic tinyId: e.g., synAIR001, synWAT012, synSOL020."""
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

    for i, (name, question, defn) in enumerate(TOPIC_A_AIR, start=1):
        records.append(
            _build_record(
                _make_tiny_id("AIR", i), name, question, defn,
                "Air Quality Monitoring",
            )
        )

    for i, (name, question, defn) in enumerate(TOPIC_B_WATER, start=1):
        records.append(
            _build_record(
                _make_tiny_id("WAT", i), name, question, defn,
                "Water Quality Assessment",
            )
        )

    for i, (name, question, defn) in enumerate(TOPIC_C_SOIL, start=1):
        records.append(
            _build_record(
                _make_tiny_id("SOL", i), name, question, defn,
                "Soil Composition Analysis",
            )
        )

    return records


# ---------------------------------------------------------------------------
# Manifest — domain, sub-domain, expected clustering
# ---------------------------------------------------------------------------
# Each entry: (within-topic index 0-19, sub_domain, expected_cluster)
#
# expected_cluster values:
#   "air", "water", "soil"  — domain-specific, should cluster within domain
#   "xd:pH"                 — cross-domain pH measurement
#   "xd:temperature"        — cross-domain temperature measurement
#   "xd:heavy_metals"       — cross-domain heavy metal contamination
#   "xd:coordinates"        — cross-domain geographic location
#   "xd:regulatory"         — cross-domain regulatory threshold / exceedance
#   "xd:seasonal"           — cross-domain seasonal variation
#   "xd:sampling"           — cross-domain sampling methodology

_MANIFEST_AIR = [
    # 0-9: Core pollutants
    ("Core Pollutants",    "air"),             # PM2.5
    ("Core Pollutants",    "air"),             # PM10
    ("Core Pollutants",    "air"),             # ozone
    ("Core Pollutants",    "air"),             # NO2
    ("Core Pollutants",    "air"),             # SO2
    ("Core Pollutants",    "air"),             # CO
    ("Core Pollutants",    "air"),             # AQI
    ("Heavy Metals",       "xd:heavy_metals"), # airborne lead
    ("Core Pollutants",    "air"),             # benzene
    ("Core Pollutants",    "air"),             # VOC
    # 10-14: Meteorological / context
    ("Meteorological",     "xd:temperature"),  # ambient temperature
    ("Meteorological",     "air"),             # relative humidity
    ("Meteorological",     "air"),             # wind speed
    ("Meteorological",     "air"),             # atmospheric pressure
    ("Meteorological",     "air"),             # visibility distance
    # 15-19: Sampling and compliance
    ("Sampling",           "xd:sampling"),     # sampling frequency
    ("Sampling",           "xd:coordinates"),  # station coordinates
    ("Compliance",         "xd:regulatory"),   # exceedance day count
    ("pH Measurement",     "xd:pH"),           # acidity of precipitation
    ("Seasonal Patterns",  "xd:seasonal"),     # seasonal pollutant trend
]

_MANIFEST_WATER = [
    # 0-9: Core water quality
    ("Core Parameters",    "water"),            # dissolved oxygen
    ("pH Measurement",     "xd:pH"),            # water pH
    ("Core Parameters",    "water"),            # turbidity
    ("Nutrients",          "water"),            # nitrate
    ("Nutrients",          "water"),            # phosphate
    ("Microbiology",       "water"),            # E. coli
    ("Microbiology",       "water"),            # total coliform
    ("Core Parameters",    "water"),            # conductivity
    ("Temperature",        "xd:temperature"),   # water temperature
    ("Core Parameters",    "water"),            # BOD
    # 10-14: Additional parameters
    ("Core Parameters",    "water"),            # COD
    ("Heavy Metals",       "xd:heavy_metals"),  # lead in water
    ("Heavy Metals",       "xd:heavy_metals"),  # mercury in water
    ("Core Parameters",    "water"),            # chlorophyll-a
    ("Core Parameters",    "water"),            # TDS
    # 15-19: Sampling and compliance
    ("Sampling",           "xd:sampling"),      # water sampling method
    ("Sampling",           "xd:coordinates"),   # site coordinates
    ("Compliance",         "xd:regulatory"),    # regulatory exceedance
    ("Core Parameters",    "water"),            # salinity
    ("Seasonal Patterns",  "xd:seasonal"),      # seasonal variation
]

_MANIFEST_SOIL = [
    # 0-9: Core composition
    ("Core Composition",   "soil"),             # organic matter
    ("Core Composition",   "soil"),             # total nitrogen
    ("Core Composition",   "soil"),             # available phosphorus
    ("Core Composition",   "soil"),             # exchangeable potassium
    ("pH Measurement",     "xd:pH"),            # soil pH
    ("Core Composition",   "soil"),             # CEC
    ("Physical Properties", "soil"),            # bulk density
    ("Physical Properties", "soil"),            # moisture
    ("Microbiology",       "soil"),             # microbial biomass C
    ("Heavy Metals",       "xd:heavy_metals"),  # lead in soil
    # 10-14: Additional parameters
    ("Heavy Metals",       "xd:heavy_metals"),  # cadmium in soil
    ("Physical Properties", "soil"),            # texture
    ("Temperature",        "xd:temperature"),   # soil temperature
    ("Core Composition",   "soil"),             # conductivity
    ("Sampling",           "xd:sampling"),      # sampling depth
    # 15-19: Sampling and compliance
    ("Sampling",           "xd:coordinates"),   # GPS coordinates
    ("Compliance",         "xd:regulatory"),    # regulatory threshold
    ("Seasonal Patterns",  "xd:seasonal"),      # seasonal organic matter
    ("Core Composition",   "soil"),             # C:N ratio
    ("Physical Properties", "soil"),            # aggregate stability
]

_DOMAIN_LABELS = {
    "Air Quality Monitoring":    "air_quality",
    "Water Quality Assessment":  "water_quality",
    "Soil Composition Analysis": "soil_composition",
}

_VERBOSITY = {
    "Air Quality Monitoring":    "terse",
    "Water Quality Assessment":  "informational",
    "Soil Composition Analysis": "expansive",
}


def generate_manifest(records: list) -> list[dict]:
    """Build manifest rows aligned to generate_all() output order."""
    manifest_data = _MANIFEST_AIR + _MANIFEST_WATER + _MANIFEST_SOIL
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
        description="Generate synthetic CDE JSON for pipeline QC validation."
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
        help="Output manifest TSV path (default: <output_dir>/synthetic_manifest.tsv)",
    )
    args = parser.parse_args()

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
            os.path.dirname(args.output), "synthetic_manifest.tsv"
        )
    manifest_rows = generate_manifest(records)
    write_manifest_tsv(manifest_rows, manifest_path)

    # Summary
    topic_counts = {}
    for rec in records:
        tag = rec["definitions"][0]["tags"][0]
        topic_counts[tag] = topic_counts.get(tag, 0) + 1

    print(f"Generated {len(records)} synthetic CDEs → {args.output}")
    print(f"Manifest ({len(manifest_rows)} rows) → {manifest_path}")
    for tag, count in topic_counts.items():
        print(f"  {tag}: {count} CDEs")

    # Cross-domain cluster summary
    xd_counts = {}
    for row in manifest_rows:
        cl = row["expected_cluster"]
        if cl.startswith("xd:"):
            xd_counts.setdefault(cl, []).append(row["tinyId"])
    print(f"\nCross-domain overlap: {len(xd_counts)} groups, "
          f"{sum(len(v) for v in xd_counts.values())} CDEs")
    for cl, ids in sorted(xd_counts.items()):
        print(f"  {cl}: {', '.join(ids)}")

    # Verbosity stats
    for label, topic in [
        ("Air (terse)", TOPIC_A_AIR),
        ("Water (informational)", TOPIC_B_WATER),
        ("Soil (expansive)", TOPIC_C_SOIL),
    ]:
        avg_def = sum(len(d) for _, _, d in topic) / len(topic)
        avg_name = sum(len(n) for n, _, _ in topic) / len(topic)
        print(f"  {label}: avg name {avg_name:.0f} chars, avg def {avg_def:.0f} chars")


if __name__ == "__main__":
    main()
