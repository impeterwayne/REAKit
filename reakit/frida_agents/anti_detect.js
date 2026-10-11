/*
 * anti_detect.js -- an OBSERVER of anti-instrumentation / anti-root checks. It
 * changes NOTHING.
 *
 * REAKIT AGENT
 * ------------
 * Bundled with ReaKit and loaded by `rea frida probe --script anti_detect`
 * (resolved from reakit/frida_agents/anti_detect.js). Load with --spawn to see the
 * early phase, or attach to a running pid for the steady state. Every message is
 * emitted as { t, tag, msg } so the ReaKit probe runner can parse and tee it to the
 * workspace frida log; a heartbeat and a stream-first-hit guarantee the last events
 * before a self-kill are already on the wire.
 *
 * PURPOSE
 * -------
 * Answer "if a detector is running, what is it looking at?" WITHOUT answering it
 * with a patch. That division is deliberate: an observation agent must not also
 * intervene (no exit-blocking, no Interceptor.replace of a detection function, no
 * NOPing). A probe that patches while it watches produces a process whose behaviour
 * you can no longer use as evidence about the original -- the death you prevented is
 * exactly the signal you were there to date. (For neutralising a death site, use the
 * separate hook_patch.js agent.)
 *
 * WHAT IT REPORTS
 * ---------------
 *   - env_probe : every open/openat/fopen/access/stat/readlink on an interesting
 *                 path (/proc, /sys, magisk, su, frida, xposed, ...) with the
 *                 caller module+offset -- "0x1cef8 in libX.so checks root"
 *   - termination: exit/exit_group/_exit/abort/kill/tgkill/raise/pthread_kill with
 *                 caller, so a self-destruct is attributed to a module
 *   - thread_create: pthread_create/clone with the real entry point
 *   - loader    : dlopen/android_dlopen_ext/dlsym, so a runtime-resolved symbol shows
 *   - selfView  : the process's own view of "am I instrumented" (TracerPid,
 *                 frida-named maps/threads/modules, TCP listeners)
 *
 * CONFIG KNOBS (CONFIG below, or rpc.exports.config({...}) at runtime)
 * -------------------------------------------------------------------
 *   watchMs            : collect this long, then emit the RESULT block (0 = only on stop())
 *   heartbeatMs        : liveness proof interval; its absence at T means the process
 *                        (or the script) was gone before T
 *   streamFirstHit     : emit a LIVE line the moment a category first fires
 *   pathFilter         : substrings that mark a path access as environment probing
 *   allThreads         : report events on every thread (true) or just main
 *   maxLinesPerCategory: hard cap on stored lines per category
 *
 * TARGET: frida 16.x. The Java bridge is only used to record the Android version,
 * never to hook Java (that would change the timing this agent measures).
 *
 * OUTPUT FORMAT
 * -------------
 *   { t: <ISO timestamp>, tag: <TAG>, msg: <string> }
 *   TAGS: ARMED | LIVE | HEARTBEAT | RESULT | HOOK-ERR
 *   The RESULT line's msg is a JSON string of the full counts/details/selfView.
 */

var CONFIG = {
  // How long to keep collecting before emitting the RESULT block. 0 = emit only
  // on the stop()/report() RPC, for an interactive session.
  watchMs: 12000,
  // Stream a heartbeat every N ms. This exists because of a measured failure mode:
  // a detector that kills the process inside the watch window means an agent that
  // only reports at the end reports nothing at all. The heartbeat says "the script
  // was still alive at T", separating "the target died" from "my script never armed".
  heartbeatMs: 1000,
  // Stream a line the moment a category fires for the first time, so the last
  // events before a death are on the wire already.
  streamFirstHit: true,
  // Substrings that mark a path access as environment probing. Everything else is
  // still counted, but not individually reported (a busy app opens thousands of files).
  pathFilter: ['/proc', '/sys', 'magisk', 'supersu', 'frida', 'xposed', 'gum-js',
               '/data/local/tmp', 'busybox', 're.frida', 'linjector'],
  // Report process-wide events for every thread (true) or only the main thread.
  allThreads: true,
  // Hard cap on reported lines per category, so a chatty target cannot flood the log.
  maxLinesPerCategory: 60,
};

