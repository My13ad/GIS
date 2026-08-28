# 优路元航 GIS 工作台设计系统

## 0. Research Log

- Existing UI audit: the current Streamlit screen is a stacked document (`title/status -> controls + metric cards -> map -> downloads`). Its generous title treatment, card-like metrics, and detached delivery section read as a demonstration rather than a repeat-use tool.
- Direction: retain IBM Carbon's cool-gray layers, navy chrome, square geometry, dense labels, and single blue interaction color. Convert the page into a product shell without changing the data, map, validation, or artifact APIs.
- Layout mechanics: the desktop shell uses a compact project bar followed by a `3 / 8 / 3` work grid. The map owns the largest track and the document remains the sole scroll owner because Streamlit cannot provide a reliable bounded multi-pane runtime without custom components.
- Visual/browser research and visual QA are intentionally skipped because the task explicitly prohibits browser QA. Streamlit `AppTest` is the structural state harness for this pass.

## 1. Product Character

This is a municipal GIS delivery workbench for a project member who repeatedly loads one dataset, confirms its validity, inspects its spatial result, and produces handoff files. It is factual, compact, and stable under operational use. The signature is a **navy project bar with a blue stage rail**: the bar establishes persistent product identity, while the rail exposes the active workflow stages without pretending to be navigation.

The hierarchy is map-first. Source controls occupy a narrow left rail, the map is the dominant central canvas, and factual inspection plus delivery actions share a right rail. This removes the demo feel by replacing a presentation sequence and promotional-scale title with persistent work regions, compact metadata, visible state, and colocated outputs.

## 2. Tokens

### Color

| Token | Value | Role |
| --- | --- | --- |
| `--shell-canvas` | `#f4f4f4` | Page canvas |
| `--shell-surface` | `#ffffff` | Map and control surfaces |
| `--shell-layer` | `#e8e8e8` | Secondary rail bands |
| `--shell-hover` | `#e0e0e0` | Neutral hover/selected layer |
| `--chrome-navy` | `#0b1f33` | Project bar and strongest chrome |
| `--chrome-navy-hover` | `#142f4c` | Navy interactive hover |
| `--text-primary` | `#161616` | Main text |
| `--text-secondary` | `#525252` | Supporting text |
| `--text-muted` | `#6f6f6f` | Tertiary metadata |
| `--text-inverse` | `#ffffff` | Text on navy/blue |
| `--border-subtle` | `#c6c6c6` | Dividers |
| `--border-strong` | `#8d8d8d` | Map/input boundaries |
| `--accent-blue` | `#0f62fe` | Actions, focus, active stage |
| `--accent-blue-hover` | `#0353e9` | Action hover |
| `--accent-blue-active` | `#002d9c` | Action press |
| `--status-success` | `#198038` | Valid state marker |
| `--status-warning` | `#f1c21b` | Export warning marker |
| `--status-error` | `#da1e28` | Validation/export error marker |

Blue is the only accent. Status colors always have visible text. There are no gradients, decorative imagery, translucent surfaces, or colored metric cards. The embedded Folium map keeps its core-owned data colors.

### Typography

- UI: `"IBM Plex Sans", "Noto Sans SC", "Microsoft YaHei", sans-serif`.
- Data: `"IBM Plex Mono", "SFMono-Regular", Consolas, monospace`.
- `--type-product`: 1rem / 600 / 1.25, project identity.
- `--type-panel`: 0.75rem / 600 / 1.3, panel and stage labels.
- `--type-body`: 0.875rem / 400 / 1.45, controls and descriptions.
- `--type-data`: 0.875rem / 500 / 1.35, filenames and values.
- `--type-caption`: 0.75rem / 400 / 1.4, metadata.

All letter spacing is `0`. Tabular values use tabular figures. No marketing display type or page-scale heading exists in the shell.

### Space, Shape, Depth

- 4px base: `--space-1` 4px, `--space-2` 8px, `--space-3` 12px, `--space-4` 16px, `--space-5` 20px, `--space-6` 24px, `--space-8` 32px.
- `--project-bar-height`: 48px; `--control-height`: 40px; pointer targets remain at least 44px where Streamlit permits.
- `--radius-0`: 0; `--radius-1`: 2px; `--radius-2`: 4px. Structural panels and map use 0; controls use 2px; notices may use 4px.
- Depth is tonal layering plus 1px borders. No shell box shadows.

## 3. Product Shell

```text
desktop >= 1024px
┌ project / mode ───────────── stage rail ───── dataset status ┐ 48px
├ source rail 3/14 ┬──────── map canvas 8/14 ───────┬ inspection 3/14 ┤
│ data source      │ map header + source note       │ dataset rows   │
│ upload/validate  │ dominant 680px map             │ city table     │
│ schema guidance  │                                │ delivery files │
└──────────────────┴────────────────────────────────┴────────────────┘

tablet 768-1023px
┌ project bar / wrapped status ┐
├ source / validation           ┤
├ map canvas (560px)            ┤
├ inspection + delivery         ┤
└──────────────────────────────┘

mobile < 768px
┌ project bar ────────────────┐
├ source / validation         ┤
├ map canvas (500px)          ┤
├ dataset inspection          ┤
└ delivery actions            ┘
```

