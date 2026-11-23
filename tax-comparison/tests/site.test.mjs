import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { computeOicRcp, computePartnershipGate } from "../site/ea-procedure-math.mjs";

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
