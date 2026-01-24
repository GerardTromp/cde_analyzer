#
# File: CDE_Schema/LLM_Classification.py
#
# Data models for LLM-based phrase classification and curation.
#

from enum import Enum
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel


class InstrumentFamily(str, Enum):
    """
    Known instrument families for automatic detection.

    Each family represents a group of related instruments, questionnaires,
    or assessment tools that share a common origin or purpose. The family_id
    enables grouping related subscales/subinstruments for analysis.
    """
    NEURO_QOL = "neuro-qol"           # Neuro-QOL subscales
    PROMIS = "promis"                  # PROMIS instruments
    MDS_UPDRS = "mds-updrs"           # Movement Disorder Society - UPDRS
    SF_HEALTH = "sf-health"            # SF-36, SF-12, Short Form Health Survey
    BECK = "beck"                      # Beck Depression/Anxiety Inventory
    PHQ = "phq"                        # Patient Health Questionnaire family
    GAD = "gad"                        # Generalized Anxiety Disorder scales
    MMSE = "mmse"                      # Mini-Mental State Examination
    MOCA = "moca"                      # Montreal Cognitive Assessment
    NIHSS = "nihss"                    # NIH Stroke Scale
    PDQUALIF = "pdqualif"             # Parkinson's Disease Quality of Life
    DSQ = "dsq"                        # DePaul Symptom Questionnaire
    ROME = "rome"                      # Rome criteria modules
    OTHER = "other"                    # Known instrument, family not determined
    UNKNOWN = "unknown"               # Could not determine if instrument

    @classmethod
    def get_display_name(cls, family_id: str) -> str:
        """Get human-readable display name for a family_id."""
        display_names = {
            "neuro-qol": "Neuro-QOL",
            "promis": "PROMIS",
            "mds-updrs": "MDS-UPDRS",
            "sf-health": "SF Health Survey",
            "beck": "Beck Inventory",
            "phq": "PHQ",
            "gad": "GAD",
            "mmse": "MMSE",
            "moca": "MoCA",
            "nihss": "NIHSS",
            "pdqualif": "PDQUALIF",
            "dsq": "DSQ",
            "rome": "Rome Criteria",
            "other": "Other Instrument",
            "unknown": "Unknown",
        }
        return display_names.get(family_id, family_id.upper())


@dataclass
class InstrumentIdentification:
    """
    Two-tier instrument identification with family grouping.

    Enables grouping related instruments (e.g., all Neuro-QOL subscales)
    while retaining specific subscale/subinstrument identity. This supports:
    - Family-level analysis and substitution testing
    - Subscale-specific tracking
    - Confidence-based curation workflows
    """
    family_id: str                     # e.g., "neuro-qol"
    family_display_name: str           # e.g., "Neuro-QOL" (for substitution)
    instrument_id: str                 # e.g., "neuro-qol-ability-participate-sra"
    canonical_name: str                # Full instrument name
    family_confidence: float           # 0.0-1.0 confidence in family assignment
    identification_method: str         # "pattern", "llm", "manual"
    needs_review: bool = False         # True if confidence < threshold


class ConfidenceQuintile(str, Enum):
    """
    Classification confidence levels using quintile system.

    Maps confidence scores (0.0-1.0) to discrete categories:
    - highly_likely:   81-100% (0.81-1.00)
    - likely:          61-80%  (0.61-0.80)
    - indeterminate:   41-60%  (0.41-0.60)
    - unlikely:        21-40%  (0.21-0.40)
    - highly_unlikely: 0-20%   (0.00-0.20)
    """
    HIGHLY_LIKELY = "highly_likely"
    LIKELY = "likely"
    INDETERMINATE = "indeterminate"
    UNLIKELY = "unlikely"
    HIGHLY_UNLIKELY = "highly_unlikely"

    @classmethod
    def from_confidence(cls, confidence: float) -> "ConfidenceQuintile":
        """Map a 0.0-1.0 confidence score to a quintile."""
        if confidence > 0.8:
            return cls.HIGHLY_LIKELY
        elif confidence > 0.6:
            return cls.LIKELY
        elif confidence > 0.4:
            return cls.INDETERMINATE
        elif confidence > 0.2:
            return cls.UNLIKELY
        else:
            return cls.HIGHLY_UNLIKELY


