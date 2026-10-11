// mem_helper.js -- a small, persistent memory-ops agent exposed over rpc.exports.
//
// REAKIT AGENT
// ------------
// Bundled with ReaKit. ReaKit's SessionManager injects this ONCE per session and
// keeps it resident, then calls its exports for every `rea frida mem read|write|
// scan|protect` request -- rather than injecting a fresh script per operation.
//
// Every parameter is passed as a real RPC ARGUMENT, never string-interpolated into
// source, so there is no JS-injection surface: an attacker-controlled address or
// pattern is just data to ptr()/Memory.scanSync. Addresses may be given as a hex
// string ("0x7f..."), a decimal string, or a number; toPtr() normalizes all of them.
//
// Exports (each wrapped in try/catch; returns { ok: true, ... } or { error: "..." }):
//   readMemory(address, size)               -> { ok, address, size, hex }
//   writeMemory(address, hexData)           -> { ok, address, written }
//   scanMemory(address, size, pattern)      -> { ok, matches: [{address, size}, ...] }
//   protectMemory(address, size, protection)-> { ok, address, size, protection }  (default "rwx")
//   ping()                                  -> "pong"   (transport sanity check)
//
// TARGET: frida 16.x by default; the API used here (Memory.scanSync, readByteArray,
// writeByteArray, Memory.protect) is stable across frida 16/17.
'use strict';

// Accept "0x..", a decimal string, or a number. ptr() handles hex strings and
// numbers directly; a bare decimal string is coerced through Number first.
function toPtr(address) {
  if (address === null || address === undefined) {
    throw new Error('address is required');
  }
  if (typeof address === 'number') return ptr(address);
  var s = '' + address;
  if (/^0[xX][0-9a-fA-F]+$/.test(s)) return ptr(s);
  if (/^[0-9]+$/.test(s)) return ptr(s);        // ptr() accepts decimal strings too
  // last resort: let ptr() try to parse whatever was given
  return ptr(s);
}

// Bytes -> space-free lowercase hex string.
function bytesToHex(bytes) {
  var u8 = new Uint8Array(bytes);
  var out = '';
  for (var i = 0; i < u8.length; i++) {
    out += ('0' + u8[i].toString(16)).slice(-2);
  }
  return out;
}

// Hex string ("deadbeef" or "de ad be ef") -> array of byte values.
function hexToBytes(hexData) {
  var clean = ('' + hexData).replace(/[\s,]/g, '');
  if (clean.length % 2 !== 0) throw new Error('hex data has an odd number of nibbles');
  if (!/^[0-9a-fA-F]*$/.test(clean)) throw new Error('hex data contains non-hex characters');
  var bytes = [];
  for (var i = 0; i < clean.length; i += 2) {
    bytes.push(parseInt(clean.substr(i, 2), 16));
  }
  return bytes;
}

rpc.exports = {
  ping: function () { return 'pong'; },

  // Read `size` bytes at `address`; return them as a lowercase hex string.
  readMemory: function (address, size) {
    try {
      var p = toPtr(address);
      var n = parseInt(size, 10);
      if (!(n > 0)) return { error: 'size must be a positive integer' };
      var bytes = p.readByteArray(n);
      if (bytes === null) return { error: 'readByteArray returned null (unreadable region)' };
      return { ok: true, address: p.toString(), size: n, hex: bytesToHex(bytes) };
    } catch (e) {
      return { error: '' + e };
    }
  },

  // Write the bytes decoded from `hexData` at `address`.
  writeMemory: function (address, hexData) {
    try {
      var p = toPtr(address);
      var bytes = hexToBytes(hexData);
      if (!bytes.length) return { error: 'hex data decoded to zero bytes' };
      p.writeByteArray(bytes);
      return { ok: true, address: p.toString(), written: bytes.length };
    } catch (e) {
      return { error: '' + e };
    }
  },

  // Scan [address, address+size) for `pattern` (a Frida match pattern such as
  // "de ad ?? ef"). Uses Memory.scanSync so the result is returned in one call.
  scanMemory: function (address, size, pattern) {
    try {
      var p = toPtr(address);
      var n = parseInt(size, 10);
      if (!(n > 0)) return { error: 'size must be a positive integer' };
      if (!pattern) return { error: 'pattern is required' };
      var hits = Memory.scanSync(p, n, '' + pattern);
      var matches = hits.map(function (h) {
        return { address: h.address.toString(), size: h.size };
      });
      return { ok: true, count: matches.length, matches: matches };
    } catch (e) {
      return { error: '' + e };
    }
  },

  // Change the protection of [address, address+size) (default "rwx").
  protectMemory: function (address, size, protection) {
    try {
      var p = toPtr(address);
      var n = parseInt(size, 10);
      if (!(n > 0)) return { error: 'size must be a positive integer' };
      var prot = protection || 'rwx';
      var ok = Memory.protect(p, n, prot);
      return { ok: !!ok, address: p.toString(), size: n, protection: prot };
    } catch (e) {
      return { error: '' + e };
    }
  }
};

try { send({ t: Date.now(), ev: 'MEM-READY', exports: Object.keys(rpc.exports) }); } catch (e) {}
