"""Tests for logic/phrase_miner.py — dedup, k-mer extraction, masking, mine_phrases."""

import pytest

from CDE_Schema.CDE_Item import CDEItem
from CDE_Schema.classes import Designation, Definition
from logic.phrase_miner import (
    CDERef,
    DedupResult,
    KmerCount,
    MinerConfig,
    Phrase,
    TokenSeq,
    count_kmers_with_masking,
    dedup_field_texts,
    extract_field_texts,
    extend_verbatim_span,
    kmer_count_to_phrase,
    mask_phrases_naive,
    mine_phrases,
)
from utils.phrase_miner_vocab import Vocabulary


# ---------------------------------------------------------------------------
# Helpers — build minimal CDEItem objects for testing
# ---------------------------------------------------------------------------

def _make_cde(tiny_id: str, designations=None, definitions=None):
    """Build a minimal CDEItem with the given fields."""
    desig_list = None
    if designations is not None:
        desig_list = [
            Designation(designation=d, sources=None, tags=None)
            for d in designations
        ]
    def_list = None
    if definitions is not None:
        def_list = [
            Definition(definition=d, sources=None, tags=None)
            for d in definitions
        ]
    return CDEItem(
        tinyId=tiny_id,
        nihEndorsed=None,
        elementType=None,
        archived=None,
        stewardOrg=None,
        registrationState=None,
        designations=desig_list,
        definitions=def_list,
        classification=None,
        referenceDocuments=None,
        properties=None,
        ids=None,
        attachments=None,
        sources=None,
        createdBy=None,
    )


def _make_token_seq(tokens, tinyid, mask_owner=None, field_path="test"):
    """Build a TokenSeq from raw token IDs."""
    if mask_owner is None:
        mask_owner = [None] * len(tokens)
    ref = CDERef(tinyId=tinyid, field_path=field_path, token_span=(0, len(tokens)))
    return TokenSeq(tokens=tokens, cde_ref=ref, mask_owner=mask_owner)


def _build_vocab(words):
    """Build a Vocabulary from a list of words, returning (vocab, id_list)."""
    vocab = Vocabulary()
    ids = [vocab.add_token(w) for w in words]
    return vocab, ids


# ===================================================================
# 1. dedup_field_texts
# ===================================================================

class TestDedupFieldTexts:
    """Tests for dedup_field_texts() — Stage 0a."""

    def test_basic_dedup_two_identical_designations(self):
        """Two CDEs sharing the same designation text are detected."""
        items = [
            _make_cde("t1", designations=["Pain severity score"]),
            _make_cde("t2", designations=["Pain severity score"]),
        ]
        cfg = MinerConfig(dedup_min_count=2)
        results = dedup_field_texts(items, cfg)
        assert len(results) == 1
        assert results[0].text == "Pain severity score"
        assert results[0].tinyids == {"t1", "t2"}

    def test_dedup_whitespace_normalised(self):
        """Whitespace differences are collapsed before hashing."""
        items = [
            _make_cde("t1", designations=["Pain  severity   score"]),
            _make_cde("t2", designations=["Pain severity score"]),
        ]
        cfg = MinerConfig(dedup_min_count=2)
        results = dedup_field_texts(items, cfg)
        assert len(results) == 1

    def test_dedup_threshold_not_met(self):
        """Texts appearing only once are excluded."""
        items = [
            _make_cde("t1", designations=["Unique text A"]),
            _make_cde("t2", designations=["Unique text B"]),
        ]
        cfg = MinerConfig(dedup_min_count=2)
        results = dedup_field_texts(items, cfg)
        assert len(results) == 0

    def test_dedup_respects_higher_threshold(self):
        """Raising dedup_min_count excludes texts below the threshold."""
        items = [
            _make_cde("t1", designations=["Shared text"]),
            _make_cde("t2", designations=["Shared text"]),
            _make_cde("t3", designations=["Shared text"]),
        ]
        # Threshold of 2: should match
        cfg2 = MinerConfig(dedup_min_count=2)
        assert len(dedup_field_texts(items, cfg2)) == 1

        # Threshold of 4: should not match
        cfg4 = MinerConfig(dedup_min_count=4)
        assert len(dedup_field_texts(items, cfg4)) == 0

    def test_dedup_sorted_by_tinyid_count_descending(self):
        """Results are sorted most-shared first."""
        items = [
            _make_cde("t1", designations=["Shared A"]),
            _make_cde("t2", designations=["Shared A"]),
            _make_cde("t3", designations=["Shared B"]),
            _make_cde("t4", designations=["Shared B"]),
            _make_cde("t5", designations=["Shared B"]),
        ]
        cfg = MinerConfig(dedup_min_count=2)
        results = dedup_field_texts(items, cfg)
        assert len(results) == 2
        assert len(results[0].tinyids) >= len(results[1].tinyids)
        assert results[0].text == "Shared B"

    def test_dedup_empty_and_none_texts_skipped(self):
        """Empty strings and missing fields do not cause errors."""
        items = [
            _make_cde("t1", designations=[""]),
            _make_cde("t2", designations=[""]),
            _make_cde("t3"),  # no designations at all
        ]
        cfg = MinerConfig(dedup_min_count=2)
        results = dedup_field_texts(items, cfg)
        assert len(results) == 0

    def test_dedup_definitions_field(self):
        """Dedup works across definitions when field_names includes 'definition'."""
        items = [
            _make_cde("t1", definitions=["Measure of pain intensity"]),
            _make_cde("t2", definitions=["Measure of pain intensity"]),
        ]
        cfg = MinerConfig(dedup_min_count=2, field_names=["definition"])
        results = dedup_field_texts(items, cfg)
        assert len(results) == 1

    def test_dedup_no_tinyid_skipped(self):
        """CDEs with no tinyId are skipped."""
        items = [
            _make_cde(None, designations=["Pain score"]),
            _make_cde(None, designations=["Pain score"]),
        ]
        cfg = MinerConfig(dedup_min_count=2)
        results = dedup_field_texts(items, cfg)
        assert len(results) == 0


