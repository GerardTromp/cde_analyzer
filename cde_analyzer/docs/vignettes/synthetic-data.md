# Synthetic QC Data

Controlled synthetic CDEs for testing embedding, clustering, and stripping
pipelines. The data isolates two measurable effects of instrument/boilerplate
noise on embeddings:

- **Gravity** -- shared instruments and phrases pull semantically unrelated CDEs
  together in embedding space.
- **Drift** -- instrument/temporal noise shifts a CDE's embedding away from its
  clean counterpart; terse CDEs drift more because noise is proportionally larger.

## Data sets at a glance

### Mixed-domain collection (360 CDEs)

| Set | CDEs | Generator | Topics | Purpose |
|-----|-----:|-----------|--------|---------|
| Base | 60 | `generate_synthetic_cdes.py` | Air / Water / Soil | Clean controls, cross-domain overlap |
| 1A | 60 | `generate_synthetic_set1a.py` | UHI / Stormwater / Indoor AQ | Gravity -- environmental instruments |
| 1B | 60 | `generate_synthetic_set1b.py` | Pain / Cognitive / Sleep | Gravity -- clinical instruments |
| 2 | 180 | `generate_synthetic_set2.py` | (copies of Base) | Drift -- dose-tier noise on base CDEs |

### Health-focused collection (360 CDEs)

| Set | CDEs | Generator | Topics | Purpose |
|-----|-----:|-----------|--------|---------|
| Health Base | 60 | `generate_health_base.py` | Cardiovascular / Respiratory / Metabolic | Clean controls, cross-domain overlap |
| Health Gravity A | 60 | `generate_health_gravity_a.py` | Mental Health / Musculoskeletal / GI | Gravity -- clinical instruments (PHI/COAS) |
| Health Gravity B | 60 | `generate_synthetic_set1b.py` | Pain / Cognitive / Sleep | Gravity -- clinical instruments (SSS/FAB) |
| Health Drift | 180 | `generate_health_drift.py` | (copies of Health Base) | Drift -- dose-tier noise on health base CDEs |

All output lives under `data/synthetic_qc/`.

## Base set (60 CDEs)

Three environmental domains, 20 CDEs each, no instrument or temporal noise.
Each domain uses a different verbosity tier so that noise effects can be
compared against content length:

| Domain | TinyId prefix | Verbosity | Avg definition |
|--------|--------------|-----------|----------------|
| Air Quality Monitoring | `synAIR` | terse | ~60 chars |
| Water Quality Assessment | `synWAT` | informational | ~200 chars |
| Soil Composition Analysis | `synSOL` | expansive | ~450 chars |

Seven cross-domain concept groups (`xd:pH`, `xd:temperature`,
`xd:heavy_metals`, `xd:sampling`, `xd:coordinates`, `xd:regulatory`,
`xd:seasonal`) place CDEs from different domains into the same expected
cluster, testing whether a clustering algorithm can bridge topic boundaries.

## Set 1A -- Urban/Environmental (60 CDEs)

New topics with embedded **environmental instruments** and temporal phrases.

### Topics

| Topic | TinyId prefix | Verbosity |
|-------|--------------|-----------|
| Urban Heat Island Assessment | `synUHI` | terse |
| Stormwater Runoff Monitoring | `synSRM` | informational |
| Indoor Air Quality Evaluation | `synIAQ` | expansive |

### Instrument families

**Family 1: Environmental Stress Index (ESI)** -- 3 sub-scales

- ESI Heat Exposure (UHI topic)
- ESI Water Stress (SRM topic)
- ESI Air Contamination (IAQ topic)

**Family 2: Community Resilience Assessment Tool (CRAT)** -- 3 sub-scales

- CRAT Infrastructure Vulnerability (UHI + SRM)
- CRAT Health Impact (IAQ + UHI)
- CRAT Environmental Burden (SRM + IAQ)

### Injection distribution (per 20-CDE topic)

| CDE index | Noise applied | Purpose |
|-----------|--------------|---------|
| 0--5 | ESI sub-scale in name + temporal in question + anchor in definition | Strong gravity via ESI |
| 6--11 | CRAT sub-scale in name + temporal in question + anchor in definition | Strong gravity via CRAT |
| 12--14 | ESI instrument in definition only | Weak gravity |
| 15--16 | Temporal phrase only | Temporal-only gravity |
| 17--19 | Clean -- cross-domain overlap CDEs | Controls |

