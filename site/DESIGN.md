# toolsmoke landing page: design notes

## Reference object

A **laboratory inspection report**: the stapled, hole-punched test certificate an accredited test lab issues for a specimen.
The specimen is your LLM endpoint. The test method is the 31 toolsmoke probes, and the result is a signed sheet with a
red rubber stamp. Everything on the page comes from that paper object, not from web UI conventions:

- off-white report paper with a faint graph-paper grid, binder holes in the left margin, and a perforated edge
- a letterhead (the toolsmoke mark printed in black ink), report number, sheet numbering, "specimen / method / client" form fields
- results typed on a line printer, ticked or crossed in pen, then stamped (**NOT AGENT-READY**) and signed
- reviewer annotations in red pen in the margin (circles, arrows, underlines) for the "how it catches the leak" section
- an exhibit photo (the demo GIF) held on with a paper clip, a references list with footnote numbers, and an "end of report" rule

The sibling project agentckpt uses a film-editing-bench look (dark, cyan/violet, Martian Mono + Instrument Sans).
This page shares none of it: light paper instead of dark, ink + vermilion instead of cyan/violet, serif + typewriter + handwriting instead of mono + sans.

## Palette

| Role | Hex | Notes |
|---|---|---|
| Paper | `#f2eee3` | page background (warm off-white) |
| Paper, darker (holes, exhibit mount, tabs) | `#e4ddcb` | |
| Grid line | `#dde2d5` | graph-paper lines, 1px every 24px, heavier every 120px (`#ccd4c4`) |
| Rule | `#2b2925` | form rules and table lines |
| Ink | `#1d1c1a` | text, ticks, letterhead mark |
| Ink, secondary | `#57534b` | labels (7.0:1 on paper) |
| Ink, faint | `#6e695f` | captions (5.1:1 on paper) |
| Stamp vermilion | `#c3271b` | FAIL crosses, the stamp, reviewer's pen (4.9:1 on paper) |
| Pencil ochre | `#8a5a00` | WARN marks (5.6:1 on paper) |
| Ochre wash | `#e2cc96` at 60% | marker highlighting under leaked text (fills only, never as text colour). A tint of the ochre, so no new hue (was a yellow `#f4e27a` until 2026-10-10) |

No gradients and no glow anywhere. The grid is an SVG pattern, not a CSS gradient.

## Fonts (self-hosted woff2, Latin subset, all SIL OFL 1.1: `site/fonts/OFL.txt`)

| Use | Font | Why |
|---|---|---|
| Display + prose | **Fraunces** (variable, opsz 9–144, wght 400–900, WONK on) | an old-style "soft serif" with real quirks, like a lab's printed letterhead |
| Report data, labels, code | **Courier Prime** Regular + Bold | typewriter / line-printer face for the results table and form fields |
| Reviewer notes, signature | **Caveat** (wght 500–700) | handwriting for the red-pen margin notes |

No Inter and no default sans-serif + monospace pairing. Fallback stacks are short (`serif`, `monospace`, `cursive`).

## Layout grid

- Desktop: a 12-column sheet (max 1240px). A 64px binder margin on the left holds three punched holes.
  The layout is asymmetric and editorial:
  - letterhead row: mark + lab name (cols 1–7), report no. / sheet (cols 9–12, right-aligned, typewriter)
  - title block: big Fraunces headline across cols 1–8; the form fields (specimen, method, verdict + stamp) sit in a ruled box in cols 9–12
  - the results table prints across the full width in two newspaper-style columns (items 1–16 | 17–31), followed by a summary line and a signature block
  - section sheets below alternate: a narrow left "§" column (cols 1–2) with section numbers and a wide body (cols 3–12); the annotation section adds a right margin for red-pen notes
- Mobile (< 760px): one column. The binder holes become a perforated top edge, and the form box moves under the title. The table becomes one column, and margin notes are drawn inline over the sheet.
- No cards, no three-up feature grid. The probe list is a test schedule with dotted leaders, and references are footnotes.

## Animation plan

1. **Printing (hero):** after load, the results table prints one line at a time. Each row is revealed left to right in stepped increments, like a print head. Then its mark is pen-drawn in the result column (✓ in ink, ✗ in vermilion, ? in ochre, – for skip) with an SVG stroke. The summary counters fill in as rows complete.
2. **Stamp and seal:** when the last row is in, the **NOT AGENT-READY** stamp drops onto the verdict field: scale 1.25 → 0.97 → 1, landing at −8°, with a brief darker "press" frame. The ink is uneven (a static SVG noise mask, no filter animation). The signature is then written in (black ink, Caveat), and the round toolsmoke inspection seal is pressed beside it.
3. **Reviewer annotations (scroll):** sheet 2 shows the raw response for finding `tools.choice_none`. As each of four margin steps reaches mid-screen, a red-pen annotation is drawn (stroke-dashoffset). The steps are: (1) underline `tool_choice: "none"` with the note "asked for no tools"; (2) highlight and circle the leaked `<tool_call>` text, with an arrow to "tool call leaked as plain text!"; (3) underline `"tool_calls": none`; (4) mark toolsmoke's real FAIL line and stamp **CAUGHT** beside it. On phones the sheet sticks to the top and only the current note is shown.
4. **Micro-interactions:** copy buttons ink a small "COPIED" stamp; folder index tabs (uvx / pipx / Action) lift on hover/focus; probe ids in the schedule show their observation on hover/focus; links get a wavy red underline on hover; a "reprint" button replays the hero.
- `prefers-reduced-motion: reduce`: everything renders in its final state (printed, ticked, stamped, annotated) with no motion.
- Only transform/opacity/clip-path/stroke-dashoffset are animated; there are no infinite or full-screen animations.

