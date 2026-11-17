#!/usr/bin/env python3
"""
Build "Recursive Martijn": a 4-style code family instanced from the Recursive VF,
modelled on Rec Mono Duotone (frozen code stylistic sets, code ligatures in calt,
reduced-slant italics, RIBBI naming).

Note: this is a proportional font specced for programming. With MONO at 0.35
the glyphs have varying advance widths (post.isFixedPitch is 0), so it will
not keep columns aligned the way a true monospace font (MONO 1) does.

Usage (from repo root):
    ./venv/bin/python src/build-scripts/recursive-martijn/build.py
"""

import subprocess
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

REPO = Path(__file__).resolve().parents[3]
VF = REPO / "fonts/ArrowType-Recursive-1.085/Recursive_Desktop/Recursive_VF_1.085.ttf"
OUT = REPO / "fonts/RecursiveMartijn"

FAMILY = "Recursive Martijn"
PS_FAMILY = "RecursiveMartijn"
VERSION = "1.085"

# Shared by all four styles
BASE = {"MONO": 0.35, "CRSV": 1}
ITALIC_SLNT = -10  # same reduced slant as Rec Mono for Code

# Duotone mix (as in Rec Mono Duotone): a near-Linear Regular,
# Casual (CASL 1) for Italic, Bold & Bold Italic. Duotone's bolds are wght 750;
# we use 700, which reads less heavy in an editor.
BOLD_WGHT = 700
STYLES = {
    # style name: (CASL, wght, slnt, bold, italic)
    "Regular": (0.1, 400, 0, False, False),
    "Italic": (1, 400, ITALIC_SLNT, False, True),
    "Bold": (1, BOLD_WGHT, 0, True, False),
    "Bold Italic": (1, BOLD_WGHT, ITALIC_SLNT, True, True),
}

# Same frozen features as Rec Mono for Code
FREEZE = "ss03,ss05,ss08,ss09,ss12"


def dlig_to_calt(font):
    """Rename dlig -> calt so code ligatures are on by default, keep FeatureList sorted."""
    gsub = font["GSUB"].table
    records = gsub.FeatureList.FeatureRecord
    for r in records:
        if r.FeatureTag == "dlig":
            r.FeatureTag = "calt"
    order = sorted(range(len(records)), key=lambda i: records[i].FeatureTag)
    remap = {old: new for new, old in enumerate(order)}
    gsub.FeatureList.FeatureRecord = [records[i] for i in order]
    for sr in gsub.ScriptList.ScriptRecord:
        langsyses = [sr.Script.DefaultLangSys] + [l.LangSys for l in sr.Script.LangSysRecord]
        for ls in filter(None, langsyses):
            ls.FeatureIndex = sorted(remap[i] for i in ls.FeatureIndex)
            if ls.ReqFeatureIndex != 0xFFFF:
                ls.ReqFeatureIndex = remap[ls.ReqFeatureIndex]


def set_names(font, style, bold, italic):
    ps_style = style.replace(" ", "")
    full = FAMILY if style == "Regular" else f"{FAMILY} {style}"
    name = font["name"]
    # drop everything except copyright/trademark/license-ish records, then write fresh
    keep = {0, 7, 8, 9, 11, 12, 13, 14}
    name.names = [n for n in name.names if n.nameID in keep]
    values = {
        1: FAMILY,
        2: style,
        3: f"{VERSION};ARRW;{PS_FAMILY}-{ps_style}",
        4: full,
        5: f"Version {VERSION}",
        6: f"{PS_FAMILY}-{ps_style}",
        16: FAMILY,
        17: style,
    }
    for nid, val in values.items():
        name.setName(val, nid, 3, 1, 0x409)
        name.setName(val, nid, 1, 0, 0)

    os2 = font["OS/2"]
    os2.usWeightClass = BOLD_WGHT if bold else 400
    fs = os2.fsSelection & ~(1 | 32 | 64)  # clear ITALIC, BOLD, REGULAR
    fs |= (1 if italic else 0) | (32 if bold else 0)
    if not bold and not italic:
        fs |= 64
    os2.fsSelection = fs
    font["head"].macStyle = (1 if bold else 0) | (2 if italic else 0)
    font["post"].italicAngle = float(ITALIC_SLNT) if italic else 0.0

    # Drop the STAT/variation leftovers that reference removed name IDs
    for tag in ("STAT",):
        if tag in font:
            del font[tag]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    freezer = Path(sys.executable).parent / "pyftfeatfreeze"
    for style, (casl, wght, slnt, bold, italic) in STYLES.items():
        loc = dict(BASE, CASL=casl, wght=wght, slnt=slnt)
        print(f"{style}: {loc}")
        font = instancer.instantiateVariableFont(
            TTFont(VF), loc, updateFontNames=False
        )
        tmp = OUT / f"_tmp-{style.replace(' ', '')}.ttf"
        font.save(tmp)

        final = OUT / f"{PS_FAMILY}-{style.replace(' ', '')}-{VERSION}.ttf"
        subprocess.run(
            [str(freezer), "-f", FREEZE, str(tmp), str(final)], check=True
        )
        tmp.unlink()

        font = TTFont(final)
        dlig_to_calt(font)
        set_names(font, style, bold, italic)
        widths = {w for w, _ in font["hmtx"].metrics.values() if w}
        font["post"].isFixedPitch = 1 if len(widths) == 1 else 0
        font.save(final)
        print(f"  -> {final.relative_to(REPO)}")


if __name__ == "__main__":
    main()
