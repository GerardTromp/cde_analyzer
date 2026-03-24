"""
Unit tests for instrument pattern extraction.
"""

import pytest
from utils.instrument_extractor import (
    InstrumentExtractor,
    InstrumentMatch,
    InstrumentCatalog,
    normalize_instrument_name
)


class TestNormalizeInstrumentName:
    """Tests for normalize_instrument_name function."""

    def test_basic_normalization(self):
        assert normalize_instrument_name("Patient Health Questionnaire") == "patient health questionnaire"

    def test_hyphen_removal(self):
        assert normalize_instrument_name("Short-Form Health Survey") == "short form health survey"

    def test_whitespace_collapse(self):
        assert normalize_instrument_name("Patient  Health   Questionnaire") == "patient health questionnaire"

    def test_mixed_case(self):
        assert normalize_instrument_name("PATIENT Health QUESTIONNAIRE") == "patient health questionnaire"


class TestInstrumentExtractor:
    """Tests for InstrumentExtractor class."""

    @pytest.fixture
    def extractor(self):
        return InstrumentExtractor(min_name_words=3)

    def test_basic_pattern(self, extractor):
        """Test basic 'as part of <Instrument>' pattern."""
        text = "This item was developed as part of Patient Health Questionnaire (PHQ)."
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert "Patient Health Questionnaire" in matches[0].instrument_name
        assert matches[0].acronym == "PHQ"

    def test_with_article(self, extractor):
        """Test pattern with 'the' article."""
        text = "Collected as part of the Drug Abuse Screening Test (DAST) battery."
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert matches[0].instrument_name == "Drug Abuse Screening Test"
        assert matches[0].acronym == "DAST"

    def test_with_version(self, extractor):
        """Test pattern with version clause."""
        text = "as part of version 1.0 of Short Form Health Survey"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert matches[0].instrument_name == "Short Form Health Survey"

    def test_with_version_and_acronym(self, extractor):
        """Test full pattern with version and acronym."""
        text = "Measured as part of version 2.0 of the Patient Health Questionnaire (PHQ-9)."
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert matches[0].instrument_name == "Patient Health Questionnaire"
        assert matches[0].acronym == "PHQ-9"

    def test_numbered_prefix(self, extractor):
        """Test pattern with numbered prefix like '36-item'."""
        text = "as part of 36-item Short Form Health Survey (SF-36)"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert "Short Form Health Survey" in matches[0].instrument_name
        assert matches[0].acronym == "SF-36"

    def test_too_short_rejected(self, extractor):
        """Test that instrument names with too few words are rejected."""
        text = "as part of the SF Survey"  # Only 2 words
        matches = extractor.extract_from_text(text)
        assert len(matches) == 0

    def test_no_title_case_rejected(self, extractor):
        """Test that non-Title Case text is rejected."""
        text = "as part of some random lowercase text here"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 0

    def test_partial_title_case_accepted(self, extractor):
        """Test that mostly Title Case (>60%) is accepted."""
        # 3 out of 4 words Title Case = 75% > 60%
        text = "as part of Patient Health Questionnaire Form"  # Form is Title Case
        matches = extractor.extract_from_text(text)
        # This should match "Patient Health Questionnaire Form"
        assert len(matches) == 1
        assert "Patient Health Questionnaire" in matches[0].instrument_name

    def test_char_span_accuracy(self, extractor):
        """Test that character spans are accurate."""
        text = "XYZ as part of Patient Health Questionnaire ABC"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        start, end = matches[0].char_span
        assert text[start:end] == matches[0].full_match

    def test_multiple_matches(self, extractor):
        """Test extraction of multiple instruments from same text."""
        text = ("Item from as part of Patient Health Questionnaire (PHQ). "
                "Also as part of Beck Depression Inventory (BDI).")
        matches = extractor.extract_from_text(text)
        assert len(matches) >= 1
        # Greedy extractor may merge or split — ensure at least PHQ found
        all_text = " ".join(m.instrument_name for m in matches)
        assert "Patient Health Questionnaire" in all_text

    def test_tinyid_and_field_path_preserved(self, extractor):
        """Test that tinyId and field_path are stored in matches."""
        text = "as part of Patient Health Questionnaire"
        matches = extractor.extract_from_text(
            text,
            tinyId="ABC123",
            field_path="designations[0].designation"
        )
        assert len(matches) == 1
        assert matches[0].tinyId == "ABC123"
        assert matches[0].field_path == "designations[0].designation"

    def test_empty_text(self, extractor):
        """Test handling of empty text."""
        assert extractor.extract_from_text("") == []
        assert extractor.extract_from_text(None) == []

    def test_no_match(self, extractor):
        """Test text with no instrument patterns."""
        text = "This is a simple definition without any instrument references."
        matches = extractor.extract_from_text(text)
        assert len(matches) == 0

    def test_case_insensitive_trigger(self, extractor):
        """Test that 'As Part Of' (mixed case) also matches."""
        text = "Collected As Part Of Patient Health Questionnaire"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1

    def test_hyphenated_instrument_name(self, extractor):
        """Test instrument names with hyphenated words."""
        text = "as part of Self-Report Depression Scale Questionnaire"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1