# ===================================================================
# 2. extract_field_texts
# ===================================================================

class TestExtractFieldTexts:
    """Tests for extract_field_texts()."""

    def test_designation_extraction(self):
        item = _make_cde("t1", designations=["Pain score", "Severity"])
        results = extract_field_texts(item, ["designation"])
        assert len(results) == 2
        assert results[0] == ("designations[0].designation", "Pain score")
        assert results[1] == ("designations[1].designation", "Severity")

    def test_definition_extraction(self):
        item = _make_cde("t1", definitions=["A measure of pain"])
        results = extract_field_texts(item, ["definition"])
        assert len(results) == 1
        assert results[0][1] == "A measure of pain"

    def test_no_matching_fields(self):
        item = _make_cde("t1", designations=["Pain"])
        results = extract_field_texts(item, ["definition"])
        assert len(results) == 0

    def test_empty_designations_list(self):
        item = _make_cde("t1")
        results = extract_field_texts(item, ["designation"])
        assert len(results) == 0


# ===================================================================
# 3. count_kmers_with_masking (k-mer extraction)
# ===================================================================

class TestCountKmersWithMasking:
    """Tests for count_kmers_with_masking() — k-mer extraction."""

    def test_basic_kmer_counts(self):
        """A 3-token sequence with k=2 produces two distinct 2-mers."""
        vocab, ids = _build_vocab(["alpha", "beta", "gamma"])
        seq = _make_token_seq(ids, "t1")
        results = count_kmers_with_masking([seq], k=2, freq_min=1)
        # Two 2-mers: (alpha,beta) and (beta,gamma)
        assert len(results) == 2

    def test_freq_min_filter(self):
        """K-mers below freq_min are excluded."""
        vocab, ids = _build_vocab(["alpha", "beta", "gamma"])
        seq = _make_token_seq(ids, "t1")
        # Each 2-mer appears only once; freq_min=2 should exclude all
        results = count_kmers_with_masking([seq], k=2, freq_min=2)
        assert len(results) == 0

    def test_repeated_kmer_across_sequences(self):
        """Same k-mer in two sequences has frequency=2."""
        vocab, ids = _build_vocab(["alpha", "beta"])
        seq1 = _make_token_seq(list(ids), "t1")
        seq2 = _make_token_seq(list(ids), "t2")
        results = count_kmers_with_masking([seq1, seq2], k=2, freq_min=1)
        assert len(results) == 1
        assert results[0].frequency == 2
        assert results[0].tinyids == {"t1", "t2"}

    def test_masked_tokens_excluded(self):
        """K-mers that span masked tokens are skipped."""
        vocab, ids = _build_vocab(["alpha", "beta", "gamma"])
        # Mask the middle token
        mask = [None, "owned", None]
        seq = _make_token_seq(ids, "t1", mask_owner=mask)
        results = count_kmers_with_masking([seq], k=2, freq_min=1)
        # Neither (alpha,beta) nor (beta,gamma) is fully unmasked
        assert len(results) == 0

    def test_k_equals_sequence_length(self):
        """K equal to the full sequence length produces one k-mer."""
        vocab, ids = _build_vocab(["alpha", "beta", "gamma"])
        seq = _make_token_seq(ids, "t1")
        results = count_kmers_with_masking([seq], k=3, freq_min=1)
        assert len(results) == 1
        assert results[0].kmer == tuple(ids)

    def test_k_exceeds_sequence_length(self):
        """K larger than the sequence produces no k-mers."""
        vocab, ids = _build_vocab(["alpha", "beta"])
        seq = _make_token_seq(ids, "t1")
        results = count_kmers_with_masking([seq], k=3, freq_min=1)
        assert len(results) == 0

    def test_single_token_sequence_k1(self):
        """A single-token sequence with k=1 yields one 1-mer."""
        vocab, ids = _build_vocab(["alpha"])
        seq = _make_token_seq(ids, "t1")
        results = count_kmers_with_masking([seq], k=1, freq_min=1)
        assert len(results) == 1

    def test_tinyid_dedup_within_sequence(self):
        """Multiple occurrences in the same CDE count as one tinyId."""
        vocab, ids = _build_vocab(["alpha", "beta", "alpha", "beta"])
        seq = _make_token_seq(ids, "t1")
        results = count_kmers_with_masking([seq], k=2, freq_min=1)
        # (alpha, beta) appears twice but same tinyId
        ab = [r for r in results if r.kmer == (ids[0], ids[1])]
        assert len(ab) == 1
        assert ab[0].frequency == 2
        assert ab[0].tinyids == {"t1"}


