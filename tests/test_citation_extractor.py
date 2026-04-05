"""Tests for legallm.citation_extractor module."""

from legallm.citation_extractor import (
    ExtractedCitation,
    citation_summary,
    deduplicate_case_citations,
    extract_citations,
    mask_citations,
    normalize_citation,
)

# ============================================================================
# Citation extraction
# ============================================================================


class TestExtractCitations:
    def test_basic_us_citation(self):
        text = "The Court held in 500 U.S. 100 (1990) that the statute was valid."
        result = extract_citations(text)
        assert len(result.case_citations) >= 1
        cite = result.case_citations[0]
        assert cite.volume == "500"
        assert cite.page == "100"
        assert cite.target_type == "case"

    def test_federal_reporter_citation(self):
        text = "As discussed in 123 F.3d 456 (9th Cir. 2020), the standard applies."
        result = extract_citations(text)
        assert len(result.case_citations) >= 1
        cite = result.case_citations[0]
        assert cite.volume == "123"
        assert cite.page == "456"
        assert cite.court_year is not None
        assert "9th Cir" in cite.court_year

    def test_f_supp_citation(self):
        text = "The district court in 789 F. Supp. 2d 100 (S.D.N.Y. 2015) found that."
        result = extract_citations(text)
        assert len(result.case_citations) >= 1

    def test_multiple_citations(self):
        text = "See 500 U.S. 100 (1990); see also 123 F.3d 456 (9th Cir. 2020) and 300 U.S. 200 (1985)."
        result = extract_citations(text)
        assert len(result.case_citations) >= 3

    def test_case_name_extraction(self):
        text = "In Smith v. Jones, 500 U.S. 100 (1990), the Court held that."
        result = extract_citations(text)
        assert len(result.case_citations) >= 1
        cite = result.case_citations[0]
        assert cite.case_name is not None
        assert "Smith" in cite.case_name
        assert "Jones" in cite.case_name

    def test_in_re_case_name(self):
        text = "In In re Estate of Williams, 300 F.3d 500 (5th Cir. 2002), the court found."
        result = extract_citations(text)
        assert len(result.case_citations) >= 1

    def test_short_form_citations(self):
        text = "As noted above, Id. at 105. See also supra at 200."
        result = extract_citations(text)
        assert result.short_form_count >= 1
        short_forms = [c for c in result.citations if c.target_type == "short_form"]
        assert len(short_forms) >= 1
        assert short_forms[0].excluded_reason == "context_dependent_short_form"
        assert short_forms[0].resolution_status == "excluded"

    def test_statute_citations(self):
        text = "Pursuant to 42 U.S.C. § 1983, the plaintiff brought this action."
        result = extract_citations(text)
        assert result.statute_count >= 1
        statutes = [c for c in result.citations if c.target_type == "statute"]
        assert len(statutes) >= 1
        assert statutes[0].excluded_reason == "non_case_reference"

    def test_no_citations(self):
        text = "The plaintiff walked into the store and slipped on a wet floor."
        result = extract_citations(text)
        assert len(result.case_citations) == 0
        assert result.short_form_count == 0

    def test_empty_text(self):
        result = extract_citations("")
        assert len(result.citations) == 0

    def test_citations_sorted_by_position(self):
        text = "See 500 U.S. 100 and also 300 U.S. 200 and then 400 U.S. 300."
        result = extract_citations(text)
        positions = [c.start for c in result.citations]
        assert positions == sorted(positions)

    def test_state_reporter_citation(self):
        text = "The court held in 150 N.E.2d 300 (1958) that."
        result = extract_citations(text)
        assert len(result.case_citations) >= 1

    def test_citation_with_pincite(self):
        text = "As stated in 500 U.S. 100, 115 (1990), the rule is clear."
        result = extract_citations(text)
        assert len(result.case_citations) >= 1


# ============================================================================
# Normalization
# ============================================================================


class TestNormalization:
    def test_normalize_us_reporter(self):
        assert normalize_citation("500", "U.S.", "100") == "500 U.S. 100"

    def test_normalize_f3d(self):
        result = normalize_citation("123", "F. 3d", "456")
        assert result == "123 F.3d 456"

    def test_normalize_f_supp_2d(self):
        result = normalize_citation("789", "F. Supp. 2d", "100")
        assert result == "789 F.Supp.2d 100"

    def test_normalize_sct(self):
        result = normalize_citation("130", "S. Ct.", "2000")
        assert result == "130 S.Ct. 2000"

    def test_normalize_ne2d(self):
        result = normalize_citation("150", "N.E. 2d", "300")
        assert result == "150 N.E.2d 300"