if (typeof CONFIG_OVERRIDE !== 'undefined' && CONFIG_OVERRIDE.anti_detect) {
  Object.assign(CONFIG, CONFIG_OVERRIDE.anti_detect);
}

var counts = {};
var lines = {};
var started = Date.now();

function ts() { return new Date().toISOString(); }

// The ReaKit envelope: every line is { t, tag, msg }.
function emit(tag, msg) {
  try { send({ t: ts(), tag: tag, msg: msg }); } catch (e) { /* transport gone */ }
}

function bump(cat, msg) {
  counts[cat] = (counts[cat] || 0) + 1;
  if (!lines[cat]) lines[cat] = [];
  if (lines[cat].length < CONFIG.maxLinesPerCategory) lines[cat].push(msg);
  if (CONFIG.streamFirstHit && counts[cat] === 1) {
    // On the wire immediately: if the target dies a moment later, this is the only
    // trace of the event that existed.
    emit('LIVE', cat + ' (+' + (Date.now() - started) + 'ms): ' + msg);
  }
}

function backtraceOwners(ctx) {
  // Module+offset for every return address inside a mapped module. The link
  // register is read first because on arm64 it is where the caller of the hooked
  // export lives, and it survives even when Thread.backtrace cannot unwind (Frida's
  // unwinder needs the target's frames intact, which is not guaranteed in a
  // constructor or a signal path).
  try {
    var owners = [];
    var lr = null;
    try { lr = ctx.lr; } catch (e) { lr = null; }
    if (lr) { owners.push(describe(lr, 'lr')); }
    var bt = Thread.backtrace(ctx, Backtracer.ACCURATE);
    for (var i = 0; i < bt.length && owners.length < 5; i++) {
      owners.push(describe(bt[i], 'bt' + i));
    }
    return owners.length ? owners : ['no-unwind'];
  } catch (e) {
    return ['bt-failed:' + e.message];
  }
}

function describe(addr, tag) {
  try {
    var d = DebugSymbol.fromAddress(addr);
    if (d && d.moduleName) {
      var base = Module.findBaseAddress(d.moduleName);
      var off = base ? addr.sub(base) : null;
      return d.moduleName + (off ? '+0x' + off.toString(16) : '+?') + '(' + tag + ')';
    }
    if (d && d.name) return d.name + '(' + tag + ')';
    return 'anon:' + addr + '(' + tag + ')';
  } catch (e) {
    return 'addr?' + addr;
  }
}

function ownerString(ctx) {
  // Takes the context explicitly. `this` inside a Frida Interceptor callback is not
  // reliably set when the callback is an anonymous function expression; the symptom
  // of getting this wrong is "cannot read property 'context' of undefined", which
  // reads like a hooking failure and is actually a binding mistake. Callers pass
  // `this.context`.
  if (!ctx) return 'no-ctx';
  return backtraceOwners(ctx).join(' | ');
}

function looksInteresting(p) {
  for (var i = 0; i < CONFIG.pathFilter.length; i++) {
    if (p.indexOf(CONFIG.pathFilter[i]) >= 0) return true;
  }
  return false;
}

function hookExport(modName, exp, cat, argIndex) {
  var addr = Module.findExportByName(modName, exp);
  if (addr === null) return false;
  try {
    Interceptor.attach(addr, {
      onEnter: function (args) {
        try {
          var p = null;
          if (argIndex >= 0) p = args[argIndex].readUtf8String();
          var who = ownerString(this.context);
          if (p === null) { bump(cat, exp + '() <- ' + who); return; }
          if (looksInteresting(p)) {
            bump(cat, exp + '("' + p + '") <- ' + who);
          } else {
            counts[cat + '_quiet'] = (counts[cat + '_quiet'] || 0) + 1;
          }
        } catch (e) { /* unreadable pointer: count it, never throw out of a hook */ }
      }
    });
    return true;
  } catch (e) {
    bump('hook_errors', modName + '!' + exp + ': ' + e.message);
    return false;
  }
}

