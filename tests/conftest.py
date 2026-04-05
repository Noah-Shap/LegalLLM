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
def sample_brief_multi_section():
    """A brief with separate Statement of Facts and Procedural History sections."""
    return (
        "IN THE UNITED STATES COURT OF APPEALS\n"
        "FOR THE NINTH CIRCUIT\n\n"
        "I. STATEMENT OF FACTS\n\n"
        "On June 15, 2023, the plaintiff entered into a contract with "
        "defendant for the purchase of commercial real estate located "
        "at 123 Main Street. The contract specified a closing date of "
        "August 1, 2023. Prior to closing, an inspection revealed "
        "significant structural damage to the foundation that had not "
        "been disclosed by the seller. The plaintiff retained an expert "
        "who estimated repair costs at approximately two hundred "
        "thousand dollars. Despite repeated demands for disclosure of "
        "known defects, the defendant maintained that the property was "
        "in good condition. Several witnesses corroborated the poor "
        "condition of the building including the building inspector "
        "and two independent contractors.\n\n"
        "II. PROCEDURAL HISTORY\n\n"
        "The plaintiff filed suit on September 1, 2023 in the District "
        "Court for the Central District of California. The defendant "
        "moved to dismiss under Rule 12(b)(6), which was denied on "
        "November 15, 2023. Discovery proceeded through March 2024, "
        "during which time the defendant produced documents showing "
        "prior knowledge of the structural defects. The district court "
        "granted summary judgment in favor of the plaintiff on April "
        "30, 2024. The defendant timely appealed.\n\n"
        "III. ARGUMENT\n\n"
        "The district court correctly granted summary judgment because "
        "the undisputed evidence established fraudulent concealment. "
        "Under the applicable legal standard, a party seeking summary "
        "judgment must demonstrate that there is no genuine dispute as "
        "to any material fact and that the movant is entitled to judgment "
        "as a matter of law. Here, the record evidence overwhelmingly "
        "supports the trial court's conclusion. The defendant's own "
        "documents, produced during discovery, confirm that the defendant "
        "had actual knowledge of the structural defects prior to entering "
        "into the purchase agreement. The defendant's expert testimony "
        "was properly excluded as unreliable under Daubert, and the "
        "remaining evidence was insufficient to create a genuine dispute. "
        "The court's analysis of the fraud elements was thorough and "
        "well-supported by the record. We respectfully request that this "
        "Court affirm the judgment of the district court in all respects "
        "and award costs to the appellee.\n"
    )


@pytest.fixture
def sample_brief_counter_statement():
    """An appellee brief with COUNTER-STATEMENT OF FACTS heading."""
    return (
        "IN THE UNITED STATES COURT OF APPEALS\n"
        "FOR THE FIFTH CIRCUIT\n\n"
        "COUNTER-STATEMENT OF FACTS\n\n"
        "Appellee respectfully submits this counter-statement to correct "
        "several material misrepresentations in Appellant's brief. The "
        "record clearly shows that on March 1, 2023, the parties entered "
        "into a settlement agreement that was memorialized in writing. "
        "Appellant's characterization of the negotiations omits critical "
        "context provided by the contemporaneous correspondence between "
        "counsel. The evidence presented at the hearing demonstrated that "
        "both parties understood and agreed to the material terms of the "
        "settlement well before the formal written agreement was signed. "
        "Multiple depositions confirmed this understanding.\n\n"
        "ARGUMENT\n\n"
        "The judgment should be affirmed.\n"
    )


@pytest.fixture
def sample_brief_nature_of_case():
    """A state court brief using NATURE OF THE CASE heading."""
    return (
        "IN THE COURT OF APPEALS OF THE STATE OF NEW YORK\n\n"
        "NATURE OF THE CASE\n\n"
        "This is an action for personal injury arising from a slip and "
        "fall at the defendant's grocery store on December 10, 2022. "
        "The plaintiff, a 67-year-old retired teacher, suffered a broken "
        "hip and wrist when she slipped on water that had accumulated "
        "near the produce section. Store surveillance footage confirmed "
        "the hazardous condition had existed for at least forty-five "
        "minutes prior to the incident without any corrective action. "
        "The store manager testified that the floor was last inspected "
        "two hours before the incident. Medical records document three "
        "surgeries and ongoing physical therapy.\n\n"
        "STANDARD OF REVIEW\n\n"
        "The standard of review for this appeal is de novo.\n"
    )


@pytest.fixture
def sample_brief_introduction_factual():
    """A cert petition with a factual INTRODUCTION section."""
    return (
        "IN THE SUPREME COURT OF THE UNITED STATES\n\n"
        "INTRODUCTION\n\n"
        "This case presents the question whether the Fourth Amendment "
        "permits law enforcement to conduct a warrantless search of a "
        "vehicle parked in the curtilage of a home. On the morning of "
        "April 5, 2022, officers approached petitioner's residence and "
        "without a warrant lifted a tarp covering a motorcycle in the "
        "driveway to confirm its VIN number. The motorcycle had been "
        "reported stolen two weeks earlier. Petitioner was subsequently "
        "arrested and charged with receiving stolen property. The state "
        "trial court denied petitioner's motion to suppress, and the "
        "state supreme court affirmed, holding that the automobile "
        "exception to the warrant requirement applied regardless of "
        "the vehicle's location. This Court should grant certiorari "
        "to resolve the circuit split on this question.\n\n"
        "REASONS FOR GRANTING\n\n"
        "The petition should be granted.\n"
    )


@pytest.fixture
def sample_brief_introduction_argumentative():
    """A federal appellate opening brief with an argumentative INTRODUCTION."""
    return (
        "IN THE UNITED STATES COURT OF APPEALS\n"
        "FOR THE SEVENTH CIRCUIT\n\n"
        "INTRODUCTION\n\n"
        "We argue that the district court committed reversible error "
        "in granting summary judgment. This court should reverse because "
        "the standard of review was misapplied. For these reasons the "
        "judgment below cannot stand and must be vacated.\n\n"
        "STATEMENT OF FACTS\n\n"
        "On January 10, 2023, the appellant entered into a licensing "
        "agreement with the appellee for the use of patented technology. "
        "The agreement specified royalty payments of five percent on "
        "net sales. Over the next eighteen months, the appellee failed "
        "to make any royalty payments despite generating over ten million "
        "dollars in revenue from products incorporating the licensed "
        "technology. Internal communications produced during discovery "
        "revealed that appellee's executives were aware of the royalty "
        "obligation but deliberately chose not to pay.\n\n"
        "ARGUMENT\n\n"
        "The court below erred in its analysis.\n"
    )


@pytest.fixture
def sample_brief_very_long_facts():
    """A brief with an excessively long facts section (for max-length guardrail testing)."""
    # Generate a long facts section (~60k chars in a 70k char document).
    facts_body = "The following events occurred: " + "The record shows detailed proceedings over many months. " * 600
    return (
        "COVER PAGE AND CAPTION\n\n"
        "STATEMENT OF FACTS\n\n" + facts_body + "\n\nARGUMENT\n\n"
        "The judgment should be reversed.\n"
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