# ===================================================================
# 4. Masking — mask_phrases_naive
# ===================================================================

class TestMaskPhrasesNaive:
    """Tests for mask_phrases_naive() — marking tokens as owned."""

    def _make_phrase(self, phrase_id, token_ids):
        """Build a minimal Phrase for masking tests."""
        return Phrase(
            phrase_id=phrase_id,
            token_ids=tuple(token_ids),
            text="",
            frequency=1,
            distinct_tinyids=set(),
            k=len(token_ids),
            occurrences=[],
            extension_method="kmer",
        )

    def test_basic_masking(self):
        """Matching tokens are masked with the phrase ID."""
        seq = _make_token_seq([0, 1, 2, 3], "t1")
        phrase = self._make_phrase("p1", [1, 2])
        mask_phrases_naive([seq], [phrase])
        assert seq.mask_owner == [None, "p1", "p1", None]

    def test_masking_prevents_overlap(self):
        """An already-masked region is not overwritten by a second phrase."""
        seq = _make_token_seq([0, 1, 2, 3], "t1")
        p1 = self._make_phrase("p1", [0, 1, 2])
        p2 = self._make_phrase("p2", [1, 2, 3])
        mask_phrases_naive([seq], [p1, p2])
        # p1 should own positions 0-2; p2 cannot match because position 1,2 are taken
        assert seq.mask_owner == ["p1", "p1", "p1", None]

    def test_no_match_leaves_unmasked(self):
        """Tokens not matching any phrase remain None."""
        seq = _make_token_seq([0, 1, 2], "t1")
        phrase = self._make_phrase("p1", [5, 6])
        mask_phrases_naive([seq], [phrase])
        assert seq.mask_owner == [None, None, None]

    def test_multiple_non_overlapping_matches(self):
        """Two non-overlapping occurrences of the same phrase are both masked."""
        # Sequence: A B A B
        seq = _make_token_seq([0, 1, 0, 1], "t1")
        phrase = self._make_phrase("p1", [0, 1])
        mask_phrases_naive([seq], [phrase])
        assert seq.mask_owner == ["p1", "p1", "p1", "p1"]

    def test_masking_across_sequences(self):
        """Masking applies independently to each TokenSeq."""
        seq1 = _make_token_seq([0, 1, 2], "t1")
        seq2 = _make_token_seq([0, 1, 2], "t2")
        phrase = self._make_phrase("p1", [0, 1])
        mask_phrases_naive([seq1, seq2], [phrase])
        assert seq1.mask_owner == ["p1", "p1", None]
        assert seq2.mask_owner == ["p1", "p1", None]

    def test_empty_phrase_list(self):
        """No phrases means nothing is masked."""
        seq = _make_token_seq([0, 1, 2], "t1")
        mask_phrases_naive([seq], [])
        assert seq.mask_owner == [None, None, None]


