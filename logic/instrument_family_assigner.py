"""
Instrument family assignment orchestration.

Coordinates the workflow for assigning instrument family identifications:
1. Load instrument matches from InstrumentCatalog
2. Apply pattern-based family detection
3. Generate instrument_id slugs
4. Flag uncertain cases for optional LLM adjudication
5. Output enhanced instruments.tsv and instrument_families.tsv

Usage:
    from logic.instrument_family_assigner import InstrumentFamilyAssigner

    assigner = InstrumentFamilyAssigner(confidence_threshold=0.7)
    assigner.assign_families(catalog)
    assigner.write_enhanced_output(catalog, output_dir)
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from utils.instrument_extractor import InstrumentCatalog, InstrumentMatch, VariantInfo
from utils.instrument_family_patterns import InstrumentFamilyDetector

logger = logging.getLogger(__name__)


@dataclass
class FamilyAssignmentStats:
    """Statistics from family assignment process."""
    total_instruments: int = 0
    total_matches: int = 0
    families_detected: int = 0
    needs_review_count: int = 0
    family_distribution: Dict[str, int] = None
    spelling_variants_merged: int = 0
    merged_variant_groups: int = 0

    def __post_init__(self):
        if self.family_distribution is None:
            self.family_distribution = {}


class InstrumentFamilyAssigner:
    """
    Orchestrates instrument family assignment workflow.

    Provides methods for:
    - Assigning families using pattern detection
    - Generating enhanced output files
    - Tracking assignment statistics
    """

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        generate_family_summary: bool = True,
        merge_spelling_variants: bool = True,
        spelling_similarity_threshold: float = 0.85,
    ):
        """
        Initialize the assigner.

        Args:
            confidence_threshold: Minimum confidence for automatic acceptance.
            generate_family_summary: Whether to generate instrument_families.tsv.
            merge_spelling_variants: Whether to merge spelling variants before assignment.
            spelling_similarity_threshold: Similarity threshold for variant merging.
        """
        self.confidence_threshold = confidence_threshold
        self.generate_family_summary = generate_family_summary
        self.merge_spelling_variants = merge_spelling_variants
        self.spelling_similarity_threshold = spelling_similarity_threshold
        self._detector = InstrumentFamilyDetector(confidence_threshold=confidence_threshold)
        self._stats = FamilyAssignmentStats()
        self._merged_variants: Dict[str, List[VariantInfo]] = {}

    def assign_families(self, catalog: InstrumentCatalog) -> FamilyAssignmentStats:
        """
        Assign family identifications to all instruments in the catalog.

        Updates InstrumentMatch objects in place with family fields.
        Assigns sequential instrument_ids (instrument_0001, instrument_0002, etc.)
        sorted by normalized instrument name for deterministic ordering.

        If merge_spelling_variants is enabled, spelling variants are merged
        before family assignment.

        Args:
            catalog: InstrumentCatalog with detected instruments

        Returns:
            FamilyAssignmentStats with assignment statistics
        """
        # Merge spelling variants first (if enabled)
        if self.merge_spelling_variants:
            self._merged_variants = catalog.merge_spelling_variants(
                similarity_threshold=self.spelling_similarity_threshold
            )

        self._stats = FamilyAssignmentStats()
        family_counts: Dict[str, int] = {}

        # Sort instrument keys for deterministic sequential numbering
        sorted_keys = sorted(catalog.instruments.keys())

        for instrument_number, normalized_name in enumerate(sorted_keys, start=1):
            matches = catalog.instruments[normalized_name]
            self._stats.total_instruments += 1
            self._stats.total_matches += len(matches)

            for match in matches:
                # Detect family and generate identification with sequential ID
                result = self._detector.detect_and_identify(
                    instrument_name=match.instrument_name,
                    full_match=match.full_match,
                    acronym=match.acronym,
                    instrument_number=instrument_number,
                )

                # Populate family fields
                match.family_id = result["family_id"]
                match.family_display_name = result["family_display_name"]
                match.instrument_id = result["instrument_id"]
                match.family_confidence = result["family_confidence"]
                match.identification_method = result["identification_method"]
                match.needs_review = result["needs_review"]
                # Populate subinstrument fields for hierarchical instruments
                match.subinstrument_name = result.get("subinstrument_name")
                match.subinstrument_id = result.get("subinstrument_id")

                # Track statistics
                family_id = result["family_id"]
                family_counts[family_id] = family_counts.get(family_id, 0) + 1

                if result["needs_review"]:
                    self._stats.needs_review_count += 1

        self._stats.families_detected = len(family_counts)
        self._stats.family_distribution = family_counts

        # Track spelling variant merge stats
        if self._merged_variants:
            self._stats.merged_variant_groups = len(self._merged_variants)
            self._stats.spelling_variants_merged = sum(
                len(variants) for variants in self._merged_variants.values()
            )

        logger.info(
            f"Family assignment complete: {self._stats.total_instruments} instruments, "
            f"{self._stats.families_detected} families, "
            f"{self._stats.needs_review_count} need review"
            + (f", {self._stats.spelling_variants_merged} spelling variants merged"
               if self._stats.spelling_variants_merged else "")
        )

        return self._stats

    def write_enhanced_instruments_tsv(
        self,
        catalog: InstrumentCatalog,
        output_path: Path,
    ) -> None:
        """
        Write enhanced instruments.tsv with family columns.

        Adds columns: family_id, family_display_name, instrument_id,
        family_confidence, identification_method, needs_review

        Args:
            catalog: InstrumentCatalog with family assignments
            output_path: Path to output TSV file
        """
        fieldnames = [
            "instrument_id",
            "family_id",
            "family_display_name",
            "subinstrument_name",
            "subinstrument_id",
            "normalized_name",
            "canonical_name",
            "acronym",
            "frequency",
            "n_tinyids",
            "family_confidence",
            "identification_method",
            "needs_review",
            "tinyids",
            "example_contexts",
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()

            for normalized_name, matches in sorted(catalog.instruments.items()):
                if not matches:
                    continue

                first_match = matches[0]
                tinyids = sorted({m.tinyId for m in matches if m.tinyId})
                acronyms = sorted({m.acronym for m in matches if m.acronym})

                # Get example contexts (first 3 unique full matches)
                seen_contexts = set()
                example_contexts = []
                for m in matches:
                    if m.full_match not in seen_contexts and len(example_contexts) < 3:
                        example_contexts.append(m.full_match)
                        seen_contexts.add(m.full_match)

                writer.writerow({
                    "instrument_id": first_match.instrument_id or "",
                    "family_id": first_match.family_id or "",
                    "family_display_name": first_match.family_display_name or "",
                    "subinstrument_name": first_match.subinstrument_name or "",
                    "subinstrument_id": first_match.subinstrument_id or "",
                    "normalized_name": normalized_name,
                    "canonical_name": first_match.instrument_name,
                    "acronym": "|".join(acronyms) if acronyms else "",
                    "frequency": len(matches),
                    "n_tinyids": len(tinyids),
                    "family_confidence": f"{first_match.family_confidence:.2f}" if first_match.family_confidence is not None else "",
                    "identification_method": first_match.identification_method or "",
                    "needs_review": "True" if first_match.needs_review else "False",
                    "tinyids": "|".join(tinyids),
                    "example_contexts": "|".join(example_contexts),
                })

        logger.info(f"Wrote enhanced instruments to {output_path}")

    def write_enhanced_verbatim_tsv(
        self,
        catalog: InstrumentCatalog,
        output_path: Path,
    ) -> None:
        """
        Write enhanced instruments_verbatim.tsv with family columns.

        Outputs one row per exact verbatim form for curation.
        instrument_id is first column to help identify spelling variants
        that belong to the same instrument.

        Args:
            catalog: InstrumentCatalog with family assignments
            output_path: Path to output TSV file
        """
        fieldnames = [
            "instrument_id",
            "normalized_name",
            "family_id",
            "subinstrument_name",
            "subinstrument_id",
            "family_confidence",
            "needs_review",
            "acronym",
            "verbatim_name",
            "full_match",
            "family_full_match",  # full_match with family name only (e.g., "as part of PROMIS")
            "frequency",
            "n_tinyids",
            "tinyids",
        ]

        # Group by verbatim form
        verbatim_groups: Dict[str, Dict] = {}

        for normalized_name, matches in catalog.instruments.items():
            for match in matches:
                verbatim_key = (normalized_name, match.instrument_name)
                if verbatim_key not in verbatim_groups:
                    # Generate family_full_match by replacing instrument name with family name
                    # e.g., "as part of PROMIS Pain Interference" -> "as part of PROMIS"
                    family_full_match = match.full_match
                    if match.family_display_name and match.instrument_name:
                        family_full_match = match.full_match.replace(
                            match.instrument_name,
                            match.family_display_name
                        )

                    verbatim_groups[verbatim_key] = {
                        "instrument_id": match.instrument_id,
                        "normalized_name": normalized_name,
                        "family_id": match.family_id,
                        "subinstrument_name": match.subinstrument_name,
                        "subinstrument_id": match.subinstrument_id,
                        "family_confidence": match.family_confidence,
                        "needs_review": match.needs_review,
                        "acronym": match.acronym,
                        "verbatim_name": match.instrument_name,
                        "full_match": match.full_match,
                        "family_full_match": family_full_match,
                        "matches": [],
                        "tinyids": set(),
                    }
                verbatim_groups[verbatim_key]["matches"].append(match)
                if match.tinyId:
                    verbatim_groups[verbatim_key]["tinyids"].add(match.tinyId)

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()

            for verbatim_key, data in sorted(verbatim_groups.items()):
                tinyids = sorted(data["tinyids"])
                writer.writerow({
                    "instrument_id": data["instrument_id"] or "",
                    "normalized_name": data["normalized_name"],
                    "family_id": data["family_id"] or "",
                    "subinstrument_name": data["subinstrument_name"] or "",
                    "subinstrument_id": data["subinstrument_id"] or "",
                    "family_confidence": f"{data['family_confidence']:.2f}" if data['family_confidence'] is not None else "",
                    "needs_review": "True" if data["needs_review"] else "False",
                    "acronym": data["acronym"] or "",
                    "verbatim_name": data["verbatim_name"],
                    "full_match": data["full_match"],
                    "family_full_match": data["family_full_match"],
                    "frequency": len(data["matches"]),
                    "n_tinyids": len(tinyids),
                    "tinyids": "|".join(tinyids),
                })

        logger.info(f"Wrote enhanced verbatim instruments to {output_path}")

    def _write_curated_tsv(
        self,
        catalog: InstrumentCatalog,
        output_path: Path,
    ) -> None:
        """
        Write simplified curated TSV with 4 columns for curator review.

        Columns:
            instrument_id: Sequential identifier for the instrument
            pattern: The full_match text (renamed for direct use by strip_discover)
            family_full_match: Full match with family name substituted
            tinyids: Pipe-separated document IDs

        Args:
            catalog: InstrumentCatalog with family assignments
            output_path: Path to output TSV file
        """
        fieldnames = ["instrument_id", "pattern", "family_full_match", "tinyids"]

        # Group by (normalized_name, full_match) so each distinct verbatim
        # form gets its own row.  The old key (normalized_name, instrument_name)
        # silently dropped variants with different full_match but the same
        # canonical instrument_name (e.g., "version 1.0 of 36-item SF-36"
        # was lost when "version 2.0 of 12-item SF-12" was written first).
        verbatim_groups: Dict[str, Dict] = {}

        for normalized_name, matches in catalog.instruments.items():
            for match in matches:
                verbatim_key = (normalized_name, match.full_match)
                if verbatim_key not in verbatim_groups:
                    family_full_match = match.full_match
                    if match.family_display_name and match.instrument_name:
                        family_full_match = match.full_match.replace(
                            match.instrument_name,
                            match.family_display_name
                        )
                    verbatim_groups[verbatim_key] = {
                        "instrument_id": match.instrument_id,
                        "full_match": match.full_match,
                        "family_full_match": family_full_match,
                        "tinyids": set(),
                    }
                if match.tinyId:
                    verbatim_groups[verbatim_key]["tinyids"].add(match.tinyId)

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()

            for verbatim_key, data in sorted(verbatim_groups.items()):
                tinyids = sorted(data["tinyids"])
                writer.writerow({
                    "instrument_id": data["instrument_id"] or "",
                    "pattern": data["full_match"],
                    "family_full_match": data["family_full_match"],
                    "tinyids": "|".join(tinyids),
                })

        logger.info(f"Wrote curated file to {output_path}")

    def write_families_summary_tsv(
        self,
        catalog: InstrumentCatalog,
        output_path: Path,
    ) -> None:
        """
        Write instrument_families.tsv summary file.

        Groups instruments by family with aggregate statistics.

        Args:
            catalog: InstrumentCatalog with family assignments
            output_path: Path to output TSV file
        """
        fieldnames = [
            "family_id",
            "family_display_name",
            "n_instruments",
            "n_tinyids",
            "total_frequency",
            "top_instruments",
            "all_acronyms",
        ]

        # Get family summary from catalog
        families_summary = catalog.get_families_summary()

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()

            for family_id, data in sorted(families_summary.items()):
                # Get top 5 instruments by name
                top_instruments = data["instruments"][:5]

                writer.writerow({
                    "family_id": family_id,
                    "family_display_name": data["display_name"],
                    "n_instruments": data["n_instruments"],
                    "n_tinyids": data["n_tinyids"],
                    "total_frequency": data["total_frequency"],
                    "top_instruments": "|".join(top_instruments),
                    "all_acronyms": "|".join(data["acronyms"]),
                })

        logger.info(f"Wrote families summary to {output_path}")

    def write_all_outputs(
        self,
        catalog: InstrumentCatalog,
        output_dir: Path,
    ) -> Dict[str, Path]:
        """
        Write all enhanced output files.

        Args:
            catalog: InstrumentCatalog with family assignments
            output_dir: Output directory

        Returns:
            Dict mapping output type to file path
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs = {}

        # Enhanced instruments.tsv
        instruments_path = output_dir / "instruments.tsv"
        self.write_enhanced_instruments_tsv(catalog, instruments_path)
        outputs["instruments"] = instruments_path

        # Enhanced verbatim.tsv
        verbatim_path = output_dir / "instruments_verbatim.tsv"
        self.write_enhanced_verbatim_tsv(catalog, verbatim_path)
        outputs["instruments_verbatim"] = verbatim_path

        # Family summary
        if self.generate_family_summary:
            families_path = output_dir / "instrument_families.tsv"
            self.write_families_summary_tsv(catalog, families_path)
            outputs["instrument_families"] = families_path

        # Simplified pattern files for discovery workflow:
        #   curated_fullmatch.tsv - full instrument substitution (pattern = full_match)
        #   mined_patterns.tsv    - mined patterns for discover_verbatim input
        # Both have 4 columns: instrument_id, pattern, family_full_match, tinyids
        # Note: curated.tsv is reserved for human-edited patterns (copied from coalesced.tsv)
        curated_fullmatch_path = output_dir / "curated_fullmatch.tsv"
        self._write_curated_tsv(catalog, curated_fullmatch_path)
        outputs["curated_fullmatch"] = curated_fullmatch_path

        mined_patterns_path = output_dir / "mined_patterns.tsv"
        self._write_curated_tsv(catalog, mined_patterns_path)
        outputs["mined_patterns"] = mined_patterns_path

        # Write stats JSON
        stats_path = output_dir / "family_assignment_stats.json"
        stats_data = {
            "total_instruments": self._stats.total_instruments,
            "total_matches": self._stats.total_matches,
            "families_detected": self._stats.families_detected,
            "needs_review_count": self._stats.needs_review_count,
            "family_distribution": self._stats.family_distribution,
        }
        # Add spelling variant merge stats if any merges occurred
        if self._stats.spelling_variants_merged > 0:
            stats_data["spelling_variants_merged"] = self._stats.spelling_variants_merged
            stats_data["merged_variant_groups"] = self._stats.merged_variant_groups

            # Build detailed variant info with types
            # Count variants by type
            variant_type_counts: Dict[str, int] = {}
            merged_variants_detail = {}

            for canonical, variant_infos in self._merged_variants.items():
                merged_variants_detail[canonical] = []
                for vi in variant_infos:
                    merged_variants_detail[canonical].append({
                        "variant": vi.variant_name,
                        "type": vi.variant_type,
                        "differences": vi.differences,
                        "tinyIds": vi.tinyIds,  # CDEs containing this variant for QC
                    })
                    # Count by type
                    variant_type_counts[vi.variant_type] = (
                        variant_type_counts.get(vi.variant_type, 0) + 1
                    )

            stats_data["variant_type_counts"] = variant_type_counts
            stats_data["merged_variants"] = merged_variants_detail

        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, indent=2)
        outputs["stats"] = stats_path

        return outputs

    @property
    def stats(self) -> FamilyAssignmentStats:
        """Get assignment statistics."""
        return self._stats

    def get_instruments_needing_review(
        self,
        catalog: InstrumentCatalog,
    ) -> List[InstrumentMatch]:
        """
        Get list of instruments flagged for review.

        Args:
            catalog: InstrumentCatalog with family assignments

        Returns:
            List of InstrumentMatch objects where needs_review=True
        """
        needs_review = []
        for matches in catalog.instruments.values():
            for match in matches:
                if match.needs_review:
                    needs_review.append(match)
        return needs_review
