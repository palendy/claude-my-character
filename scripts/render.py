#!/usr/bin/env python3
"""Render /내캐릭터 result: profile.json (written by Claude) + stats.json → one offline HTML page.

The page holds a Wrapped-style story, the personality reading and a 1080x1350 share card
(inline SVG) with a [PNG로 저장] button. No network, no external fonts or scripts.

Usage: python3 render.py PROFILE.json STATS.json [--out ~/내캐릭터/내캐릭터-YYYYMMDD.html]
       python3 render.py --gallery OUT.html   # every species/eye/mouth/accessory, for checking
"""
import argparse
import datetime as dt
import html
import json
import math
import os
import sys

INK = "#3b2f2f"


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


# ======================================================================
# Character kit — everything lives in a 400x400 box, facing the viewer.
# ======================================================================
BODY_PATH = "M200 108 C292 108 332 172 332 242 C332 312 282 346 200 346 C118 346 68 312 68 242 C68 172 108 108 200 108 Z"
SW = 'stroke="%s" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"' % INK

SPECIES = [
    "cat", "dog", "bear", "panda", "rabbit", "fox", "hamster", "owl",
    "penguin", "dino", "ghost", "robot", "slime", "otter", "chick",
]
EYES = ["round", "sparkle", "sleepy", "determined", "wink", "dot", "star", "teary"]
MOUTHS = ["smile", "cat", "o", "flat", "grin", "smirk", "wobbly"]
ACCESSORIES = [
    "glasses", "magnifier", "coffee", "headset", "laptop", "nightcap", "wizard_hat", "crown",
    "hardhat", "checklist", "bow", "sprout", "flag", "sweat", "zzz", "sparkles", "rocket",
    "shield", "terminal", "bug_net", "scarf", "heart", "book", "wrench", "stopwatch", "lightbulb",
]