@dataclass
class LLMResponse:
    """
    Single LLM provider response for a phrase classification.

    Captures the raw response from one provider for later aggregation.
    """
    provider: str                         # "claude", "openai", "google"
    model_id: str                         # Specific model version
    classification: str                   # Category classification
    confidence: float                     # 0.0-1.0 confidence score
    quintile: ConfidenceQuintile          # Derived quintile
    reasoning: str                        # LLM explanation for classification
    raw_response: Optional[str] = None    # Full response for debugging
    latency_ms: Optional[int] = None      # Response time in milliseconds
    tokens_used: Optional[int] = None     # Tokens consumed


@dataclass
class FieldContext:
    """
    Context around a phrase occurrence in a CDE field.

    Captures the surrounding text to provide context for LLM classification.
    """
    tinyId: str                           # CDE document identifier
    field_path: str                       # e.g., "definitions[0].definition"
    full_text: str                        # Complete field text
    phrase_start: int                     # Character offset where phrase starts
    phrase_end: int                       # Character offset where phrase ends
    surrounding_text: Optional[str] = None  # Window around phrase (if truncated)

    @property
    def text(self) -> str:
        """Extract the phrase text from full_text using offsets."""
        return self.full_text[self.phrase_start:self.phrase_end]

    @property
    def before_text(self) -> str:
        """Text before the phrase."""
        return self.full_text[:self.phrase_start]

    @property
    def after_text(self) -> str:
        """Text after the phrase."""
        return self.full_text[self.phrase_end:]


@dataclass
class PhraseContext:
    """
    Full context for a phrase to send to LLM for classification.

    Aggregates all information about a phrase needed for LLM queries:
    - The phrase itself (lemmatized and verbatim forms)
    - Where it appears (field contexts)
    - Frequency statistics
    """
    phrase_id: str                        # e.g., "phrase_00001"
    lemma_text: str                       # Lemmatized/normalized phrase
    verbatim_forms: List[str]             # All observed surface forms
    field_contexts: List[FieldContext]    # Sample contexts where phrase appears
    frequency: int                        # Total occurrence count
    n_tinyids: int                        # Number of distinct CDE documents
    k: Optional[int] = None               # Original k-mer length (if applicable)
    extension_method: Optional[str] = None  # "kmer", "debruijn", or "anchor"


@dataclass
class AggregatedClassification:
    """
    Reconciled classification from multiple LLMs.

    Combines responses from all queried providers into a single
    classification with agreement metadata.
    """
    phrase_id: str
    phrase_text: str                      # Lemmatized phrase text
    category: str                         # Final assigned category
    final_quintile: ConfidenceQuintile    # Aggregated confidence quintile
    confidence_score: float               # Aggregated confidence (0.0-1.0)
    agreement_level: str                  # "unanimous", "majority", "split"
    individual_responses: List[LLMResponse]  # Per-provider responses
    verbatim_forms: List[str]             # All verbatim variants
    n_tinyids: int                        # Document count
    combined_reasoning: str = ""          # Combined reasoning from all LLMs
    sample_contexts: List[str] = field(default_factory=list)  # Example contexts


@dataclass
class QueryModuleConfig:
    """
    Configuration for a query module.

    Defines parameters for running a specific classification module.
    """
    module_name: str                      # e.g., "instrument", "temporal"
    reference_file: Optional[str] = None  # Known examples list (e.g., instruments)
    output_categories: List[str] = field(default_factory=list)  # Valid categories
    batch_size: int = 20                  # Phrases per LLM request
    max_context_chars: int = 500          # Context window size per occurrence
    max_contexts_per_phrase: int = 3      # Number of example contexts to include


class ClassificationResult(BaseModel):
    """
    Pydantic model for classification output serialization.

    Used for JSON/TSV output of classification results.
    """
    phrase_id: str
    phrase_text: str
    category: str
    quintile: str
    confidence: float
    agreement: str
    llm_votes: str                        # "claude:category,openai:category,..."
    reasoning: str
    verbatim_forms: str                   # Pipe-separated variants
    n_tinyids: int
    sample_contexts: Optional[str] = None  # Pipe-separated sample contexts


class RunStatistics(BaseModel):
    """
    Statistics for a classification run.

    Captured in llm_run_log.json for tracking and debugging.
    """
    run_id: str
    timestamp: str                        # ISO8601 timestamp
    module: str                           # Query module used
    providers: List[str]                  # LLM providers used
    aggregation_method: str               # How results were combined
    phrases_processed: int
    total_api_calls: int
    tokens_used: Dict[str, int]           # Per-provider token usage
    processing_time_seconds: float
    quintile_distribution: Dict[str, int]  # Count per quintile
    category_distribution: Dict[str, int]  # Count per category
    error_count: int = 0
    errors: List[str] = []
