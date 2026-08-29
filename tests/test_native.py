"""Offline tests for reakit.native - ELF parsing, classification, extraction.

These build tiny synthetic ELF shared objects in memory (no compiler, no Ghidra)
and drive extraction over a synthetic APK, so they run anywhere.
"""

import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reakit.config import ConfigManager
from reakit import native


def build_elf(
    *,
    bits: int = 64,
    machine: int = 183,        # EM_AARCH64
    e_type: int = 3,           # ET_DYN
    little: bool = True,
    exports: tuple[str, ...] = ("JNI_OnLoad", "Java_com_x_Y_z"),
    imports: tuple[str, ...] = ("dlopen",),
    soname: str = "libtest.so",
) -> bytes:
    """Hand-builds a minimal but valid ELF with .dynsym/.dynstr/.dynamic/.text.

    Enough structure for reakit.native.ElfFile to parse machine, symbols,
    DT_NEEDED / DT_SONAME and exported/imported symbol classification.
    """
    endian = "<" if little else ">"
    is64 = bits == 64

    # --- string table for section names ---
    shstr = b"\x00"
    sh_offsets = {}
    for name in (".text", ".dynsym", ".dynstr", ".dynamic", ".shstrtab", ".comment"):
        sh_offsets[name] = len(shstr)
        shstr += name.encode() + b"\x00"

    # --- .dynstr: symbol + soname strings ---
    dynstr = b"\x00"
    str_off = {}
    for s in (*exports, *imports, soname):
        if s not in str_off:
            str_off[s] = len(dynstr)
            dynstr += s.encode() + b"\x00"

    # --- .dynsym ---
    def sym(name, defined):
        st_name = str_off[name]
        st_info = (1 << 4)  # STB_GLOBAL, STT_NOTYPE
        st_shndx = 1 if defined else 0  # 1 = .text, 0 = SHN_UNDEF
        if is64:
            return struct.pack(endian + "IBBHQQ", st_name, st_info, 0, st_shndx, 0x1000, 0)
        return struct.pack(endian + "IIIBBH", st_name, 0x1000, 0, st_info, 0, st_shndx)

    dynsym = sym("\x00" if False else exports[0], True)[:0]  # placeholder
    dynsym = b""
    # index 0 is the null symbol
    dynsym += (b"\x00" * (24 if is64 else 16))
    for e in exports:
        dynsym += sym(e, True)
    for i in imports:
        dynsym += sym(i, False)

    # --- .dynamic: DT_NEEDED(libc.so via dynstr) DT_SONAME DT_NULL ---
    # add libc.so to dynstr
    libc_off = len(dynstr)
    dynstr += b"libc.so\x00"
    soname_off = str_off[soname]
    dyn_fmt = endian + ("qQ" if is64 else "iI")
    dynamic = b""
    dynamic += struct.pack(dyn_fmt, 1, libc_off)     # DT_NEEDED
    dynamic += struct.pack(dyn_fmt, 14, soname_off)  # DT_SONAME
    dynamic += struct.pack(dyn_fmt, 0, 0)            # DT_NULL

    text = b"\x00" * 32
    comment = b"REAKit synthetic\x00"

    # --- lay out sections in the file after the header + section table ---
    if is64:
        eh_size = 64
        sh_entsize = 64
    else:
        eh_size = 52
        sh_entsize = 40
    num_sections = 7  # null + 6 named
    sht_off = eh_size
    body_off = sht_off + num_sections * sh_entsize

    blobs = {
        ".text": text,
        ".dynsym": dynsym,
        ".dynstr": dynstr,
        ".dynamic": dynamic,
        ".shstrtab": shstr,
        ".comment": comment,
    }
    offsets = {}
    cur = body_off
    for name, blob in blobs.items():
        offsets[name] = cur
        cur += len(blob)
    total = cur

    buf = bytearray(total)

    # ELF header
    buf[0:4] = b"\x7fELF"
    buf[4] = 2 if is64 else 1
    buf[5] = 1 if little else 2
    buf[6] = 1  # version
    if is64:
        struct.pack_into(
            endian + "HHIQQQIHHHHHH", buf, 16,
            e_type, machine, 1, 0, 0, sht_off, 0,
            eh_size, 0, 0, sh_entsize, num_sections, 5,  # shstrndx = 5
        )
    else:
        struct.pack_into(
            endian + "HHIIIIIHHHHHH", buf, 16,
            e_type, machine, 1, 0, 0, sht_off, 0,
            eh_size, 0, 0, sh_entsize, num_sections, 5,
        )

    # Section headers. Index order must match shstrndx=5 (.shstrtab).
    sh_types = {
        ".text": 1, ".dynsym": 11, ".dynstr": 3,
        ".dynamic": 6, ".shstrtab": 3, ".comment": 1,
    }
    section_list = [".text", ".dynsym", ".dynstr", ".dynamic", ".shstrtab", ".comment"]

    def write_sh(idx, name, addr=0):
        off = sht_off + idx * sh_entsize
        name_off = sh_offsets[name] if name else 0
        blob = blobs.get(name, b"")
        entsize = (24 if is64 else 16) if name == ".dynsym" else (
            (16 if is64 else 8) if name == ".dynamic" else 0
        )
        link = 2 if name == ".dynsym" else 0  # .dynsym links to .dynstr (index 2)
        if is64:
            struct.pack_into(
                endian + "IIQQQQIIQQ", buf, off,
                name_off, sh_types.get(name, 0), 0, addr,
                offsets.get(name, 0), len(blob), link, 0, 0, entsize,
            )
        else:
            struct.pack_into(
                endian + "IIIIIIIIII", buf, off,
                name_off, sh_types.get(name, 0), 0, addr,
                offsets.get(name, 0), len(blob), link, 0, 0, entsize,
            )

    write_sh(0, "")  # null section
    for i, name in enumerate(section_list, start=1):
        write_sh(i, name, addr=0x1000 if name == ".text" else 0)

    for name, blob in blobs.items():
        buf[offsets[name]:offsets[name] + len(blob)] = blob

    return bytes(buf)