**Temporal phrases** rotate: "Over the past 30 days", "During the last
12 months", "In the past 7 days".

**Cross-domain groups** (7): `xd1a:temperature`, `xd1a:particulates`,
`xd1a:coordinates`, `xd1a:regulatory`, `xd1a:seasonal`,
`xd1a:health_impact`, `xd1a:sampling`.

## Set 1B -- Clinical (60 CDEs)

Same injection structure as 1A, but with clinical topics and instruments.

### Topics

| Topic | TinyId prefix | Verbosity |
|-------|--------------|-----------|
| Pain Assessment | `synPAN` | terse |
| Cognitive Function Evaluation | `synCOG` | informational |
| Sleep Quality Measurement | `synSLP` | expansive |

### Instrument families

**Family 1: Symptom Severity Scale (SSS)** -- 3 sub-scales

- SSS Pain Interference (Pain topic)
- SSS Cognitive Difficulty (Cognitive topic)
- SSS Sleep Disturbance (Sleep topic)

**Family 2: Functional Assessment Battery (FAB)** -- 3 sub-scales

- FAB Physical Function (Pain + Cognitive)
- FAB Daily Living Activities (Sleep + Pain)
- FAB Emotional Well-Being (Cognitive + Sleep)

**Temporal phrases**: "In the past 7 days", "Over the past 2 weeks",
"During the past 4 weeks" (matching real PROMIS/PHQ patterns).

**Cross-domain groups** (7): `xd1b:severity`, `xd1b:function`,
`xd1b:medication`, `xd1b:qol`, `xd1b:demographics`, `xd1b:comorbidity`,
`xd1b:treatment`.

## Set 2 -- Noisy copies (180 CDEs)

Takes the base 60 CDEs and produces 3 dose tiers x 60 = 180 noisy variants.
The same temporal phrase ("Over the past 30 days") and the same injection
formula are applied uniformly, so the **only varying factor is source
verbosity**. This enables a clean 3x3 comparison grid.

### Instruments

- **Environmental Monitoring Protocol (EMP)** -- domain sub-scales:
  EMP Atmospheric Analysis (Air), EMP Aquatic Assessment (Water),
  EMP Pedological Survey (Soil)
- **Field Sampling Quality Assurance (FSQA)** -- used in Tier 3 only

### Noise tiers

| Tier | Suffix | Components | Expected drift |
|------|--------|------------|----------------|
| 1 (light) | `_t1` | Temporal phrase only | Minimal |
| 2 (medium) | `_t2` | Instrument name only | Moderate |
| 3 (heavy) | `_t3` | Temporal + instrument + FSQA anchor | Maximum |

### Tier injection details

**Tier 1** -- designation 2: prepend "Over the past 30 days, ..." ;
definition: append ", measured over the past 30 days."

**Tier 2** -- designation 1: prepend "EMP {sub-scale} - " ;
definition: append "A field of the Environmental Monitoring Protocol (EMP)."

**Tier 3** -- all of Tier 1 + Tier 2 + definition: append
"Based on the Field Sampling Quality Assurance (FSQA)."

### TinyId convention

`syn{DOMAIN}{NNN}_t{TIER}` -- e.g., `synAIR001_t1`, `synWAT015_t2`,
`synSOL008_t3`.

### Expected drift pattern

| Source verbosity | Tier 1 | Tier 2 | Tier 3 |
|------------------|--------|--------|--------|
| terse (Air, ~60 chars) | moderate | moderate | **maximum** |
| informational (Water, ~200 chars) | small | small | moderate |
| expansive (Soil, ~450 chars) | negligible | negligible | small |

## Health Base (60 CDEs)

Three clinical domains, 20 CDEs each, no instrument or temporal noise.
Designed for health-tuned embedding models where all topics should be
in the biomedical domain.

| Domain | TinyId prefix | Verbosity | Avg definition |
|--------|--------------|-----------|----------------|
| Cardiovascular Assessment | `synCRD` | terse | ~66 chars |
| Respiratory Function Evaluation | `synRSP` | informational | ~179 chars |
| Metabolic Health Monitoring | `synMET` | expansive | ~418 chars |

