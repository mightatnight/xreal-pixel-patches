# Root cause: XREAL Air 2 / Air 2 Pro black on Pixel 10 Pro

Addresses are 8051 code addresses in the Air 2-family DP-bridge image `1140`
(file offset = code + `0x40`, see the nyan kit's container documentation). Registers are
bridge `page:reg`, as the bridge firmware addresses them in XDATA.

## What the phone sees

Everything looks healthy from Android's side once the external display is enabled:
DisplayPort alt mode on 4 lanes (pin assignment C), HPD high, link training "success",
EDID read (1920×1080@60, 1280×720@60), SurfaceFlinger presenting frames, USB audio
working. The glasses stay black. The same happens with official firmware.

Note: if the "use / mirror display" prompt is dismissed, Android keeps the external
display disabled and sends no frames at all. That is a separate, phone-side reason for a
black screen; accept the prompt first.

## Where the bridge stops

Bridge state read live from the glasses while the Pixel drove them, compared with a
working laptop (same 1080p60 RGB 8-bit stream; Mvid/Nvid `0x8000` on both):

| Register | Meaning | Laptop (picture) | Pixel (black) |
|---|---|---|---|
| `E0:90` | link state machine | `0B` | `09` |
| `E3:6C` bit 7 | PCR PLL lock | set | set |
| `F2:DF` bit 6 | pixel clock (PCR) stable | **set** | **clear** |
| `F2:F4..F8` | PCR clock measurement | real value, band 3 | **0**, default `F7=0x28`, band 0 |
| `F2:37/3A/3B/3C` | PCR PLL setting | `00 04 F7 CA` | **`00 00 00 00`** |
| XDATA `0446` | video OK flag | `01` | `00` |
| page `E7` | output timing | configured | empty |
| `F1:CC..D3` | per-lane error counters | `0x8000` (clean) | `0x8000` (clean) |

The lanes are clean and the stream header is correct; the bridge simply never gets a
usable pixel clock.

## The mechanism

The pixel-clock-recovery (PCR) state machine (sub-state XDATA `06EC`, code
`0x4600..0x48F8`) runs per link start:

- **state 0** (`0x461F`) resets the measurement;
- **state 1** (`0x467B`) waits until the measurement is ready (`F2:E2 & 0x30 == 0x10`,
  10 rounds), takes `MK = F2:F6:F5:F4` (stored at XDATA `0448`), prints
  `"MKvalue = 0x%lx"`, sets the band `F2:63[2:0]` from `F2:F8`, and programs the PLL:
  `F2:37/3A/3B/3C = MK`;
- later states wait for lock and stability.

With the Pixel 10 Pro's stream the measurement in state 1 returns **zero**. The firmware
does not check it: the PLL is programmed with 0, produces no clock, the next measurement
is zero again, and the loop never recovers. PCR never becomes stable, the link state
machine stays at 9, the video-OK flag stays 0, and the glasses' MCU — which only opens the
OLED panels after it sees video — keeps them off.

Giving the PLL any sane starting value breaks the loop: once a clock exists, the
firmware's own re-measurement works and it reprograms the PLL with the real value
(`0x04F7CA` on the Pixel at 1080p60, identical to the laptop's).

Why the Pixel's stream starts the measurement at zero while a laptop's does not was not
determined (the stream header, colour format and link were ruled out; see
[verification.md](verification.md)).

## The fix: `mkcalc`

The 21-byte `MKvalue` print sequence at `0x472F` is replaced by `LCALL 0x9166` (plus
padding). The routine at `0x9166` ([`patches/mkcalc.asm`](../patches/mkcalc.asm), 145
bytes in unreferenced zero padding before the HDCP-init routine at `0x91FD`):

1. returns immediately if the measured MK (XDATA `0448`) is non-zero — the vendor path is
   untouched on hosts where the measurement works;
2. otherwise computes the stream's pixel clock ratio from values the bridge already has:
   `Q = (LINK_BW_SET × Mvid) / (Nvid >> 6)` — `LINK_BW_SET` is IRAM `2E` (stored by the
   AUX handler for writes to DPCD `0x100`), Mvid is `F3:CC..CE`, Nvid is `F3:D8..DA`;
3. picks the band as the number of doublings until `Q × 2^band ≥ 0x7C0` (1080p → 3,
   720p → 4, 1080p120 / SBS60 → 2, matching the bands the firmware measures itself);
4. sets `F2:63[2:0]` = band and stores `MK = (Q << band) × 116` to `0448`, from where the
   vendor code programs the PLL.

The firmware's own 32-bit multiply (`0x1963`) and divide (`0x19EE`) are used. If no
stream data is available, the 1080p60 values are used.

## The second problem: HDCP during link bring-up — `nohdcp`

The Pixel starts HDCP about a second after video starts (HDCP 2.2 attempts that fail at
the pairing step, then HDCP 1.x). With HDCP advertised, the bridge stalls at `E0:90 = 8`
during this and never reaches PCR state 1, so `mkcalc` alone does not help.

The same stall is reproducible on a laptop: requesting HDCP before or within ~4 s of
video start keeps the glasses dark (even after HDCP is turned off again), while HDCP
enabled on an already running picture works fine.

The per-connect HDCP init (`0x91FD`, called from the link state machine at `0x3512`)
already has an "HDCP Invalid" branch (taken when XDATA `E6DE.5` is clear or `E0BC` is
non-zero). `nohdcp` makes that branch unconditional (`0x9219` `JNZ 928A` → `SJMP 928A`).
DPCD Bcaps `0x68028` reads `00` and RxCaps `0x6921D` reads `00 00 00` afterwards, so the
phone never starts HDCP.

## Ruled out (tested on hardware)

| Hypothesis | Test | Result |
|---|---|---|
| Phone-side display policy | display enabled, frames presented | still black |
| Glasses cannot decrypt HDCP | HDCP 2.2 enabled on a running laptop picture | picture stays |
| HDCP alone | `nohdcp` only (HDCP no longer advertised, no HDCP on the Pixel) | still black |
| Mvid equality gate (`0x8E2E`, needs 4 identical Mvid samples) | gate bypassed | still black; the Pixel's Mvid is constant anyway |
| Link rate HBR vs RBR | RBR forced (`06CF` = `06`) | still black |
| Colour format / bit depth | MISC0 `F3:EB` | `0x20` (RGB 8 bpc) on both hosts |