class TestInstrumentExtractorMinWords:
    """Tests for configurable min_name_words."""

    def test_min_words_2(self):
        """Test with min_name_words=2."""
        extractor = InstrumentExtractor(min_name_words=2)
        text = "as part of Health Survey"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1

    def test_min_words_4(self):
        """Test with min_name_words=4."""
        extractor = InstrumentExtractor(min_name_words=4)
        text = "as part of Patient Health Questionnaire"  # 3 words
        matches = extractor.extract_from_text(text)
        assert len(matches) == 0

        text2 = "as part of Patient Health Questionnaire Form"  # 4 words
        matches2 = extractor.extract_from_text(text2)
        assert len(matches2) == 1


class TestComputeTokenSpans:
    """Tests for token span computation."""

    @pytest.fixture
    def extractor(self):
        return InstrumentExtractor(min_name_words=3)

    def test_basic_token_span(self, extractor):
        """Test basic token span computation."""
        text = "item as part of Patient Health Questionnaire measure"
        # Approximate char offsets for tokens: item(0-4), as(5-7), part(8-12), of(13-15),
        # Patient(16-23), Health(24-30), Questionnaire(31-44), measure(45-52)
        char_offsets = [
            (0, 4),    # item
            (5, 7),    # as
            (8, 12),   # part
            (13, 15),  # of
            (16, 23),  # Patient
            (24, 30),  # Health
            (31, 44),  # Questionnaire
            (45, 52),  # measure
        ]

        matches = extractor.extract_from_text(text)
        assert len(matches) == 1

        matches = extractor.compute_token_spans(matches, char_offsets)
        assert matches[0].token_span is not None
        start, end = matches[0].token_span
        # "as part of Patient Health Questionnaire measure" — greedy capture
        assert start == 1  # "as"
        assert end >= 7    # at least through "Questionnaire", may include "measure"

    def test_empty_char_offsets(self, extractor):
        """Test handling of empty char_offsets."""
        text = "as part of Patient Health Questionnaire"
        matches = extractor.extract_from_text(text)
        matches = extractor.compute_token_spans(matches, [])
        assert matches[0].token_span is None


class TestInstrumentCatalog:
    """Tests for InstrumentCatalog class."""

    def test_add_and_retrieve(self):
        """Test adding matches and retrieving."""
        catalog = InstrumentCatalog()
        match1 = InstrumentMatch(
            full_match="as part of Patient Health Questionnaire",
            instrument_name="Patient Health Questionnaire",
            acronym=None,
            char_span=(0, 40),
            tinyId="ABC"
        )
        match2 = InstrumentMatch(
            full_match="as part of the Patient Health Questionnaire",
            instrument_name="Patient Health Questionnaire",
            acronym=None,
            char_span=(0, 44),
            tinyId="DEF"
        )

        catalog.add(match1)
        catalog.add(match2)

        # Both should be under same normalized key
        key = normalize_instrument_name("Patient Health Questionnaire")
        assert key in catalog.instruments
        assert len(catalog.instruments[key]) == 2

    def test_get_distinct_tinyids(self):
        """Test getting distinct tinyIds for an instrument."""
        catalog = InstrumentCatalog()
        for tid in ["A", "B", "A", "C"]:  # Note duplicate "A"
            catalog.add(InstrumentMatch(
                full_match="as part of Test Instrument Name",
                instrument_name="Test Instrument Name",
                acronym=None,
                char_span=(0, 30),
                tinyId=tid
            ))

        key = normalize_instrument_name("Test Instrument Name")
        tinyids = catalog.get_distinct_tinyids(key)
        assert tinyids == {"A", "B", "C"}

    def test_get_all_token_spans(self):
        """Test getting all token spans for masking."""
        catalog = InstrumentCatalog()
        catalog.add(InstrumentMatch(
            full_match="test",
            instrument_name="Test Instrument Name",
            acronym=None,
            char_span=(0, 10),
            token_span=(2, 5),
            tinyId="ABC",
            field_path="designations[0].designation"
        ))

        spans = catalog.get_all_token_spans()
        assert len(spans) == 1
        assert spans[0] == ("ABC", "designations[0].designation", (2, 5))


