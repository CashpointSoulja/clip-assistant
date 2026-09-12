const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(require('node:path').join(__dirname, 'web/app.js'), 'utf8');
const initSource = source.slice(source.indexOf('function initHeroMotion()'), source.indexOf('async function api')) + '\nmodule.exports = { initHeroMotion };';

function harness({ reduced = false, fine = true } = {}) {
  const raf = []; let next = 0; const cancelled = new Set();
  const listeners = {}; const vars = {};
  const node = { model: {}, style: { setProperty(k, v) { vars[k] = v; } }, addEventListener() {} };
  const document = { hidden: false, addEventListener(type, fn) { listeners[type] = fn; }, querySelector(sel) { return sel === '.intro-orbit' ? node : null; } };
  const window = {
    innerWidth: 1000, innerHeight: 800,
    matchMedia: q => ({ matches: q.includes('reduced') ? reduced : fine, addEventListener() {} }),
    addEventListener(type, fn) { listeners[type] = fn; },
    requestAnimationFrame(fn) { raf.push({ id: ++next, fn }); return next; },
    cancelAnimationFrame(id) { cancelled.add(id); },
  };
  const performance = { now: () => 0 };
  const context = { document, window, performance, requestAnimationFrame: window.requestAnimationFrame, cancelAnimationFrame: window.cancelAnimationFrame, module: { exports: {} }, console, $: () => node };
  vm.runInNewContext(initSource, context, { filename: 'web/app.js' });
  context.module.exports.initHeroMotion();
  return { document, window, listeners, raf, cancelled, vars, node };
}

let h = harness();
assert.equal(h.raf.length, 0, 'idle hero schedules no frame');
h.listeners.pointermove({ clientX: 1000, clientY: 0 });
assert.equal(h.raf.length, 1, 'pointer movement schedules motion');
let frame = h.raf.shift(); frame.fn(16);
assert.equal(h.raf.length, 1, 'motion eases toward target');
for (let i = 0; i < 300 && h.raf.length; i++) { frame = h.raf.shift(); frame.fn(16); }
assert.equal(h.raf.length, 0, 'motion settles without a perpetual loop');
h.listeners.pointermove({ clientX: 0, clientY: 0 });
assert.equal(h.raf.length, 1, 'new target schedules another frame');
h.document.hidden = true; h.listeners.visibilitychange();
assert(h.cancelled.size >= 1, 'hidden document cancels pending frame');

assert.equal(harness({ reduced: true }).raf.length, 0, 'reduced motion schedules nothing');
assert.equal(harness({ fine: false }).raf.length, 0, 'coarse pointer schedules nothing');
console.log('hero motion regression checks passed');
