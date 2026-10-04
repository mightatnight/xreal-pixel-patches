#!/usr/bin/env python3
"""Flash the Pixel-fix DP image with the nyan Real firmware kit's own DP flasher.

The kit's xreal/dp_flash.py is used unmodified.  At runtime this wrapper only adds the
two output SHA-256s pinned in patches/build_dp.py to its allowlist (Air 2 / Air 2 Pro
PIDs).  Everything else is the kit's: PID and container checks, bank0 tag, the
official recovery image requirement (nyan-real-firmware-kit/firmware/air2/1140),
ack handling and the post-flash version read.

  python tools/flash_dp.py                                 identify glasses, read DP version
  python tools/flash_dp.py --image air2-dp-pixel.bin       inspect only, nothing is written
  python tools/flash_dp.py --image air2-dp-pixel.bin --flash
  python tools/flash_dp.py --restore --flash               official DP image back
  python tools/flash_dp.py --offline-check FILE            image checks only, no USB access

Linux: run as root or give your user access to the glasses' hidraw/USB nodes.
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "nyan-real-firmware-kit" / "xreal"
if not (KIT / "dp_flash.py").exists():
    sys.exit("nyan-real-firmware-kit submodule missing: git submodule update --init")
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(ROOT / "patches"))

OFFLINE = "--offline-check" in sys.argv
if OFFLINE:                                   # the kit imports hid at module load
    sys.modules.setdefault("hid", types.ModuleType("hid"))

import build_dp          # noqa: E402  pinned outputs
import dp_flash as F     # noqa: E402  nyan Real firmware kit, Apache-2.0

AIR2_PIDS = {0x0428, 0x0432}
PINNED = {out: "Pixel fix (mkcalc+nohdcp) on " + name for name, out in build_dp.INPUTS.values()}
for digest, label in PINNED.items():
    F.KNOWN_IMAGES[digest] = (set(AIR2_PIDS), label)
_approved = F.image_approved
F.image_approved = lambda profile, digest: _approved(profile, digest) or (
    digest in PINNED and profile["project"] == 0x0900)

if OFFLINE:
    path = Path(sys.argv[sys.argv.index("--offline-check") + 1])
    F.check_image(path.read_bytes(), None)
    print("offline check passed: the kit's container, CRC, bank0 and SHA checks accept", path)
else:
    F.main()
