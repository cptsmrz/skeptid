# SKEPTID: UI task list (hand-off)

## Rules
- Work ONLY inside `web/` on branch `feat/ui` (worktree `skeptid-ui`). Never touch `src/`, `tests/`, `config/`, or `SPEC.md`.
- Read `SPEC.md` sections 8, 11.1, 11.2, 11.3 first. They define the API, layout, visual direction, and glass rules.
- Plain HTML/CSS/JS. No framework, no build step, no CDN. Self-hosted fonts in `web/fonts`, or the system fallback stack.
- Mock mode is `?mock=1`. Real mode calls the endpoints in section 8. Never show a number that is not in the API response.
- Provider entries in the API now include `validated` (bool). Show a neutral "not validated" tag when it is false or when `model_version` contains "mock" or "heuristic".
- The two lanes (Message, Media) share no state.
- Commit after each group below. If the same fix fails twice, stop and report.

## Start here
Run `git status` and `git log --oneline`, read the existing `web/` code, and mark which items below are already done. Do not redo finished work.

## Group A: fixes to the first UI pass
1. Mock badge reflects real state (`?mock=1` and `response.mock`), never static.
2. Error copy in plain words ("Couldn't reach the analysis service") with a next step.
3. Make the paper grain visible (4-6% light, 6-8% dark). Inset shadow on trays. Empty, loading, and fail states rendered as glass panels per section 11.3.
4. Replace duplicate empty-state cards with example buttons. Remove all developer copy ("not on the desk in this revision").
5. "Analyse" is the filled primary button. "Choose file" is secondary.
6. Equal tray heights. Nav: disabled "Audio" tab with a "soon" tag. Theme toggle is an icon with an `aria-label`.
7. Media tray: visible drop target, accepted formats and limits (JPG, PNG, WebP up to 10 MB; MP4, MOV, AVI up to 50 MB and 60 s).
8. WCAG AA contrast (4.5:1) for all small text in both themes.
9. Result layout: two columns at 1100 px and wider. Left: evidence in a scroll-contained panel (max-height about 480 px). Right: sticky summary with verdict, risk bar, providers. Stack on narrow screens in this order: verdict, providers, evidence.
10. Spans: stronger highlight plus underline (not colour alone), numbered markers linked to a "Why flagged" list (description and weight). On LOW show "No strong indicators". Convert backend code-point offsets with `Array.from`; test with an emoji. In mock mode, generate spans from the actual input so they always align to words.
11. Verdict: signal colours (verdigris LOW, ochre MEDIUM, oxide red HIGH) on the label, plus a thin risk bar with ticks at 0.35 and 0.70. Replace "Level" with "Label". Hide the full UUID behind a copy button.
12. Providers: human names ("SKEPTID model", "Open-source model", "External service"), a "Shown result" marker, "Model" instead of `model_version`, plain agreement copy ("All three agree, spread 0.05"), and a strip plot of the three risks on a 0-1 axis with thresholds.
13. Mock example buttons renamed to human examples ("Safe message", "Phishing email", "Threat", "Providers disagree", "One provider down", "All providers down"), shown only in mock mode, in one quiet row.
14. Rename "This lane" to "History".

## Group B: Media lane and Records (UI-2)
- Media intake tray: image and video. Result view with verdict, providers panel, and the forensic anomaly map as an overlay with an opacity slider (label it "forensic anomaly map", not model attention).
- Video: frame strip with real thumbnails and a risk-over-time chart beneath it, aligned and clickable.
- Email attachments list with "Send to Media intake" (the only crossing between lanes; it copies the file).
- Records view: reads `/api/metrics`, active primary per modality, metrics per model version, confusion matrix, and a "not evaluated" state where data is missing.
- Feedback buttons: "Correct" / "Wrong, it was...".

## Group C: checks before reporting
- No console errors. Both themes verified. Correct at 360 px and 1440 px.
- Keyboard: Tab reaches both drop zones with a visible focus ring.
- Check against the hard constraints in section 11.2: no gradient text, neon glows, emoji icons, large rounded corners, hero sections, or fake numbers.
- Report with screenshots of: empty desk (light and dark), a HIGH message result, a disagreement result, an image result with the anomaly map, a video timeline, and a 360 px view.