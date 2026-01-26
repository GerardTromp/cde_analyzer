"""
K-mer frequency histogram generation.

Generates histograms showing the distribution of k-mer counts by distinct tinyIds
after frequency filtering but before min_tinyIds filtering.

This helps visualize:
- How many k-mers appear in exactly N documents
- The long-tail distribution of phrase frequencies
- The impact of different min_tinyIds thresholds

Usage:
    from utils.histogram_generator import HistogramCollector

    collector = HistogramCollector(output_dir=Path("output"))
    collector.add_kmer_counts(k=10, tinyid_counts=[2, 3, 5, 2, 8, ...])
    collector.generate_histograms(min_tinyids_threshold=2)
"""

import logging
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class HistogramCollector:
    """
    Collects k-mer tinyId counts per k value and generates histogram plots.

    Attributes:
        output_dir: Directory where histogram files will be saved
        k_distributions: Dict mapping k value to list of tinyId counts
    """

    def __init__(self, output_dir: Path):
        """
        Initialize the histogram collector.

        Args:
            output_dir: Directory for output files (histograms subdir created within)
        """
        self.output_dir = output_dir
        self.histogram_dir = output_dir / "histograms"
        self.k_distributions: Dict[int, List[int]] = {}

    def add_kmer_counts(self, k: int, tinyid_counts: List[int]) -> None:
        """
        Add tinyId count distribution for a k value.

        Args:
            k: The k-mer length
            tinyid_counts: List of tinyId counts for each k-mer at this k value
                          (one entry per k-mer, value = number of distinct tinyIds)
        """
        if k not in self.k_distributions:
            self.k_distributions[k] = []
        self.k_distributions[k].extend(tinyid_counts)

    def generate_histograms(
        self,
        min_tinyids_threshold: int = 2,
        max_display_count: int = 50,
    ) -> Optional[Path]:
        """
        Generate histogram plots for collected k-mer distributions.

        Creates:
        - Individual histogram per k value
        - Combined summary histogram across all k values
        - CSV file with raw distribution data

        Args:
            min_tinyids_threshold: The min_tinyids filter used (for annotation)
            max_display_count: Maximum tinyId count to show on x-axis (bins above grouped)

        Returns:
            Path to histogram directory, or None if matplotlib unavailable
        """
        if not self.k_distributions:
            logger.warning("No k-mer distributions collected; skipping histogram generation")
            return None

        try:
            import matplotlib.pyplot as plt
            import matplotlib.ticker as ticker
        except ImportError:
            logger.warning(
                "matplotlib not installed; skipping histogram generation. "
                "Install with: pip install matplotlib"
            )
            return None

        self.histogram_dir.mkdir(parents=True, exist_ok=True)

        # Write raw data to CSV
        self._write_distribution_csv()

        # Generate individual histograms per k
        for k, counts in sorted(self.k_distributions.items()):
            self._generate_k_histogram(
                k, counts, min_tinyids_threshold, max_display_count, plt
            )

        # Generate combined summary
        self._generate_combined_histogram(
            min_tinyids_threshold, max_display_count, plt
        )

        logger.info(f"Generated histograms in {self.histogram_dir}")
        return self.histogram_dir

    def _write_distribution_csv(self) -> None:
        """Write raw distribution data to CSV for further analysis."""
        csv_path = self.histogram_dir / "kmer_distributions.csv"

        with csv_path.open('w', encoding='utf-8') as f:
            f.write("k,tinyid_count,n_kmers\n")

            for k, counts in sorted(self.k_distributions.items()):
                count_freq = Counter(counts)
                for tinyid_count, n_kmers in sorted(count_freq.items()):
                    f.write(f"{k},{tinyid_count},{n_kmers}\n")

        logger.debug(f"Wrote distribution data to {csv_path}")

    def _generate_k_histogram(
        self,
        k: int,
        counts: List[int],
        min_tinyids_threshold: int,
        max_display_count: int,
        plt,
    ) -> None:
        """Generate histogram for a single k value."""
        fig, ax = plt.subplots(figsize=(10, 6))

        # Count frequencies
        count_freq = Counter(counts)

        # Prepare bins (1 to max_display_count, with overflow bin)
        max_count = max(counts) if counts else 1
        if max_count > max_display_count:
            # Group high counts into overflow bin
            display_counts = []
            for c in counts:
                display_counts.append(min(c, max_display_count))
            bins = list(range(1, max_display_count + 2))
            x_labels = [str(i) for i in range(1, max_display_count)] + [f"{max_display_count}+"]
        else:
            display_counts = counts
            bins = list(range(1, max_count + 2))
            x_labels = [str(i) for i in range(1, max_count + 1)]

        # Plot histogram
        n, bins_out, patches = ax.hist(
            display_counts,
            bins=bins,
            edgecolor='black',
            alpha=0.7,
            align='left',
        )

        # Color bars below threshold differently
        for i, patch in enumerate(patches):
            if i + 1 < min_tinyids_threshold:
                patch.set_facecolor('lightcoral')
                patch.set_alpha(0.5)
            else:
                patch.set_facecolor('steelblue')

        # Add threshold line
        if min_tinyids_threshold > 1:
            ax.axvline(
                x=min_tinyids_threshold - 0.5,
                color='red',
                linestyle='--',
                linewidth=2,
                label=f'min_tinyids threshold ({min_tinyids_threshold})'
            )
            ax.legend()

        # Labels and title
        ax.set_xlabel('Number of distinct tinyIds (documents)')
        ax.set_ylabel('Number of k-mers')
        ax.set_title(f'K-mer Distribution for k={k}\n(n={len(counts):,} k-mers)')

        # Set x-axis ticks
        ax.set_xticks(range(1, len(x_labels) + 1))
        ax.set_xticklabels(x_labels, rotation=45 if len(x_labels) > 20 else 0)

        # Add grid
        ax.yaxis.grid(True, alpha=0.3)

        # Calculate stats for annotation
        above_threshold = sum(1 for c in counts if c >= min_tinyids_threshold)
        below_threshold = len(counts) - above_threshold

        stats_text = (
            f"Total k-mers: {len(counts):,}\n"
            f"Above threshold: {above_threshold:,} ({100*above_threshold/len(counts):.1f}%)\n"
            f"Filtered out: {below_threshold:,} ({100*below_threshold/len(counts):.1f}%)"
        )
        ax.text(
            0.98, 0.95, stats_text,
            transform=ax.transAxes,
            verticalalignment='top',
            horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            fontsize=9,
        )

        plt.tight_layout()
        fig.savefig(self.histogram_dir / f"histogram_k{k:02d}.png", dpi=150)
        plt.close(fig)

    def _generate_combined_histogram(
        self,
        min_tinyids_threshold: int,
        max_display_count: int,
        plt,
    ) -> None:
        """Generate combined summary histogram across all k values."""
        fig, ax = plt.subplots(figsize=(12, 7))

        # Combine all counts
        all_counts = []
        for counts in self.k_distributions.values():
            all_counts.extend(counts)

        if not all_counts:
            plt.close(fig)
            return

        count_freq = Counter(all_counts)
        max_count = max(all_counts)

        # Prepare data for bar chart
        if max_count > max_display_count:
            # Bin high counts
            binned_freq = Counter()
            for count, freq in count_freq.items():
                if count >= max_display_count:
                    binned_freq[max_display_count] += freq
                else:
                    binned_freq[count] = freq
            x_range = list(range(1, max_display_count + 1))
            x_labels = [str(i) for i in range(1, max_display_count)] + [f"{max_display_count}+"]
        else:
            binned_freq = count_freq
            x_range = list(range(1, max_count + 1))
            x_labels = [str(i) for i in x_range]

        y_values = [binned_freq.get(x, 0) for x in x_range]

        # Color based on threshold
        colors = ['lightcoral' if x < min_tinyids_threshold else 'steelblue' for x in x_range]

        bars = ax.bar(x_range, y_values, color=colors, edgecolor='black', alpha=0.7)

        # Threshold line
        if min_tinyids_threshold > 1:
            ax.axvline(
                x=min_tinyids_threshold - 0.5,
                color='red',
                linestyle='--',
                linewidth=2,
                label=f'min_tinyids threshold ({min_tinyids_threshold})'
            )
            ax.legend()

        ax.set_xlabel('Number of distinct tinyIds (documents)')
        ax.set_ylabel('Number of k-mers (all k values combined)')
        ax.set_title(
            f'Combined K-mer Distribution\n'
            f'(k={min(self.k_distributions.keys())}-{max(self.k_distributions.keys())}, '
            f'n={len(all_counts):,} total k-mers)'
        )

        ax.set_xticks(x_range)
        ax.set_xticklabels(x_labels, rotation=45 if len(x_labels) > 20 else 0)
        ax.yaxis.grid(True, alpha=0.3)

        # Stats annotation
        above_threshold = sum(1 for c in all_counts if c >= min_tinyids_threshold)
        below_threshold = len(all_counts) - above_threshold

        stats_text = (
            f"Total k-mers: {len(all_counts):,}\n"
            f"Above threshold: {above_threshold:,} ({100*above_threshold/len(all_counts):.1f}%)\n"
            f"Filtered out: {below_threshold:,} ({100*below_threshold/len(all_counts):.1f}%)\n"
            f"K range: {min(self.k_distributions.keys())}-{max(self.k_distributions.keys())}"
        )
        ax.text(
            0.98, 0.95, stats_text,
            transform=ax.transAxes,
            verticalalignment='top',
            horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            fontsize=10,
        )

        plt.tight_layout()
        fig.savefig(self.histogram_dir / "histogram_combined.png", dpi=150)
        plt.close(fig)

        logger.info(
            f"Combined histogram: {len(all_counts):,} k-mers, "
            f"{above_threshold:,} above threshold ({100*above_threshold/len(all_counts):.1f}%)"
        )
