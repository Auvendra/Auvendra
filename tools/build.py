#!/usr/bin/env python3
"""Generate the profile cards in assets/*.svg.

Everything visual on the profile comes from this file: the ASCII portraits,
the card layouts, the animations and the embedded font subsets. Edit the
text below, then run:

    pip install -r tools/requirements.txt
    python tools/build.py

Each SVG is self-contained (GitHub only renders SVGs that load nothing
external), so fonts are subset to the glyphs a card uses and inlined.
"""
from __future__ import annotations

import base64
import html
import io
import textwrap
from pathlib import Path

import numpy as np
from fontTools import subset
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "src"
FONTS = ROOT / "tools" / "fonts"
OUT = ROOT / "assets"

# ── palette: black, five grays, and Mikasa's scarf ────────────────────────────
BG = "#0a0a0a"
LINE = "#1d1d1d"
RAIL = "#2a2a2a"
DIM = "#4d4d4d"
MUTED = "#6e6e6e"
MID = "#949494"
LIGHT = "#d2d2d2"
WHITE = "#f3f3f3"
RED = "#c1121f"

W = 1000  # every card is 1000 units wide; README scales it to the column
ADV = 0.6  # JetBrains Mono advance width, in em

FONT_FILES = {
    ("normal", 200): "JetBrainsMono-ExtraLight.ttf",
    ("italic", 200): "JetBrainsMono-ExtraLightItalic.ttf",
    ("normal", 400): "JetBrainsMono-Regular.ttf",
    ("normal", 700): "JetBrainsMono-Bold.ttf",
}

BASE_CSS = """
text{font-family:J,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.art{font-size:var(--fs);white-space:pre}
.rv{animation:rv .9s cubic-bezier(.2,.7,.2,1) backwards}
@keyframes rv{from{opacity:0}}
.up{animation:up 1.1s cubic-bezier(.2,.7,.2,1) backwards}
@keyframes up{from{opacity:0;transform:translateY(10px)}}
.blink{animation:blink 1.1s steps(1) infinite}
@keyframes blink{50%{opacity:0}}
.ants{stroke-dasharray:3 5;animation:ants 1.2s linear infinite}
@keyframes ants{to{stroke-dashoffset:-16}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def font_face(style: str, weight: int, chars: set[str]) -> str:
    font = TTFont(FONTS / FONT_FILES[(style, weight)])
    cmap = font.getBestCmap()
    missing = sorted(ch for ch in chars if ord(ch) not in cmap and not ch.isspace())
    if missing:
        raise SystemExit(f"JetBrains Mono {style} {weight} lacks glyphs: {missing}")
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []  # no ligatures: ASCII art needs every glyph literal
    opts.hinting = False
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(chars | {" "})))
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (f"@font-face{{font-family:J;font-style:{style};font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")


class Card:
    RADIUS = 14

    def __init__(self, name: str, height: int, title: str, desc: str):
        self.name, self.h, self.title, self.desc = name, height, title, desc
        self.body: list[str] = []
        self.defs: list[str] = []
        self.css: list[str] = []
        self.used: dict[tuple[str, int], set[str]] = {}

    def add(self, *parts: str) -> None:
        self.body.extend(parts)

    def glyphs(self, s: str, weight: int = 400, italic: bool = False) -> None:
        self.used.setdefault(("italic" if italic else "normal", weight), set()).update(s)

    def _attrs(self, x, y, size, weight, italic, spacing, anchor, cls, style, extra):
        a = [f'x="{x:g}"', f'y="{y:g}"', f'font-size="{size:g}"']
        if weight != 400:
            a.append(f'font-weight="{weight}"')
        if italic:
            a.append('font-style="italic"')
        if spacing:
            a.append(f'letter-spacing="{spacing:g}"')
        if anchor:
            a.append(f'text-anchor="{anchor}"')
        if cls:
            a.append(f'class="{cls}"')
        if style:
            a.append(f'style="{style}"')
        if extra:
            a.append(extra)
        return " ".join(a)

    def text(self, x, y, s, *, size, fill, weight=400, italic=False, spacing=0,
             anchor=None, cls=None, style=None, extra=None) -> str:
        self.glyphs(s, weight, italic)
        a = self._attrs(x, y, size, weight, italic, spacing, anchor, cls, style, extra)
        return f'<text {a} fill="{fill}">{esc(s)}</text>'

    def rich(self, x, y, runs, *, size, weight=400, italic=False, spacing=0,
             anchor=None, cls=None, style=None) -> str:
        """One line of text in several colours: runs = [(text, fill), ...]."""
        spans = []
        for s, fill in runs:
            self.glyphs(s, weight, italic)
            spans.append(f'<tspan fill="{fill}">{esc(s)}</tspan>')
        a = self._attrs(x, y, size, weight, italic, spacing, anchor, cls, style, None)
        return f'<text {a} xml:space="preserve">{"".join(spans)}</text>'

    def label(self, x, y, s, *, cls=None, style=None) -> str:
        """Section label: a small red square and spaced capitals."""
        return (f'<g class="{cls or ""}" style="{style or ""}">'
                f'<rect x="{x}" y="{y - 8}" width="7" height="7" fill="{RED}"/>'
                + self.text(x + 18, y, s, size=12, fill=MUTED, weight=700, spacing=3)
                + "</g>")

    def render(self) -> str:
        faces = "".join(font_face(st, wt, ch) for (st, wt), ch in sorted(self.used.items()))
        r, h = self.RADIUS, self.h
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img" aria-labelledby="t d">
<title id="t">{esc(self.title)}</title>
<desc id="d">{esc(self.desc)}</desc>
<defs>
<style>{faces}{BASE_CSS}{"".join(self.css)}</style>
<clipPath id="card"><rect width="{W}" height="{h}" rx="{r}"/></clipPath>
<filter id="grain" x="0" y="0" width="100%" height="100%">
<feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="7" stitchTiles="stitch"/>
<feColorMatrix values="0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 .075 0 0 0 0"/>
</filter>
<radialGradient id="vig" cx=".5" cy=".45" r=".75">
<stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/>
</radialGradient>
{"".join(self.defs)}
</defs>
<g clip-path="url(#card)">
<rect width="{W}" height="{h}" fill="{BG}"/>
{chr(10).join(self.body)}
<rect width="{W}" height="{h}" fill="url(#vig)"/>
<rect width="{W}" height="{h}" filter="url(#grain)"/>
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="{r}" fill="none" stroke="{LINE}"/>
</svg>
"""

    def save(self) -> None:
        svg = self.render()
        (OUT / f"{self.name}.svg").write_text(svg, encoding="utf-8")
        print(f"assets/{self.name}.svg  {len(svg) / 1024:6.1f} KB")


