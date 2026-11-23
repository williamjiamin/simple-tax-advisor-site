import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { computeOicRcp, computePartnershipGate } from "../site/ea-procedure-math.mjs";
import {
  assessPenaltyRelief,
  evaluateTaxAuthority,
  filterVerifiedSources,
  isTaxResearchEnabled,
} from "../site/tax-research-verifier.mjs";

const root = new URL("../", import.meta.url);
const LEAK_RE = /\b(AGY|Fable|Codex|Minimax|GOAG|PR\s*#\d+|Shipyard|Guild)\b/i;
test("FAQ JSON-LD is valid and has FAQPage type", () => {
  const faq = JSON.parse(fs.readFileSync(new URL("site/faq.schema.json", root), "utf8"));
  assert.equal(faq["@type"], "FAQPage");
  assert.ok(faq.mainEntity.length >= 4);
});
test("translations cover required locales", () => {
  const t = JSON.parse(fs.readFileSync(new URL("site/i18n.json", root), "utf8"));
  for (const lang of ["en", "zh-hans", "ja"]) assert.ok(t[lang].title && t[lang].disclaimer);
});
test("site remains local-first and marks sample data", () => {
  const html = fs.readFileSync(new URL("site/index.html", root), "utf8");
  assert.match(html, /Illustrative data only/);
  assert.match(html, /tax_schedules\.json/);
  assert.match(html, /ea-procedure-lab\.html/);
});

test("D32-B08/B09 26 SVG plates, workflow atlas, and interactive tax gates are valid and leak-free", () => {
  const atlasRaw = fs.readFileSync(new URL("data/d32_tax_workflow_atlas.json", root), "utf8");
  assert.equal(LEAK_RE.test(atlasRaw), false);
  const atlas = JSON.parse(atlasRaw);
  assert.equal(atlas.ty2025_workflow_plates.length, 14);
  assert.equal(atlas.procedure_plates.length, 12);

  for (const plate of [...atlas.ty2025_workflow_plates, ...atlas.procedure_plates]) {
    const svg = fs.readFileSync(new URL(`site/${plate.svg}`, root), "utf8");
    assert.ok(svg.includes("<svg"));
    assert.equal(LEAK_RE.test(svg), false);
  }

  const labHtml = fs.readFileSync(new URL("site/ea-procedure-lab.html", root), "utf8");
  assert.match(labHtml, /acadifi\.com\/labs/);
  assert.match(labHtml, /robotforge\.org\/labs/);
  assert.match(labHtml, /LIPAI WANG/);
  assert.equal(LEAK_RE.test(labHtml), false);

  const k1 = computePartnershipGate({
    loss: 4800,
    outsideBasis: 3600,
    sec754StepUp: 0,
    atRisk: 2500,
    passiveIncome: 1200,
  });
  assert.deepEqual(k1, {
    effectiveBasis: 3600,
    basisSuspended: 1200,
    atRiskSuspended: 1100,
    passiveSuspended: 1300,
    allowed: 1200,
  });

  const oic = computeOicRcp(9800, 475, "lump_sum");
  assert.equal(oic.rcp, 15500);
  assert.equal(oic.initialPayment, 3100);
});

test("Tax Research Citation & 2026 AEP Penalty Relief verifier passes models, kill switches, and leak scan", () => {
  assert.equal(isTaxResearchEnabled({}), true);
  assert.equal(isTaxResearchEnabled({ queryString: "?tax_research=off" }), false);
  assert.equal(isTaxResearchEnabled({ env: { TAX_RESEARCH_DISABLED: "1" } }), false);

  const authModel = JSON.parse(fs.readFileSync(new URL("data/tax_research/authority_model.json", root), "utf8"));
  const penMatrix = JSON.parse(fs.readFileSync(new URL("data/tax_research/penalty_matrix.json", root), "utf8"));
  const sources = JSON.parse(fs.readFileSync(new URL("data/tax_research/sources.json", root), "utf8"));
  const cards = JSON.parse(fs.readFileSync(new URL("data/tax_research/reference_cards.json", root), "utf8"));
  const qBank = JSON.parse(fs.readFileSync(new URL("data/tax_research/questions.json", root), "utf8"));

  assert.equal(authModel.categories.length, 17);
  assert.equal(penMatrix.rows.length, 17);
  assert.equal(sources.sources.length, 37);
  assert.equal(cards.cards.length, 6);
  assert.equal(qBank.questions.length, 80);

  const plrPost1976 = evaluateTaxAuthority(
    { kind: "plr", issuedOn: "1980-05-01", sameTaxpayer: false, appliesToPeriod: true, conflictingAuthority: false },
    authModel.categories,
  );
  assert.equal(plrPost1976.substantialAuthorityUse, "enumerated_nonprecedential_material_subject_to_weight_analysis");
  assert.equal(plrPost1976.probability, null);

  const faqNews = evaluateTaxAuthority(
    { kind: "faq", faqLinkedNewsRelease: true, appliesToPeriod: true, conflictingAuthority: false },
    authModel.categories,
  );
  assert.equal(faqNews.substantialAuthorityUse, "qualifying_fact_sheet_faq_penalty_authority_review");

  const aep2026 = assessPenaltyRelief({
    penalty_code: "6656",
    return_form: "941",
    tax_year: 2026,
    original_due_date: "2026-07-31",
    received_date: "2026-08-17",
    is_original_return: true,
    aep_considered: true,
    aep_transcript_verified: true,
    history_clean: true,
    related_accounts_reviewed: true,
  });
  assert.equal(aep2026.routes.aep.status, "eligible");
  assert.equal(aep2026.preferredRoute, "aep");

  const cutoff2027 = assessPenaltyRelief({
    penalty_code: "6651(a)(1)",
    return_form: "1040",
    tax_year: 2026,
    original_due_date: "2027-04-15",
    received_date: "2027-07-10",
    is_original_return: true,
    aep_considered: true,
    aep_transcript_verified: true,
    history_clean: true,
    related_accounts_reviewed: true,
  });
  assert.equal(cutoff2027.routes.fta.status, "not_applicable");
  assert.equal(cutoff2027.routes.aep.status, "eligible");

  const missingTranscript = assessPenaltyRelief({
    penalty_code: "6651(a)(1)",
    return_form: "1040",
    tax_year: 2025,
    original_due_date: "2026-04-15",
    received_date: "2026-08-20",
    is_original_return: true,
    aep_considered: null,
    aep_transcript_verified: false,
    history_clean: null,
    related_accounts_reviewed: false,
  });
  assert.equal(missingTranscript.routes.aep.status, "review_required");
  assert.ok(missingTranscript.routes.aep.missingEvidence.includes("aep_transcript_verified"));

  assert.ok(filterVerifiedSources(sources.sources, { query: "6662" }).length >= 1);

  for (const rel of [
    "site/tax-research-verifier.html",
    "site/tax-research-verifier.mjs",
    "site/tax-research-verifier-ui.js",
    "site/index.html",
    "site/ea-procedure-lab.html",
    "site/figures/authority_tree.svg",
    "site/figures/penalty_relief_tree.svg",
  ]) {
    const raw = fs.readFileSync(new URL(rel, root), "utf8");
    assert.equal(LEAK_RE.test(raw), false, `Leak detected in ${rel}`);
  }
  const verifierHtml = fs.readFileSync(new URL("site/tax-research-verifier.html", root), "utf8");
  assert.match(verifierHtml, /tax-research-verifier-ui\.js/);
  assert.match(verifierHtml, /authority_tree\.svg/);
});