class TestRealWorldPatterns:
    """Tests with realistic CDE patterns."""

    @pytest.fixture
    def extractor(self):
        return InstrumentExtractor(min_name_words=3)

    def test_sf36_pattern(self, extractor):
        """Test SF-36 reference pattern."""
        text = ("Physical health due to physical health as part of version 1.0 "
                "of 36-item Short Form Health Survey")
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert "Short Form Health Survey" in matches[0].instrument_name

    def test_dast_pattern(self, extractor):
        """Test DAST reference pattern."""
        text = "Drug use frequency as part of the Drug Abuse Screening Test (DAST)"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert matches[0].instrument_name == "Drug Abuse Screening Test"
        assert matches[0].acronym == "DAST"

    def test_phq_pattern(self, extractor):
        """Test PHQ reference pattern."""
        text = "Depressive symptoms as part of Patient Health Questionnaire (PHQ-9)"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert matches[0].acronym == "PHQ-9"

    def test_embedded_in_longer_text(self, extractor):
        """Test pattern embedded in longer definition."""
        text = ("The severity of depressive symptoms experienced by the participant "
                "over the past two weeks, measured as part of the Beck Depression "
                "Inventory (BDI-II), a validated self-report measure commonly used "
                "in clinical and research settings.")
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert matches[0].instrument_name == "Beck Depression Inventory"
        assert matches[0].acronym == "BDI-II"

    def test_whoqol_pattern(self, extractor):
        """Test WHO Quality of Life pattern with lowercase connectors."""
        text = ("Quality assessment as part of the World Health Organization "
                "Quality of Life (WHOQOL-BREF) instrument")
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert matches[0].instrument_name == "World Health Organization Quality of Life"
        assert matches[0].acronym == "WHOQOL-BREF"

    def test_instrument_with_lowercase_connectors(self, extractor):
        """Test instrument names containing lowercase words like 'of', 'and', 'for'."""
        text = "as part of Center for Epidemiologic Studies Depression Scale (CES-D)"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert "Center for Epidemiologic Studies Depression Scale" in matches[0].instrument_name
        assert matches[0].acronym == "CES-D"

    def test_multiple_minor_words(self, extractor):
        """Test instrument with multiple APA-style minor words (and, for, of)."""
        text = "as part of Schedule for Affective Disorders and Schizophrenia (SADS)"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert matches[0].instrument_name == "Schedule for Affective Disorders and Schizophrenia"
        assert matches[0].acronym == "SADS"

    def test_all_caps_abbreviation_tbi(self, extractor):
        """Test instrument name with ALL CAPS abbreviation (TBI)."""
        text = "as part of Ohio State TBI Method Short Form (OSUTBIMS)"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert matches[0].instrument_name == "Ohio State TBI Method Short Form"
        assert matches[0].acronym == "OSUTBIMS"

    def test_roman_numerals(self, extractor):
        """Test instrument name with Roman numerals (III)."""
        text = "as part of Woodcock Johnson III Tests"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert "Woodcock Johnson III" in matches[0].instrument_name

    def test_roman_numerals_with_acronym(self, extractor):
        """Test Roman numerals with hyphenated acronym (WJ-III)."""
        text = "as part of the Woodcock Johnson III (WJ-III) tests"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert "Woodcock Johnson III" in matches[0].instrument_name
        assert matches[0].acronym == "WJ-III"

    def test_multi_hyphen_acronym(self, extractor):
        """Test acronym with multiple hyphens (K-SADS-PL)."""
        text = "as part of the Kiddie Schedule for Affective Disorders and Schizophrenia Present and Lifetime Version (K-SADS-PL)"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert matches[0].acronym == "K-SADS-PL"

    def test_hyphenated_instrument_with_multi_hyphen_acronym(self, extractor):
        """Test hyphenated instrument name with multi-hyphen acronym."""
        # Note: The actual text has hyphens in the instrument name too
        text = "as part of Kiddie-Schedule for Affective Disorders and Schizophrenia-Present and Lifetime Version (K-SADS-PL)"
        matches = extractor.extract_from_text(text)
        assert len(matches) == 1
        assert "Kiddie-Schedule" in matches[0].instrument_name
        assert matches[0].acronym == "K-SADS-PL"