- Streamlit uses `layout="wide"`; the block container is full width with 16px desktop and 12px mobile gutters and no marketing-style max-width.
- Desktop primary columns use `[3, 8, 3]`; the map is therefore the largest surface. Below 1024px, all three Streamlit columns stack in source, map, inspection/delivery order so neither rail is compressed into an unusable narrow track.
- The document owns vertical scrolling. Rails are visually bounded but not independently scrollable. All grid/flex descendants use `min-width: 0`; long names use `overflow-wrap: anywhere`.
- Map height is 680px desktop, 560px tablet, and 500px mobile. The iframe itself carries Streamlit's `stCustomComponentV1` test ID, so responsive rules target `iframe[data-testid="stCustomComponentV1"]` directly.

## 4. Stable Structure

Stable HTML markers are structural hooks, not fake controls:

- `.project-bar`: product name, mode label, dataset validity and filename.
- `.stage-rail`: visible ordered labels `01 数据`, `02 校验`, `03 地图`, `04 交付`; active work is communicated through text and the blue rule.
- `.workbench-panel-header[data-panel="source|map|inspect|deliver"]`: compact index, panel title, and optional status. It precedes the native Streamlit controls it labels.
- `.inspection-list`: compact label/value rows for dataset metrics.
- `.delivery-note`: factual format/scope guidance adjacent to native download controls.

Markers contain no buttons, inputs, links, or click handlers. Every action remains a native Streamlit control and remains visible to `AppTest`.

## 5. Components and States

### Project Bar

- Left: `优路元航 / GIS 工作台`; center: stage rail; right: `数据有效`, source, filename, row count.
- Valid uses a small success marker plus text. Invalid upload errors render in the source rail and prevent stale map/delivery rendering.
- On mobile, identity stays first and metadata wraps below; nothing truncates the only filename reference.

### Panel Header

- Anatomy: two-digit stage index, sentence-case Chinese title, optional state label, bottom divider.
- Source `01 数据源`; map `03 地图画布`; inspection `02 数据检查`; delivery `04 交付文件`.
- No oversized headings. Panel headers establish scanning rhythm across all regions.

### Source Rail

- Native radio chooses demo/upload; native uploader appears only for upload. Validation feedback stays in this rail.
- States: demo-ready, upload-empty, validating through Streamlit rerun, valid, typed validation error.
- Schema help is concise and adjacent to the uploader; no onboarding card or feature copy.

### Map Canvas

- The map is the only richly textured surface and the largest grid track.
- A compact header and network note precede the official AMap JS API iframe.
- States: rendered; core/Streamlit loading; validation-blocked before render. CSV remains the equivalent nonvisual data path.

### Inspection List

- Replaces four metric cards with rows: `记录数`, `覆盖城市`, `高严重度`, `坐标参考`.
- Each row is label left, mono/tabular value right, separated by a subtle rule. The existing city distribution table follows.
- No KPI deltas, icons, analytics, or card grid.

### Delivery Group

- CSV and interactive HTML downloads appear first; static PNG generation follows in the same rail.
- States: ready, generating, generated with two PNG downloads, typed export failure, dataset-changed cache invalidation.
- Labels state the exact format and scope. Generation remains explicit and never runs on page load.

## 6. Interaction and Accessibility

- Native Streamlit behavior is preserved. Hover/focus/active feedback uses color plus a 100ms `opacity` or `transform` transition; press may translate by 1px.
- `prefers-reduced-motion` removes transitions and transforms. There is no decorative motion.
- WCAG 2.2 AA target: 4.5:1 body contrast, 3:1 UI boundaries, visible 2px blue focus outline, logical source -> map -> inspection -> delivery keyboard order, and no horizontal page overflow at 375px.
- Color never carries status alone. Native form labels remain visible. Errors identify the schema/export cause and next action.

## 7. Responsive and Content Stress

- At 1280px the `3 / 8 / 3` shell is present and the map is visually dominant.
- At 768px all work regions stack in task order; the compact project bar remains a two-column grid with its stage rail on the second row.
- At 375px regions form one column in task order, all action controls span the rail, and the map remains taller than any support region.
- Empty upload, long Chinese filename, wrapped validation error, generated PNG names, and unavailable basemap tiles must not force horizontal scrolling or detach labels from controls.

## 8. Accepted Debt

| Item | Why accepted | Exit |
| --- | --- | --- |
| Streamlit columns cannot become a true independently scrolling three-pane shell without custom components | Only Streamlit and existing dependencies are allowed; document scrolling preserves native behavior and accessibility | Reassess only if custom components enter scope |
| Folium iframe semantics are limited | Third-party boundary; CSV is the equivalent data route | Reassess in a later browser/accessibility QA phase |
| Streamlit DOM test IDs may change across versions | Scoped CSS is needed for native-control theming | Reverify on Streamlit upgrade |
| Browser visual QA is not run | Explicit task prohibition | Run 375/768/1280 visual QA in a later approved phase |
| Static PNG export depends on local export engines | Existing core runtime contract | Resolve through deployment/runtime work, not UI scope |
