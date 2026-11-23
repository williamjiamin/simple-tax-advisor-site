const FTA_CODES = new Set(["6651(a)(1)", "6651(a)(2)", "6651(a)(3)", "6656", "6698(a)(1)", "6699(a)(1)"]);
const AEP_FORMS = new Set(["1040", "1120", "1120-S", "1065", "940", "941", "CT-1"]);
const EMPLOYMENT_FORMS = new Set(["940", "941", "CT-1"]);
const EXCLUDED_FTA_FORMS = new Set(["706", "709", "990", "990-T", "5500", "other"]);

export function isTaxResearchEnabled({ queryString = "", settings = {}, env = {} } = {}) {
  const params = new URLSearchParams(String(queryString).replace(/^\?/, ""));
  if (params.get("tax_research") === "off") return false;
  if (settings["tax_research/enabled"] === false) return false;
  const raw = String(env.TAX_RESEARCH_DISABLED ?? "").trim().toLowerCase();
  return !["1", "true", "yes", "on"].includes(raw);
}

export function evaluateTaxAuthority(record, categories, context = {}) {
  const kind = record.kind;
  const category = categories.find((c) => c.kind === kind);
  if (!category) {
    throw new Error(`Unknown authority category: ${kind}`);
  }
  const asOf = context.asOf || "2026-11-22";
  const purpose = context.purpose || "substantial_authority";
  const circuit = context.circuit || "unknown";
  const issuedOn = record.issuedOn || record.issued_on || null;
  const sameTaxpayer = record.sameTaxpayer ?? record.same_taxpayer ?? null;
  const faqLinked = record.faqLinkedNewsRelease ?? record.faq_linked_news_release ?? null;
  const issueMatch = record.issueMatch || record.issue_match || "unknown";
  const appliesToPeriod = record.appliesToPeriod ?? record.applies_to_period ?? null;
  const status = record.status || "current";

  const gaps = [];
  const cautions = [];
  const reasons = [];
  let excluded = false;

  if (status !== "current" || appliesToPeriod === false) {
    excluded = true;
    reasons.push("Current-law reliance is blocked by supplied status or period facts; preserve historical context separately.");
  }
  if (issuedOn && issuedOn > asOf) {
    excluded = true;
    reasons.push("The source was issued after the supplied research date.");
  }
  if (appliesToPeriod === null) {
    gaps.push("Verify period applicability and effective dates.");
  }

  let role = category.legal_role;
  let courtPriority = 1;
  if (kind === "supreme_court") {
    role = "potential_nationwide_controlling_interpretation";
    courtPriority = 0;
  } else if (kind === "circuit_court") {
    const srcCircuit = record.circuit || "unknown";
    if (circuit === "unknown" || srcCircuit === "unknown") {
      role = "jurisdiction_requires_review";
      gaps.push("Identify the appellate circuit that would review this dispute.");
    } else if (srcCircuit === circuit) {
      role = "potential_controlling_appellate_interpretation";
      courtPriority = purpose === "merits" ? 0 : 1;
    } else {
      role = "potential_persuasive_judicial_interpretation";
    }
    if (purpose === "substantial_authority") {
      cautions.push("Geographic applicability is generally disregarded for the regulatory weight test; appellate control follows a separate rule.");
    }
  } else if (kind === "tax_court_summary") {
    role = "nonprecedential_small_case_decision";
  } else if (kind === "plr" || kind === "tam") {
    role = "taxpayer_specific_nonprecedential_determination";
    if (sameTaxpayer === null) {
      gaps.push("Determine whether the ruling addresses this taxpayer and facts.");
    }
    cautions.push("Public inspection does not convert a written determination into binding precedent for unrelated taxpayers.");
  }

  if (kind === "cca") {
    cautions.push("Chief Counsel Advice is nonprecedential and is not expressly enumerated as a separate item in 26 CFR 1.6662-4.");
  }
  if (kind === "irm" || kind === "publication") {
    cautions.push("Operational manuals and publications do not override controlling statutes, regulations, or judicial decisions.");
  }
  if (record.conflictingAuthority !== false) {
    gaps.push("Check and document adverse or contrary authorities.");
  }

  let substantial = category.substantial_authority_use;
  if (kind === "plr" || kind === "tam") {
    if (sameTaxpayer === true) {
      substantial = "taxpayer_specific_written_determination_special_rule_review";
      gaps.push("Verify written-determination reliance conditions and factual accuracy under the special regulatory rule.");
    } else if (!issuedOn) {
      substantial = "issuance_date_required";
      gaps.push("Confirm issuance date against the 1976-11-01 boundary.");
    } else if (issuedOn >= "1976-11-01") {
      substantial = "enumerated_nonprecedential_material_subject_to_weight_analysis";
    } else {
      substantial = "not_within_enumerated_post_1976_category";
    }
  } else if (kind === "faq") {
    if (faqLinked === true) {
      substantial = "qualifying_fact_sheet_faq_penalty_authority_review";
    } else if (faqLinked === null) {
      substantial = "fact_sheet_news_release_link_requires_verification";
      gaps.push("Verify whether the FAQ belongs to a Fact Sheet linked to an agency news release.");
    } else {
      substantial = "ordinary_faq_not_substantial_authority_by_itself";
    }
    cautions.push("Fact Sheet FAQ penalty protection does not make an FAQ binding substantive law.");
  }

  if (excluded) {
    substantial = "blocked_by_screening_facts";
  }
  if (issueMatch === "remote") {
    cautions.push("Remote factual relevance carries little weight regardless of source tier.");
  }
  reasons.push("Weigh supporting and opposing authorities together; editorial priority orders research without numeric legal probability.");

  const tier = excluded ? 3 : gaps.length > 0 ? 2 : courtPriority;
  return {
    kind,
    label: category.label,
    branch: category.branch,
    purpose,
    screeningStatus: excluded ? "exclude_current_reliance" : gaps.length > 0 ? "review_required" : "ready_for_analysis",
    legalRole: role,
    substantialAuthorityUse: substantial,
    editorialPriority: category.research_priority,
    sortTier: tier,
    missingEvidence: gaps,
    reasons,
    cautions,
    sourceIds: [...category.source_ids],
    legalConclusion: "not_determined",
    probability: null,
  };
}