def shade(hex_color, f):
    """f<1 darker, f>1 lighter."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    if f < 1:
        r, g, b = (int(c * f) for c in (r, g, b))
    else:
        r, g, b = (int(c + (255 - c) * (f - 1)) for c in (r, g, b))
    return "#%02x%02x%02x" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def ears(sp, c):
    body, inner, dark = c["body"], c["cheek"], shade(c["body"], 0.75)
    if sp == "cat":
        return (f'<path d="M92 170 L104 74 L170 120 Z" fill="{body}" {SW}/>'
                f'<path d="M308 170 L296 74 L230 120 Z" fill="{body}" {SW}/>'
                f'<path d="M108 140 L113 98 L146 122 Z" fill="{inner}"/><path d="M292 140 L287 98 L254 122 Z" fill="{inner}"/>')
    if sp == "fox":
        return (f'<path d="M84 180 L96 56 L178 118 Z" fill="{body}" {SW}/>'
                f'<path d="M316 180 L304 56 L222 118 Z" fill="{body}" {SW}/>'
                f'<path d="M102 146 L108 86 L150 120 Z" fill="{INK}" opacity=".85"/><path d="M298 146 L292 86 L250 120 Z" fill="{INK}" opacity=".85"/>')
    if sp in ("bear", "panda", "otter"):
        col = INK if sp == "panda" else body
        r = 26 if sp == "otter" else 36
        y = 136 if sp == "otter" else 126
        return (f'<circle cx="112" cy="{y}" r="{r}" fill="{col}" {SW}/><circle cx="288" cy="{y}" r="{r}" fill="{col}" {SW}/>'
                + ("" if sp == "panda" else f'<circle cx="112" cy="{y}" r="{r-14}" fill="{inner}"/><circle cx="288" cy="{y}" r="{r-14}" fill="{inner}"/>'))
    if sp == "rabbit":
        return (f'<ellipse cx="156" cy="62" rx="24" ry="66" fill="{body}" {SW} transform="rotate(-8 156 62)"/>'
                f'<ellipse cx="244" cy="62" rx="24" ry="66" fill="{body}" {SW} transform="rotate(8 244 62)"/>'
                f'<ellipse cx="156" cy="66" rx="11" ry="46" fill="{inner}" transform="rotate(-8 156 66)"/>'
                f'<ellipse cx="244" cy="66" rx="11" ry="46" fill="{inner}" transform="rotate(8 244 66)"/>')
    if sp == "hamster":
        return (f'<circle cx="122" cy="128" r="24" fill="{body}" {SW}/><circle cx="278" cy="128" r="24" fill="{body}" {SW}/>'
                f'<circle cx="122" cy="128" r="12" fill="{inner}"/><circle cx="278" cy="128" r="12" fill="{inner}"/>')
    if sp == "owl":
        return (f'<path d="M100 158 L96 92 L150 124 Z" fill="{dark}" {SW}/>'
                f'<path d="M300 158 L304 92 L250 124 Z" fill="{dark}" {SW}/>')
    if sp == "dino":
        spikes = ""
        for i, (x, y) in enumerate([(130, 122), (165, 104), (200, 98), (235, 104), (270, 122)]):
            spikes += f'<path d="M{x-17} {y+16} L{x} {y-26} L{x+17} {y+16} Z" fill="{c["accent"]}" {SW}/>'
        return spikes
    if sp == "robot":
        return (f'<line x1="200" y1="112" x2="200" y2="62" {SW}/><circle cx="200" cy="56" r="14" fill="{c["accent"]}" {SW}/>'
                f'<rect x="54" y="196" width="22" height="56" rx="8" fill="{dark}" {SW}/><rect x="324" y="196" width="22" height="56" rx="8" fill="{dark}" {SW}/>')
    if sp == "chick":
        return f'<path d="M196 112 C186 84 200 72 206 70 C204 86 214 92 224 88 C220 102 210 108 204 112 Z" fill="{body}" {SW}/>'
    return ""


def tail(sp, c):
    if sp == "fox":
        return (f'<path d="M300 300 C380 290 392 200 352 170 C350 230 320 260 290 270 Z" fill="{c["body"]}" {SW}/>'
                f'<path d="M352 170 C372 186 380 210 376 232 C362 214 352 196 352 170 Z" fill="#ffffff"/>')
    if sp == "dino":
        return f'<path d="M300 300 C350 310 380 300 392 270 C370 300 330 286 310 268 Z" fill="{c["body"]}" {SW}/>'
    if sp == "dog":
        return f'<path d="M318 286 C350 270 352 240 340 228" fill="none" stroke="{INK}" stroke-width="12" stroke-linecap="round"/>'
    if sp == "cat":
        return f'<path d="M318 300 C372 300 366 220 336 214" fill="none" stroke="{INK}" stroke-width="22" stroke-linecap="round"/><path d="M318 300 C372 300 366 220 336 214" fill="none" stroke="{c["body"]}" stroke-width="10" stroke-linecap="round"/>'
    return ""


def body(sp, c):
    b, belly, dark = c["body"], c["belly"], shade(c["body"], 0.8)
    if sp == "ghost":
        return (f'<path d="M200 104 C290 104 328 170 328 240 L328 332 C312 352 296 318 280 336 C264 354 248 318 232 336 '
                f'C216 354 200 318 184 336 C168 354 152 318 136 336 C120 354 104 318 72 332 L72 240 C72 170 110 104 200 104 Z" fill="{b}" {SW}/>')
    if sp == "slime":
        return (f'<path d="M200 96 C226 150 334 200 334 274 C334 330 280 350 200 350 C120 350 66 330 66 274 C66 200 174 150 200 96 Z" fill="{b}" {SW}/>'
                f'<ellipse cx="128" cy="236" rx="18" ry="34" fill="#ffffff" opacity=".55" transform="rotate(24 128 236)"/>')
    if sp == "robot":
        return (f'<rect x="76" y="112" width="248" height="232" rx="56" fill="{b}" {SW}/>'
                f'<rect x="106" y="164" width="188" height="122" rx="30" fill="{shade(b, 0.55)}" {SW}/>'
                f'<circle cx="104" cy="320" r="6" fill="{INK}"/><circle cx="296" cy="320" r="6" fill="{INK}"/>')
    feet = (f'<ellipse cx="152" cy="346" rx="30" ry="16" fill="{dark}" {SW}/>'
            f'<ellipse cx="248" cy="346" rx="30" ry="16" fill="{dark}" {SW}/>')
    if sp in ("penguin", "chick", "owl"):
        foot_col = "#f4a340"
        feet = (f'<path d="M128 344 L176 344 L152 330 Z" fill="{foot_col}" {SW}/>'
                f'<path d="M224 344 L272 344 L248 330 Z" fill="{foot_col}" {SW}/>')
    out = feet + f'<path d="{BODY_PATH}" fill="{b}" {SW}/>'
    if sp == "penguin":
        out += f'<path d="M200 148 C262 148 290 196 290 252 C290 306 252 334 200 334 C148 334 110 306 110 252 C110 196 138 148 200 148 Z" fill="{belly}"/>'
    elif sp == "owl":
        out += f'<ellipse cx="200" cy="292" rx="70" ry="46" fill="{belly}"/>'
        out += "".join(f'<path d="M{x} {y} q8 8 16 0" fill="none" stroke="{dark}" stroke-width="4" stroke-linecap="round"/>'
                       for x, y in [(170, 280), (194, 292), (218, 280), (182, 306), (206, 306)])
    elif sp in ("hamster", "fox", "otter", "bear", "dog", "cat", "rabbit", "panda", "dino", "chick"):
        out += f'<ellipse cx="200" cy="296" rx="76" ry="44" fill="{belly}"/>'
    if sp == "fox":
        out += (f'<path d="M96 236 C120 270 160 276 182 258 C170 290 120 300 92 270 Z" fill="#ffffff"/>'
                f'<path d="M304 236 C280 270 240 276 218 258 C230 290 280 300 308 270 Z" fill="#ffffff"/>')
    if sp == "panda":
        out += (f'<ellipse cx="160" cy="226" rx="28" ry="34" fill="{INK}" transform="rotate(-24 160 226)"/>'
                f'<ellipse cx="240" cy="226" rx="28" ry="34" fill="{INK}" transform="rotate(24 240 226)"/>')
    if sp == "dog":
        out += (f'<ellipse cx="92" cy="200" rx="28" ry="58" fill="{dark}" {SW} transform="rotate(18 92 200)"/>'
                f'<ellipse cx="308" cy="200" rx="28" ry="58" fill="{dark}" {SW} transform="rotate(-18 308 200)"/>')
    if sp not in ("ghost", "slime", "robot"):
        out += (f'<ellipse cx="76" cy="272" rx="18" ry="28" fill="{b}" {SW} transform="rotate(24 76 272)"/>'
                f'<ellipse cx="324" cy="272" rx="18" ry="28" fill="{b}" {SW} transform="rotate(-24 324 272)"/>')
    return out


def eyes(style, sp):
    lx, rx, y = 160, 240, 226
    light = "#ffffff"
    ink = "#ffffff" if sp == "panda" else INK
    hi = INK if sp == "panda" else light
    if sp == "robot":
        ink, hi = "#7cf3ff", INK
        y = 220
    if sp == "owl":
        ring = "".join(f'<circle cx="{x}" cy="{y}" r="30" fill="#fff7e6" {SW}/>' for x in (lx, rx))
    else:
        ring = ""

    def ball(x, r=15):
        return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{ink}"/><circle cx="{x+5}" cy="{y-6}" r="{r*0.36:.1f}" fill="{hi}"/>'

    if style == "sparkle":
        return ring + "".join(
            f'<circle cx="{x}" cy="{y}" r="19" fill="{ink}"/><circle cx="{x+6}" cy="{y-7}" r="7" fill="{hi}"/>'
            f'<circle cx="{x-6}" cy="{y+7}" r="3.5" fill="{hi}"/>' for x in (lx, rx))
    if style == "sleepy":
        return ring + "".join(f'<path d="M{x-16} {y} Q{x} {y+12} {x+16} {y}" fill="none" stroke="{ink}" stroke-width="6" stroke-linecap="round"/>' for x in (lx, rx))
    if style == "determined":
        return ring + ball(lx) + ball(rx) + (
            f'<path d="M{lx-20} {y-30} L{lx+16} {y-20}" stroke="{ink}" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M{rx+20} {y-30} L{rx-16} {y-20}" stroke="{ink}" stroke-width="7" stroke-linecap="round"/>')
    if style == "wink":
        return ring + ball(lx) + f'<path d="M{rx-16} {y+2} Q{rx} {y-14} {rx+16} {y+2}" fill="none" stroke="{ink}" stroke-width="6" stroke-linecap="round"/>'
    if style == "dot":
        return ring + "".join(f'<circle cx="{x}" cy="{y}" r="8" fill="{ink}"/>' for x in (lx, rx))
    if style == "star":
        def star(x):
            pts = []
            for i in range(10):
                r = 18 if i % 2 == 0 else 8
                a = -math.pi / 2 + i * math.pi / 5
                pts.append(f"{x + r*math.cos(a):.1f},{y + r*math.sin(a):.1f}")
            return f'<polygon points="{" ".join(pts)}" fill="{ink if sp=="robot" else "#ffcc33"}" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>'
        return ring + star(lx) + star(rx)
    if style == "teary":
        return ring + ball(lx, 17) + ball(rx, 17) + "".join(
            f'<path d="M{x-14} {y+16} Q{x} {y+24} {x+14} {y+16}" fill="none" stroke="#7ec8ff" stroke-width="5" stroke-linecap="round"/>' for x in (lx, rx))
    return ring + ball(lx) + ball(rx)


def mouth(style, sp):
    y = 262
    col = "#7cf3ff" if sp == "robot" else INK
    beak = sp in ("owl", "penguin", "chick")
    out = ""
    if beak:
        out += f'<path d="M186 {y-10} L214 {y-10} L200 {y+8} Z" fill="#f4a340" {SW}/>'
        return out
    if sp in ("cat", "fox", "dog", "bear", "panda", "hamster", "otter", "rabbit"):
        out += f'<ellipse cx="200" cy="{y-12}" rx="9" ry="6" fill="{INK}"/>'
    if style == "cat":
        out += f'<path d="M180 {y} Q190 {y+12} 200 {y} Q210 {y+12} 220 {y}" fill="none" stroke="{col}" stroke-width="5" stroke-linecap="round"/>'
    elif style == "o":
        out += f'<ellipse cx="200" cy="{y+6}" rx="9" ry="11" fill="{col}"/>'
    elif style == "flat":
        out += f'<path d="M186 {y+4} L214 {y+4}" stroke="{col}" stroke-width="5" stroke-linecap="round"/>'
    elif style == "grin":
        out += (f'<path d="M178 {y} Q200 {y+34} 222 {y} Z" fill="{INK}" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>'
                f'<path d="M190 {y+14} Q200 {y+24} 210 {y+14} Z" fill="#ff7a8a"/>')
    elif style == "smirk":
        out += f'<path d="M186 {y+6} Q204 {y+14} 218 {y}" fill="none" stroke="{col}" stroke-width="5" stroke-linecap="round"/>'
    elif style == "wobbly":
        out += f'<path d="M180 {y+6} q5 -6 10 0 t10 0 t10 0 t10 0" fill="none" stroke="{col}" stroke-width="5" stroke-linecap="round"/>'
    else:
        out += f'<path d="M184 {y} Q200 {y+18} 216 {y}" fill="none" stroke="{col}" stroke-width="5" stroke-linecap="round"/>'
    if sp in ("cat", "fox"):
        out += "".join(f'<path d="M{x1} {yy} L{x2} {yy+d}" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>'
                       for x1, x2, yy, d in [(122, 92, 252, -6), (122, 94, 264, 4), (278, 308, 252, -6), (278, 306, 264, 4)])
    return out


def cheeks(sp, c):
    if sp == "robot":
        return '<rect x="118" y="252" width="26" height="10" rx="5" fill="#ff8fab" opacity=".8"/><rect x="256" y="252" width="26" height="10" rx="5" fill="#ff8fab" opacity=".8"/>'
    r = 26 if sp == "hamster" else 17
    return (f'<ellipse cx="128" cy="258" rx="{r}" ry="{r*0.62:.0f}" fill="{c["cheek"]}" opacity=".75"/>'
            f'<ellipse cx="272" cy="258" rx="{r}" ry="{r*0.62:.0f}" fill="{c["cheek"]}" opacity=".75"/>')


def accessory(name, c, sp):
    a = c["accent"]
    top = 92 if sp in ("rabbit", "robot") else 112
    if name == "glasses":
        return (f'<circle cx="160" cy="226" r="26" fill="#ffffff" fill-opacity=".25" {SW}/>'
                f'<circle cx="240" cy="226" r="26" fill="#ffffff" fill-opacity=".25" {SW}/><path d="M186 224 Q200 214 214 224" fill="none" {SW}/>')
    if name == "magnifier":
        return (f'<line x1="352" y1="318" x2="384" y2="356" stroke="#8a5a3b" stroke-width="14" stroke-linecap="round"/>'
                f'<circle cx="334" cy="292" r="34" fill="#dff4ff" fill-opacity=".7" {SW}/><path d="M318 278 Q326 270 338 270" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>')
    if name == "coffee":
        return (f'<path d="M30 268 L80 268 L74 326 L36 326 Z" fill="#ffffff" {SW}/><path d="M80 282 C98 282 98 306 78 308" fill="none" {SW}/>'
                f'<rect x="34" y="286" width="42" height="14" fill="{a}"/>'
                f'<path d="M46 256 q-8 -12 0 -24 M62 256 q-8 -12 0 -24" fill="none" stroke="#b9a89a" stroke-width="4" stroke-linecap="round"/>')
    if name == "headset":
        return (f'<path d="M86 214 C86 110 314 110 314 214" fill="none" stroke="{INK}" stroke-width="12"/>'
                f'<rect x="64" y="196" width="32" height="54" rx="14" fill="{a}" {SW}/><rect x="304" y="196" width="32" height="54" rx="14" fill="{a}" {SW}/>'
                f'<path d="M80 250 C84 286 130 292 156 286" fill="none" stroke="{INK}" stroke-width="5"/><circle cx="160" cy="286" r="8" fill="{INK}"/>')
    if name == "laptop":
        return (f'<path d="M120 300 L280 300 L268 352 L132 352 Z" fill="#c9d1dc" {SW}/>'
                f'<path d="M100 352 L300 352 L292 368 L108 368 Z" fill="#aab4c2" {SW}/><circle cx="200" cy="326" r="8" fill="{a}"/>')
    if name == "nightcap":
        return (f'<path d="M110 {top+40} C130 {top-40} 250 {top-60} 330 {top-10} C300 {top+0} 290 {top+20} 290 {top+40} Z" fill="{a}" {SW}/>'
                f'<path d="M104 {top+40} C150 {top+24} 250 {top+24} 296 {top+40}" fill="none" stroke="#ffffff" stroke-width="16" stroke-linecap="round"/>'
                f'<circle cx="334" cy="{top-6}" r="16" fill="#ffffff" {SW}/>')
    if name == "wizard_hat":
        return (f'<path d="M126 {top+18} L210 {top-96} L276 {top+18} Z" fill="#6c4bd8" {SW}/>'
                f'<ellipse cx="200" cy="{top+20}" rx="110" ry="20" fill="#6c4bd8" {SW}/>'
                f'<path d="M206 {top-30} l6 12 13 2 -10 9 3 13 -12 -7 -12 7 3 -13 -10 -9 13 -2 Z" fill="#ffd84a"/>')
    if name == "crown":
        return (f'<path d="M140 {top+8} L140 {top-40} L170 {top-12} L200 {top-50} L230 {top-12} L260 {top-40} L260 {top+8} Z" fill="#ffd84a" {SW}/>'
                f'<circle cx="200" cy="{top-14}" r="7" fill="#ff5d73"/>')
    if name == "hardhat":
        return (f'<path d="M110 {top+40} C110 {top-30} 290 {top-30} 290 {top+40} Z" fill="#ffc83d" {SW}/>'
                f'<rect x="94" y="{top+30}" width="212" height="18" rx="9" fill="#ffc83d" {SW}/><path d="M200 {top-14} L200 {top+30}" {SW}/>')
    if name == "checklist":
        return (f'<rect x="306" y="246" width="70" height="92" rx="8" fill="#ffffff" {SW}/><rect x="326" y="238" width="30" height="16" rx="4" fill="{a}" {SW}/>'
                + "".join(f'<path d="M318 {y} l6 6 10 -12" fill="none" stroke="#2fb36d" stroke-width="5" stroke-linecap="round"/><line x1="342" y1="{y}" x2="364" y2="{y}" stroke="#c7bfb6" stroke-width="5" stroke-linecap="round"/>' for y in (276, 298, 320)))
    if name == "bow":
        return (f'<path d="M262 {top+4} L230 {top-22} L230 {top+30} Z" fill="{a}" {SW}/><path d="M262 {top+4} L294 {top-22} L294 {top+30} Z" fill="{a}" {SW}/>'
                f'<circle cx="262" cy="{top+4}" r="10" fill="{a}" {SW}/>')
    if name == "sprout":
        return (f'<path d="M200 {top} L200 {top-36}" {SW}/><path d="M200 {top-30} C176 {top-58} 150 {top-40} 160 {top-24} C172 {top-14} 192 {top-20} 200 {top-30} Z" fill="#7bd36a" {SW}/>'
                f'<path d="M200 {top-30} C224 {top-58} 250 {top-40} 240 {top-24} C228 {top-14} 208 {top-20} 200 {top-30} Z" fill="#7bd36a" {SW}/>')
    if name == "flag":
        return (f'<line x1="40" y1="330" x2="40" y2="200" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>'
                f'<path d="M42 202 L110 220 L42 244 Z" fill="{a}" {SW}/><text x="52" y="231" font-size="17" font-weight="900" fill="#ffffff" font-family="sans-serif">PR</text>')
    if name == "sweat":
        return f'<path d="M298 160 C286 184 286 196 298 200 C310 196 310 184 298 160 Z" fill="#9fd8ff" {SW}/>'
    if name == "zzz":
        return (f'<text x="300" y="120" font-size="38" font-weight="900" fill="{INK}" font-family="sans-serif">Z</text>'
                f'<text x="334" y="88" font-size="28" font-weight="900" fill="{INK}" font-family="sans-serif">z</text>'
                f'<text x="358" y="64" font-size="20" font-weight="900" fill="{INK}" font-family="sans-serif">z</text>')
    if name == "sparkles":
        def sp4(x, y, r, col):
            return f'<path d="M{x} {y-r} Q{x} {y} {x+r} {y} Q{x} {y} {x} {y+r} Q{x} {y} {x-r} {y} Q{x} {y} {x} {y-r} Z" fill="{col}"/>'
        return sp4(52, 120, 18, "#ffd84a") + sp4(352, 150, 14, "#ffffff") + sp4(70, 200, 10, "#ffffff") + sp4(340, 70, 12, "#ffd84a")
    if name == "rocket":
        return (f'<g transform="rotate(30 350 120)"><path d="M350 60 C372 84 372 130 362 150 L338 150 C328 130 328 84 350 60 Z" fill="#ffffff" {SW}/>'
                f'<circle cx="350" cy="102" r="9" fill="{a}" {SW}/><path d="M340 150 L350 178 L360 150 Z" fill="#ff8a3d"/></g>')
    if name == "shield":
        return (f'<path d="M24 236 L74 222 L124 236 C124 290 100 322 74 336 C48 322 24 290 24 236 Z" fill="{a}" {SW}/>'
                f'<path d="M52 278 l16 16 30 -34" fill="none" stroke="#ffffff" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>')
    if name == "terminal":
        return (f'<rect x="282" y="40" width="104" height="72" rx="10" fill="#22232b" {SW}/><circle cx="298" cy="54" r="4" fill="#ff5f57"/><circle cx="312" cy="54" r="4" fill="#febc2e"/><circle cx="326" cy="54" r="4" fill="#28c840"/>'
                f'<text x="296" y="96" font-size="22" font-weight="700" fill="#7CFFB2" font-family="monospace">&gt;_</text>')
    if name == "bug_net":
        return (f'<line x1="330" y1="350" x2="360" y2="150" stroke="#8a5a3b" stroke-width="9" stroke-linecap="round"/>'
                f'<ellipse cx="362" cy="122" rx="34" ry="30" fill="#ffffff" fill-opacity=".5" {SW}/>'
                f'<circle cx="362" cy="122" r="9" fill="{INK}"/><path d="M354 112 l-8 -8 M370 112 l8 -8" stroke="{INK}" stroke-width="3"/>')
    if name == "scarf":
        return (f'<path d="M96 300 C150 322 250 322 304 300 L300 324 C250 344 150 344 100 324 Z" fill="{a}" {SW}/>'
                f'<path d="M250 326 L262 372 L290 364 L274 320 Z" fill="{a}" {SW}/>')
    if name == "heart":
        return f'<path d="M352 120 C352 96 384 96 384 120 C384 140 352 156 352 164 C352 156 320 140 320 120 C320 96 352 96 352 120 Z" fill="#ff6b8a" {SW}/>'
    if name == "book":
        return (f'<path d="M24 280 L74 270 L124 280 L124 344 L74 334 L24 344 Z" fill="#ffffff" {SW}/><path d="M74 270 L74 334" {SW}/>'
                f'<path d="M24 280 L24 344" stroke="{a}" stroke-width="8"/>')
    if name == "wrench":
        return (f'<g transform="rotate(-40 350 290)"><rect x="342" y="250" width="16" height="96" rx="8" fill="#b8c2cc" {SW}/>'
                f'<path d="M332 256 C332 226 368 226 368 256 L358 256 L358 240 L342 240 L342 256 Z" fill="#b8c2cc" {SW}/></g>')
    if name == "stopwatch":
        return (f'<circle cx="62" cy="300" r="34" fill="#ffffff" {SW}/><rect x="54" y="254" width="16" height="12" rx="3" fill="{a}" {SW}/>'
                f'<path d="M62 300 L62 280 M62 300 L76 308" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>')
    if name == "lightbulb":
        return (f'<path d="M350 40 C324 40 312 62 318 82 C322 96 334 102 336 116 L364 116 C366 102 378 96 382 82 C388 62 376 40 350 40 Z" fill="#ffe066" {SW}/>'
                f'<rect x="336" y="118" width="28" height="14" rx="4" fill="#b8c2cc" {SW}/>')
    return ""


FRONT_ACC = {"glasses", "laptop", "scarf"}
HEAD_ACC = {"nightcap", "wizard_hat", "crown", "hardhat", "bow", "sprout", "headset"}


def character_svg(p, size=400, standalone=False):
    sp = p.get("species", "cat")
    if sp not in SPECIES:
        sp = "cat"
    col = p.get("colors") or {}
    c = {
        "body": col.get("body", "#ffd6a5"),
        "belly": col.get("belly", "#fff6ea"),
        "accent": col.get("accent", "#ff7aa2"),
        "cheek": col.get("cheek", "#ff9eb5"),
    }
    if sp == "penguin" and "body" not in col:
        c["body"] = "#3d4a63"
    accs = [x for x in p.get("accessories", []) if x in ACCESSORIES][:4]
    back = "".join(accessory(x, c, sp) for x in accs if x not in FRONT_ACC and x not in HEAD_ACC)
    head = "".join(accessory(x, c, sp) for x in accs if x in HEAD_ACC)
    front = "".join(accessory(x, c, sp) for x in accs if x in FRONT_ACC)
    shadow = '<ellipse cx="200" cy="362" rx="120" ry="16" fill="#000000" opacity=".10"/>'
    inner = (shadow + tail(sp, c) + ears(sp, c) + body(sp, c) + cheeks(sp, c) + eyes(p.get("eyes", "round"), sp)
             + mouth(p.get("mouth", "smile"), sp) + front + head + back + (p.get("extra_svg") or ""))
    if standalone:
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="{size}" height="{size}">{inner}</svg>'
    return inner


# ======================================================================
# Share card (1080 x 1350) — pure SVG so it can become a PNG offline
# ======================================================================
FONT = "'Pretendard','Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR','Noto Sans CJK KR',sans-serif"


def wrap_text(s, width):
    """Rough Korean-aware wrap by visual width (Hangul ≈ 1, ASCII ≈ 0.55)."""
    lines, cur, w = [], "", 0.0
    for ch in str(s):
        cw = 0.55 if ord(ch) < 128 else 1.0
        if ch == "\n" or (w + cw > width and ch != " "):
            lines.append(cur.rstrip())
            cur, w = ("" if ch in "\n " else ch), (0 if ch in "\n " else cw)
            continue
        cur += ch
        w += cw
    if cur.strip():
        lines.append(cur.rstrip())
    return lines


def card_svg(p, s):
    pal = p.get("colors") or {}
    bg1 = pal.get("bg", "#fff1d6")
    bg2 = pal.get("bg2", shade(bg1, 0.92))
    acc = pal.get("accent", "#ff7aa2")
    rarity = p.get("rarity", {}) or {}
    tc = (p.get("type_code") or {}).get("code", "")
    tot = s.get("totals", {})
    per = s.get("period", {})
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" id="share-card" viewBox="0 0 1080 1350" width="1080" height="1350" font-family="{FONT}">',
         f'<defs><linearGradient id="cbg" x1="0" y1="0" x2="0.4" y2="1"><stop offset="0" stop-color="{bg1}"/><stop offset="1" stop-color="{bg2}"/></linearGradient>'
         f'<pattern id="dots" width="36" height="36" patternUnits="userSpaceOnUse"><circle cx="4" cy="4" r="2.4" fill="{INK}" opacity=".07"/></pattern></defs>',
         f'<rect width="1080" height="1350" rx="0" fill="url(#cbg)"/><rect width="1080" height="1350" fill="url(#dots)"/>',
         f'<rect x="36" y="36" width="1008" height="1278" rx="48" fill="none" stroke="{INK}" stroke-width="6"/>']
    # header chips
    o.append(f'<text x="84" y="118" font-size="30" font-weight="800" fill="{INK}" opacity=".7">Claude가 본 나 · /내캐릭터</text>')
    if rarity.get("tier"):
        o.append(f'<g transform="translate(996 82)"><rect x="-190" y="0" width="190" height="56" rx="28" fill="{INK}"/>'
                 f'<text x="-95" y="38" text-anchor="middle" font-size="28" font-weight="900" fill="#ffd84a">{esc(rarity.get("tier"))} {"★" * int(rarity.get("stars", 0))}</text></g>')
    # stage + character
    o.append(f'<circle cx="540" cy="436" r="256" fill="#ffffff" opacity=".55"/><circle cx="540" cy="436" r="256" fill="none" stroke="{INK}" stroke-width="5" stroke-dasharray="4 18" stroke-linecap="round" opacity=".5"/>')
    o.append(f'<g transform="translate(310 196) scale(1.15)">{character_svg(p)}</g>')
    # catchphrase bubble (auto width, never leaves a lone quote mark on its own line)
    cp = p.get("catchphrase")
    if cp:
        lines = wrap_text(cp, 8)[:2]
        lines[0] = "“" + lines[0]
        lines[-1] = lines[-1] + "”"
        widest = max(sum(0.55 if ord(ch) < 128 else 1.0 for ch in t) for t in lines)
        bw = max(180, min(300, int(widest * 31 + 56)))
        bh = 40 + 42 * len(lines)
        bx = 1030 - bw
        o.append(f'<g transform="translate({bx} 190)"><rect x="0" y="0" width="{bw}" height="{bh}" rx="26" fill="#ffffff" stroke="{INK}" stroke-width="5"/>'
                 f'<path d="M40 {bh-3} L22 {bh+34} L84 {bh-3} Z" fill="#ffffff" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/><rect x="34" y="{bh-12}" width="56" height="12" fill="#ffffff"/>'
                 + "".join(f'<text x="{bw/2}" y="{58 + 42*i}" text-anchor="middle" font-size="31" font-weight="800" fill="{INK}">{esc(t)}</text>' for i, t in enumerate(lines))
                 + "</g>")
    # name / title / type code
    o.append(f'<text x="540" y="776" text-anchor="middle" font-size="74" font-weight="900" fill="{INK}">{esc(p.get("name",""))}</text>')
    if p.get("title"):
        o.append(f'<text x="540" y="828" text-anchor="middle" font-size="32" font-weight="700" fill="{INK}" opacity=".75">{esc(p.get("title"))}</text>')
    if tc:
        letters = list(tc)
        w = 76 * len(letters) + 12 * (len(letters) - 1)
        x0 = 540 - w / 2
        for i, ch in enumerate(letters):
            x = x0 + i * 88
            o.append(f'<rect x="{x}" y="852" width="76" height="76" rx="20" fill="{acc if i % 2 == 0 else "#ffffff"}" stroke="{INK}" stroke-width="5"/>'
                     f'<text x="{x+38}" y="907" text-anchor="middle" font-size="44" font-weight="900" fill="{INK}">{esc(ch)}</text>')
    # stats: two columns, number outside the bar
    stats = (p.get("stats") or [])[:6]
    y0 = 966
    for i, st in enumerate(stats):
        col_x = 84 if i % 2 == 0 else 572
        y = y0 + (i // 2) * 60
        v = max(0, min(100, int(st.get("value", 0))))
        o.append(f'<text x="{col_x}" y="{y+26}" font-size="27" font-weight="800" fill="{INK}">{esc(st.get("label",""))}</text>'
                 f'<rect x="{col_x+148}" y="{y+4}" width="234" height="28" rx="14" fill="#ffffff" stroke="{INK}" stroke-width="4"/>'
                 f'<rect x="{col_x+152}" y="{y+8}" width="{226*v/100:.0f}" height="20" rx="10" fill="{acc}"/>'
                 f'<text x="{col_x+424}" y="{y+28}" text-anchor="end" font-size="26" font-weight="900" fill="{INK}">{v}</text>')
    # badges row
    badges = (p.get("badges") or [])[:3]
    if badges:
        bw = 300
        x0 = 540 - (bw * len(badges) + 24 * (len(badges) - 1)) / 2
        for i, b in enumerate(badges):
            x = x0 + i * (bw + 24)
            name = esc(b.get("name", ""))
            fs = 26 if len(b.get("name", "")) <= 9 else 22
            o.append(f'<rect x="{x}" y="1170" width="{bw}" height="64" rx="32" fill="#ffffff" stroke="{INK}" stroke-width="4"/>'
                     f'<text x="{x+40}" y="1213" text-anchor="middle" font-size="32">{esc(b.get("icon",""))}</text>'
                     f'<text x="{x+68}" y="1211" font-size="{fs}" font-weight="800" fill="{INK}">{name}</text>')
    foot = f'{per.get("from","")[:7].replace("-", ".")} ~ {per.get("to","")[:7].replace("-", ".")} · 나의 말 {tot.get("my_prompts",0):,}번 · 도구 {tot.get("claude_tool_calls",0):,}번'
    o.append(f'<text x="540" y="1282" text-anchor="middle" font-size="22" font-weight="700" fill="{INK}" opacity=".55">{esc(foot)}</text>')
    o.append("</svg>")
    return "".join(o)


# ======================================================================
# Page
# ======================================================================
CSS = """
:root{--ink:#3b2f2f;--paper:#fffaf2;--bg:#fff3e2;--accent:#ff7aa2;--soft:#ffe3ec;--muted:#7a6b66;--card:#ffffff}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:'Pretendard','Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:880px;margin:0 auto;padding:40px max(16px,env(safe-area-inset-right,0px)) 80px max(16px,env(safe-area-inset-left,0px));display:flex;flex-direction:column;gap:28px}
.slide{background:var(--card);border:4px solid var(--ink);border-radius:32px;padding:36px 32px;box-shadow:8px 8px 0 var(--ink);position:relative;overflow:hidden}
.slide.hero{background:linear-gradient(160deg,var(--bg1),var(--bg2));text-align:center;padding-top:28px}
.kicker{font-size:15px;font-weight:800;letter-spacing:.02em;color:var(--muted);margin:0 0 6px}
h1{font-size:clamp(40px,8vw,64px);line-height:1.1;margin:6px 0 4px;font-weight:900;text-wrap:balance}
h2{font-size:clamp(26px,4.4vw,34px);margin:0 0 18px;font-weight:900;text-wrap:balance}
.title{font-size:20px;font-weight:700;color:var(--muted);margin:0}
.chips{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin:16px 0 4px}
.chip{border:3px solid var(--ink);border-radius:999px;padding:4px 14px;font-weight:800;background:#fff}
.chip.dark{background:var(--ink);color:#ffd84a}
.char{width:min(360px,80%);margin:0 auto;display:block;filter:drop-shadow(0 6px 0 rgba(0,0,0,.06))}
.typecode{display:flex;justify-content:center;gap:10px;margin:18px 0 6px}
.typecode b{width:62px;height:62px;border:4px solid var(--ink);border-radius:18px;display:grid;place-items:center;font-size:34px;font-weight:900;background:#fff}
.typecode b:nth-child(odd){background:var(--accent)}
.axes{display:grid;gap:12px;margin-top:18px;text-align:left}
.axis{display:grid;grid-template-columns:1fr 2fr 1fr;align-items:center;gap:10px;font-size:15px;font-weight:700}
.axis .r{text-align:right}
.axis .on{color:var(--ink)}.axis .off{color:#b7aaa4}
.track{height:14px;border:3px solid var(--ink);border-radius:99px;background:#fff;position:relative}
.track i{position:absolute;top:50%;width:22px;height:22px;border-radius:50%;background:var(--accent);border:3px solid var(--ink);transform:translate(-50%,-50%)}
.bigs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.big{border:3px solid var(--ink);border-radius:24px;padding:18px 20px;background:var(--paper)}
.big .n{font-size:42px;font-weight:900;line-height:1.1;letter-spacing:-.02em}
.big .l{font-weight:800;margin-top:4px}
.big .c{color:var(--muted);font-size:15px;margin-top:6px}
.clock{display:flex;align-items:flex-end;gap:4px;height:170px;margin:10px 0 6px;padding-top:10px}
.clock div{flex:1;background:var(--accent);border:2px solid var(--ink);border-bottom:none;border-radius:8px 8px 0 0;min-height:3px;position:relative}
.clock div.top{background:#ffd84a}
.clock-x{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);font-weight:700;border-top:3px solid var(--ink);padding-top:4px}
.lead{font-size:19px;font-weight:700;margin:12px 0 0}
.traits{display:grid;gap:16px}
.trait{border:3px solid var(--ink);border-radius:22px;padding:18px 20px;background:var(--paper)}
.trait h3{margin:0 0 6px;font-size:21px}
.trait p{margin:0}
.ev{margin-top:10px;font-size:14px;color:var(--muted);background:#fff;border:2px dashed #cdbfb8;border-radius:12px;padding:8px 12px}
.ev b{color:var(--ink)}
.bars{display:grid;gap:14px}
.bar{display:grid;grid-template-columns:110px 1fr 46px;gap:12px;align-items:center;font-weight:800}
.bar .t{height:22px;border:3px solid var(--ink);border-radius:99px;background:#fff;overflow:hidden}
.bar .t i{display:block;height:100%;background:var(--accent);border-right:3px solid var(--ink)}
.bar small{grid-column:2 / 4;font-weight:500;color:var(--muted);margin-top:-8px;font-size:14px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-top:18px}
.box{border:3px solid var(--ink);border-radius:22px;padding:16px 18px;background:var(--paper)}
.box h3{margin:0 0 4px;font-size:18px}
.box p{margin:0}
.quotes{display:flex;flex-wrap:wrap;gap:10px}
.q{background:#fff;border:3px solid var(--ink);border-radius:20px 20px 20px 4px;padding:8px 16px;font-weight:800}
.q small{color:var(--muted);font-weight:700;margin-left:6px}
.badges{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.badge{border:3px solid var(--ink);border-radius:22px;padding:16px;background:var(--paper);display:flex;gap:14px;align-items:flex-start}
.badge .i{font-size:38px;line-height:1}
.badge h3{margin:0;font-size:18px}
.badge p{margin:2px 0 0;font-size:14px;color:var(--muted)}
.match{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.match .m{border:3px solid var(--ink);border-radius:22px;padding:16px;background:var(--paper);text-align:center}
.match svg{width:150px;height:150px}
.match h3{margin:4px 0 2px}
.match .tag{display:inline-block;font-weight:900;border:3px solid var(--ink);border-radius:99px;padding:0 12px;background:#fff;font-size:14px}
.say{font-size:22px;font-weight:800;line-height:1.55;background:var(--soft);border:3px solid var(--ink);border-radius:26px;padding:22px 24px;position:relative}
.roast{margin-top:16px;font-weight:700;color:var(--muted)}
.cardwrap{overflow:hidden;border-radius:24px;border:4px solid var(--ink)}
.cardwrap svg{display:block;width:100%;height:auto}
.btns{display:flex;gap:12px;flex-wrap:wrap;margin-top:18px}
button{font:inherit;font-weight:900;font-size:18px;border:4px solid var(--ink);border-radius:18px;padding:12px 22px;background:#ffd84a;color:var(--ink);cursor:pointer;box-shadow:4px 4px 0 var(--ink)}
button:active{transform:translate(3px,3px);box-shadow:1px 1px 0 var(--ink)}
button.sec{background:#fff}
.foot{color:var(--muted);font-size:13px;text-align:center}
.reveal{opacity:0;transform:translateY(24px);transition:opacity .6s ease,transform .6s ease}
.reveal.in{opacity:1;transform:none}
@media (max-width:520px){.slide{padding:26px 18px;box-shadow:5px 5px 0 var(--ink)}.bar{grid-template-columns:84px 1fr 40px}.typecode b{width:50px;height:50px;font-size:28px}}
@media (prefers-reduced-motion:reduce){.reveal{opacity:1;transform:none;transition:none}}
"""

JS = r"""
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.12});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
document.querySelectorAll('[data-count]').forEach(el=>{
  const end=parseFloat(el.dataset.count), dec=(el.dataset.count.split('.')[1]||'').length, suf=el.dataset.suffix||'';
  const run=()=>{const t0=performance.now();const f=t=>{const k=Math.min(1,(t-t0)/1100),v=end*(1-Math.pow(1-k,3));
    el.textContent=(dec?v.toFixed(dec):Math.round(v).toLocaleString('ko-KR'))+suf;if(k<1)requestAnimationFrame(f)};requestAnimationFrame(f)};
  new IntersectionObserver((es,o)=>es.forEach(e=>{if(e.isIntersecting){run();o.disconnect()}}),{threshold:.5}).observe(el);
});
function cardBlob(){return new Promise((res,rej)=>{
  const svg=document.getElementById('share-card');
  const xml=new XMLSerializer().serializeToString(svg);
  const img=new Image();
  img.onload=()=>{const c=document.createElement('canvas');c.width=1080;c.height=1350;const g=c.getContext('2d');g.drawImage(img,0,0,1080,1350);c.toBlob(b=>b?res(b):rej(new Error('blob')),'image/png')};
  img.onerror=rej;
  img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(xml);
})}
document.getElementById('save').addEventListener('click',async()=>{
  try{const b=await cardBlob();const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=document.body.dataset.file+'.png';document.body.appendChild(a);a.click();a.remove();}
  catch(e){alert('PNG로 만들지 못했어요. 카드를 화면 캡처해 주세요.')}
});
document.getElementById('copy').addEventListener('click',async e=>{
  try{const b=await cardBlob();await navigator.clipboard.write([new ClipboardItem({'image/png':b})]);e.target.textContent='복사했어요 ✓'}
  catch(err){e.target.textContent='복사가 막혔어요 — 저장을 써 주세요'}
});
"""


def axes_html(tc):
    out = []
    for ax in (tc or {}).get("axes", [])[:4]:
        v = max(0.0, min(1.0, float(ax.get("value", 0.5))))
        left_on = v < 0.5
        out.append(f'<div class="axis"><span class="{"on" if left_on else "off"}">{esc(ax.get("left",""))}</span>'
                   f'<div class="track"><i style="left:{v*100:.0f}%"></i></div>'
                   f'<span class="r {"off" if left_on else "on"}">{esc(ax.get("right",""))}</span></div>')
    return "".join(out)


def num_html(v):
    """'1,234' → count-up span; anything else as text."""
    s = str(v)
    raw = s.replace(",", "")
    num = ""
    i = 0
    while i < len(raw) and (raw[i].isdigit() or raw[i] == "."):
        num += raw[i]
        i += 1
    suffix = raw[i:]
    if num and num.replace(".", "", 1).isdigit():
        return f'<span data-count="{num}" data-suffix="{esc(suffix)}">{esc(s)}</span>'
    return esc(s)


def merge_fixed(p, s):
    """Type code and rarity come from the shared formula in stats.json, never from the model."""
    st = s.get("type_code") or {}
    if st.get("code"):
        tc = dict(p.get("type_code") or {})
        tc.update(code=st["code"], name=st["name"], axes=st["axes"])
        p["type_code"] = tc
        r = dict(p.get("rarity") or {})
        r.update(tier=st["rarity"]["tier"], stars=st["rarity"]["stars"])
        p["rarity"] = r
    return p


def page(p, s):
    pal = p.get("colors") or {}
    bg1 = pal.get("bg", "#fff1d6")
    bg2 = pal.get("bg2", shade(bg1, 0.92))
    acc = pal.get("accent", "#ff7aa2")
    soft = shade(acc, 1.75)
    tc = p.get("type_code") or {}
    rarity = p.get("rarity") or {}
    name = p.get("name", "내 캐릭터")
    hours = (s.get("time") or {}).get("hour_hist") or [0] * 24
    hmax = max(hours) or 1
    top_h = hours.index(hmax)

    sec = []
    # 1 hero
    sec.append(f'''<section class="slide hero">
<p class="kicker">Claude가 {esc(s.get("totals",{}).get("my_prompts",0))}번의 대화로 그려 본 당신</p>
<svg class="char" viewBox="0 0 400 400" role="img" aria-label="{esc(name)} 캐릭터">{character_svg(p)}</svg>
<h1>{esc(name)}</h1><p class="title">{esc(p.get("title",""))}</p>
<div class="chips">{f'<span class="chip dark">{esc(rarity.get("tier"))} {"★"*int(rarity.get("stars",0))}</span>' if rarity.get("tier") else ""}
{"".join(f'<span class="chip">#{esc(t)}</span>' for t in p.get("hashtags", [])[:4])}</div>
{f'<p class="title">{esc(rarity.get("reason",""))}</p>' if rarity.get("reason") else ""}
</section>''')
    # 2 type code
    if tc.get("code"):
        sec.append(f'''<section class="slide reveal"><p class="kicker">나의 개발 유형 코드</p><h2>{esc(tc.get("code"))} · {esc(tc.get("name",""))}</h2>
<div class="typecode">{"".join(f"<b>{esc(ch)}</b>" for ch in tc.get("code",""))}</div>
<div class="axes">{axes_html(tc)}</div>{f'<p class="lead">{esc(tc.get("summary"))}</p>' if tc.get("summary") else ""}</section>''')
    # 3 wrapped numbers
    if p.get("wrapped"):
        bigs = "".join(f'<div class="big"><div class="n">{num_html(w.get("big",""))}</div><div class="l">{esc(w.get("label",""))}</div>'
                       f'<div class="c">{esc(w.get("comment",""))}</div></div>' for w in p["wrapped"][:6])
        sec.append(f'<section class="slide reveal"><p class="kicker">숫자로 본 우리 사이</p><h2>{esc(p.get("wrapped_title","올해 Claude와 함께한 기록"))}</h2><div class="bigs">{bigs}</div></section>')
    # 4 clock
    bars = "".join(f'<div class="{"top" if i == top_h else ""}" style="height:{max(2, h*100/hmax):.0f}%" title="{i}시 · {h}번"></div>' for i, h in enumerate(hours))
    sec.append(f'''<section class="slide reveal"><p class="kicker">하루 중 언제 Claude를 부르나</p><h2>{esc(p.get("chronotype","나의 작업 시계"))}</h2>
<div class="clock">{bars}</div><div class="clock-x"><span>0시</span><span>6시</span><span>12시</span><span>18시</span><span>23시</span></div>
{f'<p class="lead">{esc(p.get("chronotype_comment"))}</p>' if p.get("chronotype_comment") else ""}</section>''')
    # 5 traits
    if p.get("traits"):
        tr = "".join(f'<div class="trait"><h3>{esc(t.get("emoji",""))} {esc(t.get("title",""))}</h3><p>{esc(t.get("body",""))}</p>'
                     f'<div class="ev"><b>근거</b> · {esc(t.get("evidence",""))}</div></div>' for t in p["traits"][:4])
        sec.append(f'<section class="slide reveal"><p class="kicker">Claude가 본 성격</p><h2>이런 사람이에요</h2><div class="traits">{tr}</div></section>')
    # 6 stats
    if p.get("stats"):
        bs = "".join(f'<div class="bar"><span>{esc(x.get("label",""))}</span><div class="t"><i style="width:{max(0,min(100,int(x.get("value",0))))}%"></i></div>'
                     f'<span>{int(x.get("value",0))}</span>{f"<small>{esc(x.get("evidence"))}</small>" if x.get("evidence") else ""}</div>' for x in p["stats"][:6])
        extra = ""
        if p.get("superpower") or p.get("weakness"):
            extra = (f'<div class="two"><div class="box"><h3>⚡ 필살기</h3><p>{esc(p.get("superpower",""))}</p></div>'
                     f'<div class="box"><h3>🫠 약점</h3><p>{esc(p.get("weakness",""))}</p></div></div>')
        sec.append(f'<section class="slide reveal"><p class="kicker">능력치</p><h2>스탯 카드</h2><div class="bars">{bs}</div>{extra}</section>')
    # 7 catchphrases
    if p.get("catchphrases"):
        qs = "".join(f'<span class="q">{esc(q.get("text",""))}<small>{esc(q.get("count",""))}</small></span>' for q in p["catchphrases"][:10])
        sec.append(f'<section class="slide reveal"><p class="kicker">입버릇 모음</p><h2>Claude가 제일 많이 들은 말</h2><div class="quotes">{qs}</div>'
                   f'{f"<p class=lead>{esc(p.get("catchphrase_comment"))}</p>" if p.get("catchphrase_comment") else ""}</section>')
    # 8 badges
    if p.get("badges"):
        bd = "".join(f'<div class="badge"><span class="i">{esc(b.get("icon",""))}</span><div><h3>{esc(b.get("name",""))}</h3><p>{esc(b.get("desc",""))}</p></div></div>' for b in p["badges"][:6])
        sec.append(f'<section class="slide reveal"><p class="kicker">획득한 업적</p><h2>배지</h2><div class="badges">{bd}</div></section>')
    # 9 match
    mt = []
    for key, tag in (("best_match", "찰떡궁합 💞"), ("worst_match", "상극 ⚡")):
        m = p.get(key)
        if m:
            mt.append(f'<div class="m"><span class="tag">{tag}</span><svg viewBox="0 0 400 400">{character_svg(m)}</svg>'
                      f'<h3>{esc(m.get("name",""))}</h3><p>{esc(m.get("why",""))}</p></div>')
    if mt:
        sec.append(f'<section class="slide reveal"><p class="kicker">동료 궁합</p><h2>같이 일하면?</h2><div class="match">{"".join(mt)}</div></section>')
    # 10 claude says
    if p.get("claude_says"):
        sec.append(f'''<section class="slide reveal"><p class="kicker">Claude의 한마디</p><div class="say">{esc(p.get("claude_says"))}</div>
{f'<p class="roast">🌶️ 매운맛 한 줄 · {esc(p.get("roast"))}</p>' if p.get("roast") else ""}
{f'<p class="roast">🔮 내일의 개발 운세 · {esc(p.get("fortune"))}</p>' if p.get("fortune") else ""}</section>''')
    # 11 card
    sec.append(f'''<section class="slide reveal"><p class="kicker">공유용 카드</p><h2>저장해서 자랑하기</h2>
<div class="cardwrap">{card_svg(p, s)}</div>
<div class="btns"><button id="save">PNG로 저장</button><button id="copy" class="sec">이미지 복사</button></div></section>''')
    sec.append(f'<p class="foot">이 페이지는 내 PC의 Claude Code 기록으로만 만들었고, 어디에도 올라가지 않았어요 · {esc(s.get("generated_at","")[:10])}</p>')

    fname = f"내캐릭터-{dt.date.today():%Y%m%d}"
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(name)} · 내캐릭터</title>
<style>{CSS}:root{{--bg:{bg2};--bg1:{bg1};--bg2:{bg2};--accent:{acc};--soft:{soft}}}</style></head>
<body data-file="{esc(fname)}"><main class="wrap">{"".join(sec)}</main><script>{JS}</script></body></html>'''


def gallery():
    cells = []
    base = {"colors": {"body": "#ffd6a5", "belly": "#fff6ea", "accent": "#ff7aa2", "cheek": "#ff9eb5"}}
    for sp in SPECIES:
        cells.append((sp, dict(base, species=sp)))
    for e in EYES:
        cells.append(("eyes:" + e, dict(base, species="bear", eyes=e)))
    for m in MOUTHS:
        cells.append(("mouth:" + m, dict(base, species="cat", mouth=m)))
    for a in ACCESSORIES:
        cells.append(("acc:" + a, dict(base, species="hamster", accessories=[a])))
    items = "".join(f'<figure><svg viewBox="0 0 400 400" width="160" height="160">{character_svg(p)}</svg><figcaption>{esc(n)}</figcaption></figure>' for n, p in cells)
    return (f'<!doctype html><meta charset="utf-8"><title>캐릭터 키트</title><style>body{{font-family:sans-serif;background:#fff3e2;display:flex;flex-wrap:wrap;gap:8px;padding:16px}}'
            f'figure{{margin:0;background:#fff;border:2px solid #3b2f2f;border-radius:14px;text-align:center;padding:6px}}figcaption{{font-size:12px}}</style>{items}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", nargs="?")
    ap.add_argument("stats", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--gallery")
    a = ap.parse_args()
    if a.gallery:
        open(a.gallery, "w").write(gallery())
        print(a.gallery)
        return
    if not (a.profile and a.stats):
        ap.error("profile.json 과 stats.json 이 필요합니다")
    s = json.load(open(a.stats))
    p = merge_fixed(json.load(open(a.profile)), s)
    out = a.out or os.path.join(os.path.expanduser("~/내캐릭터"), f"내캐릭터-{dt.date.today():%Y%m%d}.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(page(p, s))
    open(os.path.splitext(out)[0] + "-card.svg", "w").write(card_svg(p, s))
    print(out)


if __name__ == "__main__":
    main()
