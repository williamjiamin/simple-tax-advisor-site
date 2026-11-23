/** Original default-on adapter for the existing educational repository. */
export const killSwitch = 'TAX_RESEARCH_DISABLED';

export function enabled(settings = {}, environment = globalThis.process?.env ?? {}) {
  const value = Object.hasOwn(settings, 'tax_research/enabled') ? settings['tax_research/enabled'] : true;
  if (typeof value !== 'boolean') throw new TypeError('Feature setting must be boolean');
  const killed = ['1', 'true', 'yes', 'on'].includes(String(environment[killSwitch] ?? '').trim().toLowerCase());
  return value && !killed;
}

export function augment(previous, build, settings = {}, environment = globalThis.process?.env ?? {}) {
  if (!enabled(settings, environment)) return previous;
  if (typeof build !== 'function') throw new TypeError('build must be callable');
  return build(previous);
}

export function referenceCard(dataset) {
  if (!dataset || dataset.schema_version !== '1.0' || !Array.isArray(dataset.cards)) {
    throw new TypeError('Invalid research-card dataset');
  }
  // The browser consumes exported results from the canonical model. It never
  // reimplements tax eligibility or injects untrusted markup into the document.
  return {
    kind: 'tax_research_reference',
    researchAsOf: dataset.research_as_of,
    cards: dataset.cards.map(card => ({
      title: String(card.title), text: String(card.text),
      sourceIds: Array.isArray(card.source_ids) ? [...card.source_ids] : []
    }))
  };
}
