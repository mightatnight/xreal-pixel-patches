# xreal-pixel-patches

Firmware patches that make **XREAL Air 2 / Air 2 Pro** glasses show a picture on the
**Google Pixel 10 Pro** over USB-C DisplayPort.

On a Pixel 10 Pro the glasses play sound, Android reports an external display, the link
trains — and the screens stay black. This happens on official and on nyan Real firmware.
The cause is in the glasses' DisplayPort bridge firmware, and this repository patches it.

---

## ⚠️ WARNING — this can break your glasses

**These patches rewrite the firmware of your glasses. A wrong image, an interrupted
transfer or a mistake on your side can leave the glasses unusable. You use this
entirely at your own risk. Nobody here is responsible for a damaged device.**

- **No firmware is distributed here.** Not XREAL's, not nyan's builds, not the patched
  result. You supply the input image yourself; the builder turns it into a patched image
  on your machine. Do not open issues asking for firmware or download links.
- **Keep the official firmware files.** They are your only recovery path. Full firmware
  readback from the glasses is not available.
- Read the nyan Real firmware kit's own warnings and instructions first. Everything here
  sits on top of that kit, and its rules apply.
- **Tested on exactly one setup** (Air 2 Pro + Pixel 10 Pro, see below). Anything else is
  untested.

---

## 🙏 A BIG thank you to nyan (8796n)

