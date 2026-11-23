import { computeOicRcp, computePartnershipGate } from "./ea-procedure-math.mjs";

const atlasEl = document.getElementById("atlas-grid");
const filterEl = document.getElementById("atlas-filter");
const lossEl = document.getElementById("loss-val");
const basisEl = document.getElementById("basis-val");
const stepEl = document.getElementById("sec754-val");
const atRiskEl = document.getElementById("atrisk-val");
const passiveEl = document.getElementById("passive-val");
const k1OutEl = document.getElementById("k1-output");

const equityEl = document.getElementById("oic-equity");
const monthlyEl = document.getElementById("oic-monthly");
const modeEl = document.getElementById("oic-mode");
const oicOutEl = document.getElementById("oic-output");

let atlasData = null;

function renderK1() {
  const res = computePartnershipGate({
    loss: Number(lossEl.value),
    outsideBasis: Number(basisEl.value),
    sec754StepUp: Number(stepEl.value),
    atRisk: Number(atRiskEl.value),
    passiveIncome: Number(passiveEl.value),
  });
  k1OutEl.innerHTML =
    `<strong>Effective Basis (incl. &sect;754): $${res.effectiveBasis.toLocaleString()}</strong><br>` +
    `Allowed Loss: $${res.allowed.toLocaleString()} &middot; Basis Hold: $${res.basisSuspended.toLocaleString()} &middot; At-Risk Hold: $${res.atRiskSuspended.toLocaleString()} &middot; Passive Hold: $${res.passiveSuspended.toLocaleString()}`;
}

function renderOic() {
  const res = computeOicRcp(
    Number(equityEl.value),
    Number(monthlyEl.value),
    modeEl.value,
  );
  oicOutEl.innerHTML =
    `<strong>Reasonable Collection Potential (${res.months} mo): $${res.rcp.toLocaleString()}</strong><br>` +
    `Future Income Add-on: $${res.futureIncome.toLocaleString()} &middot; Initial Payment: $${res.initialPayment.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function renderAtlas() {
  if (!atlasData) return;
  const filter = filterEl.value;
  const items = [
    ...(filter === "all" || filter === "b08"
      ? atlasData.ty2025_workflow_plates.map((p) => ({ ...p, tag: "TY2025 Workflow" }))
      : []),
    ...(filter === "all" || filter === "b09"
      ? atlasData.procedure_plates.map((p) => ({ ...p, tag: "Tax Procedure & Circular 230" }))
      : []),
  ];
  atlasEl.innerHTML = items
    .map(
      (item) =>
        `<article class="card"><span class="eyebrow">${item.tag}</span><h3>${item.title}</h3><img src="${item.svg}" alt="${item.title}" loading="lazy" style="width:100%;height:auto;border-radius:8px"></article>`,
    )
    .join("");
}

for (const el of [lossEl, basisEl, stepEl, atRiskEl, passiveEl]) {
  el.addEventListener("input", renderK1);
}
for (const el of [equityEl, monthlyEl, modeEl]) {
  el.addEventListener("input", renderOic);
}
filterEl.addEventListener("change", renderAtlas);

renderK1();
renderOic();

fetch("../data/d32_tax_workflow_atlas.json")
  .then((r) => r.json())
  .then((data) => {
    atlasData = data;
    renderAtlas();
  })
  .catch(() => {
    atlasEl.textContent = "Load via local HTTP server to browse all 26 SVG plates.";
  });
