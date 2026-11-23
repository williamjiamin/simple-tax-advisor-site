import {
  assessPenaltyRelief,
  evaluateTaxAuthority,
  filterVerifiedSources,
  isTaxResearchEnabled,
} from "./tax-research-verifier.mjs";

const rootEl = document.getElementById("tax-research-root");
const disabledEl = document.getElementById("tax-research-disabled");

if (!isTaxResearchEnabled({ queryString: window.location.search })) {
  if (rootEl) rootEl.hidden = true;
  if (disabledEl) disabledEl.hidden = false;
} else {
  const [authorityModel, penaltyMatrix, sourcesPayload, cardsPayload, questionsPayload] =
    await Promise.all([
      fetch("../data/tax_research/authority_model.json").then((r) => r.json()),
      fetch("../data/tax_research/penalty_matrix.json").then((r) => r.json()),
      fetch("../data/tax_research/sources.json").then((r) => r.json()),
      fetch("../data/tax_research/reference_cards.json").then((r) => r.json()),
      fetch("../data/tax_research/questions.json").then((r) => r.json()),
    ]);

  const categories = authorityModel.categories;
  const sources = sourcesPayload.sources;
  const questions = questionsPayload.questions;

  // 1. Populate authority selector & render live role/weight evaluator
  const kindSel = document.getElementById("auth-kind");
  for (const cat of categories) {
    const opt = document.createElement("option");
    opt.value = cat.kind;
    opt.textContent = `[P${cat.research_priority}] ${cat.label} (${cat.branch})`;
    kindSel.appendChild(opt);
  }
  kindSel.value = "plr";

  const authInputs = [
    kindSel,
    document.getElementById("auth-purpose"),
    document.getElementById("auth-issued"),
    document.getElementById("auth-same-taxpayer"),
    document.getElementById("auth-faq-linked"),
    document.getElementById("auth-match"),
  ];
  const authOut = document.getElementById("auth-eval-output");

  function renderAuthEval() {
    const sameRaw = document.getElementById("auth-same-taxpayer").value;
    const faqRaw = document.getElementById("auth-faq-linked").value;
    const res = evaluateTaxAuthority(
      {
        kind: kindSel.value,
        issuedOn: document.getElementById("auth-issued").value || null,
        sameTaxpayer: sameRaw === "unknown" ? null : sameRaw === "yes",
        faqLinkedNewsRelease: faqRaw === "unknown" ? null : faqRaw === "yes",
        issueMatch: document.getElementById("auth-match").value,
        appliesToPeriod: true,
        conflictingAuthority: false,
      },
      categories,
      { purpose: document.getElementById("auth-purpose").value, circuit: "ninth" },
    );
    authOut.innerHTML = `
      <div class="result"><span>Screening Status</span><strong>${res.screeningStatus}</strong><small>Editorial priority ${res.editorialPriority} · Tier ${res.sortTier}</small></div>
      <div class="result"><span>Legal Role</span><strong>${res.legalRole.replace(/_/g, " ")}</strong><small>Judicial/statutory classification kept separate from penalty score</small></div>
      <div class="result"><span>26 CFR 1.6662-4 Use</span><strong>${res.substantialAuthorityUse.replace(/_/g, " ")}</strong><small>Legal conclusion: ${res.legalConclusion}</small></div>
      ${res.cautions.length || res.missingEvidence.length ? `<div class="notice" style="grid-column:1/-1">${[...res.missingEvidence.map((m) => `Verify: ${m}`), ...res.cautions].join(" · ")}</div>` : ""}
    `;
  }
  for (const el of authInputs) el.addEventListener("change", renderAuthEval);
  renderAuthEval();

  // 2. Render 37 Official Sources register with search & type filter
  const srcQueryEl = document.getElementById("source-search");
  const srcTypeEl = document.getElementById("source-type");
  const srcCountEl = document.getElementById("source-count");
  const srcListEl = document.getElementById("source-list");

  function renderSources() {
    const list = filterVerifiedSources(sources, {
      query: srcQueryEl.value,
      sourceType: srcTypeEl.value,
    });
    srcCountEl.textContent = `${list.length} of ${sources.length} verified primary sources shown (checked ${sourcesPayload.research_as_of})`;
    srcListEl.innerHTML = list
      .map(
        (s) => `
        <article class="result">
          <span class="eyebrow">${s.id} · ${s.source_type.toUpperCase()} · ${s.pinpoint}</span>
          <h3 style="margin:6px 0 4px;font-size:1.02rem"><a href="${s.url}" target="_blank" rel="noreferrer">${s.title}</a></h3>
          <p style="margin:4px 0;font-size:.9rem">${s.summary}</p>
          <small style="color:#52647b">Caution: ${s.limitations}</small>
        </article>`,
      )
      .join("");
  }
  srcQueryEl.addEventListener("input", renderSources);
  srcTypeEl.addEventListener("change", renderSources);
  renderSources();

  // 3. Penalty Relief & 2026 AEP vs 2027 FTA Transition Screener
  const pFormEl = document.getElementById("pen-form");
  const pCodeEl = document.getElementById("pen-code");
  const pYearEl = document.getElementById("pen-year");
  const pDueEl = document.getElementById("pen-due");
  const pRecEl = document.getElementById("pen-received");
  const pHistoryEl = document.getElementById("pen-history");
  const pTranscriptEl = document.getElementById("pen-transcript");
  const pAepEl = document.getElementById("pen-aep-considered");
  const pErrorEl = document.getElementById("pen-irs-error");
  const penOutEl = document.getElementById("pen-output");

  function applyPreset(name) {
    if (name === "legacy-2024") {
      pFormEl.value = "1040"; pCodeEl.value = "6651(a)(1)"; pYearEl.value = "2024";
      pDueEl.value = "2025-04-15"; pRecEl.value = "2025-08-20";
      pHistoryEl.value = "clean"; pTranscriptEl.value = "yes"; pAepEl.value = "no"; pErrorEl.value = "no";
    } else if (name === "aep-2026-941") {
      pFormEl.value = "941"; pCodeEl.value = "6656"; pYearEl.value = "2026";
      pDueEl.value = "2026-07-31"; pRecEl.value = "2026-08-17";
      pHistoryEl.value = "clean"; pTranscriptEl.value = "yes"; pAepEl.value = "yes"; pErrorEl.value = "no";
    } else if (name === "missing-transcript") {
      pFormEl.value = "1040"; pCodeEl.value = "6651(a)(1)"; pYearEl.value = "2025";
      pDueEl.value = "2026-04-15"; pRecEl.value = "2026-08-20";
      pHistoryEl.value = "unknown"; pTranscriptEl.value = "no"; pAepEl.value = "unknown"; pErrorEl.value = "no";
    } else if (name === "post-2027-cutoff") {
      pFormEl.value = "1040"; pCodeEl.value = "6651(a)(1)"; pYearEl.value = "2026";
      pDueEl.value = "2027-04-15"; pRecEl.value = "2027-07-10";
      pHistoryEl.value = "clean"; pTranscriptEl.value = "yes"; pAepEl.value = "yes"; pErrorEl.value = "no";
    }
    renderPenalty();
  }

  for (const btn of document.querySelectorAll("[data-preset]")) {
    btn.addEventListener("click", () => applyPreset(btn.dataset.preset));
  }

  function renderPenalty() {
    const hVal = pHistoryEl.value;
    const res = assessPenaltyRelief({
      penalty_code: pCodeEl.value,
      return_form: pFormEl.value,
      tax_year: Number(pYearEl.value),
      original_due_date: pDueEl.value,
      received_date: pRecEl.value,
      is_original_return: true,
      aep_considered: pAepEl.value === "unknown" ? null : pAepEl.value === "yes",
      aep_transcript_verified: pTranscriptEl.value === "yes",
      history_clean: hVal === "unknown" ? null : hVal === "clean",
      related_accounts_reviewed: pTranscriptEl.value === "yes",
      currently_required_returns_filed_or_extended: true,
      paid_or_arranged_to_pay: true,
      irs_error: pErrorEl.value === "yes",
      penalty_factually_valid: pErrorEl.value !== "yes",
    });

    const routeLabels = {
      correction: "1. Assessment Correction",
      fta: "2. Legacy FTA",
      aep: "3. 2026+ AEP Relief",
      reasonable_cause: "4. Reasonable Cause",
      estimated: "5. Sec. 6654(e)(3) Waiver",
    };
    penOutEl.innerHTML =
      `<div class="notice" style="grid-column:1/-1"><strong>Preferred Screened Route:</strong> ${routeLabels[res.preferredRoute]} · Verify transcript &amp; IRS notice before relying.</div>` +
      Object.entries(res.routes)
        .map(
          ([key, r]) => `
          <article class="result">
            <span>${routeLabels[key]}</span>
            <strong>${r.status.replace(/_/g, " ")}</strong>
            <small>${r.reasons[0] || ""}</small>
            ${r.missingEvidence.length ? `<div style="margin-top:6px;font-size:.82rem;color:#9a3412">Missing: ${r.missingEvidence.join(", ")}</div>` : ""}
          </article>`,
        )
        .join("");
  }
  for (const el of [pFormEl, pCodeEl, pYearEl, pDueEl, pRecEl, pHistoryEl, pTranscriptEl, pAepEl, pErrorEl]) {
    el.addEventListener("change", renderPenalty);
    el.addEventListener("input", renderPenalty);
  }
  renderPenalty();

  // 4. 17-Row IRM Penalty Matrix + 6 Canonical Reference Cards
  document.getElementById("matrix-body").innerHTML = penaltyMatrix.rows
    .map(
      (row) =>
        `<tr><td><strong>${row.id}</strong></td><td>${row.scope}</td><td>${row.decision_boundary}</td><td><code>${row.pinpoint}</code></td></tr>`,
    )
    .join("");

  document.getElementById("cards-grid").innerHTML = cardsPayload.cards
    .map(
      (c) => `
      <article class="result">
        <span class="eyebrow">${(c.source_ids || []).join(" · ")}</span>
        <h3 style="margin:6px 0">${c.title}</h3>
        <p style="margin:0;font-size:.9rem">${c.text || ""}</p>
      </article>`,
    )
    .join("");

  // 5. Practice Question Sampler (all 80 questions accessible by index/topic)
  const qTopicSel = document.getElementById("q-topic");
  const topics = ["all", ...new Set(questions.map((q) => q.topic))];
  for (const t of topics) {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t === "all" ? `All Topics (${questions.length} Qs)` : t;
    qTopicSel.appendChild(opt);
  }
  let qIdx = 0;
  let revealed = false;

  function renderQuestion() {
    const topic = qTopicSel.value;
    const pool = topic === "all" ? questions : questions.filter((q) => q.topic === topic);
    const q = pool[qIdx % pool.length];
    document.getElementById("q-meta").textContent = `${q.id} · ${q.topic} · ${q.difficulty} (${(qIdx % pool.length) + 1}/${pool.length})`;
    document.getElementById("q-stem").textContent = q.stem;
    document.getElementById("q-options").innerHTML = q.options
      .map(
        (o) =>
          `<button type="button" class="result" data-opt="${o.key}" style="text-align:left;cursor:pointer;${
            revealed && o.key === q.answer ? "border:2px solid #0f766e;background:#ecfdf5" : ""
          }"><strong>${o.key}.</strong> ${o.text}</button>`,
      )
      .join("");
    const expEl = document.getElementById("q-explanation");
    expEl.hidden = !revealed;
    expEl.innerHTML = `<strong>Answer: ${q.answer}</strong> — ${q.explanation} <br><small>Sources: ${q.source_ids.join(", ")}</small>`;

    for (const btn of document.querySelectorAll("[data-opt]")) {
      btn.addEventListener("click", () => {
        revealed = true;
        renderQuestion();
      });
    }
  }
  qTopicSel.addEventListener("change", () => { qIdx = 0; revealed = false; renderQuestion(); });
  document.getElementById("q-next").addEventListener("click", () => { qIdx++; revealed = false; renderQuestion(); });
  renderQuestion();
}