**This project would not exist without the [nyan Real firmware kit](https://github.com/8796n/nyan-real-firmware-kit)
by [8796n](https://github.com/8796n).** nyan reverse-engineered the Air-family firmware
container, its CRC and bank0 tag, the HID protocol, the DP-bridge and MCU flashing
procedures, and published a careful, guarded, reproducible way to build and flash patched
images — without distributing a single byte of firmware.

Everything here stands on that work: the container and checksum code is nyan's, the
flashing is done by nyan's flashers, the recommended base is nyan's Air 2 build, and the
"patches, never firmware" approach is copied from nyan's kit on purpose. If this helps
you, please go and star [nyan's kit](https://github.com/8796n/nyan-real-firmware-kit)
and check out [nyan Real / Spatial Wall](https://github.com/8796n/nyan-real-spatial-wall).

**ありがとうございます、nyan!**

---

## What the patches do

| Patch | Where | Effect |
|---|---|---|
| `mkcalc` | DP bridge, code `0x472F` + 145 bytes at `0x9166` | When the bridge's pixel-clock measurement comes back as zero (what happens with the Pixel 10 Pro), compute a starting PLL band/value from the video stream itself (link rate × Mvid / Nvid) so the pixel clock can lock. The bridge's own re-measurement then takes over. A normal (non-zero) measurement is left untouched. |
| `nohdcp` | DP bridge, code `0x9219` (1 byte) | The glasses stop advertising HDCP, so the phone does not start HDCP while the link is coming up (that early handshake stalls the bridge's startup). |

Both are required. The full analysis — registers, firmware addresses, what was ruled
out — is in [docs/root-cause.md](docs/root-cause.md); test results are in
[docs/verification.md](docs/verification.md).

## Trade-offs

- **No HDCP on any host.** Protected video (Netflix and similar) will refuse to play or
  drop to low resolution on the glasses, on every device. Normal desktop, games and video
  are unaffected.
- **nyan's true-720p mode is broken** with the patched nyan image (the picture wraps
  vertically and judders). Use 1080p. The official base does not offer 720p at all.
- 72 / 90 / 120 Hz and Full-SBS were not tested on the Pixel.
- Only the DP bridge image is patched. Keep the MCU image that belongs to your base.

## Tested

| | |
|---|---|
| Glasses | XREAL Air 2 Pro (PID `0x0432`) |
| Phone | Pixel 10 Pro, Android 17 beta (`DP11.260918.006`) — 1080p60, HBR, 4 lanes |
| Also checked | Linux laptop (AMD Radeon 880M): still works |
| Base | **nyan Air 2 build: hardware-tested.** Official base: built and checked offline only. |
| Air 2 (non-Pro) | same image, untested |

## Inputs and outputs

The builder accepts exactly one of these inputs and pins the output:

| Base | Input DP image | Input SHA-256 | Output SHA-256 |
|---|---|---|---|
| nyan Real kit (recommended, tested) | nyan's Air 2 DP output | `46556947E81DD7EBBD7F26B2541B63E0362804C166C020639DA908D2ABB2F486` | `F8C401B4B724451963943AAE4F9A2CE4D9FC098959187D231E39AD81812A3AD8` |
| official | `1140` | `350BACE369A83823D8EF867AE04AD07CF64D724C10EC7CEECFB83861AC9672F3` | `82F168B47BB1177AAEBF971AF76EDA27092107ED02F64BBBE345963E14709E2A` |

Pair the patched DP image with the **MCU image of the same base**: nyan's Air 2 MCU
output for the nyan base, the official `09.1.00.180_20240507.bin` for the official base.

## How to use

Python 3.10+. Run everything from the repository root.

### 1. Get the code (with nyan's kit as a submodule)

```bash
git clone --recursive https://github.com/mightatnight/xreal-pixel-patches
cd xreal-pixel-patches
pip install -r requirements.txt        # hidapi, only needed for flashing
```

### 2. Put the official firmware where nyan's kit expects it

Follow the [nyan kit README](https://github.com/8796n/nyan-real-firmware-kit/blob/main/README.en.md):
place the official Air 2 / Air 2 Pro files (you obtain them yourself) at

```
nyan-real-firmware-kit/firmware/air2/1140
nyan-real-firmware-kit/firmware/air2/09.1.00.180_20240507.bin
```

and back them up somewhere else as well. The flashers refuse to run without them.

### 3. Build the input and the patched DP image

nyan base (recommended — build nyan's images first with nyan's builders):

```bash
python nyan-real-firmware-kit/xreal/air2/build_dp.py  --src nyan-real-firmware-kit/firmware/air2/1140 --out air2-dp.bin
python nyan-real-firmware-kit/xreal/air2/build_mcu.py --src nyan-real-firmware-kit/firmware/air2/09.1.00.180_20240507.bin --out air2-mcu.bin
python patches/build_dp.py --src air2-dp.bin --out air2-dp-pixel.bin
```

official base:

```bash
python patches/build_dp.py --src nyan-real-firmware-kit/firmware/air2/1140 --out air2-dp-pixel.bin
```

Check that the printed output SHA-256 matches the table above. `--check-only` builds in
memory, `--verify FILE` proves an existing file is byte-identical.

### 4. Flash — MCU first, then DP

Connect only the target glasses directly to the computer. Do not unplug or let the
computer sleep during a transfer. On Linux run as root (or grant hidraw/USB access).

```bash
# MCU of the same base
python nyan-real-firmware-kit/xreal/mcu_flash.py --image air2-mcu.bin --flash     # nyan base
python nyan-real-firmware-kit/xreal/mcu_flash.py --restore --flash                # official base

# patched DP: inspect first, then write
python tools/flash_dp.py --image air2-dp-pixel.bin
python tools/flash_dp.py --image air2-dp-pixel.bin --flash
```

`tools/flash_dp.py` runs nyan's `dp_flash.py` unmodified and only allows the two pinned
output hashes in addition to the kit's own. After the write the DP version must read
`1140`; `1109` means the bridge fell back to its internal image (recoverable — flash a
good image again).

### 5. On the Pixel

Plug the glasses in and **accept the "use / mirror display" prompt**. If it was dismissed
once, Android keeps the external display disabled (black) until it is enabled again.

## Going back

```bash
python tools/flash_dp.py --image air2-dp.bin --flash        # nyan's unpatched DP image
python tools/flash_dp.py --restore --flash                  # official DP image
```

See the nyan kit's "If something goes wrong" section for fallback and bootloader recovery.

## Repository layout

```
patches/build_dp.py     builds the patched DP image from your input (no hardware access)
patches/mkcalc.asm      source of the 8051 fallback routine
patches/asm8051.py      tiny assembler used to build it
tools/flash_dp.py       allowlist wrapper around the nyan kit's DP flasher
docs/                   root cause and verification
nyan-real-firmware-kit/ submodule: https://github.com/8796n/nyan-real-firmware-kit
```

## License

Apache License 2.0, the same as the nyan Real firmware kit. See [LICENSE](LICENSE) and
[NOTICE](NOTICE). The license covers this repository's code and documentation only, not
any firmware it processes.

Not affiliated with, endorsed by, or connected to XREAL, Google, or the nyan Real
project. Product names are used only to identify the hardware.