function hookTerminators() {
  // A detector's self-destruct is often a direct libc call; the caller offset is
  // what identifies it. A module that issues `svc #0` itself will NOT show up here --
  // the absence of a report plus a death is itself the signal that a libc hook
  // cannot see it.
  ['exit', 'exit_group', '_exit', 'abort', 'kill', 'tgkill', 'raise', 'pthread_kill']
    .forEach(function (fn) {
      var a = Module.findExportByName('libc.so', fn);
      if (a === null) return;
      try {
        Interceptor.attach(a, {
          onEnter: function (args) {
            bump('termination', fn + '(' + args.join(',') + ') <- ' +
                 ownerString(this.context));
          }
        });
      } catch (e) { bump('hook_errors', fn + ': ' + e.message); }
    });
}

function hookThreadCreation() {
  var pc = Module.findExportByName('libc.so', 'pthread_create');
  if (pc !== null) {
    try {
      Interceptor.attach(pc, {
        onEnter: function (args) {
          bump('thread_create', 'pthread_create entry=' + args[2] + ' <- ' +
               ownerString(this.context));
        }
      });
    } catch (e) { bump('hook_errors', 'pthread_create: ' + e.message); }
  }
  // clone() is how a detector bypasses the pthread wrapper; args[3] points at the
  // argument block whose fifth word holds the real entry point on arm64.
  var cl = Module.findExportByName('libc.so', 'clone');
  if (cl !== null) {
    try {
      Interceptor.attach(cl, {
        onEnter: function (args) {
          var extra = '';
          try { extra = ' realEntry=' + args[3].add(96).readPointer(); } catch (e) {}
          bump('thread_create', 'clone()' + extra + ' <- ' + ownerString(this.context));
        }
      });
    } catch (e) { bump('hook_errors', 'clone: ' + e.message); }
  }
}

function hookLoader() {
  ['dlopen', 'android_dlopen_ext', 'dlsym'].forEach(function (fn) {
    var a = Module.findExportByName('libc.so', fn);
    if (a === null) return;
    try {
      Interceptor.attach(a, {
        onEnter: function (args) {
          var s = null;
          try { s = args[0].readUtf8String(); } catch (e) {}
          bump('loader', fn + '("' + s + '") <- ' + ownerString(this.context));
        }
      });
    } catch (e) { bump('hook_errors', fn + ': ' + e.message); }
  });
}

function selfView() {
  // What the process can see about itself right now. This is evidence about the
  // *environment*, not about the detector: it says what is available to be found,
  // which is the other half of attributing a death.
  var out = {};
  var files = ['/proc/self/status', '/proc/self/maps', '/proc/self/task',
               '/proc/net/tcp', '/proc/net/tcp6', '/proc/self/cmdline'];
  out.files = {};
  files.forEach(function (f) {
    try {
      var content = File.readAllText(f);
      if (f === '/proc/self/status') {
        var m = content.match(/TracerPid:\s*(\d+)/);
        out.tracerpid = m ? m[1] : 'absent';
        // A detector may match any of these names; report which are present so a
        // "frida is visible here" claim is not made from memory.
        out.status_flags = (content.match(/^(Name|State|Seccomp):.*$/gm) || []).join(' ; ');
      } else if (f === '/proc/net/tcp' || f === '/proc/net/tcp6') {
        var listening = (content.match(/^[^\n]*\s0A\s/gm) || []).length;
        out[f] = 'lines=' + content.split('\n').length + ' listening=' + listening;
      } else if (f === '/proc/self/maps') {
        var hits = (content.match(/frida|gum|gadget|linjector/gi) || []);
        out.frida_named_maps = hits.length;
        out.map_sample = hits.slice(0, 5);
      } else {
        out[f] = 'readable (' + content.length + ' B)';
      }
    } catch (e) {
      out[f] = 'unreadable: ' + e.message;
    }
  });
  try {
    out.current_thread = Process.getCurrentThreadId();
    out.threads = Process.enumerateThreads().map(function (t) { return t.id; }).slice(0, 24);
  } catch (e) { out.threads = 'enumerate failed: ' + e.message; }
  try {
    out.modules_named = Process.enumerateModules()
      .filter(function (m) { return /frida|gum|gadget|linjector/i.test(m.name); })
      .map(function (m) { return m.name + '@' + m.base; });
  } catch (e) { out.modules_named = []; }
  return out;
}

