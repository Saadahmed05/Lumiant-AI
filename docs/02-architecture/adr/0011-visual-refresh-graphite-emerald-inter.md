# ADR-0011: Visual refresh — graphite and emerald, Inter, system theme, one primitive layer

- **Status:** Accepted
- **Date:** 2026-11-11
- **Session:** S07
- **Related:** DEC-019 (superseded in part), DEC-020, ISSUES #39, `docs/UI_UX_AUDIT.md`

## Context
The owner asked for the web app to feel like a premium software product: a new colour and font combination, and every component engineered properly. An audit of the running app found the structure sound but the visual layer reading as a developer tool:

- every number set in Geist Mono (117 uses), so KPIs looked like terminal output;
- a neon glow on the active nav item and the Analyst button, a grid and two radial lights behind every page;
- 43 uppercase wide-tracked labels, one above every page title repeating the nav label;
- five corner radii with no rule;
- no shared control layer: 41 buttons, 7 selects, 8 inputs, 3 tab bars and 3 tables styled by hand per page, which is why Admin, Costs, Reports and Risks looked plainer than Overview.

`docs/UI_UX_AUDIT.md` had advised against a redesign. This decision changes the visual layer only; routes, navigation, behaviour, copy, permissions and data access are untouched.

## Decision
1. **Colour.** Graphite neutrals with one working accent (emerald, hue about 168°, kept on the teal side so it stays apart from the status green) and one attention colour (amber). Token names are unchanged; only values moved. The glow, the grid and the radial lights are removed. Glass is kept only for chrome that floats over scrolling content (command bar, palette), with a solid fallback under `prefers-reduced-transparency`.
2. **Type.** Inter (variable, with the optical-size axis) for all text and numbers, self-hosted from the `inter-ui` npm package through `next/font/local`. Numbers use tabular figures in the sans (`.figure`). Geist Mono is kept only for identifiers (`.code`): item codes, warehouse and lot ids, request refs, usernames, SQL, `kbd`.
3. **Theme.** With no saved choice the OS setting decides and is followed live; the toggle still overrides and is remembered; "Theme: match system" in the palette forgets the choice. `public/theme-init.js` writes the effective theme to `<html data-theme>` before first paint (light sets the attribute, dark leaves it off), so the CSS keeps one dark block and one light block.
4. **Shape.** One radius rule: `rounded-control` 8 px (buttons, inputs, tabs), `rounded-panel` 12 px (cards), `rounded-float` 14 px (popovers, dialogs), `rounded-full` for pills. Tailwind's `rounded-sm/md/lg/xl` are not used in pages.
5. **Primitive layer.** `apps/web/src/components/ui/`: Button, IconButton, Field, Input, Textarea, Select, SearchInput, Tabs, Segmented, Badge, Chip, DataTable parts, PageHeader, EmptyState, float surfaces. Pages compose these instead of styling controls by hand. Built with `clsx` only; no new styling dependency.

## Consequences
- A palette change is again a one-file change, and a control change is a one-component change.
- Light is now what a light-OS user sees first, so both themes carry the same contrast gate (TEST_RUNS S07-1). Two light-theme gaps found by the gate were fixed: the critical status red and the warning label colour.
- Form-control borders moved from `line` to `control-line`, which meets 3:1 on every plane (WCAG 1.4.11).
- The emerald accent is close in hue to "good" status green. The rule that a status is always shown with an icon and a label, never colour alone, now carries more weight.
- One more font package (`inter-ui`, 352 kB woff2, self-hosted). No font CDN; CSP `font-src 'self'` unchanged.
- Without JavaScript the theme falls back to dark.

## Alternatives considered
- Midnight navy with an indigo accent — closer to the blue and violet data series; the chart palette would need re-validation.
- Ink with a champagne-gold accent — collides with the amber attention colour.
- Light-only "paper and ink" — the largest change, and drops the dark theme the demos rely on.
- IBM Plex Sans / Manrope — both workable; Inter has the best tabular numerals and optical sizing in one family.
- Adopting Carbon or Fluent — a second component system on top of working Radix primitives, and a rewrite of every page.
- CSS `light-dark()` for single-definition tokens — needs recent browsers and is not read by the contrast tooling.

## Revisit when
The customer supplies a brand (colours, logo, font); user testing with warehouse and finance staff shows a clear preference for one theme; or a density setting is requested.
