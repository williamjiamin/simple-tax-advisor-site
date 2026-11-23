import test from 'node:test';
import assert from 'node:assert/strict';
import { enabled, augment, referenceCard } from '../../src/tax_research/adapter.mjs';

test('ships enabled; explicit setting and environment kill it', () => {
  assert.equal(enabled(), true);
  assert.equal(enabled({'tax_research/enabled': false}), false);
  for (const value of ['1', 'true', ' YES ', 'on']) {
    assert.equal(enabled({}, {TAX_RESEARCH_DISABLED: value}), false);
  }
  assert.equal(enabled({}, {TAX_RESEARCH_DISABLED: '0'}), true);
  assert.throws(() => enabled({'tax_research/enabled': 'false'}), TypeError);
  assert.throws(() => enabled({'tax_research/enabled': null}), TypeError);
});

test('environment kill is read from the host when no binding is supplied', () => {
  const old = process.env.TAX_RESEARCH_DISABLED;
  process.env.TAX_RESEARCH_DISABLED = '1';
  try { assert.equal(enabled(), false); }
  finally {
    if (old === undefined) delete process.env.TAX_RESEARCH_DISABLED;
    else process.env.TAX_RESEARCH_DISABLED = old;
  }
});

test('disabled path preserves original bytes and never touches the feature', () => {
  const base = new Uint8Array([0, 127, 128, 255, 13, 10]);
  const output = augment(base, () => {throw new Error('must not run');}, {}, {TAX_RESEARCH_DISABLED: '1'});
  assert.equal(output, base);
  assert.deepEqual([...output], [0, 127, 128, 255, 13, 10]);
});

test('enabled path builds once and leaves base object untouched', () => {
  const base = Object.freeze({legacy: 'stable'});
  let calls = 0;
  const output = augment(base, b => { calls++; return {...b, research: true}; });
  assert.equal(calls, 1);
  assert.deepEqual(base, {legacy: 'stable'});
  assert.deepEqual(output, {legacy: 'stable', research: true});
});

test('card adapter makes no tax decision or markup interpretation', () => {
  const input = {schema_version: '1.0', research_as_of: '2026-11-22', cards: [{title:'Authority', text:'<study>', source_ids:['AUTH-6110']}]};
  const output = referenceCard(input);
  assert.equal(output.cards[0].text, '<study>');
  output.cards[0].sourceIds.push('OTHER');
  assert.deepEqual(input.cards[0].source_ids, ['AUTH-6110']);
  assert.throws(() => referenceCard({}), TypeError);
});