## Data

All sample numbers come from `ROWS` in `app.js`, a copy of the README sample run that `tests/test_docs_sync.py` checks.

## Logo (2026-10-10)
The old mark (a green `>_` on a dark rounded square) belonged to the rejected terminal look. It is replaced by a **round inspection seal**, the kind a lab presses next to the signature:
- black ink `#1d1c1a`: a heavy outer ring, a hairline ring and an inner ring. **TOOLSMOKE** is set on the top arc and **AGENT READINESS** on the bottom arc, in Courier Prime Bold converted to paths so the SVG needs no font. Two stars sit at 3 and 9 o'clock, with "No. 031" (the 31 probes) inside.
- one vermilion `#c3271b` fountain-pen check. Its width tapers from heavy to a hairline (not a uniform cartoon stroke), and it overshoots the inner ring the way a hand check would.
- light rubber-stamp ink loss from a static SVG noise mask on the black ink only. The background is a round `#f2eee3` paper disc, which keeps it readable on GitHub's dark theme. There is no rounded-square app tile, glow or gradient.
- **Favicon** (`site/favicon.svg`) is the simplified 16px variant: paper disc, black ring, vermilion check. The letterhead uses the same simplified mark with an extra hairline ring, next to the Fraunces wordmark.
- Files: canonical `assets/logo.svg`, with copies at `docs/assets/logo.svg` and `site/seal.svg`. `assets/logo-512.png` is the seal centred on a paper square (used as the avatar). Everything is generated by `.github/assets/make_logo.py`; `tests/test_docs_sync.py` checks the copies.
- OG images (`site/social-preview.png`, `docs/assets/og-docs.png` via `#docs`) come from `.github/assets/social-preview.html`. They use the same letterhead mark and seal.

## Tightening pass (2026-10-10, toward `design/registry.md`)
- Palette reduced to the registered four (paper, ink, vermilion, ochre) plus their tints and greys. The blue signature ink became black ink, and the yellow highlighter became an ochre wash.
- The seal is pressed next to the signature at the end of the print sequence.
- The docs site now wears the same skin (`docs/stylesheets/report.css`). It uses paper background, ink header, vermilion links, and self-hosted Fraunces + Courier Prime (`docs/assets/fonts/`). This replaces Material's Google-hosted Inter + JetBrains Mono and its green accent, and the dark-mode toggle is dropped. Docs *content* is unchanged.
- No digital look is added: no glow, gradient, blur or neon. The terminal GIF stays as a paper-clipped photo print (Exhibit A).

## Registry difference check
toolsmoke holds the factory's single paper / print / stamp / typewriter slot, so it is the only project allowed these:
- **Background:** light warm paper. agentckpt is mid-tone LCD green, certfan near-black, linelore pure white, runbill cool concrete grey.
- **Colours:** none of `#f2eee3 #1d1c1a #c3271b #8a5a00` appears in another column.
- **Fonts:** Fraunces, Courier Prime and Caveat are not used by any other project (they use Silkscreen/Pixelify, Anybody/Atkinson, Schibsted/Fragment Mono, Unbounded/Red Hat).
- **Rendering:** a skeuomorphic printed document. The others are pixel art, generative SVG, kinetic type and isometric 3D.
- **Logo:** a round ink seal with a pen check. The others are a pixel flag, a fan of lines, a pure type mark and an isometric cube stack, and none is a rounded app tile.

## Ban-list self-check

| Banned | Present? | How it's avoided |
|---|---|---|
| Dark background with cyan/purple/blue gradients | **No** | light paper `#f2eee3`; only ink, vermilion, ochre. The demo GIF is a dark *photo* exhibit, not the page background |
| Gradient text | **No** | all text is flat ink or vermilion |
| Glow / glowing borders | **No** | no box-shadow glows; no shadows except a 1px hard offset on the exhibit print |
| Glassmorphism | **No** | no blur, no translucent panels, no backdrop-filter |
| Hero with copy left + animated card right | **No** | the title runs across 8 columns with a static form box beside it (the stamp lands in it at the end). The animation is the full-width results table *below* the title |
| Three-column feature cards | **No** | features are a single-column test schedule with dotted leaders, references are footnotes |
| Generic SaaS / dev-tool template layout | **No** | letterhead, report no., form fields, binder holes, signature block, sheet numbering; no navbar pills, no big centered CTA band |
| Inter (or default sans) + monospace pairing | **No** | Fraunces (serif) + Courier Prime (typewriter) + Caveat (handwriting) |