class TestElfParser(unittest.TestCase):
    def test_parse_aarch64_dyn(self):
        info = native.parse_elf_bytes(build_elf(bits=64, machine=183))
        self.assertTrue(info["valid"], info.get("error"))
        self.assertEqual(info["bits"], 64)
        self.assertEqual(info["machine"], "AArch64")
        self.assertEqual(info["abi_guess"], "arm64-v8a")
        self.assertEqual(info["type"], "DYN")
        self.assertEqual(info["soname"], "libtest.so")
        self.assertIn("libc.so", info["needed"])
        self.assertIn("JNI_OnLoad", info["exports"])
        self.assertIn("Java_com_x_Y_z", info["jni_exports"])
        self.assertTrue(info["has_jni_onload"])
        self.assertIn("dlopen", info["imports"])

    def test_parse_arm32_and_x86(self):
        arm = native.parse_elf_bytes(build_elf(bits=32, machine=40))
        self.assertEqual(arm["machine"], "ARM")
        self.assertEqual(arm["abi_guess"], "armeabi-v7a")
        self.assertEqual(arm["bits"], 32)
        x86 = native.parse_elf_bytes(build_elf(bits=64, machine=62))
        self.assertEqual(x86["machine"], "x86-64")
        self.assertEqual(x86["abi_guess"], "x86_64")

    def test_not_elf_and_payload_detection(self):
        info = native.parse_elf_bytes(b"PK\x03\x04rest-of-zip")
        self.assertFalse(info["valid"])
        self.assertEqual(info["payload"], "ZIP/JAR/APK archive")
        dex = native.parse_elf_bytes(b"dex\n035\x00stuff")
        self.assertEqual(dex["payload"], "DEX bytecode (dynamic feature module)")
        junk = native.parse_elf_bytes(b"\x01\x02\x03\x04nope")
        self.assertFalse(junk["valid"])
        self.assertIsNone(junk["payload"])


