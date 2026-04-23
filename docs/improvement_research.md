# AlderIPM-Sim Improvement Research Report

> Research conducted 2026-04-17 — actionable recommendations for the AlderIPM-Sim ecological modeling toolkit (Python, R, and web implementations).

---

## 1. Ecological Modeling Tool UI/UX

### Current landscape

Forest management decision-support tools (e.g., the USFS [Ecosystem Management Decision Support (EMDS)](https://research.fs.usda.gov/pnw/products/dataandtools/ecosystem-management-decision-support-emds-system) system) increasingly emphasize web-based delivery, GIS integration, and scenario comparison. The common failure mode is exposing raw scientific complexity to practitioners who need actionable guidance.

### Recommendations

| # | Recommendation | Rationale |
|---|----------------|-----------|
| 1.1 | **Add a "Manager Mode" toggle** that hides ODE parameters and shows only scenario presets (e.g., "Low intervention", "Aggressive biocontrol", "Do nothing") with plain-language outcomes. | Forest managers are not modelers — they need decision framing, not parameter sliders. EMDS and the UK Forest Research [Decision Support Tools](https://www.forestresearch.gov.uk/climate-change/resources/decision-support-tools/) both default to scenario-based interfaces. |
| 1.2 | **Show a traffic-light risk summary** at the top of every view: green/amber/red for pest outbreak risk, tree mortality risk, and biocontrol sufficiency. | Dashboard UI best practices ([Design Studio 2026 guide](https://www.designstudiouiux.com/blog/dashboard-ui-design-guide/)) emphasize leading with the most important metric. |
| 1.3 | **Provide guided workflows** ("Step 1: Describe your stand → Step 2: Set management goals → Step 3: View recommendations") rather than a flat tab layout. | Multi-step wizards reduce cognitive load for non-technical users. Tools like iNaturalist succeed because they guide users through data entry. |
| 1.4 | **Add contextual help tooltips** for every parameter and output, written in plain language with ecological interpretation (e.g., "φ controls how many birds visit your stand — higher values mean more natural pest control"). | Users of ecological DSS tools consistently cite "understanding what the model is telling me" as the top barrier ([Schmolke et al. 2010](https://faculty.sites.iastate.edu/tesfatsi/archive/tesfatsi/EcoModGoodPractices.SchmolkeEtAl2010.pdf)). |
| 1.5 | **Include a map-based entry point** (even a simple regional selector) so managers can start from "my forest" rather than "my parameters". | GIS-first workflow is standard in EMDS 8.6 and LANDIS-II. Even a coarse regional selector adds spatial context. |

---

## 2. Scientific Visualization Best Practices

### Recommendations

| # | Recommendation | Rationale |
|---|----------------|-----------|
| 2.1 | **Use Viridis (or Cividis) as the default continuous colormap** for heatmaps, contour plots, and bifurcation diagrams. Remove any rainbow/jet colormaps. | Viridis is perceptually uniform, colorblind-safe, and prints well in grayscale. It is the scientific community standard. |
| 2.2 | **Use ColorBrewer qualitative palettes** (max 6 colors) for categorical series (pest, tree, bird trajectories). Specifically, the `Set2` or `Dark2` schemes work well. | ColorBrewer palettes are validated for colorblind accessibility and print reproduction. |
| 2.3 | **Add dual-encoding to all line plots**: color + line style (solid/dashed/dotted) + optional marker shape. | Multi-channel encoding ensures plots are readable in grayscale printouts and for colorblind users. |
| 2.4 | **For bifurcation diagrams**, use filled/unfilled markers to distinguish stable/unstable branches, and add a shaded "danger zone" region where tipping is imminent. | Standard dynamical systems convention; makes the qualitative message immediately visible. |
| 2.5 | **For phase portraits**, add arrow glyphs on trajectories to show flow direction, and mark equilibria with distinct symbols (filled circle = stable, open circle = unstable, half-filled = saddle). | Standard notation from nonlinear dynamics textbooks; aids interpretation. |
| 2.6 | **Provide publication-quality SVG/PDF export** with customizable font sizes, axis labels, and figure dimensions. | Researchers need to drop figures directly into manuscripts. Current PNG-only export limits utility. |

---

## 3. Interactive Parameter Exploration

### Recommendations

| # | Recommendation | Rationale |
|---|----------------|-----------|
| 3.1 | **Group sliders by ecological meaning**, not alphabetical order. Use collapsible sections: "Pest dynamics", "Tree growth", "Bird behavior", "Management controls". | [Visual Parameter Space Exploration (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10947302/) shows that semantic grouping reduces errors in parameter specification. |
| 3.2 | **Add a "Reset to defaults" button** per group and globally. Show the default value as a tick mark on each slider. | Users frequently get lost in parameter space. Easy reset prevents frustration. |
| 3.3 | **Implement linked parameter sweeps**: let users drag a range on one slider to trigger a sweep visualization showing how output changes across that range, overlaid as a ribbon/fan chart. | MATLAB Sensitivity Analysis toolbox ([MathWorks](https://www.mathworks.com/help/sldo/sensitivity-analysis.html)) demonstrates this pattern effectively. |
| 3.4 | **Show Sobol sensitivity indices** as a bar chart alongside parameter sliders, so users immediately see which parameters matter most. | [EasyModelAnalysis.jl](https://docs.sciml.ai/EasyModelAnalysis/dev/tutorials/sensitivity_analysis/) and the [CODEE journal](https://scholarship.claremont.edu/cgi/viewcontent.cgi?article=1079&context=codee) both recommend making sensitivity visible during exploration. |
| 3.5 | **Add a "Compare scenarios" mode** that shows two parameter sets side-by-side with diff-highlighted outputs. | Forest managers think in terms of "what if I do A vs. B?" — comparative views directly support this. |
| 3.6 | **Implement parameter presets** loaded from JSON: "Calibrated (UK Alnus)", "High pest pressure", "Strong biocontrol", "Climate stress". | Lowers entry barrier and provides validated starting points. |

---

## 4. Early Warning Signal Visualization

### Current tools reviewed

- [Early Warning Signals Toolbox](https://www.early-warning-signals.org/) (R, established standard)
- [ewstools](https://github.com/ThomasMBury/ewstools) (Python, complements R package)
- [EWSmethods](https://nsojournals.onlinelibrary.wiley.com/doi/10.1111/ecog.06674) (R, community-level, includes EWSNet ML model)

### Recommendations

| # | Recommendation | Rationale |
|---|----------------|-----------|
| 4.1 | **Add a "risk gauge" widget** — a semicircular gauge showing current tipping risk from 0–100%, computed from combined EWS indicators (variance trend, AC1 trend, spectral reddening). | Non-technical users need a single summary metric. The EWS Toolbox provides individual indicators but no unified risk score. |
| 4.2 | **Show rolling-window EWS indicators as sparklines** alongside the main time series, with trend lines and confidence bands. | This is the standard layout in ewstools and the EWS Toolbox. AlderIPM-Sim should match this convention. |
| 4.3 | **Add a "traffic light timeline"** below the main time series: green → amber → red as EWS indicators cross configurable thresholds. | Makes temporal progression of risk immediately legible without reading statistical indicators. |
| 4.4 | **Integrate Kendall tau trend statistics** with p-values displayed directly on EWS plots, following [Dakos et al. 2012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3261433/) methodology. | Statistical significance of trends is essential for scientific credibility. |
| 4.5 | **Consider integrating EWSNet** (deep learning tipping point prediction) as an optional "AI-assisted" warning, following the [EWSmethods](https://nsojournals.onlinelibrary.wiley.com/doi/10.1111/ecog.06674) approach. | Provides a complementary ML-based second opinion on tipping risk. |
| 4.6 | **Add an animation/playback mode** that shows the system evolving through time with EWS indicators updating in real time. | Seeing the approach to a tipping point unfold over time builds intuition about critical slowing down ([PNAS deep learning EWS](https://www.pnas.org/doi/10.1073/pnas.2106140118)). |

---

## 5. Streamlit App Best Practices

### Recommendations

| # | Recommendation | Rationale |
|---|----------------|-----------|
| 5.1 | **Cache ODE solutions with `@st.cache_data`**, keyed on the full parameter vector (as a tuple). Set `ttl=3600` to prevent stale cache buildup. | ODE integration is the most expensive operation. Caching avoids recomputation when users toggle between tabs without changing parameters ([Streamlit docs](https://docs.streamlit.io/develop/concepts/architecture/caching)). |
| 5.2 | **Use `@st.cache_resource` for the model object itself** (parameter registry, compiled ODE function) since these are global resources, not serializable data. | Prevents re-initialization on every rerun ([Streamlit caching overview](https://docs.streamlit.io/develop/concepts/architecture/caching)). |
| 5.3 | **Use `st.fragment`** (experimental) for independent UI sections (e.g., the EWS sparklines, the parameter sensitivity bar chart) so they rerun independently without triggering a full page rerun. | Reduces latency when users interact with controls that only affect one section. |
| 5.4 | **Move to native multi-page app structure** (`pages/` directory) with separate files for Simulation, Analysis, Early Warnings, Control Optimization, and Data Fitting. | Native multi-page apps share session state automatically and provide sidebar navigation ([Streamlit multi-page docs](https://discuss.streamlit.io/t/caching-across-pages-in-multipage-app/53020)). |
| 5.5 | **Use Plotly for all interactive charts** (not Matplotlib) to get hover tooltips, zoom, pan, and data export for free. | Streamlit best practices recommend Plotly or Altair for interactive apps, Matplotlib only for static publication figures ([Streamlit charting guidance](https://docs.streamlit.io/develop/concepts/architecture/caching)). |
| 5.6 | **Add a progress bar** (`st.progress`) for long ODE integrations (>1s) and parameter sweeps. | Users need feedback that computation is happening, not frozen. |
| 5.7 | **Persist user parameter sets in `st.session_state`** with save/load/compare functionality. | Enables "what-if" workflows across page navigation without losing state. |

---

## 6. R Shiny Best Practices

### Recommendations

| # | Recommendation | Rationale |
|---|----------------|-----------|
| 6.1 | **Adopt the [golem](https://thinkr-open.github.io/golem/) framework** for production packaging. Restructure the Shiny app as an R package with golem scaffolding. | golem provides standardized structure, automated testing, dependency management, and deployment tooling ([golem CRAN docs](https://cran.r-project.org/web/packages/golem/golem.pdf)). |
| 6.2 | **Migrate from shinydashboard to [bslib](https://rstudio.github.io/bslib/)** for theming. Use Bootstrap 5 with `bslib::bs_theme()` for modern, responsive layouts. | bslib is the successor to shinydashboard, supports Bootstrap 5, and provides better mobile responsiveness. |
| 6.3 | **Use `bindCache()` on all ODE integration and equilibrium-finding reactives**, keyed on the parameter inputs. | `bindCache()` stores results in a persistent cache, so repeated parameter combinations skip recomputation ([Shiny caching guide](https://shiny.posit.co/r/articles/improve/caching/)). |
| 6.4 | **Use `bindEvent()` with an explicit "Run simulation" button** rather than recomputing on every slider change. | Prevents expensive ODE solves from triggering on intermediate slider positions during drag ([Mastering Shiny Ch.23](https://mastering-shiny.org/performance.html)). |
| 6.5 | **Combine `bindCache() |> bindEvent()`** for the main simulation reactive: cache results AND only trigger on button click. | This is the recommended pattern for expensive computations ([Appsilon ShinyConf 2025 workshop](https://appsilon.github.io/shinyconf-2025-workshop-performance/)). |
| 6.6 | **Use `future` + `promises` for async ODE integration** with `plan(multisession)`. | Keeps the UI responsive during long computations by offloading to a background R session. |
| 6.7 | **Refactor into Shiny modules**: `mod_simulation`, `mod_analysis`, `mod_warnings`, `mod_control`, `mod_fitting`. | Modules improve testability, code organization, and enable independent development of each feature area. |

---

## 7. Accessible Scientific Software

### Recommendations

| # | Recommendation | Rationale |
|---|----------------|-----------|
| 7.1 | **Use Viridis/Cividis colormaps exclusively** and provide a "High contrast" theme toggle. | Covers protanopia, deuteranopia, and tritanopia. Viridis is the gold standard for colorblind-safe scientific visualization. |
| 7.2 | **Add dual encoding on ALL plots**: color + shape, color + line style, color + pattern fill. Never encode information with color alone. | WCAG 1.4.1 "Use of Color" requirement. Also serves users printing in B&W ([Section508.gov guide](https://www.section508.gov/create/making-color-usage-accessible/)). |
| 7.3 | **Provide an accessible data table alongside every chart**. Tables are inherently screen-reader accessible and give precise values. | Charts are inherently inaccessible to screen readers. Tables provide a complete fallback ([A11Y Collective checklist](https://www.a11y-collective.com/blog/accessible-charts/)). |
| 7.4 | **Add ARIA labels to all SVG chart elements**: `role="img"` on the chart container, `aria-label` describing the chart's key message, and `role="region"` with `aria-label` on each data series. | [W3C SVG Accessibility guidance](https://www.w3.org/wiki/SVG_Accessibility/ARIA_roles_for_charts) and [MIT Visualization Group research](https://vis.csail.mit.edu/pubs/rich-screen-reader-vis-experiences/) recommend this approach. |
| 7.5 | **Ensure all text meets WCAG 2.1 AA contrast** (4.5:1 for body text, 3:1 for large text and non-text UI components). Use [WCAG contrast checker tools](https://www.allaccessible.org/blog/color-contrast-accessibility-wcag-guide-2025). | Minimum legal requirement for accessibility in many jurisdictions. |
| 7.6 | **Make sliders keyboard-accessible** with arrow key control, and provide a numeric input field as an alternative for each slider. | Slider-only interfaces are inaccessible to keyboard and screen reader users. A paired numeric input provides full accessibility. |
| 7.7 | **Add text descriptions of key chart takeaways** (auto-generated): "Pest population is projected to exceed 500 individuals/ha by year 15 under current management." | Screen reader users and users with low vision benefit from narrative summaries. The [USWDS data visualization guide](https://designsystem.digital.gov/components/data-visualizations/) recommends this pattern. |

---

## 8. Chart.js Alternatives and Enhancements (for alder-ipm-sim-web)

### Library comparison

| Feature | Chart.js (current) | Plotly.js | D3.js | Observable Plot | ECharts |
|---------|-------------------|-----------|-------|-----------------|---------|
| **Learning curve** | Low | Medium | High | Medium | Medium |
| **Scientific chart types** | Basic (line, bar, scatter) | Excellent (contour, heatmap, 3D, statistical) | Unlimited (custom) | Good (statistical, geo) | Good (heatmap, parallel coords) |
| **Interactivity** | Hover, click | Hover, zoom, pan, select, export | Custom (full control) | Hover, crosshair | Hover, zoom, brush, animation |
| **Performance (large data)** | Good (canvas) | Excellent (WebGL via scattergl) | Fair (SVG) | Good (canvas) | Excellent (canvas + WebGL) |
| **Export** | PNG only | PNG, SVG, PDF, WebP | SVG (custom) | SVG | PNG, SVG |
| **Bundle size** | ~200KB | ~3.5MB (full), ~1MB (partial) | ~300KB | ~100KB | ~1MB |
| **Accessibility** | Limited | Good (ARIA, data tables) | Custom (full control) | Limited | Limited |

Sources: [Plotly.js](https://plotly.com/javascript/), [D3.js](https://d3js.org/), [npm comparison](https://npm-compare.com/chart.js,d3,highcharts,plotly), [DigitalOcean chart library guide](https://www.digitalocean.com/community/tutorials/javascript-charts), [Medium comparison](https://medium.com/@ebojacky/d3-js-vs-plotly-which-javascript-visualization-library-should-you-choose-dbf8ad67321f)

### Recommendations

| # | Recommendation | Rationale |
|---|----------------|-----------|
| 8.1 | **Migrate the web app from Chart.js to Plotly.js** for all scientific plots (trajectories, bifurcation diagrams, contour plots, heatmaps). | Plotly.js provides contour plots, heatmaps, 3D surfaces, hover data inspection, zoom/pan, and SVG/PDF export out of the box — all essential for scientific use and missing from Chart.js. |
| 8.2 | **Use Plotly.js partial bundles** (`plotly.js-basic-dist` + `plotly.js-gl2d-dist`) to reduce bundle size from 3.5MB to ~1MB. | Full Plotly.js is large; partial bundles include only needed trace types. |
| 8.3 | **Keep Chart.js only for the simple risk gauge/dashboard widgets** if bundle size is a concern, or replace entirely with Plotly.js indicator traces. | Chart.js is still good for simple gauges and donut charts where Plotly.js overhead isn't justified. |
| 8.4 | **Use Plotly.js `scattergl` traces** for any time series with >1000 data points. | WebGL rendering is 10-100x faster than SVG for large datasets ([Plotly docs](https://plotly.com/javascript/)). |
| 8.5 | **Use Plotly.js `contour` traces** for bifurcation diagrams and parameter-space heatmaps. | Native contour support with interactive hover showing exact (parameter, eigenvalue) pairs. |
| 8.6 | **Add Plotly.js `toImage` export** with configurable format (SVG, PNG, PDF), DPI, and dimensions for publication-quality figure download. | Researchers need to export figures directly from the web app into manuscripts. |
| 8.7 | **Consider Observable Plot** as a lightweight alternative if you add a secondary "quick view" dashboard that doesn't need Plotly.js's full feature set. | Observable Plot is ~100KB and produces clean statistical graphics with minimal code. |

---

## Implementation Priority

Based on impact vs. effort, recommended implementation order:

### High impact, moderate effort
1. **Manager Mode with scenario presets** (1.1, 1.2, 3.6)
2. **Plotly.js migration for web app** (8.1–8.6)
3. **Caching optimization** — Streamlit (5.1–5.2) and Shiny (6.3–6.5)
4. **EWS risk gauge and traffic-light timeline** (4.1, 4.3)

### High impact, lower effort
5. **Colorblind-safe palettes + dual encoding** (2.1–2.3, 7.1–7.2)
6. **Parameter grouping and presets** (3.1, 3.2, 3.6)
7. **Accessible data tables alongside charts** (7.3)
8. **Contextual help tooltips** (1.4)

### Medium impact, higher effort
9. **golem framework migration for R Shiny** (6.1, 6.7)
10. **Streamlit multi-page restructure** (5.4)
11. **Sensitivity indices visualization** (3.3, 3.4)
12. **EWSNet ML integration** (4.5)
13. **Full ARIA accessibility** (7.4–7.7)

### Lower priority / nice-to-have
14. **Map-based entry point** (1.5)
15. **Animation/playback mode** (4.6)
16. **Observable Plot secondary dashboard** (8.7)
17. **Async ODE computation in Shiny** (6.6)

---

## Sources

- [EMDS — US Forest Service](https://research.fs.usda.gov/pnw/products/dataandtools/ecosystem-management-decision-support-emds-system)
- [UK Forest Research Decision Support Tools](https://www.forestresearch.gov.uk/climate-change/resources/decision-support-tools/)
- [Dashboard UI Design Guide 2026](https://www.designstudiouiux.com/blog/dashboard-ui-design-guide/)
- [Schmolke et al. 2010 — Good practices in ecological modelling](https://faculty.sites.iastate.edu/tesfatsi/archive/tesfatsi/EcoModGoodPractices.SchmolkeEtAl2010.pdf)
- [Early Warning Signals Toolbox](https://www.early-warning-signals.org/)
- [ewstools Python package](https://github.com/ThomasMBury/ewstools)
- [EWSmethods R package](https://nsojournals.onlinelibrary.wiley.com/doi/10.1111/ecog.06674)
- [Dakos et al. 2012 — Comparing EWS methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC3261433/)
- [Deep learning for EWS — PNAS](https://www.pnas.org/doi/10.1073/pnas.2106140118)
- [Streamlit Caching Docs](https://docs.streamlit.io/develop/concepts/architecture/caching)
- [golem Framework](https://thinkr-open.github.io/golem/)
- [Appsilon ShinyConf 2025 — Performance Workshop](https://appsilon.github.io/shinyconf-2025-workshop-performance/)
- [Mastering Shiny Ch.23 — Performance](https://mastering-shiny.org/performance.html)
- [Shiny bindCache docs](https://shiny.posit.co/r/articles/improve/caching/)
- [Section508.gov — Color Accessibility](https://www.section508.gov/create/making-color-usage-accessible/)
- [W3C SVG Accessibility / ARIA roles for charts](https://www.w3.org/wiki/SVG_Accessibility/ARIA_roles_for_charts)
- [MIT Vis Group — Rich Screen Reader Experiences](https://vis.csail.mit.edu/pubs/rich-screen-reader-vis-experiences/)
- [A11Y Collective — Accessible Charts Checklist](https://www.a11y-collective.com/blog/accessible-charts/)
- [USWDS Data Visualizations Guide](https://designsystem.digital.gov/components/data-visualizations/)
- [WCAG Contrast Guide 2025](https://www.allaccessible.org/blog/color-contrast-accessibility-wcag-guide-2025)
- [Plotly.js](https://plotly.com/javascript/)
- [D3.js](https://d3js.org/)
- [MathWorks Sensitivity Analysis](https://www.mathworks.com/help/sldo/sensitivity-analysis.html)
- [Visual Parameter Space Exploration — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10947302/)
- [MATLAB Epidemic ODE Sensitivity Analysis](https://www.mathworks.com/help/matlab/math/sensitivity-analysis-of-epidemic-ode-parameters.html)
- [EasyModelAnalysis.jl](https://docs.sciml.ai/EasyModelAnalysis/dev/tutorials/sensitivity_analysis/)