# ===================================================================
# 5. kmer_count_to_phrase
# ===================================================================

class TestKmerCountToPhrase:
    """Tests for kmer_count_to_phrase() conversion."""

    def test_basic_conversion(self):
        vocab, ids = _build_vocab(["pain", "severity"])
        kc = KmerCount(
            kmer=tuple(ids),
            frequency=5,
            tinyids={"t1", "t2"},
            occurrences=[],
        )
        phrase = kmer_count_to_phrase(kc, phrase_id=3, k=2, vocab=vocab)
        assert phrase.phrase_id == "phrase_00003"
        assert phrase.text == "pain severity"
        assert phrase.frequency == 5
        assert phrase.distinct_tinyids == {"t1", "t2"}
        assert phrase.k == 2
        assert phrase.token_ids == tuple(ids)


# ===================================================================
# 6. extend_verbatim_span
# ===================================================================

class TestExtendVerbatimSpan:
    """Tests for extend_verbatim_span() — punctuation extension."""

    def test_trailing_punctuation_included(self):
        text = "outcome) and other"
        # Original span covers "outcome" (0:7)
        start, end = extend_verbatim_span(text, 0, 7)
        assert start == 0
        assert end == 8  # includes ")"

    def test_leading_punctuation_included(self):
        text = '("pain score")'
        # Span covering the inner text starting at char 1
        start, end = extend_verbatim_span(text, 1, 13)
        assert start == 0  # extends left to include (
        assert end == 14  # extends right to include )

    def test_no_adjacent_punctuation(self):
        text = "plain text here"
        start, end = extend_verbatim_span(text, 0, 5)
        assert start == 0
        assert end == 5

    def test_at_text_boundaries(self):
        text = "word."
        start, end = extend_verbatim_span(text, 0, 4)
        assert end == 5  # includes trailing period


# ===================================================================
# 7. mine_phrases — end-to-end with synthetic data
# ===================================================================