# ── ASCII engine ──────────────────────────────────────────────────────────────
# Each character cell samples a 4x8 block, matching the 1:2 shape of a glyph
# cell (0.6em advance, 1.2em line height). Tone picks a ramp character; where
# a block contains a strong, consistent edge, the edge's direction picks one
# of - / | \ instead, which keeps the line art legible at small sizes.

RAMP = " .:-=+*#%@"
EDGE_CHARS = np.array(["-", "\\", "|", "/"])
CELL_W, CELL_H = 4, 8


def load_gray(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGBA")
    flat = Image.new("RGBA", im.size, (0, 0, 0, 255))
    flat.alpha_composite(im)
    return np.asarray(flat.convert("L"), dtype=np.float32) / 255


def fit(gray: np.ndarray, cols: int, rows: int, focus_x: float = 0.5) -> np.ndarray:
    """Crop to the aspect of a cols x rows character grid."""
    h, w = gray.shape
    want = (cols * ADV) / (rows * 1.2)
    if w / h > want:
        nw = int(round(h * want))
        x0 = int(np.clip(focus_x * w - nw / 2, 0, w - nw))
        return gray[:, x0:x0 + nw]
    nh = int(round(w / want))
    return gray[:nh, :]


def remove_paper(gray: np.ndarray, seal: int = 2) -> np.ndarray:
    """Turn a manga panel's white background black, keeping the figure."""
    ink = gray < 0.6
    sealed = Image.fromarray((ink * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * seal + 1))
    canvas = Image.fromarray(np.where(np.asarray(sealed) > 0, 0, 255).astype(np.uint8)).copy()
    w, h = canvas.size
    for x, y in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w - 1, h // 3)]:
        if canvas.getpixel((x, y)) == 255:
            ImageDraw.floodfill(canvas, (x, y), 128)
    paper = Image.fromarray(((np.asarray(canvas) == 128) * 255).astype(np.uint8))
    paper = np.asarray(paper.filter(ImageFilter.MaxFilter(2 * seal + 3))) > 0
    out = gray.copy()
    out[paper & (gray > 0.45)] = 0
    return out


def ascii_grid(gray, cols, rows, *, gamma=1.0, blur=0.0, edge_thresh=0.9, edge_min=6, edge_level=2,
               flat_cap=3):
    """Return (chars, levels): levels 0 = blank, 1..3 = dim / mid / bright.

    flat_cap limits how bright non-edge cells get, so contours lead and flat
    areas recede, which reads as a drawing rather than a block of @s.
    """
    im = Image.fromarray((np.clip(gray, 0, 1) * 255).astype(np.uint8))
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    im = im.resize((cols * CELL_W, rows * CELL_H), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float32) / 255
    lum = a.reshape(rows, CELL_H, cols, CELL_W).mean(axis=(1, 3)) ** gamma
    idx = np.clip(np.round(lum * (len(RAMP) - 1)).astype(int), 0, len(RAMP) - 1)
    chars = np.array(list(RAMP))[idx]
    levels = np.select([idx == 0, lum < 0.36, lum < 0.68], [0, 1, 2], 3)

    b = np.asarray(im.filter(ImageFilter.GaussianBlur(1.1)), dtype=np.float32) / 255
    p = np.pad(b, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    mag = np.hypot(gx, gy)
    line = (np.degrees(np.arctan2(gy, gx)) + 90) % 180  # edge runs perpendicular to gradient
    bins = np.select([(line < 22.5) | (line >= 157.5), line < 67.5, line < 112.5], [0, 1, 2], 3)
    strong = mag > edge_thresh
    counts = np.stack([(strong & (bins == k)).reshape(rows, CELL_H, cols, CELL_W).sum(axis=(1, 3))
                       for k in range(4)])
    is_edge = counts.max(axis=0) >= edge_min
    chars = np.where(is_edge, EDGE_CHARS[counts.argmax(axis=0)], chars)
    levels = np.where(is_edge, np.maximum(levels, edge_level), np.minimum(levels, flat_cap))
    return chars, levels


def polygon_mask(points, cols, rows, src_w, src_h, soften=0.0) -> np.ndarray:
    im = Image.new("L", (cols, rows), 0)
    ImageDraw.Draw(im).polygon([(x / src_w * cols, y / src_h * rows) for x, y in points], fill=255)
    if soften:
        im = im.filter(ImageFilter.GaussianBlur(soften))
    return np.asarray(im, dtype=np.float32) / 255


def data_uri(rgb: np.ndarray, quality: int = 86) -> str:
    """Embed a float [0,1] gray or RGB array as a base64 JPEG."""
    arr = (np.clip(rgb, 0, 1) * 255).round().astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def ink_tone(gray: np.ndarray, lo=10 / 255, hi=0.91) -> np.ndarray:
    """Lift manga black to the card's black and take the edge off paper white."""
    return lo + gray * (hi - lo)


def portrait(card: Card, key: str, image_uri: str, chars, levels, *, x, y, size, fs, classes,
             focus, reach, ascii_fade, bands=(), reveal=(0.1, 1.6), image_delay=1.2) -> str:
    """A real image in focus that dissolves into its own ASCII rendering.

    The ASCII prints first (with a red scan line), then the image fades in
    on top, masked by an ellipse around the face: outside the ellipse the
    picture gives way to characters. ascii_fade = (x1, x2) fades the ASCII
    itself out horizontally so the portrait melts into the card. bands =
    [(y, h, x1, x2), ...] cut thin strips out of the image so the characters
    underneath show through, like a frame mid-decompile.
    """
    fx, fy = focus
    rx, ry = reach
    a1, a2 = ascii_fade
    card.css.append(
        f".img{key}{{animation:img 1.4s ease {image_delay}s backwards}}@keyframes img{{from{{opacity:0}}}}"
        f".scan{key}{{opacity:0;animation:scan{key} {reveal[1] + .3:.2f}s cubic-bezier(.45,0,.25,1) {reveal[0]}s}}"
        f"@keyframes scan{key}{{0%,92%{{opacity:1}}0%{{transform:translateY(0)}}"
        f"100%{{opacity:0;transform:translateY({size}px)}}}}")
    card.defs.append(
        f'<radialGradient id="foc{key}" gradientUnits="userSpaceOnUse" cx="{fx}" cy="{fy}" r="{rx}" '
        f'gradientTransform="translate({fx} {fy}) scale(1 {ry / rx:.3f}) translate({-fx} {-fy})">'
        '<stop offset=".46" stop-color="#fff"/><stop offset=".68" stop-color="#fff" stop-opacity=".6"/>'
        '<stop offset=".9" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<mask id="im{key}" maskUnits="userSpaceOnUse" x="{x}" y="{y}" width="{size}" height="{size}">'
        f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="url(#foc{key})"/>'
        + "".join(f'<rect x="{bx1}" y="{by}" width="{bx2 - bx1}" height="{bh}"/>' for by, bh, bx1, bx2 in bands)
        + '</mask>'
        f'<linearGradient id="af{key}" gradientUnits="userSpaceOnUse" x1="{a1}" x2="{a2}">'
        '<stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#000"/></linearGradient>'
        f'<mask id="am{key}" maskUnits="userSpaceOnUse" x="{x - 20}" y="{y}" width="{size + 40}" height="{size}">'
        f'<rect x="{x - 20}" y="{y}" width="{size + 40}" height="{size}" fill="url(#af{key})"/></mask>'
        f'<pattern id="sl{key}" width="4" height="3" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="1" fill="#000" opacity=".28"/></pattern>'
        f'<linearGradient id="sg{key}"><stop offset="0" stop-color="{RED}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{RED}"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></linearGradient>')
    return (f'<g mask="url(#am{key})">'
            + ascii_markup(card, chars, levels, x0=x, y0=y, fs=fs, classes=classes, reveal=reveal)
            + f'<g mask="url(#im{key})" class="img{key}">'
            f'<image href="{image_uri}" x="{x}" y="{y}" width="{size}" height="{size}"/>'
            f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="url(#sl{key})"/></g>'
            f'<rect class="scan{key}" x="{x}" y="{y + 1}" width="{size}" height="1.6" fill="url(#sg{key})"/>'
            "</g>")


def ascii_markup(card: Card, chars, levels, *, x0, y0, fs, classes, reveal=(0.1, 1.6)) -> str:
    """Emit one <text> per tone per row, each row fading in top to bottom."""
    cw, lh = fs * ADV, fs * 1.2
    rows = chars.shape[0]
    start, span = reveal
    out = []
    for r in range(rows):
        y = y0 + r * lh + fs * 0.95
        parts = []
        for lvl, cls in classes.items():
            line = "".join(ch if lv == lvl else " " for ch, lv in zip(chars[r], levels[r]))
            body = line.lstrip()
            if not body.strip():
                continue
            card.glyphs(body)
            off = len(line) - len(body)
            parts.append(f'<text class="art {cls}" x="{x0 + off * cw:.1f}" y="{y:.1f}">{esc(body.rstrip())}</text>')
        if parts:
            out.append(f'<g class="rv" style="animation-delay:{start + span * r / rows:.2f}s">{"".join(parts)}</g>')
    return f'<g xml:space="preserve" style="--fs:{fs}px">{"".join(out)}</g>'


def typing(card: Card, x, y, phrases, *, size, prompt="> ", char_t=0.075, hold=1.5,
           del_t=0.028, gap=0.4) -> str:
    """Terminal line that types and erases each phrase in turn (SMIL)."""
    cw = size * ADV
    px = x + len(prompt) * cw
    t, spans = 0.0, []
    for text, _ in phrases:
        n = len(text)
        ev = [(t + k * char_t, k) for k in range(1, n + 1)]
        t_end = ev[-1][0] + hold
        ev += [(t_end + i * del_t, k) for i, k in enumerate(range(n - 1, -1, -1))]
        t = ev[-1][0] + gap
        spans.append(ev)
    total = t

    def keyed(ev, scale, first):
        pts = [(0.0, first)] + [(tt / total, k * scale) for tt, k in ev]
        times = ";".join(f"{tt:.4f}" for tt, _ in pts)
        vals = ";".join(f"{v:.1f}" for _, v in pts)
        return times, vals

    out = [card.text(x, y, prompt.rstrip(), size=size, fill=DIM)]
    for i, ((text, fill), ev) in enumerate(zip(phrases, spans)):
        times, vals = keyed(ev, cw, 0.0)
        width0 = len(text) * cw + 2 if i == 0 else 0  # what shows without SMIL
        card.defs.append(
            f'<clipPath id="ty{i}"><rect x="{px:.1f}" y="{y - size:.1f}" width="{width0:.1f}" height="{size * 1.5:.1f}">'
            f'<animate attributeName="width" dur="{total:.2f}s" repeatCount="indefinite" calcMode="discrete" '
            f'keyTimes="{times}" values="{vals}"/></rect></clipPath>')
        out.append(f'<g clip-path="url(#ty{i})">' + card.text(px, y, text, size=size, fill=fill) + "</g>")
    merged = sorted(e for ev in spans for e in ev)
    times, vals = keyed(merged, cw, 0.0)
    vals = ";".join(f"{px + float(v):.1f}" for v in vals.split(";"))
    out.append(f'<rect class="blink" x="{px:.1f}" y="{y - size * 0.82:.1f}" width="{cw * 0.9:.1f}" height="{size * 1.05:.1f}" fill="{LIGHT}" opacity=".85">'
               f'<animate attributeName="x" dur="{total:.2f}s" repeatCount="indefinite" calcMode="discrete" '
               f'keyTimes="{times}" values="{vals}"/></rect>')
    return "".join(out)


def pulse(cx, cy, *, r=3.5, color=RED, dur=2.2) -> str:
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="1.2">'
            f'<animate attributeName="r" values="{r};{r * 3.4}" dur="{dur}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values=".9;0" dur="{dur}s" repeatCount="indefinite"/></circle>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')


# ── cards ─────────────────────────────────────────────────────────────────────

def hero() -> None:
    c = Card("hero", 440, "Auvendra",
             "Auvendra: AI automation, integration and systems design. "
             "I like making things easier. Especially the repetitive stuff. "
             "Based in Lithuania, building with AI, open to work.")

    size, fs = 440, 6
    cols, rows = round(size / (fs * ADV)), round(size / (fs * 1.2))
    gray = load_gray(SRC / "auvendra.png")
    chars, levels = ascii_grid(fit(gray, cols, rows), cols, rows, blur=0.8, edge_thresh=0.7, edge_min=5,
                               edge_level=3, flat_cap=2)
    c.css.append(".a1{fill:#3a3a3a}.a2{fill:#7d7d7d}.a3{fill:#dcdcdc}")
    image = np.asarray(Image.fromarray((ink_tone(gray) * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS),
                       dtype=np.float32) / 255
    c.add(portrait(c, "h", data_uri(image), chars, levels, x=0, y=0, size=size, fs=fs,
                   classes={1: "a1", 2: "a2", 3: "a3"}, focus=(250, 184), reach=(232, 214),
                   ascii_fade=(380, 452), bands=[(88, 6, 150, 440), (318, 4, 96, 340)]))

    x = 488
    d = lambda s: f"animation-delay:{s}s"  # noqa: E731
    c.add(c.text(x, 64, "~/auvendra", size=12, fill=MUTED, spacing=1, cls="up", style=d(.5)),
          c.text(952, 64, "v2026.10", size=12, fill=MUTED, spacing=1, anchor="end", cls="up", style=d(.5)),
          c.text(x - 4, 150, "AUVENDRA", size=60, fill=WHITE, weight=200, spacing=9, cls="up", style=d(.7)),
          f'<rect x="{x}" y="174" width="34" height="2" fill="{RED}" class="up" style="{d(.9)}"/>',
          c.text(x + 48, 180, "AI AUTOMATION · INTEGRATION · SYSTEMS", size=12, fill=MID, weight=700,
                 spacing=2, cls="up", style=d(.9)),
          c.text(x, 238, "I like making things easier.", size=20, fill=LIGHT, cls="up", style=d(1.1)),
          c.text(x, 268, "Especially the repetitive stuff.", size=20, fill=LIGHT, cls="up", style=d(1.2)),
          f'<g class="up" style="{d(1.4)}">'
          + typing(c, x, 320, [("explain it.", WHITE), ("build it.", WHITE), ("test it.", WHITE), ("fix it.", RED)],
                   size=16) + "</g>",
          f'<line x1="{x}" y1="356" x2="952" y2="356" stroke="{LINE}" class="up" style="{d(1.5)}"/>')

    fields = [(x, "BASE", "Lithuania · EET"), (x + 146, "MODE", "building with AI"),
              (x + 346, "STATUS", "open to work")]
    for i, (fx, k, v) in enumerate(fields):
        g = [c.text(fx, 384, k, size=10.5, fill=MUTED, weight=700, spacing=2.4)]
        if k == "STATUS":
            g += [pulse(fx + 4, 403.5, r=3), c.text(fx + 16, 408, v, size=13.5, fill=LIGHT)]
        else:
            g.append(c.text(fx, 408, v, size=13.5, fill=LIGHT))
        c.add(f'<g class="up" style="{d(1.6 + i * .1):}">' + "".join(g) + "</g>")
    c.save()


def method() -> None:
    c = Card("method", 334, "How I work",
             "How I work: find what takes too much time, explain exactly what I want, build with AI, "
             "test it and explain what needs fixing, then put it to use and keep improving it.")
    c.add(c.label(56, 64, "HOW I WORK"),
          c.text(944, 64, "describe it · test it · fix it", size=12, fill=MUTED, anchor="end"),
          c.text(54, 108, "I work out what I want, then keep fixing it until it works.", size=21, fill=WHITE, weight=200))

    xs, y = [120, 310, 500, 690, 880], 186
    steps = [("01", "FIND", ["what keeps taking", "too much time?", "start there."]),
             ("02", "EXPLAIN", ["what should it do?", "what goes where?", "write it all down."]),
             ("03", "BUILD", ["AI writes the code.", "I give directions", "and check the result."]),
             ("04", "TEST", ["try it properly.", "find what breaks.", "explain the fix."]),
             ("05", "USE", ["put it to use.", "see what's annoying.", "keep improving it."])]

    # loop from TEST back to EXPLAIN
    c.add(f'<path d="M{xs[3]},{y - 10} C{xs[3]},{y - 44} {xs[1]},{y - 44} {xs[1]},{y - 10}" fill="none" stroke="#3a3a3a" class="ants"/>',
          f'<rect x="{500 - 104}" y="{y - 45}" width="208" height="18" fill="{BG}"/>',
          c.text(500, y - 32, "↩ fix it and try again", size=11.5, fill=MUTED, anchor="middle"))

    cycle, travel = 6.5, 0.82
    c.defs.append('<filter id="glow" x="-200%" y="-200%" width="500%" height="500%">'
                  '<feGaussianBlur stdDeviation="2.4"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    c.add(f'<line x1="{xs[0]}" y1="{y}" x2="{xs[-1]}" y2="{y}" stroke="{RAIL}"/>')
    for i, (x, (num, name, lines)) in enumerate(zip(xs, steps)):
        t = travel * (x - xs[0]) / (xs[-1] - xs[0])
        if t == 0:
            kt, vals = "0;.14;1", f"{RED};#3a3a3a;#3a3a3a"
        else:
            kt = f"0;{t - .004:.3f};{t:.3f};{min(t + .14, 1):.3f}" + (";1" if t + .14 < 1 else "")
            vals = f"#3a3a3a;#3a3a3a;{RED};#3a3a3a" + (";#3a3a3a" if t + .14 < 1 else "")
        anim = f'<animate attributeName="{{a}}" dur="{cycle}s" repeatCount="indefinite" keyTimes="{kt}" values="{vals}"/>'
        c.add(f'<circle cx="{x}" cy="{y}" r="6" fill="{BG}" stroke="#3a3a3a" stroke-width="1.4">{anim.format(a="stroke")}</circle>',
              f'<circle cx="{x}" cy="{y}" r="2" fill="#3a3a3a">{anim.format(a="fill")}</circle>',
              c.rich(x, y + 38, [(num + "  ", RED), (name, WHITE)], size=14, weight=700, spacing=1.5, anchor="middle"))
        for j, ln in enumerate(lines):
            c.add(c.text(x, y + 68 + j * 20, ln, size=12.5, fill=MID if j < 2 else MUTED, anchor="middle"))
    c.add(f'<circle r="3.2" fill="{RED}" filter="url(#glow)">'
          f'<animateMotion path="M{xs[0]},{y} H{xs[-1]}" dur="{cycle}s" repeatCount="indefinite" '
          f'keyPoints="0;1;1" keyTimes="0;{travel};1" calcMode="linear"/>'
          f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;{travel};{travel + .04};1" dur="{cycle}s" repeatCount="indefinite"/>'
          "</circle>")
    c.save()


def roles() -> None:
    roles = [("Automation", "Engineer"), ("Integration", "Engineer"), ("Applied AI", "Engineer"),
             ("Forward-Deployed", "/ Solutions Eng."), ("Solutions", "Architect")]
    c = Card("roles", 212, "Where I'm heading",
             "Where I'm heading: " + ", then ".join(" ".join(r) for r in roles) + ".")
    c.add(c.label(56, 64, "WHERE I'M HEADING"))
    xs, ry = [120, 310, 500, 690, 880], 120
    c.add(f'<line x1="{xs[0]}" y1="{ry}" x2="{xs[-1]}" y2="{ry}" stroke="{RAIL}"/>')
    for i, (x, (a, b)) in enumerate(zip(xs, roles)):
        last = i == len(xs) - 1
        if i:
            c.add(f'<path d="M{x - 99},{ry - 4} L{x - 95},{ry} L{x - 99},{ry + 4}" fill="none" stroke="#3e3e3e"/>')
        c.add(f'<g class="up" style="animation-delay:{.15 + i * .1:.2f}s">'
              + (pulse(x, ry, r=4.5) if last else
                 f'<circle cx="{x}" cy="{ry}" r="4.5" fill="{BG}" stroke="#4a4a4a" stroke-width="1.4"/>')
              + c.text(x, ry + 34, a, size=13.5, fill=WHITE if last else LIGHT, weight=700 if last else 400, anchor="middle")
              + c.text(x, ry + 54, b, size=13.5, fill=LIGHT if last else MUTED, anchor="middle")
              + "</g>")
    c.save()


def footer() -> None:
    c = Card("mikasa", 380, "This world is cruel. It’s also very beautiful.",
             "ASCII portrait of Mikasa Ackerman in her red scarf, with her line from Attack on Titan: "
             "This world is cruel. It’s also very beautiful.")

    size, fs, x = 380, 6, W - 380
    cols, rows = round(size / (fs * ADV)), round(size / (fs * 1.2))
    gray = remove_paper(load_gray(SRC / "mikasa.png"))
    src = gray.shape[0]
    scarf_poly = [(95, 372), (95, 300), (105, 288), (130, 284), (155, 287), (185, 279),
                  (215, 269), (245, 262), (263, 268), (267, 300), (269, 372)]

    chars, levels = ascii_grid(gray, cols, rows, blur=0.6, edge_thresh=0.7, edge_min=5, edge_level=3, flat_cap=2)
    in_scarf = polygon_mask(scarf_poly, cols, rows, src, src) > 0.5
    levels = np.where(in_scarf & (levels > 0), levels + 3, levels)

    # selective colour: the panel stays black and white, only the scarf is red
    tone = np.asarray(Image.fromarray((ink_tone(gray) * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS),
                      dtype=np.float32) / 255
    m = polygon_mask(scarf_poly, size, size, src, src, soften=2.5)[..., None]
    rgb = tone[..., None] * ((1 - m) * np.ones(3) + m * np.array([0.95, 0.07, 0.12]))

    c.css.append(".a1{fill:#3a3a3a}.a2{fill:#7d7d7d}.a3{fill:#dcdcdc}"
                 f".s1{{fill:#4f0a0f}}.s2{{fill:#8f0d18}}.s3{{fill:{RED}}}")
    c.add(portrait(c, "m", data_uri(rgb), chars, levels, x=x, y=0, size=size, fs=fs,
                   classes={1: "a1", 2: "a2", 3: "a3", 4: "s1", 5: "s2", 6: "s3"},
                   focus=(x + 180, 196), reach=(214, 226), ascii_fade=(x + 90, x + 6),
                   reveal=(0.2, 1.8), image_delay=1.4))

    c.add(c.label(56, 64, "A NOTE"),
          c.text(52, 152, "“This world is cruel.", size=30, fill=WHITE, weight=200, italic=True, cls="up", style="animation-delay:.4s"),
          c.text(52, 196, " It’s also very beautiful.”", size=30, fill=WHITE, weight=200, italic=True, cls="up", style="animation-delay:.6s"),
          f'<rect x="58" y="226" width="34" height="2" fill="{RED}" class="up" style="animation-delay:.8s"/>',
          c.text(104, 232, "MIKASA ACKERMAN", size=11.5, fill=MUTED, weight=700, spacing=2.6, cls="up", style="animation-delay:.8s"),
          c.rich(58, 306, [("try it.  find the bug.  ", MUTED), ("fix it.", RED), ("  try again.", MUTED)],
                 size=13.5, cls="up", style="animation-delay:1s"),
          c.text(58, 332, "auvendra · lithuania · 2026", size=11, fill="#5a5a5a", spacing=2, cls="up", style="animation-delay:1.1s"))
    c.save()


def divider() -> None:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 32" width="{W}" height="32">
<defs>
<linearGradient id="fade" gradientUnits="userSpaceOnUse" x1="0" y1="16" x2="{W}" y2="16">
<stop offset="0" stop-color="#fff" stop-opacity="0"/>
<stop offset=".25" stop-color="#fff" stop-opacity=".35"/>
<stop offset=".5" stop-color="#fff"/>
<stop offset=".75" stop-color="#fff" stop-opacity=".35"/>
<stop offset="1" stop-color="#fff" stop-opacity="0"/>
</linearGradient>
</defs>
<path d="M0 16H{W}" fill="none" stroke="url(#fade)" stroke-width="1.5"/>
</svg>
'''
    (OUT / "divider.svg").write_text(svg, encoding="utf-8")
    print("assets/divider.svg")


# ── project cards ─────────────────────────────────────────────────────────────
# Same frame for every project: number, title and write-up on the left, a
# panel on the right that shows what the thing actually does.

PH = 380                       # project card height
PX, PY, PW = 624, 40, 320      # right-hand panel
PHH = PH - 2 * PY
SUB = "#0d0d0d"                # panel fill, a step up from the card


def lit(attr, i, n, *, off, on=RED, dur=7.0, hold=0.14) -> str:
    """SMIL colour change that lights item i of n in turn, then hands on."""
    t = i / n
    if t == 0:
        kt, vals = f"0;{hold};1", f"{on};{off};{off}"
    else:
        kt = f"0;{t - .004:.3f};{t:.3f};{min(t + hold, 1):.3f}" + (";1" if t + hold < 1 else "")
        vals = f"{off};{off};{on};{off}" + (f";{off}" if t + hold < 1 else "")
    return (f'<animate attributeName="{attr}" dur="{dur}s" repeatCount="indefinite" '
            f'keyTimes="{kt}" values="{vals}"/>')


def pill(c: Card, x, y, s, *, size=11.5, fill=MID, stroke=RAIL, pad=10, h=24) -> tuple[str, float]:
    w = len(s) * size * ADV + 2 * pad
    return (f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="{h / 2}" fill="{SUB}" stroke="{stroke}"/>'
            + c.text(x + pad, y + h / 2 + size * 0.36, s, size=size, fill=fill)), w


def panel_head(c: Card, s: str) -> str:
    return c.text(PX + 24, PY + 32, s, size=10.5, fill=MUTED, weight=700, spacing=2.4)


def bot_panel(c: Card) -> str:
    jobs = [("activity", "who's active, who isn't"), ("votes", "tribe decisions"),
            ("timers", "nothing gets forgotten"), ("invites", "bringing people in"),
            ("roles", "the right access")]
    out = [panel_head(c, "WHAT IT HANDLES")]
    y0, step = PY + 76, 46
    for i, (job, note) in enumerate(jobs):
        y = y0 + i * step
        if i:
            out.append(f'<line x1="{PX + 24}" y1="{y - 27}" x2="{PX + PW - 24}" y2="{y - 27}" stroke="{LINE}"/>')
        out.append(f'<circle cx="{PX + 28}" cy="{y - 4.5}" r="3.5" fill="#3a3a3a">{lit("fill", i, len(jobs), off="#3a3a3a")}</circle>'
                   + c.text(PX + 44, y, job, size=14, fill=LIGHT)
                   + c.text(PX + PW - 24, y, note, size=12, fill=MUTED, anchor="end"))
    return "".join(out)


def site_panel(c: Card) -> str:
    out = [f'<line x1="{PX}" y1="{PY + 32}" x2="{PX + PW}" y2="{PY + 32}" stroke="{LINE}"/>']
    out += [f'<circle cx="{PX + 18 + k * 12}" cy="{PY + 16}" r="3.5" fill="#2f2f2f"/>' for k in range(3)]
    out.append(f'<rect x="{PX + 66}" y="{PY + 7}" width="{PW - 82}" height="18" rx="9" fill="{BG}" stroke="{LINE}"/>'
               + c.text(PX + 80, PY + 20, "doomtribe.lol", size=11.5, fill=MID))
    out.append(c.text(PX + 24, PY + 62, "SECTIONS", size=10.5, fill=MUTED, weight=700, spacing=2.4))
    tiles = ["strats", "clips", "build templates", "calculators", "role sign-ups"]
    tw, th = (PW - 48 - 10) / 2, 36
    for i, name in enumerate(tiles):
        tx, ty = PX + 24 + (i % 2) * (tw + 10), PY + 78 + (i // 2) * (th + 10)
        out.append(f'<rect x="{tx:.1f}" y="{ty}" width="{tw:.1f}" height="{th}" rx="6" fill="{BG}" stroke="{RAIL}">'
                   f'{lit("stroke", i, len(tiles), off=RAIL, dur=6.0)}</rect>'
                   + c.text(tx + 12, ty + 22.5, name, size=12, fill=LIGHT))
    lock = PX + 24 + tw + 10, PY + 78 + 2 * (th + 10)
    out.append(f'<rect x="{lock[0]:.1f}" y="{lock[1]}" width="{tw:.1f}" height="{th}" rx="6" fill="none" stroke="{RAIL}" class="ants"/>'
               + c.text(lock[0] + 12, lock[1] + 22.5, "invite only", size=12, fill=MUTED))
    out.append(c.text(PX + 24, PY + 244, "WHO GETS IN", size=10.5, fill=MUTED, weight=700, spacing=2.4))
    x = PX + 24
    for tier in ["ally", "member", "admin"]:
        p, w = pill(c, x, PY + 258, tier, stroke=RED if tier == "admin" else RAIL,
                    fill=LIGHT if tier == "admin" else MID)
        out.append(p)
        x += w + 8
    return "".join(out)


def transcript_panel(c: Card) -> str:
    out = [panel_head(c, "HOW IT WORKS")]
    x0, x1 = PX + 24, PX + PW - 24
    # the link going in
    out.append(f'<rect x="{x0}" y="{PY + 48}" width="{x1 - x0}" height="30" rx="6" fill="{BG}" stroke="{RAIL}"/>'
               f'<rect x="{x0 + 12}" y="{PY + 56.5}" width="20" height="14" rx="4" fill="{RED}"/>'
               f'<path d="M{x0 + 19.5},{PY + 60} l6,3.5 l-6,3.5z" fill="{WHITE}"/>'
               + c.text(x0 + 42, PY + 67.5, "youtube.com/watch?v=…", size=12, fill=MID))
    out.append(f'<line x1="{(x0 + x1) / 2}" y1="{PY + 82}" x2="{(x0 + x1) / 2}" y2="{PY + 102}" stroke="#3a3a3a" class="ants"/>')
    # the captions coming out, with timestamps switching on and off
    by, dur = PY + 106, 6
    kt = "0;.42;.5;.92;1"
    out.append(f'<rect x="{x0}" y="{by}" width="{x1 - x0}" height="122" rx="6" fill="{BG}" stroke="{RAIL}"/>'
               + c.text(x0 + 14, by + 24, "timestamps", size=11.5, fill=MUTED)
               + f'<g>{c.text(x1 - 54, by + 24, "on", size=11.5, fill=LIGHT, anchor="end")}'
               f'<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="{kt}" dur="{dur}s" repeatCount="indefinite"/></g>'
               + f'<g opacity="0">{c.text(x1 - 54, by + 24, "off", size=11.5, fill=MUTED, anchor="end")}'
               f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="{kt}" dur="{dur}s" repeatCount="indefinite"/></g>'
               f'<rect x="{x1 - 46}" y="{by + 12}" width="32" height="16" rx="8" fill="{RED}">'
               f'<animate attributeName="fill" values="{RED};{RED};{RAIL};{RAIL};{RED}" keyTimes="{kt}" dur="{dur}s" repeatCount="indefinite"/></rect>'
               f'<circle cx="{x1 - 22}" cy="{by + 20}" r="5.5" fill="{WHITE}">'
               f'<animate attributeName="cx" values="{x1 - 22};{x1 - 22};{x1 - 38};{x1 - 38};{x1 - 22}" keyTimes="{kt}" dur="{dur}s" repeatCount="indefinite"/></circle>'
               f'<line x1="{x0 + 14}" y1="{by + 38}" x2="{x1 - 14}" y2="{by + 38}" stroke="{LINE}"/>')
    stamps, bars = ["0:04", "0:11", "0:19", "0:26"], [196, 150, 182, 108]
    ts = "".join(c.text(x0 + 14, by + 60 + k * 18, s, size=11, fill=RED) for k, s in enumerate(stamps))
    lines = "".join(f'<rect x="{x0 + 54}" y="{by + 55 + k * 18}" width="{w}" height="6" rx="3" fill="#3a3a3a"/>'
                    for k, w in enumerate(bars))
    out.append(f'<g>{ts}<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="{kt}" dur="{dur}s" repeatCount="indefinite"/></g>'
               f'<g>{lines}<animateTransform attributeName="transform" type="translate" values="0 0;0 0;-40 0;-40 0;0 0" '
               f'keyTimes="{kt}" dur="{dur}s" repeatCount="indefinite"/></g>')
    # where it goes
    x = x0
    for s in ["→ clipboard", "→ save to file"]:
        p, w = pill(c, x, PY + 244, s)
        out.append(p)
        x += w + 8
    return "".join(out)


def onlyud_panel(c: Card) -> str:
    stats = [("3,000", "REAL USERS"), ("$2,500", "EARNED"), ("1", "PERSON RUNNING IT")]
    out = [panel_head(c, "BY THE NUMBERS")]
    for i, (num, what) in enumerate(stats):
        y = PY + 98 + i * 76
        if i:
            out.append(f'<line x1="{PX + 24}" y1="{y - 54}" x2="{PX + PW - 24}" y2="{y - 54}" stroke="{LINE}"/>')
        out.append(c.text(PX + 22, y, num, size=44, fill=WHITE, weight=200, cls="up", style=f"animation-delay:{.6 + i * .15:.2f}s")
                   + c.text(PX + PW - 24, y - 6, what, size=10.5, fill=MID, weight=700, spacing=2, anchor="end"))
    return "".join(out)


PROJECTS = [
    dict(name="bot", kind="DISCORD BOT", title="Doom Discord Bot", tagline="TRIBE ADMIN, ON AUTOPILOT",
         desc="A Discord bot for an ARK tribe. Running a tribe comes with a lot of small, repetitive jobs: "
              "keeping track of who's active, running votes, remembering timers, sending invites and "
              "sorting out roles. The bot does all of it, so nobody has to do it by hand anymore.",
         facts=[("MY PART", "designed · built with AI · tested"), ("FOR", "an ARK tribe")],
         panel=bot_panel),
    dict(name="doomtribe", kind="WEBSITE", title="Doomtribe", tagline="THE WHOLE TRIBE, ONE PLACE",
         desc="A tribe's website, and it's invite-only. Strats, clips, build templates, calculators and "
              "role sign-ups all live in one place instead of getting lost in Discord. Members, allies "
              "and admins each get their own level of access, so everyone sees what they need.",
         facts=[("MY PART", "designed · built with AI · tested"), ("LIVE", "doomtribe.lol ↗")],
         panel=site_panel),
    dict(name="transcript", kind="YOUTUBE TOOL", title="Transcript Exporter", tagline="CAPTIONS IN ONE PASTE",
         desc="Paste a YouTube link and it pulls the video's full captions and copies them straight to "
              "your clipboard. Keep the timestamps to find a moment again, or drop them for clean text. "
              "You can save it to a file too. Handy for notes, quotes or handing a long video to an AI.",
         facts=[("MY PART", "designed · built with AI · tested"), ("OUTPUT", "clipboard · file")],
         panel=transcript_panel),
    dict(name="onlyud", kind="DISCORD COMMUNITY", title="OnlyUD", tagline="3,000 REAL USERS. RUN SOLO.",
         desc="A Discord server I owned and ran completely on my own. It grew to around 3,000 real users "
              "and earned $2,500 before it closed down. With no admins, everything came straight to me: "
              "community management, support, feature requests, testing and bug reports.",
         facts=[("MY PART", "owner · solo, no admins"), ("STATUS", "closed down")],
         panel=onlyud_panel),
]


def projects() -> None:
    col = 58  # characters per write-up line: (584 - 56) / (14.5 * ADV), with a little slack
    for i, p in enumerate(PROJECTS, 1):
        c = Card(f"project-{p['name']}", PH, p["title"], f"{p['title']}: {p['desc']}")
        d = lambda s: f"animation-delay:{s}s"  # noqa: E731
        lines = textwrap.wrap(p["desc"], col)
        if len(lines) > 5:
            raise SystemExit(f"{p['name']}: write-up runs to {len(lines)} lines, the card fits 5")

        c.add(c.label(56, 64, f"{i:02d} · {p['kind']}", cls="up", style=d(.1)),
              c.text(54, 120, p["title"], size=36, fill=WHITE, weight=200, spacing=2, cls="up", style=d(.25)),
              f'<rect x="56" y="142" width="34" height="2" fill="{RED}" class="up" style="{d(.4)}"/>',
              c.text(104, 148, p["tagline"], size=12, fill=MID, weight=700, spacing=2, cls="up", style=d(.4)))
        for j, ln in enumerate(lines):
            c.add(c.text(56, 190 + j * 23, ln, size=14.5, fill=LIGHT, cls="up", style=d(.5 + j * .05)))
        c.add(f'<line x1="56" y1="306" x2="584" y2="306" stroke="{LINE}" class="up" style="{d(.7)}"/>')
        x = 56
        for k, v in p["facts"]:
            c.add(f'<g class="up" style="{d(.8)}">'
                  + c.text(x, 330, k, size=10.5, fill=MUTED, weight=700, spacing=2.4)
                  + c.text(x, 352, v, size=13.5, fill=LIGHT) + "</g>")
            x += max(len(k) * (10.5 * ADV + 2.4), len(v) * 13.5 * ADV) + 40

        c.add(f'<g class="up" style="{d(.3)}">'
              f'<rect x="{PX}" y="{PY}" width="{PW}" height="{PHH}" rx="10" fill="{SUB}" stroke="{LINE}"/>'
              + p["panel"](c) + "</g>")
        c.save()


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    hero()
    method()
    roles()
    footer()
    divider()
    projects()
