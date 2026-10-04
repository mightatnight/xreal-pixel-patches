# Verification

## Setup

| | |
|---|---|
| Glasses | XREAL Air 2 Pro, PID `0x0432` |
| Phone | Google Pixel 10 Pro, Android 17 beta `DP11.260918.006`, kernel 6.12 |
| Laptop | AMD Radeon 880M (DCN 3.5), Linux 7.2, Hyprland |
| Base firmware | nyan Real kit Air 2 outputs (DP `46556947…`, MCU `950CA953…`) |

Bridge state was read through a diagnostic MCU build that adds a read-only bridge
register command, from the laptop and from an Android app on the Pixel. That diagnostic
tooling is not part of this repository; the released patches only touch the DP image.

## Results with the released patch set (`mkcalc` + `nohdcp`)

| Host | Mode | Result |
|---|---|---|
| Pixel 10 Pro | 1080p60, HBR, 4 lanes | **picture**, panel VSYNC 60/s, PCR stable, link state `0B`; PLL ends on the bridge's own measured value |
| Pixel 10 Pro | 1280×720 (nyan true-720p) | picture shifted / wrapping, judder |
| Laptop | 1080p60 | picture (patch inactive: measurement non-zero) |
| Laptop | 1080p90 | PCR locked and stable, link state `0B` (register check; not visually confirmed with this exact image) |
| Laptop | 1280×720 (nyan true-720p) | picture shifted / wrapping |
| Laptop | DPCD read | Bcaps `00`, RxCaps `00 00 00` |

The official-base output (`82F168B4…`) applies the same patch bytes at the same vendor
addresses and passes the builder's and the kit's checks, but was not flashed.

## Patch-set matrix on the Pixel (1080p60)

| DP image (on nyan base) | Pixel |
|---|---|
| unpatched | black |
| `nohdcp` | black (PCR measurement 0) |
| `nohdcp` + RBR forced + Mvid gate bypass | black |
| `mkcalc` (HDCP still advertised) | black (stall at state 8 during HDCP) |
| constant PLL fallback + `nohdcp` + RBR + Mvid bypass | picture |
| **`mkcalc` + `nohdcp`** (released) | **picture** |

## 720p (nyan true-720p mode)

| DP image | Laptop 720p |
|---|---|
| nyan unpatched | correct |
| `mkcalc` + `nohdcp` | broken |
| print-preserving variant of `mkcalc`, alone or with HDCP off | broken |
| HDCP off that keeps the vendor "Valid" setup writes | broken |

At 720p the PCR state was identical to the unpatched image (vendor-measured PLL value,
band 4, stable). The cause was not isolated; 720p is listed as a known limitation.

## Offline checks run by the builder

- exact input SHA-256 (official `1140` or nyan Air 2 DP output);
- guard bytes at every patch site;
- only the patch records, the bank0 tag and the container CRC change;
- bank0 tag (CRC-8) and container CRC-32 verified with the nyan kit's routines;
- deterministic rebuild, pinned output SHA-256.
