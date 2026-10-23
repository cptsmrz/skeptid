# SKEPTID landing page: build prompt

Build a full-screen hero landing page for SkeptiD, a platform that checks messages, emails, images and video and shows the evidence behind every risk score. Visual style: liquid glass over a looping video background.

## Scope and hard rules
- Create ONLY: `web/landing.html`, `web/landing.css`, and new files under `web/assets/` and `web/fonts/`. Do not modify `web/index.html`, `web/app.js`, `web/styles.css`, `src/`, `tests/`, `config/`, or any existing file. You may read `web/app.js` to find route names.
- Plain HTML, CSS, and a little vanilla JS. No React, Tailwind, lucide-react, bundler, or CDN. No external URLs for fonts, images, or video.
- Icons: inline SVG, 1.5 px stroke, `currentColor`. At most 10 icons: menu, arrow-right, github, file-text, info, layers, book-open, plus.
- Honesty rules for all copy: no statistics, accuracy claims, "trusted by", testimonials, partner logos, or the phrase "AI-powered". Never imply certainty. Use only the copy given below.
- If anything cannot be done or verified (for example you cannot open a browser), say so in your report. Do not claim checks you did not run.

## Fonts
Poppins (400, 500, 600) for headings and body. Source Serif 4 italic 400, used only for `em`/`i` inside h1 to h3 and for the italic spans in the bottom quote. Self-host woff2 files in `web/fonts/` (use new file names; do not overwrite existing fonts) with `font-display: swap` and fallbacks (`system-ui`, `Georgia`). Headings use weight 500. Tell me which font files you added.

## Colour
Strict grayscale. Define tokens as `0 0% X%` HSL values. Text hierarchy: white, white/80, white/70. No coloured accents.
- Place a dark scrim (`rgba(0,0,0,0.35)`) above the video and below the content so text stays readable on bright frames.
- Text under 14 px must be at least white/80. Body text must reach 4.5:1 contrast over the scrim.

## Background video
- Source file: `web/assets/hero.mp4`, supplied by me. Poster: `web/assets/hero-poster.jpg`. Do NOT use any Google Drive URL.
- `<video autoplay muted loop playsinline preload="metadata" poster="assets/hero-poster.jpg" aria-hidden="true">`. It covers the viewport (`object-fit: cover`) at z-index 0. All content sits above at z-index 10.
- Small script: if `prefers-reduced-motion` is set or `navigator.connection.saveData` is true, pause the video and show only the poster.

## Liquid glass CSS (use exactly)
```css
:root { --radius: 1rem; }

.liquid-glass {
  background: rgba(255,255,255,0.01);
  background-blend-mode: luminosity;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  border: none;
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.1);
  position: relative;
  overflow: hidden;
}
.liquid-glass::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1.4px;
  background: linear-gradient(180deg,
    rgba(255,255,255,0.45) 0%, rgba(255,255,255,0.15) 20%,
    transparent 40%, transparent 60%,
    rgba(255,255,255,0.15) 80%, rgba(255,255,255,0.45) 100%);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  pointer-events: none;
}

.liquid-glass-strong {
  background: rgba(255,255,255,0.01);
  background-blend-mode: luminosity;
  backdrop-filter: blur(50px);
  -webkit-backdrop-filter: blur(50px);
  border: none;
  box-shadow: 4px 4px 4px rgba(0,0,0,0.05), inset 0 1px 1px rgba(255,255,255,0.15);
  position: relative;
  overflow: hidden;
}
.liquid-glass-strong::before { /* same as .liquid-glass::before, with alphas 0.5 and 0.2 */ }
```
Add a fallback: where `backdrop-filter` is unsupported, or under `prefers-reduced-transparency`, use a solid `rgba(20,20,20,0.75)` background. No border classes anywhere; the glass effect draws all borders through `::before`.

## Layout (plain CSS)
Flex row, `min-height: 100vh`. Left panel 52% width. Right panel 48% width, shown only from 1024 px up.

