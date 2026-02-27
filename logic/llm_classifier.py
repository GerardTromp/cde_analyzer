"""
Core orchestration logic for LLM-based phrase classification.

Coordinates loading phrase_miner output, building phrase contexts,
querying multiple LLM providers in parallel, and aggregating results.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
import json
import csv

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from CDE_Schema.LLM_Classification import (
    PhraseContext,
    FieldContext,
    LLMResponse,
    AggregatedClassification,
    ClassificationResult,
    RunStatistics,
    ConfidenceQuintile,
)

from utils.llm import (
    LLMConfig,
    resolve_config,
    create_providers,
    validate_providers,
    LLMProvider,
)

from utils.llm.result_aggregator import (
    ResultAggregator,
    AggregationConfig,
    AggregationMethod,
    compute_quintile_distribution,
    compute_category_distribution,
    compute_agreement_distribution,
)

from utils.query_modules import get_module, QueryModule

logger = logging.getLogger(__name__)


class LLMClassifier:
    """
    Orchestrates LLM-based classification of phrase_miner output.

    Workflow:
    1. Load phrases from phrase_miner output files
    2. Build PhraseContext objects with field contexts
    3. Query multiple LLM providers in parallel
    4. Aggregate results using configured method
    5. Write output files
    """

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        module_name: str,
        providers: List[str],
        llm_config: LLMConfig,
        aggregation_method: str = "majority",
        batch_size: int = 20,
        min_frequency: int = 1,
        context_window: int = 200,
        reference_file: Optional[Path] = None,
        original_cdes: Optional[Path] = None,
    ):
        """
        Initialize classifier.

        Args:
            input_dir: Directory with phrase_miner output files
            output_dir: Directory for classification output
            module_name: Query module to use (e.g., "instrument")
            providers: List of LLM provider names
            llm_config: Resolved LLM configuration with API keys
            aggregation_method: How to combine multi-LLM results
            batch_size: Phrases per batch for LLM calls
            min_frequency: Minimum phrase frequency to process
            context_window: Characters of context around phrase
            reference_file: Optional reference data for module
            original_cdes: Optional path to original CDE JSON for contexts
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.module_name = module_name
        self.provider_names = providers
        self.llm_config = llm_config
        self.batch_size = batch_size
        self.min_frequency = min_frequency
        self.context_window = context_window
        self.reference_file = reference_file
        self.original_cdes = original_cdes

        # Initialize aggregation
        try:
            agg_method = AggregationMethod(aggregation_method)
        except ValueError:
            agg_method = AggregationMethod.MAJORITY
        self.aggregation_config = AggregationConfig(method=agg_method)

        # Will be initialized during run
        self._module: Optional[QueryModule] = None
        self._providers: List[LLMProvider] = []
        self._phrases: List[PhraseContext] = []
        self._results: List[AggregatedClassification] = []

        # Statistics
        self._run_id = str(uuid.uuid4())[:8]
        self._start_time: Optional[datetime] = None
        self._total_tokens: Dict[str, int] = {}
        self._api_calls = 0
        self._errors: List[str] = []

    async def run(self) -> List[AggregatedClassification]:
        """
        Execute the full classification pipeline.

        Returns:
            List of aggregated classifications
        """
        self._start_time = datetime.now()
        logger.info(f"Starting classification run {self._run_id}")

        # Step 1: Initialize query module
        logger.info(f"Loading query module: {self.module_name}")
        self._module = get_module(
            self.module_name,
            reference_file=self.reference_file,
        )

        # Step 2: Create and validate LLM providers
        logger.info(f"Initializing providers: {self.provider_names}")
        self._providers = await create_providers(self.llm_config)

        if not self._providers:
            raise RuntimeError("No valid LLM providers available")

        logger.info(f"Active providers: {[p.provider_name for p in self._providers]}")

        # Step 3: Load phrases from phrase_miner output
        logger.info(f"Loading phrases from {self.input_dir}")
        self._phrases = self._load_phrases()

        if not self._phrases:
            logger.warning("No phrases to classify")
            return []

        logger.info(f"Loaded {len(self._phrases)} phrases for classification")

        # Step 4: Process phrases in batches
        self._results = await self._process_all_phrases()

        # Step 5: Write output files
        self._write_outputs()

        logger.info(f"Classification complete: {len(self._results)} phrases processed")
        return self._results

    def _load_phrases(self) -> List[PhraseContext]:
        """
        Load phrases from phrase_miner output files.

        Expected files:
        - phrases.tsv: phrase_id, phrase_text, frequency, n_tinyids, ...
        - verbatim_phrases.tsv: phrase_id, verbatim_form
        - occurrences.tsv: phrase_id, tinyId, field_path, ...

        Returns:
            List of PhraseContext objects
        """
        phrases_file = self.input_dir / "phrases.tsv"
        verbatim_file = self.input_dir / "verbatim_phrases.tsv"
        occurrences_file = self.input_dir / "occurrences.tsv"

        if not phrases_file.exists():
            raise FileNotFoundError(f"Phrases file not found: {phrases_file}")

        # Load main phrases
        phrases_data: Dict[str, Dict[str, Any]] = {}
        with open(phrases_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                phrase_id = row.get("phrase_id", "")
                frequency = int(row.get("frequency", row.get("count", 0)))

                # Apply minimum frequency filter
                if frequency < self.min_frequency:
                    continue

                phrases_data[phrase_id] = {
                    "phrase_id": phrase_id,
                    "lemma_text": row.get("phrase_text", row.get("phrase", "")),
                    "frequency": frequency,
                    "n_tinyids": int(row.get("n_tinyids", row.get("n_documents", 0))),
                    "k": int(row.get("k", 0)) if row.get("k") else None,
                    "verbatim_forms": [],
                    "field_contexts": [],
                }

        # Load verbatim forms
        if verbatim_file.exists():
            with open(verbatim_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    phrase_id = row.get("phrase_id", "")
                    verbatim = row.get("verbatim_form", row.get("verbatim", ""))
                    if phrase_id in phrases_data and verbatim:
                        phrases_data[phrase_id]["verbatim_forms"].append(verbatim)

        # Load occurrence contexts (sample)
        if occurrences_file.exists():
            with open(occurrences_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    phrase_id = row.get("phrase_id", "")
                    if phrase_id not in phrases_data:
                        continue

                    # Limit contexts per phrase
                    if len(phrases_data[phrase_id]["field_contexts"]) >= 5:
                        continue

                    context = FieldContext(
                        tinyId=row.get("tinyId", row.get("tiny_id", "")),
                        field_path=row.get("field_path", row.get("path", "")),
                        full_text=row.get("full_text", row.get("context", ""))[:self.context_window * 2],
                        phrase_start=int(row.get("phrase_start", row.get("start", 0))),
                        phrase_end=int(row.get("phrase_end", row.get("end", 0))),
                    )
                    phrases_data[phrase_id]["field_contexts"].append(context)

        # Convert to PhraseContext objects
        phrases = []
        for data in phrases_data.values():
            phrases.append(PhraseContext(
                phrase_id=data["phrase_id"],
                lemma_text=data["lemma_text"],
                verbatim_forms=data["verbatim_forms"],
                field_contexts=data["field_contexts"],
                frequency=data["frequency"],
                n_tinyids=data["n_tinyids"],
                k=data["k"],
            ))

        # Sort by frequency (most frequent first)
        phrases.sort(key=lambda p: p.frequency, reverse=True)
        return phrases

    async def _process_all_phrases(self) -> List[AggregatedClassification]:
        """
        Process all phrases through LLM providers.

        Returns:
            List of aggregated classifications
        """
        aggregator = ResultAggregator(self.aggregation_config)
        results = []

        # Build prompts from module
        system_prompt = self._module.build_system_prompt()
        user_template = self._module.build_user_prompt_template()
        categories = self._module.output_categories
        reference_examples = self._module.get_reference_examples()

        # Process in batches
        total_batches = (len(self._phrases) + self.batch_size - 1) // self.batch_size

        for batch_idx in range(total_batches):
            start = batch_idx * self.batch_size
            end = min(start + self.batch_size, len(self._phrases))
            batch = self._phrases[start:end]

            logger.info(f"Processing batch {batch_idx + 1}/{total_batches} ({len(batch)} phrases)")

            # Query all providers in parallel
            provider_responses: Dict[str, List[LLMResponse]] = {}

            async def query_provider(provider: LLMProvider):
                try:
                    responses = await provider.classify_batch(
                        phrases=batch,
                        system_prompt=system_prompt,
                        user_prompt_template=user_template,
                        categories=categories,
                        reference_examples=reference_examples,
                    )
                    self._api_calls += len(batch)

                    # Track tokens
                    for resp in responses:
                        if resp.tokens_used:
                            self._total_tokens[provider.provider_name] = (
                                self._total_tokens.get(provider.provider_name, 0) +
                                resp.tokens_used
                            )

                    return provider.provider_name, responses
                except Exception as e:
                    logger.error(f"Provider {provider.provider_name} failed: {e}")
                    self._errors.append(f"{provider.provider_name}: {str(e)}")
                    return provider.provider_name, []

            # Execute providers in parallel
            tasks = [query_provider(p) for p in self._providers]
            provider_results = await asyncio.gather(*tasks)

            for provider_name, responses in provider_results:
                if responses:
                    provider_responses[provider_name] = responses

            # Aggregate results for each phrase in batch
            for i, phrase in enumerate(batch):
                phrase_responses = []
                for provider_name, responses in provider_responses.items():
                    if i < len(responses):
                        phrase_responses.append(responses[i])

                if phrase_responses:
                    result = aggregator.aggregate(phrase, phrase_responses, categories)
                    results.append(result)
                else:
                    # Create error result if no responses
                    results.append(AggregatedClassification(
                        phrase_id=phrase.phrase_id,
                        phrase_text=phrase.lemma_text,
                        category=categories[0] if categories else "error",
                        final_quintile=ConfidenceQuintile.HIGHLY_UNLIKELY,
                        confidence_score=0.0,
                        agreement_level="none",
                        individual_responses=[],
                        verbatim_forms=phrase.verbatim_forms,
                        n_tinyids=phrase.n_tinyids,
                        combined_reasoning="No LLM responses received",
                    ))

        return results

    def _write_outputs(self):
        """Write classification results and run log."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Write classified phrases TSV
        output_file = self.output_dir / f"classified_{self.module_name}.tsv"
        self._write_classification_tsv(output_file)

        # Write run log JSON
        log_file = self.output_dir / "llm_run_log.json"
        self._write_run_log(log_file)

        logger.info(f"Output written to {self.output_dir}")

    def _write_classification_tsv(self, output_file: Path):
        """Write classification results as TSV."""
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter="\t")

            # Header
            writer.writerow([
                "phrase_id",
                "phrase_text",
                "category",
                "quintile",
                "confidence",
                "agreement",
                "llm_votes",
                "reasoning",
                "verbatim_forms",
                "n_tinyids",
            ])

            # Data rows
            for result in self._results:
                # Format LLM votes
                votes = ",".join(
                    f"{r.provider}:{r.classification}"
                    for r in result.individual_responses
                )

                writer.writerow([
                    result.phrase_id,
                    result.phrase_text,
                    result.category,
                    result.final_quintile.value,
                    f"{result.confidence_score:.3f}",
                    result.agreement_level,
                    votes,
                    result.combined_reasoning[:500] if result.combined_reasoning else "",
                    "|".join(result.verbatim_forms[:10]),
                    result.n_tinyids,
                ])

    def _write_run_log(self, log_file: Path):
        """Write run statistics as JSON."""
        end_time = datetime.now()
        duration = (end_time - self._start_time).total_seconds() if self._start_time else 0

        stats = RunStatistics(
            run_id=self._run_id,
            timestamp=self._start_time.isoformat() if self._start_time else "",
            module=self.module_name,
            providers=[p.provider_name for p in self._providers],
            aggregation_method=self.aggregation_config.method.value,
            phrases_processed=len(self._results),
            total_api_calls=self._api_calls,
            tokens_used=self._total_tokens,
            processing_time_seconds=duration,
            quintile_distribution=compute_quintile_distribution(self._results),
            category_distribution=compute_category_distribution(self._results),
            error_count=len(self._errors),
            errors=self._errors[:50],  # Limit errors in log
        )

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(stats.model_dump(), f, indent=2)

    def get_results(self) -> List[AggregatedClassification]:
        """Get classification results."""
        return self._results

    def get_statistics(self) -> Dict[str, Any]:
        """Get run statistics."""
        return {
            "run_id": self._run_id,
            "phrases_processed": len(self._results),
            "api_calls": self._api_calls,
            "tokens_used": self._total_tokens,
            "errors": len(self._errors),
            "quintile_distribution": compute_quintile_distribution(self._results),
            "category_distribution": compute_category_distribution(self._results),
        }


async def run_classification(
    input_dir: Path,
    output_dir: Path,
    module_name: str,
    providers: List[str],
    config_file: Optional[Path] = None,
    api_keys: Optional[List[str]] = None,
    aggregation_method: str = "majority",
    batch_size: int = 20,
    min_frequency: int = 1,
    context_window: int = 200,
    reference_file: Optional[Path] = None,
    original_cdes: Optional[Path] = None,
    validate_keys: bool = True,
) -> Tuple[List[AggregatedClassification], Dict[str, Any]]:
    """
    Convenience function to run classification pipeline.

    Args:
        input_dir: Directory with phrase_miner output
        output_dir: Directory for classification output
        module_name: Query module to use
        providers: List of provider names
        config_file: Optional LLM config file path
        api_keys: Optional CLI API keys (format: "provider:key")
        aggregation_method: How to aggregate multi-LLM results
        batch_size: Phrases per batch
        min_frequency: Minimum phrase frequency
        context_window: Context characters around phrase
        reference_file: Optional reference data file
        original_cdes: Optional original CDE JSON
        validate_keys: Whether to validate API keys

    Returns:
        Tuple of (classifications, statistics)
    """
    # Resolve configuration
    llm_config = resolve_config(
        requested_providers=providers,
        config_file_path=config_file,
        cli_api_keys=api_keys,
    )

    # Create classifier
    classifier = LLMClassifier(
        input_dir=input_dir,
        output_dir=output_dir,
        module_name=module_name,
        providers=providers,
        llm_config=llm_config,
        aggregation_method=aggregation_method,
        batch_size=batch_size,
        min_frequency=min_frequency,
        context_window=context_window,
        reference_file=reference_file,
        original_cdes=original_cdes,
    )

    # Run pipeline
    results = await classifier.run()
    stats = classifier.get_statistics()

    return results, stats