Seven cross-domain concept groups (`xdh:blood_pressure`, `xdh:lab_values`,
`xdh:bmi`, `xdh:demographics`, `xdh:medication`, `xdh:imaging`,
`xdh:treatment_response`) place CDEs from different domains into the same
expected cluster.

## Health Gravity A -- Clinical Specialties (60 CDEs)

New clinical topics with embedded **clinical instruments** and temporal phrases.
Same injection structure as Set 1A/1B.

### Topics

| Topic | TinyId prefix | Verbosity |
|-------|--------------|-----------|
| Mental Health Screening | `synMHL` | terse |
| Musculoskeletal Assessment | `synMSK` | informational |
| Gastrointestinal Health Evaluation | `synGIH` | expansive |

### Instrument families

**Family 1: Patient Health Inventory (PHI)** -- 3 sub-scales

- PHI Emotional Distress (Mental Health topic)
- PHI Physical Limitation (Musculoskeletal topic)
- PHI Digestive Function (GI topic)

**Family 2: Clinical Outcome Assessment Scale (COAS)** -- 3 sub-scales

- COAS Psychological Well-Being (Mental Health + Musculoskeletal)
- COAS Somatic Symptom Burden (GI + Mental Health)
- COAS Rehabilitation Progress (Musculoskeletal + GI)

**Temporal phrases**: "In the past 7 days", "Over the past 2 weeks",
"During the past 4 weeks" (matching real PROMIS/PHQ patterns).

**Cross-domain groups** (7): `xdha:severity`, `xdha:function`,
`xdha:medication`, `xdha:qol`, `xdha:demographics`, `xdha:comorbidity`,
`xdha:treatment`.

## Health Gravity B -- Clinical (60 CDEs)

This is the **existing Set 1B** (`set1b_clinical.json`), reused as-is.
The Pain/Cognitive/Sleep topics with SSS and FAB instruments are already
fully health/medical.  No new generator script needed -- combine with
the other health sets using `jq`.

## Health Drift -- Noisy copies (180 CDEs)

Takes the 60 Health Base CDEs and produces 3 dose tiers x 60 = 180 noisy
variants.  Same structure as Set 2 but with clinical instruments.

### Instruments

- **Clinical Monitoring Protocol (CMP)** -- domain sub-scales:
  CMP Cardiac Assessment (Cardiovascular), CMP Pulmonary Evaluation
  (Respiratory), CMP Metabolic Panel (Metabolic)
- **Health Data Quality Framework (HDQF)** -- used in Tier 3 only

### Noise tiers

| Tier | Suffix | Components | Expected drift |
|------|--------|------------|----------------|
| 1 (light) | `_t1` | Temporal phrase only | Minimal |
| 2 (medium) | `_t2` | CMP instrument name only | Moderate |
| 3 (heavy) | `_t3` | Temporal + CMP + HDQF anchor | Maximum |

### Expected drift pattern

| Source verbosity | Tier 1 | Tier 2 | Tier 3 |
|------------------|--------|--------|--------|
| terse (Cardiovascular, ~66 chars) | moderate | moderate | **maximum** |
| informational (Respiratory, ~179 chars) | small | small | moderate |
| expansive (Metabolic, ~418 chars) | negligible | negligible | small |

## Generation

### Mixed-domain collection

```bash
# Base set
python scripts/generate_synthetic_cdes.py \
    -o data/synthetic_qc/synthetic_cdes.json --pretty

# Set 1A -- Urban/Environmental
python scripts/generate_synthetic_set1a.py \
    -o data/synthetic_qc/set1a_urban/set1a_urban.json --pretty

# Set 1B -- Clinical
python scripts/generate_synthetic_set1b.py \
    -o data/synthetic_qc/set1b_clinical/set1b_clinical.json --pretty

# Set 2 -- Noisy copies (reads base JSON)
python scripts/generate_synthetic_set2.py \
    --source data/synthetic_qc/synthetic_cdes.json \
    -o data/synthetic_qc/set2_noisy/set2_noisy.json --pretty
```

### Health-focused collection

