"""
Multi-LLM result aggregation for phrase classification.

Provides methods for reconciling classifications from multiple LLM providers
into a single aggregated result with confidence quintiles.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import Counter
import logging

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from CDE_Schema.LLM_Classification import (
    LLMResponse,
    AggregatedClassification,
    ConfidenceQuintile,
    PhraseContext,
)

logger = logging.getLogger(__name__)


class AggregationMethod(str, Enum):
    """Methods for aggregating multi-LLM results."""
    UNANIMOUS = "unanimous"  # Requires all LLMs to agree
    MAJORITY = "majority"  # Simple majority vote
    WEIGHTED_MAJORITY = "weighted_majority"  # Weighted by confidence
    CONFIDENCE_WEIGHTED = "confidence_weighted"  # Average confidence per category


# Provider reliability weights (adjustable)
DEFAULT_PROVIDER_WEIGHTS: Dict[str, float] = {
    "claude": 1.0,
    "openai": 1.0,
    "google": 1.0,
}


@dataclass
class AggregationConfig:
    """Configuration for result aggregation."""
    method: AggregationMethod = AggregationMethod.MAJORITY
    provider_weights: Dict[str, float] = None
    min_confidence_threshold: float = 0.3
    unanimous_fallback: AggregationMethod = AggregationMethod.MAJORITY

    def __post_init__(self):
        if self.provider_weights is None:
            self.provider_weights = DEFAULT_PROVIDER_WEIGHTS.copy()


class ResultAggregator:
    """
    Aggregates classification results from multiple LLM providers.

    Supports multiple aggregation strategies and computes confidence
    quintiles from the aggregated scores.
    """

    def __init__(self, config: Optional[AggregationConfig] = None):
        """
        Initialize result aggregator.

        Args:
            config: Aggregation configuration
        """
        self.config = config or AggregationConfig()

    def aggregate(
        self,
        phrase: PhraseContext,
        responses: List[LLMResponse],
        valid_categories: List[str],
    ) -> AggregatedClassification:
        """
        Aggregate multiple LLM responses into a single classification.

        Args:
            phrase: Original phrase context
            responses: List of LLMResponse from different providers
            valid_categories: List of valid category names

        Returns:
            AggregatedClassification with final result
        """
        if not responses:
            return self._create_empty_result(phrase, valid_categories)

        # Filter out error responses
        valid_responses = [r for r in responses if r.confidence > 0.0]
        if not valid_responses:
            return self._create_empty_result(phrase, valid_categories, responses)

        # Apply aggregation method
        method = self.config.method
        if method == AggregationMethod.UNANIMOUS:
            category, confidence, agreement = self._aggregate_unanimous(
                valid_responses, valid_categories
            )
        elif method == AggregationMethod.MAJORITY:
            category, confidence, agreement = self._aggregate_majority(
                valid_responses, valid_categories
            )
        elif method == AggregationMethod.WEIGHTED_MAJORITY:
            category, confidence, agreement = self._aggregate_weighted_majority(
                valid_responses, valid_categories
            )
        elif method == AggregationMethod.CONFIDENCE_WEIGHTED:
            category, confidence, agreement = self._aggregate_confidence_weighted(
                valid_responses, valid_categories
            )
        else:
            # Default to majority
            category, confidence, agreement = self._aggregate_majority(
                valid_responses, valid_categories
            )

        # Combine reasoning from all responses
        combined_reasoning = self._combine_reasoning(valid_responses)

        return AggregatedClassification(
            phrase_id=phrase.phrase_id,
            phrase_text=phrase.lemma_text,
            category=category,
            final_quintile=ConfidenceQuintile.from_confidence(confidence),
            confidence_score=confidence,
            agreement_level=agreement,
            individual_responses=responses,
            combined_reasoning=combined_reasoning,
            verbatim_forms=phrase.verbatim_forms,
            n_tinyids=phrase.n_tinyids,
        )

    def _aggregate_unanimous(
        self,
        responses: List[LLMResponse],
        valid_categories: List[str],
    ) -> Tuple[str, float, str]:
        """
        Require unanimous agreement across all providers.

        Falls back to configured method if not unanimous.
        """
        categories = [r.classification for r in responses]
        unique_categories = set(categories)

        if len(unique_categories) == 1:
            category = categories[0]
            confidence = sum(r.confidence for r in responses) / len(responses)
            return category, confidence, "unanimous"
        else:
            # Fall back to configured fallback method
            logger.debug(f"Non-unanimous result, falling back to {self.config.unanimous_fallback}")
            if self.config.unanimous_fallback == AggregationMethod.MAJORITY:
                return self._aggregate_majority(responses, valid_categories)
            else:
                return self._aggregate_confidence_weighted(responses, valid_categories)

    def _aggregate_majority(
        self,
        responses: List[LLMResponse],
        valid_categories: List[str],
    ) -> Tuple[str, float, str]:
        """
        Simple majority vote - most common category wins.
        """
        categories = [r.classification for r in responses]
        vote_counts = Counter(categories)
        winner, winner_count = vote_counts.most_common(1)[0]

        # Determine agreement level
        total_votes = len(responses)
        if winner_count == total_votes:
            agreement = "unanimous"
        elif winner_count > total_votes / 2:
            agreement = "majority"
        else:
            agreement = "split"

        # Calculate confidence as average of winning category responses
        winner_responses = [r for r in responses if r.classification == winner]
        confidence = sum(r.confidence for r in winner_responses) / len(winner_responses)

        return winner, confidence, agreement

    def _aggregate_weighted_majority(
        self,
        responses: List[LLMResponse],
        valid_categories: List[str],
    ) -> Tuple[str, float, str]:
        """
        Weighted majority vote using provider weights.
        """
        category_weights: Dict[str, float] = {cat: 0.0 for cat in valid_categories}
        category_confidences: Dict[str, List[float]] = {cat: [] for cat in valid_categories}

        for response in responses:
            provider_weight = self.config.provider_weights.get(response.provider, 1.0)
            cat = response.classification
            if cat in category_weights:
                category_weights[cat] += provider_weight
                category_confidences[cat].append(response.confidence)

        # Find winner
        winner = max(category_weights, key=category_weights.get)
        total_weight = sum(category_weights.values())
        winner_weight = category_weights[winner]

        # Determine agreement
        if winner_weight == total_weight:
            agreement = "unanimous"
        elif winner_weight > total_weight / 2:
            agreement = "majority"
        else:
            agreement = "split"

        # Calculate confidence
        if category_confidences[winner]:
            confidence = sum(category_confidences[winner]) / len(category_confidences[winner])
        else:
            confidence = 0.5

        return winner, confidence, agreement

    def _aggregate_confidence_weighted(
        self,
        responses: List[LLMResponse],
        valid_categories: List[str],
    ) -> Tuple[str, float, str]:
        """
        Weight votes by individual confidence scores.

        Higher confidence responses have more influence.
        """
        category_scores: Dict[str, float] = {cat: 0.0 for cat in valid_categories}
        category_counts: Dict[str, int] = {cat: 0 for cat in valid_categories}

        for response in responses:
            cat = response.classification
            if cat in category_scores:
                # Weight by confidence and provider weight
                provider_weight = self.config.provider_weights.get(response.provider, 1.0)
                category_scores[cat] += response.confidence * provider_weight
                category_counts[cat] += 1

        # Find winner by weighted score
        winner = max(category_scores, key=category_scores.get)
        total_score = sum(category_scores.values())

        # Calculate final confidence
        if total_score > 0:
            confidence = category_scores[winner] / total_score
        else:
            confidence = 0.5

        # Determine agreement
        winning_count = category_counts[winner]
        total_responses = len(responses)
        if winning_count == total_responses:
            agreement = "unanimous"
        elif winning_count > total_responses / 2:
            agreement = "majority"
        else:
            agreement = "split"

        return winner, confidence, agreement

    def _combine_reasoning(self, responses: List[LLMResponse]) -> str:
        """
        Combine reasoning from multiple responses.
        """
        reasons = []
        for resp in responses:
            if resp.reasoning:
                reasons.append(f"[{resp.provider}]: {resp.reasoning}")

        return " | ".join(reasons) if reasons else ""

    def _create_empty_result(
        self,
        phrase: PhraseContext,
        valid_categories: List[str],
        responses: Optional[List[LLMResponse]] = None,
    ) -> AggregatedClassification:
        """
        Create an empty/error result when no valid responses.
        """
        return AggregatedClassification(
            phrase_id=phrase.phrase_id,
            phrase_text=phrase.lemma_text,
            category=valid_categories[0] if valid_categories else "error",
            final_quintile=ConfidenceQuintile.HIGHLY_UNLIKELY,
            confidence_score=0.0,
            agreement_level="none",
            individual_responses=responses or [],
            combined_reasoning="No valid LLM responses received",
            verbatim_forms=phrase.verbatim_forms,
            n_tinyids=phrase.n_tinyids,
        )


def aggregate_batch(
    phrases: List[PhraseContext],
    provider_responses: Dict[str, List[LLMResponse]],
    valid_categories: List[str],
    config: Optional[AggregationConfig] = None,
) -> List[AggregatedClassification]:
    """
    Aggregate results for a batch of phrases from multiple providers.

    Args:
        phrases: List of phrase contexts
        provider_responses: Dict mapping provider name to list of responses
            (responses must be in same order as phrases)
        valid_categories: Valid category names
        config: Aggregation configuration

    Returns:
        List of aggregated classifications
    """
    aggregator = ResultAggregator(config)
    results = []

    # Group responses by phrase
    for i, phrase in enumerate(phrases):
        phrase_responses = []
        for provider, responses in provider_responses.items():
            if i < len(responses):
                phrase_responses.append(responses[i])

        result = aggregator.aggregate(phrase, phrase_responses, valid_categories)
        results.append(result)

    return results


def compute_quintile_distribution(
    classifications: List[AggregatedClassification],
) -> Dict[str, int]:
    """
    Compute distribution of quintiles across classifications.

    Args:
        classifications: List of aggregated classifications

    Returns:
        Dict mapping quintile name to count
    """
    distribution = {q.value: 0 for q in ConfidenceQuintile}

    for cls in classifications:
        distribution[cls.final_quintile.value] += 1

    return distribution


def compute_agreement_distribution(
    classifications: List[AggregatedClassification],
) -> Dict[str, int]:
    """
    Compute distribution of agreement levels.

    Args:
        classifications: List of aggregated classifications

    Returns:
        Dict mapping agreement level to count
    """
    distribution: Dict[str, int] = {}

    for cls in classifications:
        level = cls.agreement_level
        distribution[level] = distribution.get(level, 0) + 1

    return distribution


def compute_category_distribution(
    classifications: List[AggregatedClassification],
) -> Dict[str, int]:
    """
    Compute distribution of categories.

    Args:
        classifications: List of aggregated classifications

    Returns:
        Dict mapping category to count
    """
    distribution: Dict[str, int] = {}

    for cls in classifications:
        cat = cls.category
        distribution[cat] = distribution.get(cat, 0) + 1

    return distribution