function addThreeYearsIso(isoDate) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(isoDate || ""))) return null;
  const [y, m, d] = isoDate.split("-").map(Number);
  if (m === 2 && d === 29) return null; // Leap-day anniversary requires manual verification
  return `${String(y + 3).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

export function assessPenaltyRelief(input) {
  const penaltyCode = input.penalty_code || "6651(a)(1)";
  const returnForm = input.return_form || "1040";
  const taxYear = Number(input.tax_year || 2025);
  const dueDate = input.original_due_date || null;
  const receivedDate = input.received_date || null;
  const historyClean = input.history_clean;
  const history = Array.isArray(input.history) ? input.history : null;

  const evalHistory = (missing, failures, { aep }) => {
    if (typeof historyClean === "boolean") {
      if (!historyClean) {
        failures.push("Prior lookback history records a disqualifying penalty or missing required filing");
      }
    } else if (history) {
      for (const row of history) {
        if (row.filing === "unknown") missing.push(`history.${row.period}.filing`);
        else if (row.filing === "missing") failures.push(`history.${row.period}: missing required return`);
        else if (row.filing === "late" && !["abated_reasonable_cause", "abated_irs_error"].includes(row.penalty)) {
          if (["1120", "1120-S"].includes(returnForm) && !aep) {
            failures.push(`history.${row.period}: prior corporate late filing precludes FTA`);
          } else {
            missing.push(`history.${row.period}.late_filing_account_review`);
          }
        }
        if (row.penalty === "unknown") missing.push(`history.${row.period}.penalty`);
        else if (["prior_fta", "prior_aep", "tolerance", "unreversed"].includes(row.penalty)) {
          failures.push(`history.${row.period}: disqualifying prior relief or unreversed penalty`);
        }
      }
    } else {
      missing.push("history");
    }
    if (input.related_accounts_reviewed !== true) {
      missing.push("related_accounts_reviewed");
    }
  };

  // 1. Assessment correction screen
  let correction = {
    status: "not_applicable",
    reasons: ["No assessment error is asserted in the supplied facts"],
    missingEvidence: [],
    citations: ["PEN_FTA_IRM"],
  };
  if (input.irs_error === true || input.penalty_factually_valid === false) {
    correction = {
      status: "eligible",
      reasons: ["Correct erroneous or invalid assessment first without consuming FTA or AEP"],
      missingEvidence: [],
      citations: ["PEN_FTA_IRM"],
    };
  }

  // 2. Legacy FTA screen
  let fta;
  if (!FTA_CODES.has(penaltyCode)) {
    fta = { status: "not_applicable", reasons: ["Penalty provision is outside FTA scope"], missingEvidence: [], citations: ["PEN_FTA_IRM", "PEN_FTA_COMPLIANCE"] };
  } else if (correction.status === "eligible") {
    fta = { status: "not_applicable", reasons: ["Erroneous assessment must be corrected first"], missingEvidence: [], citations: ["PEN_FTA_IRM"] };
  } else if (EXCLUDED_FTA_FORMS.has(returnForm)) {
    fta = { status: "not_applicable", reasons: ["Form type is outside legacy FTA scope"], missingEvidence: [], citations: ["PEN_FTA_IRM"] };
  } else if (dueDate && dueDate >= "2027-01-01") {
    fta = { status: "not_applicable", reasons: ["FTA is replaced by AEP for covered original return due dates on or after 2027-01-01"], missingEvidence: [], citations: ["PEN_AEP_FACT", "PEN_AEP_UPDATE"] };
  } else {
    const missing = [];
    const failures = [];
    const transition = taxYear >= (returnForm === "941" ? 2026 : 2025);
    if (transition && input.aep_considered === true) {
      fta = { status: "not_applicable", reasons: ["AEP was already considered on this transition return"], missingEvidence: [], citations: ["PEN_AEP_FACT", "PEN_AEP_UPDATE"] };
    } else {
      if (transition && input.aep_considered == null) missing.push("aep_considered");
      evalHistory(missing, failures, { aep: false });
      if (input.currently_required_returns_filed_or_extended === false) failures.push("currently_required_returns_filed_or_extended is not met");
      else if (input.currently_required_returns_filed_or_extended == null) missing.push("currently_required_returns_filed_or_extended");
      if (input.paid_or_arranged_to_pay === false) failures.push("paid_or_arranged_to_pay is not met");
      else if (input.paid_or_arranged_to_pay == null) missing.push("paid_or_arranged_to_pay");
      if (EMPLOYMENT_FORMS.has(returnForm) || ["1065", "1120", "1120-S"].includes(returnForm)) {
        if ((input.deposit_waivers ?? 0) >= 4) failures.push("Four or more deposit waivers in lookback");
        if (input.electronic_deposit_avoidance === "all") failures.push("Electronic-deposit avoidance accounts for all deposit penalty");
      }
      if (failures.length) {
        fta = { status: "not_eligible", reasons: failures, missingEvidence: missing, citations: ["PEN_FTA_IRM", "PEN_FTA_COMPLIANCE"] };
      } else if (missing.length) {
        fta = { status: "review_required", reasons: ["Complete required filing, payment, and transcript history checks before FTA decision"], missingEvidence: missing, citations: ["PEN_FTA_IRM", "PEN_FTA_COMPLIANCE"] };
      } else {
        fta = { status: "eligible", reasons: ["Legacy FTA screening criteria are satisfied; IRS account confirmation still applies"], missingEvidence: [], citations: ["PEN_FTA_IRM", "PEN_FTA_COMPLIANCE"] };
      }
    }
  }

  // 3. 2026+ Administrative Exemption Process (AEP) screen
  let aep;
  const aepCutoffYear = returnForm === "941" ? 2026 : 2025;
  if (!FTA_CODES.has(penaltyCode) || !AEP_FORMS.has(returnForm)) {
    aep = { status: "not_applicable", reasons: ["Penalty or return form is outside AEP eligibility list"], missingEvidence: [], citations: ["PEN_AEP_UPDATE"] };
  } else if (taxYear < aepCutoffYear) {
    aep = { status: "not_applicable", reasons: ["Tax period precedes the AEP transition boundary"], missingEvidence: [], citations: ["PEN_AEP_FACT"] };
  } else if (correction.status === "eligible") {
    aep = { status: "not_applicable", reasons: ["Correct invalid assessment first rather than consuming AEP"], missingEvidence: [], citations: ["PEN_AEP_UPDATE"] };
  } else {
    const missing = [];
    const failures = [];
    if (input.is_original_return === false) failures.push("AEP applies to eligible original returns only");
    else if (input.is_original_return == null) missing.push("is_original_return");
    const deadline = addThreeYearsIso(dueDate);
    if (dueDate && receivedDate && deadline === null) {
      missing.push("three_year_window_leap_day_review");
    } else if (deadline && receivedDate && receivedDate > deadline) {
      failures.push("Original return received more than three years after original due date (extension ignored)");
    } else if (!dueDate || !receivedDate) {
      if (!dueDate) missing.push("original_due_date");
      if (!receivedDate) missing.push("received_date");
    }
    evalHistory(missing, failures, { aep: true });
    if (input.aep_transcript_verified !== true) missing.push("aep_transcript_verified");
    if (input.aep_considered === false) missing.push("aep_original_processing_or_manual_error_review");
    else if (input.aep_considered == null) missing.push("aep_considered");
    if (EMPLOYMENT_FORMS.has(returnForm) && input.electronic_deposit_avoidance === "partial") {
      failures.push("Deposit penalty includes electronic-deposit avoidance under AEP");
    }
    if (failures.length) {
      aep = { status: "not_eligible", reasons: failures, missingEvidence: missing, citations: ["PEN_AEP_UPDATE", "PEN_AEP_FACT"] };
    } else if (missing.length) {
      aep = { status: "review_required", reasons: ["Verify original return processing, 3-yr window, and transcript indicators (never infer clean compliance from missing transcripts)"], missingEvidence: missing, citations: ["PEN_AEP_UPDATE", "PEN_AEP_FACT"] };
    } else {
      aep = { status: "eligible", reasons: ["Implemented 2026 AEP screening criteria are met for original-return processing"], missingEvidence: [], citations: ["PEN_AEP_UPDATE", "PEN_AEP_FACT", "PEN_AEP_PUBLIC"] };
    }
  }

  // 4. Reasonable Cause route
  const reasonableCause =
    penaltyCode === "6654"
      ? { status: "not_applicable", reasons: ["IRC Sec. 6654 has no general reasonable-cause exception; test Sec. 6654(e)(3) statutory waiver instead"], missingEvidence: [], citations: ["PEN_6654_STAT", "PEN_6654_IRM"] }
      : { status: "review_required", reasons: ["Evaluate ordinary business care and prudence, causal link, supporting contemporaneous records, and prompt correction"], missingEvidence: ["rc.ordinary_care", "rc.causal_link", "rc.supporting_records", "rc.prompt_correction"], citations: ["PEN_RC_PUBLIC", "PEN_RC_REG"] };

  // 5. Statutory estimated tax route
  const estimated =
    penaltyCode === "6654"
      ? { status: "review_required", reasons: ["Screen Sec. 6654(e)(3) casualty/disaster, unusual circumstances, or recent retirement/disability"], missingEvidence: ["estimated.statutory_basis"], citations: ["PEN_6654_STAT", "PEN_6654_IRM"] }
      : { status: "not_applicable", reasons: ["Specific to individual estimated tax penalty Sec. 6654"], missingEvidence: [], citations: ["PEN_6654_STAT"] };

  const order = [
    ["correction", correction],
    ["aep", aep],
    ["fta", fta],
    ["reasonable_cause", reasonableCause],
    ["estimated", estimated],
  ];
  const preferredRoute =
    order.find(([, r]) => r.status === "eligible")?.[0] ||
    order.find(([, r]) => r.status === "review_required")?.[0] ||
    "reasonable_cause";

  return {
    penaltyCode,
    returnForm,
    taxYear,
    preferredRoute,
    routes: { correction, fta, aep, reasonable_cause: reasonableCause, estimated },
  };
}

export function filterVerifiedSources(sources, { query = "", sourceType = "all" } = {}) {
  const q = String(query || "").trim().toLowerCase();
  return sources.filter((src) => {
    if (sourceType !== "all" && src.source_type !== sourceType) return false;
    if (!q) return true;
    const hay = `${src.id} ${src.title} ${src.pinpoint} ${src.summary} ${src.legal_status}`.toLowerCase();
    return hay.includes(q);
  });
}