```bash
# Health Base (60 clean CDEs)
python scripts/generate_health_base.py \
    -o data/synthetic_qc/health_base/health_base.json --pretty

# Health Gravity A (60 CDEs with instruments)
python scripts/generate_health_gravity_a.py \
    -o data/synthetic_qc/health_gravity_a/health_gravity_a.json --pretty

# Health Gravity B = Set 1B (already generated above)

# Health Drift (180 noisy copies of health base)
python scripts/generate_health_drift.py \
    --source data/synthetic_qc/health_base/health_base.json \
    -o data/synthetic_qc/health_drift/health_drift.json --pretty
```

Each script also writes a manifest TSV alongside the JSON.

## Combining sets for experiments

Sets are separate files that can be combined at will.  Merge the JSON arrays
with `jq`:

### Mixed-domain combinations

```bash
# All 4 mixed sets (360 CDEs)
jq -s 'add' data/synthetic_qc/synthetic_cdes.json \
              data/synthetic_qc/set1a_urban/set1a_urban.json \
              data/synthetic_qc/set1b_clinical/set1b_clinical.json \
              data/synthetic_qc/set2_noisy/set2_noisy.json \
    > data/synthetic_qc/combined_all.json

# Base + Set 2 only (drift analysis, 240 CDEs)
jq -s 'add' data/synthetic_qc/synthetic_cdes.json \
              data/synthetic_qc/set2_noisy/set2_noisy.json \
    > data/synthetic_qc/combined_drift.json

# Set 1A + 1B only (gravity analysis, 120 CDEs)
jq -s 'add' data/synthetic_qc/set1a_urban/set1a_urban.json \
              data/synthetic_qc/set1b_clinical/set1b_clinical.json \
    > data/synthetic_qc/combined_gravity.json
```

### Health-focused combinations

```bash
# All health sets (360 CDEs)
jq -s 'add' data/synthetic_qc/health_base/health_base.json \
              data/synthetic_qc/health_gravity_a/health_gravity_a.json \
              data/synthetic_qc/set1b_clinical/set1b_clinical.json \
              data/synthetic_qc/health_drift/health_drift.json \
    > data/synthetic_qc/combined_health.json

# Health base + drift only (240 CDEs, drift analysis)
jq -s 'add' data/synthetic_qc/health_base/health_base.json \
              data/synthetic_qc/health_drift/health_drift.json \
    > data/synthetic_qc/combined_health_drift.json

# Health gravity only (120 CDEs, gravity analysis)
jq -s 'add' data/synthetic_qc/health_gravity_a/health_gravity_a.json \
              data/synthetic_qc/set1b_clinical/set1b_clinical.json \
    > data/synthetic_qc/combined_health_gravity.json
```

## Manifest columns

### Base / Set 1A / Set 1B manifests

| Column | Description |
|--------|-------------|
| `tinyId` | Unique CDE identifier |
| `domain` | Short domain label (e.g., `air_quality`) |
| `domain_full` | Full domain tag |
| `sub_domain` | Sub-domain within topic |
| `verbosity` | `terse`, `informational`, or `expansive` |
| `expected_cluster` | Ground-truth cluster label |
| `name` | CDE designation (name) |
| `instrument` | Injected instrument name (empty if clean) |
| `temporal_phrase` | Injected temporal phrase (empty if clean) |
| `injection_site` | Where noise was placed (e.g., `name+question+definition`) |

### Set 2 manifest (additional columns)

| Column | Description |
|--------|-------------|
| `noise_tier` | `light`, `medium`, or `heavy` |
| `anchor_phrase` | FSQA anchor (Tier 3 only) |
| `source_tinyId` | Base CDE this was copied from |

## Instrument name compatibility

Synthetic instrument names are designed to match the instrument extractor
regex patterns at `instrument_extractor.py`:

- `INSTRUMENT_START`: Title Case or ALL_CAPS -- ESI, CRAT, SSS, FAB, EMP, PHI, COAS, CMP
- `INSTRUMENT_WORD`: Title/ALL_CAPS/lowercase/number words
- `ACRONYM_PATTERN`: `(ESI)`, `(CRAT)`, `(PHI)`, `(COAS)`, `(CMP)`, `(HDQF)` etc. -- ALL_CAPS in parentheses
- Anchor phrases: "as part of", "based on", "a field of" -- match
  `AS_PART_OF`, `BASED_ON`, `FIELD_OF` patterns
