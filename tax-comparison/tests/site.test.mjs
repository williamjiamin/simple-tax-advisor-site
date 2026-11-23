import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
const root = new URL("../", import.meta.url);
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
});
