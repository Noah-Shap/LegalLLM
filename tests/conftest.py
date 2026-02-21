import pytest


@pytest.fixture
def sample_brief_text():
    """A minimal mock brief with exact heading matches for facts extraction."""
    return (
        "IN THE UNITED STATES COURT OF APPEALS\n"
        "FOR THE THIRD CIRCUIT\n\n"
        "TABLE OF CONTENTS\n\n"
        "STATEMENT OF FACTS ............... 1\n"
        "ARGUMENT ......................... 10\n\n"
        "TABLE OF AUTHORITIES\n\n"
        "Some v. Case, 123 F.3d 456 (3d Cir. 2020)\n\n"
        "I. STATEMENT OF FACTS\n\n"
        "On January 1, 2024, Appellant filed a complaint alleging that "
        "Respondent violated 42 U.S.C. 1983. The district court held a "
        "hearing on March 15, 2024. Witness testimony established that "
        "the events occurred on the premises of Respondent. The court "
        "noted that 500 F.3d 100 supported the claim. Additional facts "
        "were presented including evidence from 300 U.S. 200 and the "
        "record showed that the defendant had prior knowledge of the "
        "situation as documented in various depositions and exhibits "
        "filed with the court over the course of several months of "
        "pre-trial proceedings and discovery disputes.\n\n"
        "II. ARGUMENT\n\n"
        "This Court should reverse because the lower court erred in "
        "its application of the standard of review. We argue that the "
        "district court abused its discretion.\n"
    )


@pytest.fixture
def sample_brief_soft_headings():
    """A brief that requires soft heading detection."""
    return (
        "IN THE COURT OF APPEALS\n\n"
        "A. FACTUAL OVERVIEW\n\n"
        "The plaintiff was injured on the premises. "
        "Multiple witnesses confirmed the incident occurred at noon. "
        "The defendant failed to maintain adequate safety measures "
        "despite being warned repeatedly about the hazardous conditions. "
        "Records from the building inspection showed numerous violations "
        "dating back several years before the incident in question.\n\n"
        "B. ARGUMENT AND ANALYSIS\n\n"
        "The court should find liability.\n"
    )


@pytest.fixture
def sample_pacer_stamp():
    """A PACER/ECF header stamp line."""
    return "Case 1:24-cv-00123-ABC Document 45 Filed 01/15/2024 Page 1 of 20 PageID #: 300"


@pytest.fixture
def sample_garbage_text():
    """Text that looks like broken PDF extraction."""
    return "/i255 /i128 /i064 /i032 /i255 " * 50


@pytest.fixture
def normal_english_text():
    """Normal English text with good alpha ratio."""
    return (
        "The Supreme Court of the United States held that the defendant "
        "was liable for damages arising from the breach of contract. "
        "The court noted that the evidence presented at trial clearly "
        "established that the defendant had knowledge of the terms and "
        "conditions of the agreement, and that the defendant willfully "
        "and intentionally violated those terms. The plaintiff presented "
        "testimony from multiple witnesses corroborating the claim."
    )
