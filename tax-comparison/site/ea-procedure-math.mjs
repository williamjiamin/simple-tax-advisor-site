export function computePartnershipGate({
  loss,
  outsideBasis,
  sec754StepUp,
  atRisk,
  passiveIncome,
}) {
  const effectiveBasis = Math.max(0, outsideBasis + sec754StepUp);
  const afterBasis = Math.min(Math.max(0, loss), effectiveBasis);
  const afterAtRisk = Math.min(afterBasis, Math.max(0, atRisk));
  const allowed = Math.min(afterAtRisk, Math.max(0, passiveIncome));
  return {
    effectiveBasis,
    basisSuspended: Math.max(0, loss) - afterBasis,
    atRiskSuspended: afterBasis - afterAtRisk,
    passiveSuspended: afterAtRisk - allowed,
    allowed,
  };
}

export function computeOicRcp(equity, monthlyDisposable, mode) {
  const months = mode === "periodic" ? 24 : 12;
  const futureIncome = Math.max(0, monthlyDisposable) * months;
  const rcp = Math.max(0, equity) + futureIncome;
  return {
    months,
    futureIncome,
    rcp,
    initialPayment: mode === "periodic" ? rcp / months : rcp * 0.2,
  };
}
