const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(require('node:path').join(__dirname, 'web/app.js'), 'utf8');
const initSource = source.slice(source.indexOf('function initIntro()'), source.indexOf('async function api')) + '\nmodule.exports = { initIntro };';

function harness({ seen = null, reduced = false, storageThrows = false, active = 'body' } = {}) {
  const listeners = {};
  const intro = { hidden: false, attrs: {}, listeners: {}, classList: { values: [], add(value) { this.values.push(value); } }, setAttribute(k, v) { this.attrs[k] = v; }, addEventListener(type, fn) { this.listeners[type] = fn; } };
  const skip = { listeners: {}, addEventListener(type, fn) { this.listeners[type] = fn; }, focus() { this.focused = true; } };
  const body = { focus() { this.focused = true; } };
  const appContent = [{ inert: false }, { inert: false }, { inert: false }];
  const storage = { getItem() { if (storageThrows) throw new Error('storage unavailable'); return seen ? '1' : null; }, setItem(key, value) { if (storageThrows) throw new Error('storage unavailable'); this.saved = [key, value]; } };
  const document = { activeElement: active === 'skip' ? skip : body, getElementById(id) { return id === 'intro-screen' ? intro : id === 'intro-skip' ? skip : null; }, querySelectorAll(selector) { return selector === 'body > header, body > main, body > footer' ? appContent : []; } };
  const window = { sessionStorage: storage, matchMedia: () => ({ matches: reduced }), setTimeout(fn, ms) { (listeners.timeouts ||= []).push({ fn, ms }); return listeners.timeouts.length; }, clearTimeout(id) { listeners.cleared = id; } };
  const context = { document, window, module: { exports: {} }, console, $: id => document.getElementById(id) };
  vm.runInNewContext(initSource, context, { filename: 'web/app.js' });
  context.module.exports.initIntro();
  return { intro, skip, body, storage, listeners, document };
}

// First visit: show the intro and schedule the fail-open dismissal.
let h = harness();
assert.equal(h.intro.hidden, false);
assert.equal(h.listeners.timeouts.find(t => t.ms === 2100).ms, 2100);
assert.equal(appContentState(h), true);
h.listeners.timeouts.find(t => t.ms === 0).fn();
assert.equal(h.skip.focused, true);
h.listeners.timeouts.find(t => t.ms === 2100).fn();
assert.equal(h.intro.hidden, true);
assert.equal(h.intro.attrs['aria-hidden'], 'true');
assert.deepEqual(h.storage.saved, ['clip-assistant-intro-seen', '1']);
assert.equal(appContentState(h), false);

// A seen session dismisses immediately and does not schedule another timer.
h = harness({ seen: true });
assert.equal(h.intro.hidden, true);
assert.equal(h.listeners.timeouts, undefined);

// Reduced motion follows the same immediate-dismiss path.
h = harness({ reduced: true });
assert.equal(h.intro.hidden, true);

// Storage failures do not prevent the intro from dismissing.
h = harness({ storageThrows: true });
h.listeners.timeouts.find(t => t.ms === 2100).fn();
assert.equal(h.intro.hidden, true);

// Manual skip dismisses and restores focus when skip held focus.
h = harness();
h.document.activeElement = h.skip;
h.skip.listeners.click();
assert.equal(h.intro.hidden, true);
assert.equal(h.body.focused, true);

// Escape cancels the timer and follows the same dismissal path.
h = harness();
h.intro.listeners.keydown({ key: 'Escape' });
assert.equal(h.listeners.cleared, 1);
assert.equal(h.intro.hidden, true);

console.log('intro regression checks passed');

function appContentState(h) {
  // The harness exposes the elements through the selector result; this checks
  // the real initIntro inert writes without requiring a browser DOM package.
  return h.document.querySelectorAll('body > header, body > main, body > footer').every(el => el.inert === true);
}