class TestClassify(unittest.TestCase):
    def test_packer_detection(self):
        self.assertEqual(native.classify_library("libjiagu.so")["packer"], "360 Jiagu")
        self.assertEqual(native.classify_library("libtprt.so")["packer"], "Tencent TPRT")
        self.assertIsNone(native.classify_library("librandom.so")["packer"])

    def test_framework_exact_vs_prefix(self):
        # exact match only - the libapplog_rust.so false positive we fixed
        self.assertEqual(native.classify_library("libapp.so")["framework"],
                         "Flutter AOT snapshot (Dart code lives here)")
        self.assertIsNone(native.classify_library("libapplog_rust.so")["framework"])
        self.assertEqual(native.classify_library("libflutter.so")["framework"], "Flutter engine")
        self.assertEqual(native.classify_library("libhermes.so")["framework"],
                         "React Native (Hermes VM)")


class TestExtraction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "ws"
        self.pkg = "com.test.native"
        apks = self.ws / self.pkg / "apks"
        apks.mkdir(parents=True)
        # base.apk with two ABIs + an embedded packer lib + a disguised zip
        with zipfile.ZipFile(apks / "base.apk", "w") as z:
            z.writestr("lib/arm64-v8a/libfoo.so", build_elf(bits=64, machine=183))
            z.writestr("lib/armeabi-v7a/libfoo.so", build_elf(bits=32, machine=40))
            z.writestr("lib/x86_64/libjiagu.so", build_elf(bits=64, machine=62, soname="libjiagu.so"))
            z.writestr("assets/libhidden.so", b"PK\x03\x04not-an-elf")
        self.cfg = ConfigManager(workspace_root=str(self.ws))

    def tearDown(self):
        self.tmp.cleanup()

    def test_extract_and_manifest(self):
        extractor = native.NativeExtractor(self.cfg)
        manifest = extractor.extract_package(self.pkg)
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["count"], 4)
        self.assertEqual(sorted(manifest["abis"]), ["arm64-v8a", "armeabi-v7a", "embedded", "x86_64"])

        names = {l["name"] for l in manifest["libraries"]}
        self.assertEqual(names, {"libfoo.so", "libjiagu.so", "libhidden.so"})

        jiagu = next(l for l in manifest["libraries"] if l["name"] == "libjiagu.so")
        self.assertEqual(jiagu["packer"], "360 Jiagu")

        hidden = next(l for l in manifest["libraries"] if l["name"] == "libhidden.so")
        self.assertFalse(hidden["elf"]["valid"])
        self.assertEqual(hidden["elf"]["payload"], "ZIP/JAR/APK archive")

        # manifest persisted and reloadable
        again = extractor.load_manifest(self.pkg)
        self.assertEqual(again["count"], 4)

    def test_abi_filter_and_resolve(self):
        extractor = native.NativeExtractor(self.cfg)
        # include_embedded=False so the ABI filter is the only thing selecting libs
        extractor.extract_package(self.pkg, abis=["arm64-v8a"], include_embedded=False)
        libs = extractor.list_libraries(self.pkg)
        self.assertTrue(libs)
        self.assertTrue(all(l["abi"] == "arm64-v8a" for l in libs))
        resolved = extractor.resolve_library(self.pkg, name="libfoo")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.parent.name, "arm64-v8a")


class TestEndpointSpecAndAliases(unittest.TestCase):
    def test_spec_loads_when_present(self):
        if not native.ENDPOINT_SPEC_PATH.is_file():
            self.skipTest("GhidraMCP checkout not present")
        spec = native.load_endpoint_spec()
        self.assertGreater(len(spec), 200)
        self.assertIn("/decompile_function", spec)

    def test_aliases_map_to_real_endpoints(self):
        if not native.ENDPOINT_SPEC_PATH.is_file():
            self.skipTest("GhidraMCP checkout not present")
        spec = native.load_endpoint_spec()
        for alias, (endpoint, _positional) in native.QUERY_ALIASES.items():
            self.assertIn(endpoint, spec, f"alias {alias} -> {endpoint} not in spec")


if __name__ == "__main__":
    unittest.main(verbosity=2)