class TestMinePhrases:
    """End-to-end tests for mine_phrases() with small synthetic data."""

    def _make_config(self, **overrides):
        """Build a MinerConfig suitable for testing."""
        defaults = dict(
            k_max=5,
            k_min=2,
            freq_min=2,
            min_distinct_tinyids=2,
            field_names=["designation"],
            remove_stopwords=False,
            lemmatize=False,
            skip_debruijn=True,
            skip_anchor=True,
            use_aho_corasick=False,  # use naive masking for determinism
            dedup_enabled=False,
            prefix_consolidation=False,
            generate_histograms=False,
        )
        defaults.update(overrides)
        return MinerConfig(**defaults)

    def test_repeated_bigram_detected(self):
        """A bigram repeated across 3 CDEs is detected as a phrase."""
        items = [
            _make_cde("t1", designations=["pain severity score"]),
            _make_cde("t2", designations=["pain severity rating"]),
            _make_cde("t3", designations=["pain severity level"]),
        ]
        cfg = self._make_config(k_min=2, k_max=3, freq_min=2, min_distinct_tinyids=2)
        phrases, token_seqs, vocab, _, _, _ = mine_phrases(items, cfg)
        texts = {p.text for p in phrases}
        assert "pain severity" in texts

    def test_masking_prevents_redetection(self):
        """
        A 3-mer detected at k=3 masks its tokens so the constituent
        2-mers are not double-counted at k=2.
        """
        # All 3 CDEs share the exact trigram "alpha beta gamma"
        items = [
            _make_cde("t1", designations=["alpha beta gamma"]),
            _make_cde("t2", designations=["alpha beta gamma"]),
            _make_cde("t3", designations=["alpha beta gamma"]),
        ]
        cfg = self._make_config(k_min=2, k_max=3, freq_min=2, min_distinct_tinyids=2)
        phrases, token_seqs, vocab, _, _, _ = mine_phrases(items, cfg)

        # "alpha beta gamma" should be found at k=3
        trigrams = [p for p in phrases if p.k == 3]
        assert len(trigrams) >= 1
        assert any(p.text == "alpha beta gamma" for p in trigrams)

        # After masking, "alpha beta" and "beta gamma" should NOT appear
        # because their tokens are fully masked by the trigram
        bigram_texts = {p.text for p in phrases if p.k == 2}
        assert "alpha beta" not in bigram_texts
        assert "beta gamma" not in bigram_texts

    def test_single_cde_below_min_tinyids(self):
        """Phrases from a single CDE are excluded by min_distinct_tinyids=2."""
        items = [
            _make_cde("t1", designations=["unique phrase here unique phrase here"]),
        ]
        cfg = self._make_config(k_min=2, k_max=3, freq_min=2, min_distinct_tinyids=2)
        phrases, *_ = mine_phrases(items, cfg)
        # frequency might be >= 2 within one CDE, but only 1 distinct tinyId
        assert len(phrases) == 0

    def test_empty_text_no_crash(self):
        """Empty designation text does not cause errors."""
        items = [
            _make_cde("t1", designations=[""]),
            _make_cde("t2", designations=[""]),
        ]
        cfg = self._make_config()
        phrases, *_ = mine_phrases(items, cfg)
        assert isinstance(phrases, list)

    def test_k_min_equals_k_max(self):
        """When k_min == k_max, only one k level is mined."""
        items = [
            _make_cde("t1", designations=["alpha beta gamma"]),
            _make_cde("t2", designations=["alpha beta gamma"]),
            _make_cde("t3", designations=["alpha beta delta"]),
        ]
        cfg = self._make_config(k_min=2, k_max=2, freq_min=2, min_distinct_tinyids=2)
        phrases, *_ = mine_phrases(items, cfg)
        # Only 2-mers should be found
        for p in phrases:
            assert p.k == 2

    def test_multiple_distinct_phrases(self):
        """Two different repeating phrases are both detected."""
        items = [
            _make_cde("t1", designations=["blood pressure systolic measurement"]),
            _make_cde("t2", designations=["blood pressure diastolic measurement"]),
            _make_cde("t3", designations=["blood pressure mean measurement"]),
        ]
        cfg = self._make_config(k_min=2, k_max=3, freq_min=2, min_distinct_tinyids=2)
        phrases, *_ = mine_phrases(items, cfg)
        texts = {p.text for p in phrases}
        assert "blood pressure" in texts

    def test_dedup_long_text_emitted_as_dedup_phrase(self):
        """Whole-text dedup emits phrases for texts exceeding k_max."""
        # All 3 CDEs share a designation longer than k_max=3
        long_text = "alpha beta gamma delta epsilon"  # 5 tokens > k_max=3
        items = [
            _make_cde("t1", designations=[long_text]),
            _make_cde("t2", designations=[long_text]),
            _make_cde("t3", designations=[long_text]),
        ]
        cfg = self._make_config(
            k_min=2, k_max=3, freq_min=2, min_distinct_tinyids=2,
            dedup_enabled=True, dedup_min_count=2, dedup_min_tokens=3,
        )
        phrases, _, _, _, _, dedup_phrases = mine_phrases(items, cfg)
        # The dedup phrase should be in the separate dedup_phrases list
        assert len(dedup_phrases) >= 1
        assert any("dedup_" in p.phrase_id for p in dedup_phrases)

    def test_dedup_short_text_not_emitted(self):
        """Whole-text dedup does NOT emit phrases with tokens <= k_max."""
        short_text = "alpha beta"  # 2 tokens <= k_max=3
        items = [
            _make_cde("t1", designations=[short_text]),
            _make_cde("t2", designations=[short_text]),
        ]
        cfg = self._make_config(
            k_min=2, k_max=3, freq_min=2, min_distinct_tinyids=2,
            dedup_enabled=True, dedup_min_count=2, dedup_min_tokens=2,
        )
        _, _, _, _, _, dedup_phrases = mine_phrases(items, cfg)
        # Short duplicates are left to k-mer mining, not dedup
        assert len(dedup_phrases) == 0

    def test_return_tuple_structure(self):
        """mine_phrases returns the expected 6-element tuple."""
        items = [_make_cde("t1", designations=["test"])]
        cfg = self._make_config()
        result = mine_phrases(items, cfg)
        assert len(result) == 6
        phrases, token_seqs, vocab, verbatim_tracker, instrument_catalog, dedup_phrases = result
        assert isinstance(phrases, list)
        assert isinstance(token_seqs, list)
        assert instrument_catalog is None  # extract_instruments=False
        assert isinstance(dedup_phrases, list)

    def test_no_items_returns_empty(self):
        """Empty input produces empty output without errors."""
        cfg = self._make_config()
        phrases, token_seqs, vocab, _, _, dedup_phrases = mine_phrases([], cfg)
        assert phrases == []
        assert token_seqs == []
        assert dedup_phrases == []
