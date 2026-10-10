"""Generate toolsmoke's inspection-seal logo (assets/logo.svg) and the simplified favicon (site/favicon.svg).

Black-ink round seal with Courier Prime Bold lettering set on the ring (converted to paths, so the SVG needs no
font), plus a vermilion pen check. Run from the repo root:  python .github/assets/make_logo.py <CourierPrime-Bold.ttf>
Requires fontTools (dev-only; toolsmoke itself has zero dependencies). See site/DESIGN.md, "Logo".
"""
import math
import sys

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

PAPER, INK, RED = "#f2eee3", "#1d1c1a", "#c3271b"
C = 256  # centre of the 512 box

font = TTFont(sys.argv[1])
gs, cmap, upm = font.getGlyphSet(), font.getBestCmap(), font["head"].unitsPerEm
CAP = font["OS/2"].sCapHeight or 0.62 * upm


def glyph_path(ch, matrix):
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
    gs[cmap[ord(ch)]].draw(TransformPen(pen, matrix))
    return pen.getCommands()


def ring_text(text, radius, size, track, top=True):
    """Set text on an arc. Top: reads clockwise, baseline at `radius`. Bottom: upright, cap line at `radius`."""
    s = size / upm
    adv = gs[cmap[ord(text[0])]].width * s + track  # monospace
    r_mid = radius if top else radius + CAP * s
    step = math.degrees(adv / r_mid)
    out = []
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        off = (i - (len(text) - 1) / 2) * step
        a = math.radians(off if top else -off)
        w = gs[cmap[ord(ch)]].width * s
        # local frame: x along the tangent, y down; then rotate about the centre
        ca, sa = math.cos(a), math.sin(a)
        if top:
            ox, oy = -w / 2, -radius          # baseline on the circle, glyph grows outward
        else:
            ox, oy = -w / 2, radius + CAP * s  # baseline outside, glyph grows inward (upright at the bottom)
        # glyph units -> local: (x*s + ox, -y*s + oy); local -> page: rotate by a, translate C
        m = (s * ca, s * sa, s * sa, -s * ca, C + ox * ca - oy * sa, C + ox * sa + oy * ca)
        # matrix (a, b, c, d, e, f) maps (x, y) -> (a*x + c*y + e, b*x + d*y + f)
        out.append(glyph_path(ch, (m[0], m[1], m[2], m[3], m[4], m[5])))
    return " ".join(out)


def flat_text(text, cx, baseline, size):
    s = size / upm
    w = gs[cmap[ord(text[0])]].width * s
    x = cx - w * len(text) / 2
    out = []
    for i, ch in enumerate(text):
        if ch != " ":
            out.append(glyph_path(ch, (s, 0, 0, -s, x + i * w, baseline)))
    return " ".join(out)


def star(cx, cy, r):
    pts = []
    for k in range(10):
        rr = r if k % 2 == 0 else r * 0.42
        a = math.radians(-90 + k * 36)
        pts.append(f"{cx + rr * math.cos(a):.1f} {cy + rr * math.sin(a):.1f}")
    return "M" + " L".join(pts) + "Z"




def pen_stroke(pts, widths):
    """Filled outline of a pen stroke along a polyline `pts`, half-width interpolated from `widths`."""
    left, right = [], []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        x0, y0 = pts[max(i - 1, 0)]
        x1, y1 = pts[min(i + 1, n - 1)]
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        t = i / (n - 1)
        k = t * (len(widths) - 1)
        j = min(int(k), len(widths) - 2)
        w = widths[j] + (widths[j + 1] - widths[j]) * (k - j)
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    ring = left + right[::-1]
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in ring) + "Z"


def bez(p0, p1, p2, n):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / n for i in range(n + 1))]


# a fountain-pen check: short heavy downstroke, long upstroke tapering to a hairline past the inner ring
CENTRE = bez((150, 262), (192, 280), (226, 338), 14)[:-1] + bez((226, 338), (282, 214), (392, 140), 30)
CHECK = pen_stroke(CENTRE, [9, 14, 17, 13, 8, 4, 1.2])

top = ring_text("TOOLSMOKE", 196, 47, 9, top=True)
bot = ring_text("AGENT READINESS", 196, 31, 4.5, top=False)
ink = (f'<circle cx="256" cy="256" r="236" fill="none" stroke="{INK}" stroke-width="13"/>'
       f'<circle cx="256" cy="256" r="216" fill="none" stroke="{INK}" stroke-width="3"/>'
       f'<circle cx="256" cy="256" r="174" fill="none" stroke="{INK}" stroke-width="5"/>'
       f'<path fill="{INK}" d="{top} {bot} {star(57, 256, 13)} {star(455, 256, 13)}"/>'
       f'<path fill="{INK}" d="{flat_text("No. 031", 256, 400, 25)}"/>')
grain = ('<filter id="g" filterUnits="userSpaceOnUse" x="0" y="0" width="512" height="512"><feTurbulence type="fractalNoise" baseFrequency=".75" '
         'numOctaves="2" seed="11"/><feColorMatrix values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 -12 9.4"/>'
         '<feComposite in="SourceGraphic" operator="in"/></filter>')
logo = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" role="img" '
        f'aria-label="toolsmoke inspection seal">\n<title>toolsmoke</title>\n<defs>{grain}</defs>\n'
        f'<circle cx="256" cy="256" r="250" fill="{PAPER}"/>\n'
        f'<g filter="url(#g)">{ink}</g>\n'
        f'<path fill="{RED}" d="{CHECK}"/>\n</svg>\n')
fav = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">'
       f'<title>toolsmoke</title><circle cx="32" cy="32" r="31" fill="{PAPER}"/>'
       f'<circle cx="32" cy="32" r="27" fill="none" stroke="{INK}" stroke-width="5"/>'
       f'<path d="M17 33l9 9 21-23" fill="none" stroke="{RED}" stroke-width="7.5" stroke-linecap="round" '
       f'stroke-linejoin="round"/></svg>\n')
open("assets/logo.svg", "w").write(logo)
open("site/favicon.svg", "w").write(fav)
print(len(logo), len(fav))