# ============================================================================
# Deduplication
# ============================================================================


class TestDeduplication:
    def test_exact_duplicate_removed(self):
        cite1 = ExtractedCitation(
            original_text="500 U.S. 100",
            start=0,
            end=12,
            target_type="case",
            volume="500",
            reporter="U.S.",
            page="100",
            normalized="500 U.S. 100",
        )
        cite2 = ExtractedCitation(
            original_text="500 U.S. 100 (1990)",
            start=50,
            end=70,
            target_type="case",
            volume="500",
            reporter="U.S.",
            page="100",
            normalized="500 U.S. 100",
        )
        result = deduplicate_case_citations([cite1, cite2])
        assert len(result) == 1

    def test_different_citations_kept(self):
        cite1 = ExtractedCitation(
            original_text="500 U.S. 100",
            start=0,
            end=12,
            target_type="case",
            volume="500",
            reporter="U.S.",
            page="100",
            normalized="500 U.S. 100",
        )
        cite2 = ExtractedCitation(
            original_text="300 F.3d 200",
            start=50,
            end=62,
            target_type="case",
            volume="300",
            reporter="F.3d",
            page="200",
            normalized="300 F.3d 200",
        )
        result = deduplicate_case_citations([cite1, cite2])
        assert len(result) == 2

    def test_empty_list(self):
        assert deduplicate_case_citations([]) == []

    def test_higher_priority_reporter_preferred(self):
        # U.S. should be preferred over S.Ct. for same cite
        cite_us = ExtractedCitation(
            original_text="500 U.S. 100",
            start=0,
            end=12,
            target_type="case",
            volume="500",
            reporter="U.S.",
            page="100",
            normalized="500 U.S. 100",
        )
        cite_sct = ExtractedCitation(
            original_text="110 S.Ct. 2000",
            start=50,
            end=65,
            target_type="case",
            volume="110",
            reporter="S.Ct.",
            page="2000",
            normalized="110 S.Ct. 2000",
        )
        result = deduplicate_case_citations([cite_us, cite_sct])
        # These are different citations (different normalized forms), both kept
        assert len(result) == 2


# ============================================================================
# Citation masking
# ============================================================================


class TestMaskCitations:
    def test_basic_masking(self):
        text = "The Court held in 500 U.S. 100 (1990) that the statute was valid."
        masked = mask_citations(text)
        assert "[CITATION]" in masked
        assert "500 U.S. 100" not in masked

    def test_multiple_citations_masked(self):
        text = "See 500 U.S. 100 and 123 F.3d 456."
        masked = mask_citations(text)
        assert masked.count("[CITATION]") >= 2

    def test_no_citations_unchanged(self):
        text = "The plaintiff walked into the store."
        assert mask_citations(text) == text

    def test_empty_text(self):
        assert mask_citations("") == ""

    def test_case_name_included_in_mask(self):
        text = "In Smith v. Jones, 500 U.S. 100 (1990), the Court held."
        masked = mask_citations(text)
        assert "Smith v. Jones" not in masked
        assert "[CITATION]" in masked

    def test_short_form_masked(self):
        text = "As noted in 500 U.S. 100. See also Id. at 105."
        masked = mask_citations(text)
        assert "Id." not in masked

    def test_custom_replacement(self):
        text = "The Court held in 500 U.S. 100 (1990) that."
        masked = mask_citations(text, replacement="<CITE>")
        assert "<CITE>" in masked
        assert "500 U.S. 100" not in masked

    def test_statute_not_masked(self):
        text = "Pursuant to 42 U.S.C. § 1983, the claim is valid."
        masked = mask_citations(text)
        # Statutes should not be masked (only case citations)
        assert "42 U.S.C." in masked


# ============================================================================
# Citation summary
# ============================================================================


class TestCitationSummary:
    def test_summary_fields(self):
        text = "See 500 U.S. 100 (1990) and 123 F.3d 456. Id. at 200."
        result = extract_citations(text)
        summary = citation_summary(result)
        assert "total_citations" in summary
        assert "case_citations" in summary
        assert "unique_case_citations" in summary
        assert "short_form_count" in summary
        assert "statute_count" in summary
        assert "secondary_count" in summary
        assert "normalized_case_cites" in summary
        assert isinstance(summary["normalized_case_cites"], list)

    def test_empty_summary(self):
        result = extract_citations("")
        summary = citation_summary(result)
        assert summary["total_citations"] == 0
        assert summary["case_citations"] == 0
