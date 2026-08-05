# Image-generation prompt blueprint

Replace bracketed fields and omit irrelevant optional copy. Keep the layer instructions explicit.

```text
Use case: ads-marketing.
Asset type: high-impact [platform] poster, exact aspect ratio [ratio].
Input image: the bundled approved poster is a STYLE-AND-DEPTH reference only, not an edit target.

Primary concept: [theme in one sentence].
Exact primary headline, rendered once and spelled perfectly:
“[headline]”
Hero keyword: “[keyword]”. Make it the largest contrasting typographic element.

Create a convincing naked-eye 3D illusion through physical layer relationships:
LAYER 1 — extreme foreground: enormous title fragments extend beyond canvas edges, remain razor sharp, and use controlled extrusion, narrow cast shadows, red/blue chromatic separation, offset-print ghosting, and torn glitch cuts. At least one title fragment crosses in front of the subject.
LAYER 2 — floating foreground: [1–3 theme symbols] at different scales; crop one at the frame and make another overlap the headline.
LAYER 3 — middle-ground subject: [subject], a deep blue-black editorial silhouette with electric rim light. Weave the subject through the type: one edge sits behind the hero word while another edge or luminous object breaks in front of secondary graphics. Add [theme-defining transformed object] as the concept reveal.
LAYER 4 — deep background: enlarged dark image fragments, halftone grids, grain, scan lines, and small editorial copy recede with lower contrast, blue atmosphere, and selective blur.

Create a diagonal depth path with strong scale disparity, occlusion, focus falloff, glow spill, and visible shadows between graphic planes. The result must look physically deep, as if typography and symbols jump out of the screen.

Optional supporting copy, each rendered once:
“[copy 1]”
“[copy 2]”
“[copy 3]”

Visual language: avant-garde Y2K Chinese youth-culture magazine, radical editorial typography, analog xerox grain, ink bleed, torn print, controlled brutalist collage. Dense but intentional, rebellious and premium.
Palette: [dominant saturated field], [hot accent], [acid counter-accent], deep black.
Typography: premium Chinese display type mixing distressed Song-style characters and bold condensed sans; English in heavy grotesk. Keep the exact headline legible at thumbnail size.

Avoid: flat infographic layout, boxed UI panels, evenly aligned modules, sticker-sheet composition, generic cyberpunk city, cute childish styling, excessive small copy, duplicated or garbled main text, logos, watermark, QR code.
Output: polished high-resolution raster art, exact [ratio].
```

## Targeted depth revision

Use this when the first result is visually flat:

```text
Change only the spatial construction. Preserve the headline, subject, palette, ratio, and overall concept. Increase the hero word until it breaks the canvas edges. Add clear bidirectional occlusion between type and subject, a cropped floating foreground object, stronger scale disparity, narrower cast shadows between planes, softer low-contrast deep background, and a diagonal foreground-to-background depth path. Do not add UI boxes or more copy.
```

## Targeted text revision

Use this when the title is wrong:

```text
Preserve composition, subject, palette, lighting, depth, and aspect ratio. Correct only the main headline to exactly: “[headline]”. Render it once, with no duplicated or extra characters. Keep all primary strokes readable; restrict glitch damage to letter edges and shadow layers.
```

## Final QA checklist

- Main headline is exact and singular.
- Hero keyword is dominant at thumbnail size.
- At least four visibly separated depth planes exist.
- Bidirectional occlusion is obvious.
- Foreground is cropped and sharp; background is softer and lower contrast.
- One thematic object explains the concept.
- Supporting copy stays subordinate.
- Ratio, anatomy, and exclusions are correct.
