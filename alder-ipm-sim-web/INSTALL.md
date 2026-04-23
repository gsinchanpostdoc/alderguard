# AlderIPM-Sim Web — Installation Guide

## Zero-Install Application

AlderIPM-Sim Web is a **standalone, zero-install browser application**. There is no build step, no package manager, no server, and no dependencies to install.

### Quick Start

1. Open `index.html` in any modern web browser.
2. That's it.

You can open the file directly from your file manager (double-click), or serve it from any static file server:

```bash
# Python (built-in)
cd alder-ipm-sim-web/
python -m http.server 8000
# then open http://localhost:8000

# Node.js (npx)
npx serve alder-ipm-sim-web/

# PHP (built-in)
php -S localhost:8000 -t alder-ipm-sim-web/
```

### Browser Compatibility

AlderIPM-Sim Web requires a modern browser with ES6+ support:

| Browser           | Minimum Version |
|-------------------|-----------------|
| Google Chrome     | 60+             |
| Mozilla Firefox   | 55+             |
| Microsoft Edge    | 79+ (Chromium)  |
| Safari            | 12+             |
| Opera             | 47+             |

**Not supported:** Internet Explorer (any version).

### External Dependencies

The only external resource is [Chart.js](https://www.chartjs.org/), loaded from the jsDelivr CDN:

```
https://cdn.jsdelivr.net/npm/chart.js
```

An active internet connection is required on first load to fetch Chart.js. After the browser caches it, the app works offline.

### Offline Use

To use AlderIPM-Sim Web fully offline, download Chart.js and update the `<script>` tag in `index.html`:

1. Download: https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js
2. Save as `js/chart.min.js`
3. In `index.html`, change:
   ```html
   <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
   ```
   to:
   ```html
   <script src="js/chart.min.js"></script>
   ```

### File Structure

```
alder-ipm-sim-web/
├── index.html           # Main application (open this)
├── INSTALL.md           # This file
├── README.md            # Project overview
├── css/
│   ├── style.css        # Application styles
│   └── print.css        # Print/PDF-friendly styles
├── js/
│   ├── parameters.js    # Parameter registry
│   ├── model.js         # ODE model & RK4 integrator
│   ├── simulation.js    # Simulation runner & CSV export
│   ├── warnings.js      # Early warning detection
│   ├── control.js       # Control strategy comparison
│   ├── charts.js        # Chart.js rendering
│   └── app.js           # Main application controller
├── data/
│   └── default_params.json
└── docs/                # Documentation
```