function report() {
  var out = {
    kind: 'anti_detect',
    mode: 'observer-only (this script never changes the target)',
    ranMs: Date.now() - started,
    counts: counts,
    details: lines,
    selfView: selfView(),
  };
  // The full structured result travels as a JSON string in the msg field, so the
  // ReaKit probe runner's { t, tag, msg } parser handles it like any other line.
  emit('RESULT', JSON.stringify(out));
}

function start() {
  hookExport('libc.so', 'open', 'env_probe', 0);
  hookExport('libc.so', 'openat', 'env_probe', 1);
  hookExport('libc.so', 'fopen', 'env_probe', 0);
  hookExport('libc.so', 'fopen64', 'env_probe', 0);
  hookExport('libc.so', 'access', 'env_probe', 0);
  hookExport('libc.so', 'stat', 'env_probe', 0);
  hookExport('libc.so', 'stat64', 'env_probe', 0);
  hookExport('libc.so', 'lstat', 'env_probe', 0);
  hookExport('libc.so', 'readlink', 'env_probe', 0);
  hookExport('libc.so', 'opendir', 'env_probe', 0);
  hookExport('libc.so', 'scandir', 'env_probe', 0);
  hookExport('libc.so', 'strstr', 'strstr_probe', 1);
  hookExport('libc.so', 'strcmp', 'strcmp_probe', 1);
  hookTerminators();
  hookThreadCreation();
  hookLoader();
  var sv0 = selfView();
  emit('ARMED', 'anti_detect armed (observer only) selfView=' + JSON.stringify(sv0));
  if (CONFIG.heartbeatMs > 0) {
    // The heartbeat is the liveness proof. Its absence at time T means the script
    // (or the whole process) was gone before T, which is a different finding from
    // "the target was quiet".
    setInterval(function () {
      emit('HEARTBEAT', '+' + (Date.now() - started) + 'ms counts=' +
           JSON.stringify(counts));
    }, CONFIG.heartbeatMs);
  }
  if (CONFIG.watchMs > 0) {
    var t = setTimeout(report, CONFIG.watchMs);
    setTimeout(function () { clearTimeout(t); }, CONFIG.watchMs + 1);
  }
}

rpc.exports = {
  config: function (patch) { Object.assign(CONFIG, patch); return CONFIG; },
  status: function () { return { counts: counts, ranMs: Date.now() - started }; },
  report: function () { report(); return true; },
  // Kept for interface parity with the kit's other agents; nothing is patched.
  patch: function () { return 'observed-only: nothing patched'; },
};

if (typeof Java !== 'undefined' && Java.available) {
  // Only to record what the Java side is, not to hook it: an observer that hooks
  // Java would change the timing it is there to measure.
  try {
    Java.perform(function () {
      emit('LIVE', 'java classloader ready, app=' +
           (Java.androidVersion ? 'Android ' + Java.androidVersion : 'unknown'));
    });
  } catch (e) { /* Java optional */ }
}

setImmediate(start);