### Left panel
- Glass overlay: `.liquid-glass-strong`, absolutely positioned, inset 1rem (1.5rem from 1024 px), radius 1.5rem, behind the content.
- Nav: wordmark "SKEPTID" on the left (600 weight, 1.5rem, letter-spacing -0.05em, white), preceded by a small logo mark. A "Menu" button on the right: `.liquid-glass` pill with the menu icon, at least 44 px tall.
- There is no logo file. Create `web/assets/logo.svg`: a minimal geometric mark, a thin-stroke circle with one diagonal slit (like a lens), white, legible at 32 px. Use it in the nav only. Do not repeat it above the headline.
- Hero centre (flex 1, centred):
  - h1, two lines: "Doubt it." / "Then *verify* it." The italic part is `<em>` in Source Serif 4, white/80. Size 3.75rem, 4.5rem from 1024 px; letter-spacing -0.05em; line-height 1.02.
  - Subline (white/80, max-width 34rem): "Check a message, an image or a video before you trust it. SKEPTID runs three independent checks and shows the evidence behind every risk score."
  - CTA: "Open the desk", linking to `/`. A `.liquid-glass-strong` full-radius pill with an arrow-right icon inside a 1.75rem circle (`rgba(255,255,255,0.15)`). Hover: `scale(1.05)`; active: `scale(0.95)`.
  - Three `.liquid-glass` pills, full radius, 0.8125rem text, white/80: "Email and text", "Images", "Video".
  - One `.liquid-glass` chip: "Risk score with evidence, not proof."
- Bottom quote:
  - Label "OUR RULE" (0.75rem, letter-spacing 0.2em, uppercase, white/70).
  - Quote: "A score is an *opinion.* Evidence is something you can *check.*" Mix Poppins with Source Serif 4 italic for the emphasised words.
  - Byline: "NO NUMBER WITHOUT A SOURCE", with a thin horizontal line on each side.

### Right panel (from 1024 px)
- Top bar: a `.liquid-glass` pill with three icon links: GitHub (`https://github.com/cptsmrz/skeptid`), Spec (`.../blob/main/SPEC.md`), Limits (`.../blob/main/LIMITS.md`), plus an arrow-right. Beside it, a `.liquid-glass` pill button "Open the desk" with an arrow-right icon, linking to `/`. External links use `target="_blank" rel="noopener noreferrer"` and have `aria-label`s. No social-media icons: there are no such accounts.
- Card (`.liquid-glass`, width 14rem): title "Your content, your call". Text: "Messages and files are processed in memory. An external AI service is used only if you leave it switched on, and the result always tells you."
- Bottom section (margin-top auto): a `.liquid-glass` container, radius 2.5rem, padding 1rem.
  - Two side-by-side `.liquid-glass` cards, radius 1.5rem:
    - layers icon, "Three checks": "An external model, an open-source model and SKEPTID's own model run side by side. When they disagree, we show it."
    - book-open icon, "Evidence trail": "Highlighted phrases, forensic anomaly maps and frame timelines. No score without a reason."
  - Bottom card (`.liquid-glass`): a 96 by 64 thumbnail (`web/assets/anomaly-thumb.png`, shown with `filter: grayscale(1)`), title "Forensic anomaly map", text "See which regions of an image look edited or generated, and how strongly. A signal to inspect, not proof.", and a plus button linking to `/`. Until I supply a real screenshot, use a neutral grey placeholder block labelled "Example". Never use stock photography.
- Icon containers: 2rem circles, `rgba(255,255,255,0.1)`.

### Narrow screens (under 1024 px)
The right panel's content must not be lost. Show the privacy card and the two feature cards stacked below the hero, inside the left panel. The page scrolls normally; nothing is clipped.

### Menu
The Menu button toggles a `.liquid-glass-strong` dropdown with these links: Open the desk (`/`), Records (`/`, unless `web/app.js` shows a Records route you can link to), Limits, Source on GitHub, Spec. Use `aria-expanded`; close on Escape and on an outside click.

## Interaction and accessibility
- Interactive elements: `transition: transform 0.2s ease-out`, hover `scale(1.05)`. Social/icon links: white, hover white/80.
- Because the glass has no border, every interactive element needs a visible focus ring: `outline: 2px solid rgba(255,255,255,0.9); outline-offset: 3px`.
- Under `prefers-reduced-motion`: no scale transitions and no video playback.
- Semantic landmarks (`header`, `main`, `footer`), `lang="en"`, a page title and meta description, alt text on informative images, and at least 44 px touch targets.

## Acceptance
- It opens with `python -m http.server` run inside `web/`, at `/landing.html`.
- No console errors. DevTools shows no requests to other origins (external links excluded).
- Checked at 360, 768, and 1440 px, with keyboard Tab order and focus rings.
- Every link resolves. If the app's server blocks the video or fonts through its content-security headers, tell me which header, and do not loosen it yourself.
- Report which of these checks you actually ran and which you could not.