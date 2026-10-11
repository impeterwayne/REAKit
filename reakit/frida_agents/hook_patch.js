// hook_patch.js -- neutralise ONE native death site in memory, then report PATCHED.
//
// REAKIT AGENT
// ------------
// Bundled with ReaKit and loaded by `rea frida probe --script hook_patch` (resolved
// from reakit/frida_agents/hook_patch.js). The intended flow is spawn -> attach ->
// patch -> detach: the write lands while attached, and because Memory.patchCode
// writes survive detach (Interceptor hooks do NOT), the driver can then detach so the
// app runs with no instrumentation present and its UI actually renders.
//
// Configure the four constants below from your own analysis. There is nothing
// target-specific here on purpose: the shape to look for is a short "recover the
// frame and return" epilogue that replaces a terminate call. Never substitute a NOP
// for a call that has live code after it -- the fall-through is the bug you create.
//
// CONFIG KNOBS
// ------------
//   MODULE_NAME  : the module that holds the site ('libtarget.so')
//   FILE_OFFSET  : byte offset of the sequence to replace, relative to module base
//   PATCH_BYTES  : equal-length replacement bytes (an empty array disarms the agent)
//   PRE_EXISTING : hex of PATCH_BYTES, space separated, for the idempotence check
//
// TARGET: frida 16.x (native-only; no Java bridge needed).
//
// OUTPUT: plain JSON-serializable send() lines --
//   'PATCHED'                      the site now carries the patch (or already did)
//   'PATCHFAIL'                    the patch could not be applied / was not configured
//   { t, tag:'INFO'|'ALIVE', msg } progress + heartbeat so the driver sees liveness
'use strict';

// --- configure -----------------------------------------------------------------
var MODULE_NAME = 'libtarget.so';   // the module that holds the site
var FILE_OFFSET = 0x0;              // byte offset of the sequence to replace
var PATCH_BYTES = [];               // equal-length replacement bytes
var PRE_EXISTING = '';              // hex of PATCH_BYTES, space separated, for the idempotence check
// -------------------------------------------------------------------------------

var T0 = Date.now();
function el() { return ((Date.now() - T0) / 1000).toFixed(2) + 's'; }

function info(msg) {
  try { send({ t: new Date().toISOString(), tag: 'INFO', msg: '[' + el() + '] ' + msg }); } catch (e) {}
}

function hx(p, n) {
  try {
    return Array.from(new Uint8Array(p.readByteArray(n))).map(function (b) {
      return ('0' + b.toString(16)).slice(-2);
    }).join(' ');
  } catch (e) { return '<unreadable>'; }
}

if (!PATCH_BYTES.length) {
  info('PATCH_BYTES is empty -- configure this agent before using it');
  send('PATCHFAIL');
} else {
  var timer = setInterval(function () {
    var m = null;
    try { m = Process.findModuleByName(MODULE_NAME); } catch (e) { m = null; }
    if (!m) return;                 // wait for the linker to map the module
    clearInterval(timer);

    var at = m.base.add(FILE_OFFSET);
    var before = hx(at, PATCH_BYTES.length);
    info(MODULE_NAME + ' base=' + m.base + ' bytes@0x' + FILE_OFFSET.toString(16) +
         ' = ' + before);

    if (PRE_EXISTING && before === PRE_EXISTING) {
      info('already carries the patch');
      send('PATCHED');
      return;
    }
    try {
      Memory.patchCode(at, PATCH_BYTES.length, function (code) {
        code.writeByteArray(PATCH_BYTES);
      });
      info('PATCH applied; now = ' + hx(at, PATCH_BYTES.length));
      send('PATCHED');
    } catch (e) {
      info('patch failed: ' + e);
      send('PATCHFAIL');
    }
  }, 10);
}

// Keep the message channel alive so the driver can see the agent is loaded. Cheap,
// and it gives a heartbeat you can read while waiting for the site to appear.
setInterval(function () {
  try { send({ t: new Date().toISOString(), tag: 'ALIVE', msg: '[' + el() + '] alive' }); } catch (e) {}
}, 10000);

info('patch-only agent armed');
