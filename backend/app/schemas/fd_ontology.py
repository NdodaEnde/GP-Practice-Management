"""
Financial-Disclosure ontology — Pydantic schemas the LandingAI ADE model fills
from an Exxaro annual / sustainability / investor report.

Maps to the TBox in backend/database/mining_financial_disclosure_migration.sql.
Plan: /Users/luzuko/.claude/plans/lazy-churning-mccarthy.md (step 2a).

Design rules (carried from the build sheet at
SurgiScan-Exxaro-Transition-Intelligence-MVP-Spec.md §3 and the platform's
existing GP schemas in this directory):

* Every extracted entity / fact captures the surface_form the model saw,
  verbatim — NOT a canonical_id. fd_entity_resolver.py maps surface forms to
  the canonical-ID registry (with a 0.80 confidence gate, low matches go to
  fd_facts_needs_review). The model does not know our canonical IDs.

* Numeric figures emit BOTH value_raw (verbatim, e.g. "R3.5 billion") AND
  value_zar_m (normalized to ZAR millions). The mapper / eval harness can
  cross-check the conversion. Currency defaults to ZAR; explicit non-ZAR
  figures keep their original currency tag.

* Provenance (doc_id, page, char_start/end, quote) does NOT live inside these
  schemas. LandingAI's extraction_metadata returns per-field grounding
  (chunk refs → pages) alongside the extraction dict. fd_ontology_mapper.py
  reads that metadata to build fd_source_spans rows.

* "Funding path" linkages from Coal assets / FCF to capital funds are NEVER
  presented to the model as disclosed facts. They are extracted as
  StrategicNarrative entries — the company's own quoted assertions of
  strategic intent — and the mapper stamps them `strategically_attributed`
  (spec §3.3 hard rule). The schema deliberately has NO "funding_flow" model.

* All fields are Optional. The model emits whatever it finds; absent fields
  are not invented. This mirrors the GP pattern (see gp_vitals.py).
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================
# Leaf entity classes — each maps to one node table in the TBox.
# Every entity emits a `surface_form` (verbatim) for the entity resolver.
# ============================================================


class ExtractedOrg(BaseModel):
    """An organisation mentioned in the report (the issuer, a subsidiary, a holding co, a partner)."""

    surface_form: Optional[str] = Field(
        None,
        description=(
            "Exact text used to refer to this organisation in the report, e.g. "
            "'Exxaro Resources Limited', 'Ntsimbintle Holdings (Pty) Ltd', 'Cennergi'. "
            "Do NOT normalise or expand abbreviations — capture what was written."
        ),
    )
    org_type: Optional[str] = Field(
        None,
        description=(
            "Role of the organisation: 'Issuer' (the reporting company), 'HoldingCo' "
            "(a holding company through which other assets are owned), 'Subsidiary' "
            "(majority-owned operating subsidiary), 'Partner' (joint-venture or "
            "strategic partner). Leave blank if unclear."
        ),
    )


class ExtractedAsset(BaseModel):
    """A physical / operational asset (mine, plant, wind farm, etc.)."""

    surface_form: Optional[str] = Field(
        None,
        description=(
            "Exact text used to refer to the asset, e.g. 'Grootegeluk Coal Mine', "
            "'Matla Mine', 'Tshipi Borwa', 'Tsitsikamma Community Wind Farm'. "
            "Capture exactly as written — variant spellings carry information."
        ),
    )
    commodity: Optional[str] = Field(
        None,
        description=(
            "One of: 'Coal', 'Manganese', 'Renewable', 'Other'. 'Renewable' includes "
            "wind, solar, hydro. 'Other' for anything else (e.g. iron ore). Leave "
            "blank if the report does not state the commodity."
        ),
    )
    region: Optional[str] = Field(
        None,
        description=(
            "Geographic region or province as written, e.g. 'Limpopo', 'Mpumalanga', "
            "'Northern Cape'. Free text — do not normalise."
        ),
    )
    lifecycle: Optional[str] = Field(
        None,
        description=(
            "One of: 'Producing' (in operation), 'Acquired' (newly acquired this period), "
            "'Pipeline' (under development, not yet producing). Leave blank if unclear."
        ),
    )


class ExtractedCapitalFund(BaseModel):
    """A capital category / fund as the report uses the term (sustaining, expansion, diversification, etc.)."""

    surface_form: Optional[str] = Field(
        None,
        description=(
            "Exact name used by the report, e.g. 'Sustaining Capital', 'Expansion "
            "Capital', 'Diversification capex', 'Green Diversification Fund'. "
            "Capture the wording verbatim."
        ),
    )
    fund_type: Optional[str] = Field(
        None,
        description=(
            "One of: 'Sustaining' (replacement / maintenance capex), 'Expansion' "
            "(growth capex within existing segments), 'Diversification' (capital "
            "deployed into new commodities or new businesses). Leave blank if the "
            "report does not categorise it this way."
        ),
    )


class ExtractedStrategicPillar(BaseModel):
    """A strategic pillar / segment as the report names it (Coal Ops, Green Energy, Future Minerals, etc.)."""

    surface_form: Optional[str] = Field(
        None,
        description=(
            "Exact pillar / segment name from the report, e.g. 'Coal Operations', "
            "'Energy Solutions', 'Future Minerals', 'Manganese segment'."
        ),
    )


class ExtractedFinancialFact(BaseModel):
    """A single reported financial figure: who, what metric, how much, what fiscal year."""

    subject_surface_form: Optional[str] = Field(
        None,
        description=(
            "Verbatim text of the asset / segment / fund / org the figure is FOR — "
            "e.g. 'Grootegeluk', 'Energy business', 'Manganese segment'. If the "
            "figure is for the group as a whole, write 'Group' (or whatever the "
            "report uses)."
        ),
    )
    subject_type: Optional[str] = Field(
        None,
        description=(
            "One of: 'Asset', 'StrategicPillar', 'CapitalFund', 'Org'. Helps the "
            "mapper attach the FinancialFact to the right node table."
        ),
    )
    metric: Optional[str] = Field(
        None,
        description=(
            "One of: 'EBITDA', 'FCF' (free cash flow), 'CapEx' (capital expenditure), "
            "'RevenueGross' (revenue before any ownership weighting), 'AttributableEBITDA' "
            "(ownership-weighted by the report), 'NetProfit', 'OperatingProfit'. Leave "
            "blank if the metric is not standard; the mapper rejects unknown metrics."
        ),
    )
    value_raw: Optional[str] = Field(
        None,
        description=(
            "Verbatim figure as written, INCLUDING units and currency, e.g. 'R3,500m', "
            "'R3.5 billion', '$120m', 'R20 600 million'. The mapper cross-checks this "
            "against value_zar_m to catch unit-conversion errors."
        ),
    )
    value_zar_m: Optional[float] = Field(
        None,
        description=(
            "The figure normalised to ZAR MILLIONS. Convert from billions (×1000), "
            "from other currencies (if the report provides a stated rate), and from "
            "thousand-separator variants. Example: 'R3.5 billion' → 3500.0. Example: "
            "'R20 600 million' → 20600.0. "
            "PRECISION RULE: when the SAME metric / period appears in the document "
            "as BOTH a rounded form (e.g. 'R10.4 billion' in an executive summary) "
            "AND a precise figure (e.g. 'R10 423 million' in the financial-review "
            "prose or a waterfall chart), ALWAYS take the precise figure with more "
            "significant digits. The exec-summary rounding is a presentation choice; "
            "the financial-review precise figure is the authoritative one."
        ),
    )
    currency: Optional[str] = Field(
        "ZAR",
        description=(
            "ISO 4217 currency code of the original figure: 'ZAR' (default), 'USD', "
            "'EUR'. If the report provides a stated FX rate for conversion, the "
            "mapper applies it; otherwise non-ZAR figures are flagged."
        ),
    )
    fiscal_year: Optional[int] = Field(
        None,
        description=(
            "Fiscal year the figure relates to, as a 4-digit year. 'FY2024' or "
            "'year ended 31 December 2024' → 2024."
        ),
    )
    basis: Optional[str] = Field(
        "reported",
        description=(
            "'reported' = current period as originally disclosed. 'restated' = an "
            "earlier-period figure that has been restated in this report. The mapper "
            "creates a SUPERSEDES edge for restated values."
        ),
    )


class ExtractedESGFact(BaseModel):
    """A single ESG / sustainability metric (Scope1/2/3, carbon intensity, water, etc.)."""

    subject_surface_form: Optional[str] = Field(
        None,
        description="Asset / segment / org the ESG figure applies to. 'Group' if company-wide.",
    )
    subject_type: Optional[str] = Field(
        None,
        description="'Asset' | 'StrategicPillar' | 'Org'. Determines which node table the ESGFact links to.",
    )
    metric: Optional[str] = Field(
        None,
        description=(
            "One of: 'Scope1', 'Scope2', 'Scope3', 'CarbonIntensity', 'WaterUse', "
            "'WaterIntensity', 'EnergyUse', 'Waste'. Free text accepted; mapper "
            "normalises known variants."
        ),
    )
    value_raw: Optional[str] = Field(
        None,
        description="Verbatim figure with units, e.g. '1.2 Mt CO2e', '450 kt CO2e', '0.85 t CO2e/t product'.",
    )
    value: Optional[float] = Field(
        None,
        description="Numeric value, in the unit captured below.",
    )
    unit: Optional[str] = Field(
        None,
        description="Unit, e.g. 'tCO2e', 'ktCO2e', 'MtCO2e', 'm3', 'kWh', 'MWh', 'kg'.",
    )
    fiscal_year: Optional[int] = Field(None, description="Fiscal year (4-digit).")


class ExtractedAcquisition(BaseModel):
    """An acquisition / divestment / deal disclosed in the report."""

    surface_form: Optional[str] = Field(
        None,
        description=(
            "Name of the deal as referred to in the report, e.g. 'Kalahari Manganese "
            "acquisition', 'Cennergi acquisition'. NOT the asset being acquired — the "
            "deal itself."
        ),
    )
    target_surface_form: Optional[str] = Field(
        None,
        description="Name of the asset / company being acquired or divested.",
    )
    value_raw: Optional[str] = Field(
        None,
        description="Deal value as written, e.g. 'R11.67 billion', 'R10.6bn'.",
    )
    value_zar_m: Optional[float] = Field(
        None,
        description="Deal value normalised to ZAR millions.",
    )
    announced_date: Optional[str] = Field(
        None,
        description="Date announced, as written. Free text — the mapper parses ISO-8601 dates.",
    )
    status: Optional[str] = Field(
        None,
        description="'Announced' (signed but not yet closed) or 'Closed' (completed).",
    )


class ExtractedOwnershipFact(BaseModel):
    """
    An ownership / effective-stake fact — drives the OWNS edge.

    Spec §6.2: every 'derived' rollup (attributable revenue, attributable EBITDA)
    is gated on a sourced effective_pct. The fd_ontology_mapper REJECTS any
    OwnershipFact whose grounding metadata is empty — no source quote, no OWNS
    edge. The schema captures the SHAPE of the fact; the mapper enforces the
    provenance gate via the LandingAI extraction_metadata.
    """

    owner_surface_form: Optional[str] = Field(
        None,
        description=(
            "The entity that owns / holds the stake — typically 'Exxaro' or a "
            "subsidiary name. Verbatim text from the report."
        ),
    )
    owned_surface_form: Optional[str] = Field(
        None,
        description=(
            "The asset / company being owned, e.g. 'Tshipi Borwa Mine', 'Cennergi', "
            "'Belfast Mine'."
        ),
    )
    effective_pct: Optional[float] = Field(
        None,
        description=(
            "Effective ownership percentage as a decimal between 0 and 1, e.g. "
            "60.1% → 0.601, 100% → 1.0. If the report gives both 'beneficial' and "
            "'attributable' figures, prefer 'attributable / effective'. Leave blank "
            "if not explicitly stated."
        ),
    )
    valid_from_raw: Optional[str] = Field(
        None,
        description=(
            "When this ownership became effective, as written (e.g. 'closing on "
            "1 March 2024', 'effective FY2023'). The mapper parses to a DATE."
        ),
    )
    note: Optional[str] = Field(
        None,
        description=(
            "Any qualifier: 'through Ntsimbintle Holdings', 'subject to regulatory "
            "approval', etc. These can matter for the OWNS edge's `owned_via` link."
        ),
    )


class ExtractedStrategicNarrative(BaseModel):
    """
    A linkage the COMPANY ITSELF asserts as strategy — never a disclosed cash trace.

    Spec §3.3 hard rule: any flow from a Coal asset / coal cash to a green or
    diversification destination is `strategically_attributed`, never `disclosed`.
    Public reports allocate capital at group / segment level; cash is fungible.
    The schema captures the company's stated strategy *as a quote*, and the
    mapper stamps the resulting edge with assertion_type='strategically_attributed'
    plus the verbatim quote. No quote, no edge (spec §4.4: "No quote, no edge.").

    Example linkages this captures:
      - "Coal FCF funds the transition" (CapitalFund / Asset → Diversification fund)
      - "Diversification Fund finances Kalahari Manganese" (CapitalFund → Acquisition)
      - "Sustaining capex maintains Grootegeluk" (CapitalFund → Asset, sustaining)

    Whether the SAME shape would have been 'disclosed' depends on the destination —
    the mapper applies the stamping rule based on src/dst commodity + fund_type.
    """

    source_surface_form: Optional[str] = Field(
        None,
        description=(
            "What the company says the cash / capital is COMING FROM — e.g. 'coal "
            "operations', 'our cash flows', 'Grootegeluk', 'sustaining capital'."
        ),
    )
    destination_surface_form: Optional[str] = Field(
        None,
        description=(
            "What the company says the cash / capital is GOING TO — e.g. 'energy "
            "transition', 'renewables', 'Cennergi', 'Future Minerals', 'manganese "
            "diversification'."
        ),
    )
    relation: Optional[str] = Field(
        None,
        description=(
            "One of: 'ALLOCATED_TO' (cash → fund), 'FINANCES' (fund → asset / "
            "acquisition), 'GENERATES' (asset → cash, almost always 'disclosed'), "
            "'GOVERNED_BY' (fund → pillar). The mapper uses this to choose the edge "
            "type."
        ),
    )
    company_quote: Optional[str] = Field(
        None,
        description=(
            "The COMPANY'S exact words asserting this linkage, verbatim. Without "
            "this quote the mapper refuses to create the edge. Example: 'funded "
            "through cash generated by our coal operations'."
        ),
    )


class ExtractedRestatement(BaseModel):
    """A prior-period figure that this report restates. Drives the SUPERSEDES edge."""

    subject_surface_form: Optional[str] = Field(None, description="Asset / segment / org the figure is for.")
    metric: Optional[str] = Field(None, description="Metric being restated (EBITDA, FCF, etc.).")
    fiscal_year: Optional[int] = Field(None, description="Fiscal year of the figure being restated.")
    prior_value_raw: Optional[str] = Field(None, description="Original value as previously reported, verbatim.")
    restated_value_raw: Optional[str] = Field(None, description="New restated value, verbatim.")
    restated_value_zar_m: Optional[float] = Field(None, description="Restated value normalised to ZAR millions.")
    reason: Optional[str] = Field(None, description="Reason given for the restatement, if any.")


class ExtractedReportMetadata(BaseModel):
    """Identifying metadata about the report itself."""

    issuer_surface_form: Optional[str] = Field(None, description="The reporting company name, verbatim.")
    report_type: Optional[str] = Field(
        None,
        description="One of: 'integrated' (Integrated Annual Report), 'sustainability', 'investor' (Investor presentation / Pre-close trading update).",
    )
    fiscal_year: Optional[int] = Field(None, description="Fiscal year of the report (4-digit).")
    period_end_date: Optional[str] = Field(None, description="Period-end date, as written.")
    title: Optional[str] = Field(None, description="The report's official title, e.g. 'Integrated Report 2024'.")


# ============================================================
# Top-level extraction schema — one ADE extract call fills this whole tree.
# Mirrors the GPPatientRecordExtraction pattern (see gp_processor.py line 33).
# ============================================================


class FinancialDisclosureExtraction(BaseModel):
    """
    Single-call extraction target for the Financial-Disclosure module.

    LandingAI ADE returns this whole tree from one extract(schema=...) call,
    populated by what it finds in the report's parsed markdown. Plus per-field
    grounding metadata in extraction_metadata (which the mapper reads for
    provenance).

    Empty lists are normal — the model emits only what it finds. The mapper
    handles all of (a) entity resolution to canonical IDs, (b) assertion_type
    stamping, (c) SourceSpan creation from grounding metadata.
    """

    report_metadata: Optional[ExtractedReportMetadata] = Field(
        None,
        description="Identifying metadata for the report being extracted from. Always fill this.",
    )

    orgs: List[ExtractedOrg] = Field(
        default_factory=list,
        description=(
            "Every organisation mentioned: the issuer, subsidiaries, holding "
            "companies, joint-venture partners, acquired companies."
        ),
    )

    assets: List[ExtractedAsset] = Field(
        default_factory=list,
        description=(
            "Every physical / operational asset mentioned: mines, plants, wind "
            "farms, solar projects. Capture each verbatim surface form."
        ),
    )

    capital_funds: List[ExtractedCapitalFund] = Field(
        default_factory=list,
        description=(
            "Every capital category named in the report (sustaining, expansion, "
            "diversification, etc.). One row per distinct name; do NOT deduplicate "
            "synonyms (the entity resolver does that)."
        ),
    )

    strategic_pillars: List[ExtractedStrategicPillar] = Field(
        default_factory=list,
        description="Every strategic pillar / segment named in the report.",
    )

    financial_facts: List[ExtractedFinancialFact] = Field(
        default_factory=list,
        description=(
            "Every reported numerical financial figure: revenue, EBITDA, FCF, "
            "capex, etc., attached to its subject (asset / segment / group) and "
            "fiscal year. Each as a separate row."
        ),
    )

    esg_facts: List[ExtractedESGFact] = Field(
        default_factory=list,
        description="Every ESG / sustainability metric (emissions, water, energy, waste).",
    )

    acquisitions: List[ExtractedAcquisition] = Field(
        default_factory=list,
        description="Every acquisition / divestment disclosed in this period.",
    )

    ownership_facts: List[ExtractedOwnershipFact] = Field(
        default_factory=list,
        description=(
            "Every effective-ownership statement. ESSENTIAL for any 'derived' "
            "attributable-revenue calculation downstream — the mapper requires a "
            "sourced quote for each OWNS edge."
        ),
    )

    strategic_narratives: List[ExtractedStrategicNarrative] = Field(
        default_factory=list,
        description=(
            "Linkages the company asserts as strategy — typically Coal-cash → "
            "Diversification, Fund → Project. NEVER extract these as if they were "
            "ledger flows; the mapper will reject any narrative missing a "
            "company_quote and stamp the rest 'strategically_attributed'."
        ),
    )

    restatements: List[ExtractedRestatement] = Field(
        default_factory=list,
        description="Prior-period figures this report restates.",
    )
