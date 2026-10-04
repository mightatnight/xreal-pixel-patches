#!/usr/bin/env python3
"""Build an XREAL Air 2 / Air 2 Pro DP-bridge image that works with the Pixel 10 Pro.

You supply the input image; nothing is downloaded and no hardware is touched.
Accepted inputs (exact SHA-256, checked before anything else):

  official 1140              350BACE369A83823D8EF867AE04AD07CF64D724C10EC7CEECFB83861AC9672F3
  nyan Real kit Air 2 output 46556947E81DD7EBBD7F26B2541B63E0362804C166C020639DA908D2ABB2F486

Two guarded patches are applied (details in docs/root-cause.md):

  mkcalc   0x472F  the vendor's "MKvalue" debug print -> LCALL 0x9166 (patches/mkcalc.asm).
           When the bridge's pixel-clock measurement returns 0 (as it does with the
           Pixel 10 Pro), derive a PLL band/MK from the stream (link rate x Mvid / Nvid)
           so the PLL can start; the firmware's own re-measurement then takes over.
           A non-zero measurement is left untouched.
  nohdcp   0x9219  JNZ 928A -> SJMP 928A: the per-connect HDCP init always takes the
           vendor's "HDCP Invalid" branch, so the glasses stop advertising HDCP and the
           phone never starts it during link bring-up.

The container helpers (CRC-32, bank0 tag, validation) are the nyan Real firmware kit's
own, imported from the submodule.  Output SHA-256s are pinned per input.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
KIT = ROOT / "nyan-real-firmware-kit" / "xreal"
if not (KIT / "air2" / "build_dp.py").exists():
    sys.exit("nyan-real-firmware-kit submodule missing: git submodule update --init")
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(HERE))
from air2 import build_dp as kit  # noqa: E402  (nyan Real firmware kit, Apache-2.0)
from asm8051 import assemble      # noqa: E402

HDR = 0x40
CAVE = 0x9166                      # zero padding before the HDCP-init routine at 0x91FD
CAVE_END = 0x91FD
MKCALC = assemble((HERE / "mkcalc.asm").read_text().splitlines(), CAVE)

# (label, code address, guard bytes expected at that address, replacement)
PATCHES = [
    ("mkcalc: hook the MKvalue print", 0x472F,
     bytes.fromhex("7bff7a9f798a900448121afe9005e8121b16123fc1"),
     bytes.fromhex("129166") + bytes(18)),
    ("mkcalc: fallback routine", CAVE, bytes(len(MKCALC)), MKCALC),
    ("nohdcp: always take the HDCP Invalid branch", 0x9219,
     bytes.fromhex("706f7bff7ac3"), bytes.fromhex("80")),
]

INPUTS = {   # input SHA-256 -> (name, pinned output SHA-256)
    kit.STOCK_SHA256: ("official 1140",
                       "82F168B47BB1177AAEBF971AF76EDA27092107ED02F64BBBE345963E14709E2A"),
    kit.OUTPUT_SHA256: ("nyan Real kit Air 2 output",
                        "F8C401B4B724451963943AAE4F9A2CE4D9FC098959187D231E39AD81812A3AD8"),
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest().upper()


def build(src: bytes) -> bytes:
    if len(MKCALC) > CAVE_END - CAVE:
        kit.fail("fallback routine does not fit the cave")
    out = bytearray(src)
    for label, code, guard, new in PATCHES:
        off = code + HDR
        if src[off:off + len(guard)] != guard:
            kit.fail("guard mismatch at code 0x%04X (%s)" % (code, label))
        out[off:off + len(new)] = new
    kit.fix_bank0_tag(out)
    kit.fix_container_crc(out)
    return bytes(out)


def verify(src: bytes, img: bytes) -> None:
    kit.validate_container(img, "patched image")
    payload = img[HDR:]
    if kit.crc8_tag(payload + b"\xFF" * (kit.BANK0 - 1 - len(payload)) + bytes([img[0x38]])):
        kit.fail("bank0 tag does not verify")
    allowed = {0, 1, 2, 3, 0x38}
    for _label, code, _guard, new in PATCHES:
        allowed |= set(range(code + HDR, code + HDR + len(new)))
    stray = [i for i, (a, b) in enumerate(zip(src, img)) if a != b and i not in allowed]
    if stray:
        kit.fail("bytes changed outside the patch records: " + " ".join("0x%X" % i for i in stray))
    if build(src) != img:
        kit.fail("build is not deterministic")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 epilog="You supply the firmware. This tool contains none and touches no hardware.")
    ap.add_argument("--src", type=Path, required=True, metavar="DP_IMAGE",
                    help="official 1140 or the nyan kit's Air 2 DP output")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path, metavar="FILE")
    group.add_argument("--check-only", action="store_true")
    group.add_argument("--verify", type=Path, metavar="FILE", help="check FILE is byte-identical to the build")
    a = ap.parse_args()

    src = a.src.read_bytes()
    digest = sha(src)
    if digest not in INPUTS:
        kit.fail("input SHA-256 %s is neither the official 1140 nor the nyan Air 2 output" % digest)
    kit.validate_container(src, "input")
    name, want = INPUTS[digest]
    img = build(src)
    verify(src, img)
    if sha(img) != want:
        kit.fail("output SHA-256 %s does not match the pinned %s" % (sha(img), want))

    print("=== XREAL Air 2 / Air 2 Pro DP for Pixel 10 Pro (mkcalc + nohdcp) ===")
    print("  input         : %s  %s" % (name, digest))
    for label, code, _guard, new in PATCHES:
        print("  patch         : 0x%04X  %-44s %d byte%s" % (code, label, len(new), "" if len(new) == 1 else "s"))
    print("  bank0 tag     : 0x%02X (verified)" % img[0x38])
    print("  container CRC : 0x%08X (verified)" % kit.head(img)["stored_crc"])
    print("  output SHA-256: %s (pinned)" % sha(img))
    if a.verify:
        if not a.verify.exists() or a.verify.read_bytes() != img:
            kit.fail("%s differs from the build or is missing" % a.verify)
        print("  verify        : %s [byte-identical]" % a.verify)
    elif a.check_only:
        print("  check-only    : nothing written")
    else:
        if a.out.resolve() == a.src.resolve():
            kit.fail("refusing to overwrite the input image")
        a.out.write_bytes(img)
        print("  wrote         : %s" % a.out)
    print("  hardware      : not touched")


if __name__ == "__main__":
    main()
