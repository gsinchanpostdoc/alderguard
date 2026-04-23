/**
 * Chart rendering using Plotly.js (loaded from CDN).
 * Provides scientific-quality interactive charts with zoom, pan, and hover tooltips.
 * Uses the Okabe-Ito colorblind-safe palette throughout.
 */

const ChartManager = {
  // Okabe-Ito colorblind-safe palette
  palette: {
    orange:    '#E69F00',
    skyBlue:   '#56B4E9',
    green:     '#009E73',
    yellow:    '#F0E442',
    blue:      '#0072B2',
    vermillion:'#D55E00',
    purple:    '#CC79A7',
    black:     '#000000'
  },

  // Semantic color mapping for state variables
  colors: {
    beetles:     '#D55E00',  // vermillion
    parasitoids: '#009E73',  // green
    capacity:    '#0072B2',  // blue
    defoliation: '#E69F00',  // orange
    susceptible: '#D55E00',
    infected:    '#CC79A7',
    flies:       '#009E73',
    defol:       '#E69F00'
  },

  // Track which divs have charts for cleanup
  activePlots: new Set(),

  /**
   * Get dark mode aware layout defaults.
   */
  _baseLayout() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: isDark ? 'rgba(30,40,30,0.3)' : 'rgba(245,249,245,0.5)',
      font: {
        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        size: 13,
        color: isDark ? '#c8d6c8' : '#1a2e1a'
      },
      margin: { l: 60, r: 20, t: 40, b: 50 },
      xaxis: {
        gridcolor: isDark ? 'rgba(200,214,200,0.15)' : 'rgba(0,0,0,0.08)',
        zerolinecolor: isDark ? 'rgba(200,214,200,0.3)' : 'rgba(0,0,0,0.15)'
      },
      yaxis: {
        gridcolor: isDark ? 'rgba(200,214,200,0.15)' : 'rgba(0,0,0,0.08)',
        zerolinecolor: isDark ? 'rgba(200,214,200,0.3)' : 'rgba(0,0,0,0.15)'
      }
    };
  },

  _baseConfig() {
    return {
      responsive: true,
      displayModeBar: true,
      modeBarButtonsToRemove: ['lasso2d', 'select2d', 'sendDataToCloud'],
      displaylogo: false,
      toImageButtonOptions: {
        format: 'png',
        filename: 'alder-ipm-sim_chart',
        height: 600,
        width: 900,
        scale: 2
      }
    };
  },

  /**
   * Destroy/purge an existing Plotly chart by div id.
   */
  destroy(id) {
    const el = document.getElementById(id);
    if (el) {
      try { Plotly.purge(el); } catch(e) { /* ignore */ }
    }
    this.activePlots.delete(id);
  },

  /**
   * Create a single time series subplot in a div.
   */
  _createSubplot(divId, years, data, label, color, yLabel, yUnit) {
    this.destroy(divId);
    const el = document.getElementById(divId);
    if (!el) return;

    const trace = {
      x: years,
      y: data,
      type: 'scatter',
      mode: 'lines',
      name: label,
      line: { color: color, width: 2.5, shape: 'spline' },
      fill: 'tozeroy',
      fillcolor: color + '15',
      hovertemplate: '<b>' + label + '</b><br>Year: %{x}<br>Value: %{y:.4f}<extra></extra>'
    };

    const layout = Object.assign(this._baseLayout(), {
      title: { text: label, font: { size: 14, weight: 700 } },
      xaxis: Object.assign(this._baseLayout().xaxis, {
        title: { text: 'Year', font: { size: 12 } }
      }),
      yaxis: Object.assign(this._baseLayout().yaxis, {
        title: { text: yUnit ? yLabel + ' (' + yUnit + ')' : yLabel, font: { size: 12 } },
        rangemode: 'tozero'
      }),
      showlegend: true,
      legend: { x: 1, xanchor: 'right', y: 1, bgcolor: 'rgba(255,255,255,0.7)' }
    });

    Plotly.newPlot(el, [trace], layout, this._baseConfig());
    this.activePlots.add(divId);

    // Add alt text for accessibility
    el.setAttribute('aria-label', label + ' time series chart showing ' + data.length + ' data points');
  },

  /**
   * Render all 4 subplots from a simulation result.
   */
  createSubplots(result) {
    const years = result.A.map((_, i) => i);
    this._createSubplot('chart-A', years, result.A, 'Beetles (A)', this.colors.beetles, 'Beetle density', 'ind/ha');
    this._createSubplot('chart-F', years, result.F, 'Parasitoids (F)', this.colors.parasitoids, 'Parasitoid density', 'ind/ha');
    this._createSubplot('chart-K', years, result.K, 'Carrying Capacity (K)', this.colors.capacity, 'Carrying capacity', 'relative');
    this._createSubplot('chart-D', years, result.D, 'Defoliation (D)', this.colors.defoliation, 'Defoliation fraction', '');
  },

  /**
   * Render an early warning indicator chart.
   */
  createEWChart(divId, labels, data, title, color) {
    this.destroy(divId);
    const el = document.getElementById(divId);
    if (!el) return;

    const trace = {
      x: labels,
      y: data,
      type: 'scatter',
      mode: 'lines',
      name: title,
      line: { color: color, width: 2 },
      fill: 'tozeroy',
      fillcolor: color + '15',
      hovertemplate: '<b>' + title + '</b><br>Window: %{x}<br>Value: %{y:.4f}<extra></extra>'
    };

    const layout = Object.assign(this._baseLayout(), {
      title: { text: title, font: { size: 14, weight: 700 } },
      xaxis: Object.assign(this._baseLayout().xaxis, {
        title: { text: 'Window position', font: { size: 12 } }
      }),
      yaxis: Object.assign(this._baseLayout().yaxis, {
        title: { text: title, font: { size: 12 } }
      }),
      showlegend: false
    });

    Plotly.newPlot(el, [trace], layout, this._baseConfig());
    this.activePlots.add(divId);
    el.setAttribute('aria-label', title + ' early warning indicator chart');
  },

  /**
   * Render R1 vs R2 scatter plot.
   */
  createR1R2Scatter(divId, fixedPoints) {
    this.destroy(divId);
    const el = document.getElementById(divId);
    if (!el) return;

    const validFPs = fixedPoints.filter(fp => !isNaN(fp.R1) && !isNaN(fp.R2));
    if (validFPs.length === 0) return;

    const stableFPs = validFPs.filter(fp => fp.stable);
    const unstableFPs = validFPs.filter(fp => !fp.stable);

    const traces = [];
    if (stableFPs.length > 0) {
      traces.push({
        x: stableFPs.map(fp => fp.R1),
        y: stableFPs.map(fp => fp.R2),
        type: 'scatter',
        mode: 'markers+text',
        name: 'Stable',
        text: stableFPs.map((_, i) => '#' + (fixedPoints.indexOf(stableFPs[i]) + 1)),
        textposition: 'top center',
        marker: { color: this.colors.parasitoids, size: 14, symbol: 'circle',
                  line: { color: '#fff', width: 2 } },
        hovertemplate: 'R1: %{x:.4f}<br>R2: %{y:.4f}<extra>Stable</extra>'
      });
    }
    if (unstableFPs.length > 0) {
      traces.push({
        x: unstableFPs.map(fp => fp.R1),
        y: unstableFPs.map(fp => fp.R2),
        type: 'scatter',
        mode: 'markers+text',
        name: 'Unstable',
        text: unstableFPs.map((_, i) => '#' + (fixedPoints.indexOf(unstableFPs[i]) + 1)),
        textposition: 'top center',
        marker: { color: this.colors.beetles, size: 14, symbol: 'diamond',
                  line: { color: '#fff', width: 2 } },
        hovertemplate: 'R1: %{x:.4f}<br>R2: %{y:.4f}<extra>Unstable</extra>'
      });
    }

    const layout = Object.assign(this._baseLayout(), {
      title: { text: 'R1 (Resistance) vs R2 (Resilience)', font: { size: 14, weight: 700 } },
      xaxis: Object.assign(this._baseLayout().xaxis, {
        title: { text: 'R1 (Resistance)', font: { size: 12 } },
        range: [-1.1, 1.1]
      }),
      yaxis: Object.assign(this._baseLayout().yaxis, {
        title: { text: 'R2 (Resilience)', font: { size: 12 } }
      }),
      showlegend: true,
      legend: { x: 0, y: 1, bgcolor: 'rgba(255,255,255,0.7)' }
    });

    Plotly.newPlot(el, traces, layout, this._baseConfig());
    this.activePlots.add(divId);
    el.setAttribute('aria-label', 'Resistance vs Resilience scatter plot with ' + validFPs.length + ' fixed points');
  },

  /**
   * Render control comparison grouped bar chart with cost breakdown.
   * Replaces the old createControlBarChart with running cost vs control cost.
   */
  createControlSummaryChart(divId, strategies, bestIdx) {
    this.destroy(divId);
    const el = document.getElementById(divId);
    if (!el) return;

    // Compute running cost (damage-related) and control cost per strategy
    const names = strategies.map(s => s.name);
    const controlCosts = strategies.map(s => {
      const c = s.controls || {};
      const nY = s.result ? s.result.A.length - 1 : 50;
      return 2.0 * (c.u_P || 0) * nY + 5.0 * (c.u_C || 0) * nY + 3.0 * (c.u_B || 0) * nY;
    });
    const runningCosts = strategies.map((s, i) => Math.max(0, s.J - controlCosts[i]));

    const traceRunning = {
      x: names,
      y: runningCosts,
      name: 'Running Cost (damage)',
      type: 'bar',
      marker: { color: this.palette.orange },
      hovertemplate: '<b>%{x}</b><br>Running cost: %{y:.2f}<extra></extra>'
    };

    const traceControl = {
      x: names,
      y: controlCosts,
      name: 'Control Cost',
      type: 'bar',
      marker: { color: this.palette.blue },
      hovertemplate: '<b>%{x}</b><br>Control cost: %{y:.2f}<extra></extra>'
    };

    const layout = Object.assign(this._baseLayout(), {
      title: { text: 'Management Strategy Cost Breakdown', font: { size: 14, weight: 700 } },
      barmode: 'group',
      yaxis: Object.assign(this._baseLayout().yaxis, {
        title: { text: 'Cost', font: { size: 12 } },
        rangemode: 'tozero'
      }),
      showlegend: true,
      legend: { x: 1, xanchor: 'right', y: 1, bgcolor: 'rgba(255,255,255,0.7)' }
    });

    Plotly.newPlot(el, [traceRunning, traceControl], layout, this._baseConfig());
    this.activePlots.add(divId);
    el.setAttribute('aria-label', 'Grouped bar chart comparing management strategy cost breakdown');
  },

  /**
   * Render control comparison bar chart (legacy alias).
   */
  createControlBarChart(divId, strategies, bestIdx) {
    this.createControlSummaryChart(divId, strategies, bestIdx);
  },

  /**
   * Render a stacked area chart showing temporal cost allocation per control type.
   *
   * @param {string} divId - Target div element id.
   * @param {Object} temporalData - { years, u_P, u_C, u_B, yearCost }
   */
  createTemporalAllocationChart(divId, temporalData) {
    this.destroy(divId);
    const el = document.getElementById(divId);
    if (!el) return;

    const traces = [
      {
        x: temporalData.years,
        y: temporalData.u_P,
        name: 'Parasitoid (u_P)',
        type: 'scatter',
        mode: 'lines',
        stackgroup: 'costs',
        line: { color: this.colors.parasitoids, width: 0.5 },
        fillcolor: this.colors.parasitoids + '80',
        hovertemplate: 'Year %{x}<br>u_P cost: %{y:.3f}<extra></extra>'
      },
      {
        x: temporalData.years,
        y: temporalData.u_C,
        name: 'Chemical (u_C)',
        type: 'scatter',
        mode: 'lines',
        stackgroup: 'costs',
        line: { color: this.colors.beetles, width: 0.5 },
        fillcolor: this.colors.beetles + '80',
        hovertemplate: 'Year %{x}<br>u_C cost: %{y:.3f}<extra></extra>'
      },
      {
        x: temporalData.years,
        y: temporalData.u_B,
        name: 'Bird habitat (u_B)',
        type: 'scatter',
        mode: 'lines',
        stackgroup: 'costs',
        line: { color: this.colors.capacity, width: 0.5 },
        fillcolor: this.colors.capacity + '80',
        hovertemplate: 'Year %{x}<br>u_B cost: %{y:.3f}<extra></extra>'
      }
    ];

    const layout = Object.assign(this._baseLayout(), {
      title: { text: 'Temporal Cost Allocation by Control Type', font: { size: 14, weight: 700 } },
      xaxis: Object.assign(this._baseLayout().xaxis, {
        title: { text: 'Year', font: { size: 12 } }
      }),
      yaxis: Object.assign(this._baseLayout().yaxis, {
        title: { text: 'Annual Control Cost', font: { size: 12 } },
        rangemode: 'tozero'
      }),
      showlegend: true,
      legend: { x: 1, xanchor: 'right', y: 1, bgcolor: 'rgba(255,255,255,0.7)' }
    });

    Plotly.newPlot(el, traces, layout, this._baseConfig());
    this.activePlots.add(divId);
    el.setAttribute('aria-label', 'Stacked area chart of temporal cost allocation across control types');
  },

  /**
   * Render a 2x2 subplot comparing A, F, K, D trajectories across strategies.
   * Uses domain-based positioning for vanilla Plotly.js (no make_subplots).
   *
   * @param {string} divId - Target div element id.
   * @param {Object[]} strategies - Array of strategy results with .result.{A,F,K,D}.
   */
  createTrajectoryComparison(divId, strategies) {
    this.destroy(divId);
    const el = document.getElementById(divId);
    if (!el) return;

    const paletteArr = [this.palette.blue, this.palette.orange, this.palette.green,
                        this.palette.purple, this.palette.vermillion, this.palette.skyBlue];

    // Define 2x2 subplot domains
    const subplots = [
      { xDomain: [0, 0.45], yDomain: [0.55, 1.0], key: 'A', label: 'Beetles (A)', xaxis: 'xaxis', yaxis: 'yaxis' },
      { xDomain: [0.55, 1.0], yDomain: [0.55, 1.0], key: 'F', label: 'Parasitoids (F)', xaxis: 'xaxis2', yaxis: 'yaxis2' },
      { xDomain: [0, 0.45], yDomain: [0, 0.4], key: 'K', label: 'Carrying Capacity (K)', xaxis: 'xaxis3', yaxis: 'yaxis3' },
      { xDomain: [0.55, 1.0], yDomain: [0, 0.4], key: 'D', label: 'Defoliation (D)', xaxis: 'xaxis4', yaxis: 'yaxis4' }
    ];

    const traces = [];
    const axisMap = ['', '2', '3', '4'];

    subplots.forEach((sp, spIdx) => {
      strategies.forEach((s, sIdx) => {
        if (!s.result || !s.result[sp.key]) return;
        const data = s.result[sp.key];
        const years = data.map((_, i) => i);
        const axSuffix = axisMap[spIdx];
        traces.push({
          x: years,
          y: data,
          type: 'scatter',
          mode: 'lines',
          name: s.name,
          legendgroup: s.name,
          showlegend: spIdx === 0,
          xaxis: 'x' + axSuffix,
          yaxis: 'y' + axSuffix,
          line: { color: paletteArr[sIdx % paletteArr.length], width: 2 },
          hovertemplate: '<b>' + s.name + '</b><br>Year %{x}<br>' + sp.key + ': %{y:.4f}<extra></extra>'
        });
      });
    });

    const baseLayout = this._baseLayout();
    const layout = Object.assign({}, baseLayout, {
      title: { text: 'Multi-Strategy Trajectory Comparison', font: { size: 14, weight: 700 } },
      showlegend: true,
      legend: { x: 0.5, xanchor: 'center', y: -0.05, orientation: 'h', bgcolor: 'rgba(255,255,255,0.7)' },
      margin: { l: 60, r: 20, t: 50, b: 80 }
    });

    // Configure axes for each subplot
    subplots.forEach((sp, idx) => {
      const axSuffix = idx === 0 ? '' : (idx + 1).toString();
      layout['xaxis' + axSuffix] = {
        domain: sp.xDomain,
        title: { text: 'Year', font: { size: 10 } },
        gridcolor: baseLayout.xaxis.gridcolor,
        zerolinecolor: baseLayout.xaxis.zerolinecolor,
        anchor: 'y' + axSuffix
      };
      layout['yaxis' + axSuffix] = {
        domain: sp.yDomain,
        title: { text: sp.label, font: { size: 10 } },
        gridcolor: baseLayout.yaxis.gridcolor,
        zerolinecolor: baseLayout.yaxis.zerolinecolor,
        rangemode: 'tozero',
        anchor: 'x' + axSuffix
      };
    });

    Plotly.newPlot(el, traces, layout, this._baseConfig());
    this.activePlots.add(divId);
    el.setAttribute('aria-label', '2x2 subplot comparing A, F, K, D trajectories across management strategies');
  },

  /**
   * Render PRCC horizontal bar chart.
   */
  createPRCCChart(divId, prccResults) {
    this.destroy(divId);
    const el = document.getElementById(divId);
    if (!el) return;

    // Sort by absolute PRCC value
    const sorted = prccResults.slice().sort((a, b) => Math.abs(a.prcc) - Math.abs(b.prcc));

    const colors = sorted.map(r => r.prcc >= 0 ? this.colors.beetles : this.colors.parasitoids);

    const trace = {
      y: sorted.map(r => r.paramName),
      x: sorted.map(r => r.prcc),
      type: 'bar',
      orientation: 'h',
      marker: {
        color: colors,
        line: { color: colors, width: 1 }
      },
      hovertemplate: '<b>%{y}</b><br>PRCC: %{x:.4f}<extra></extra>'
    };

    // Significance threshold lines
    const sigLine1 = {
      type: 'line', x0: 0.25, x1: 0.25, y0: -0.5, y1: sorted.length - 0.5,
      line: { color: 'rgba(0,0,0,0.3)', dash: 'dash', width: 1 }
    };
    const sigLine2 = {
      type: 'line', x0: -0.25, x1: -0.25, y0: -0.5, y1: sorted.length - 0.5,
      line: { color: 'rgba(0,0,0,0.3)', dash: 'dash', width: 1 }
    };

    const layout = Object.assign(this._baseLayout(), {
      title: { text: 'Partial Rank Correlation Coefficients with \u03c1*', font: { size: 14, weight: 700 } },
      xaxis: Object.assign(this._baseLayout().xaxis, {
        title: { text: 'PRCC', font: { size: 12 } },
        range: [-1, 1]
      }),
      yaxis: Object.assign(this._baseLayout().yaxis, {
        title: '',
        automargin: true
      }),
      shapes: [sigLine1, sigLine2],
      margin: { l: 80, r: 20, t: 50, b: 50 },
      showlegend: false
    });

    Plotly.newPlot(el, [trace], layout, this._baseConfig());
    this.activePlots.add(divId);
    el.setAttribute('aria-label', 'Horizontal bar chart of PRCC sensitivity analysis results');
  },

  /**
   * Render phase portrait (state variable X vs state variable Y).
   */
  createPhasePortrait(divId, xData, yData, xLabel, yLabel, title) {
    this.destroy(divId);
    const el = document.getElementById(divId);
    if (!el) return;

    const trace = {
      x: xData,
      y: yData,
      type: 'scatter',
      mode: 'lines+markers',
      name: title,
      line: { color: this.palette.blue, width: 2 },
      marker: { color: this.palette.blue, size: 4 },
      hovertemplate: xLabel + ': %{x:.4f}<br>' + yLabel + ': %{y:.4f}<extra></extra>'
    };

    // Start point marker
    const startTrace = {
      x: [xData[0]], y: [yData[0]],
      type: 'scatter', mode: 'markers',
      name: 'Start',
      marker: { color: this.palette.green, size: 12, symbol: 'star',
                line: { color: '#fff', width: 2 } },
      hovertemplate: 'Start<br>' + xLabel + ': %{x:.4f}<br>' + yLabel + ': %{y:.4f}<extra></extra>'
    };

    // End point marker
    const endTrace = {
      x: [xData[xData.length - 1]], y: [yData[yData.length - 1]],
      type: 'scatter', mode: 'markers',
      name: 'End',
      marker: { color: this.colors.beetles, size: 12, symbol: 'square',
                line: { color: '#fff', width: 2 } },
      hovertemplate: 'End<br>' + xLabel + ': %{x:.4f}<br>' + yLabel + ': %{y:.4f}<extra></extra>'
    };

    const layout = Object.assign(this._baseLayout(), {
      title: { text: title, font: { size: 14, weight: 700 } },
      xaxis: Object.assign(this._baseLayout().xaxis, {
        title: { text: xLabel, font: { size: 12 } }
      }),
      yaxis: Object.assign(this._baseLayout().yaxis, {
        title: { text: yLabel, font: { size: 12 } }
      }),
      showlegend: true,
      legend: { x: 1, xanchor: 'right', y: 1, bgcolor: 'rgba(255,255,255,0.7)' }
    });

    Plotly.newPlot(el, [trace, startTrace, endTrace], layout, this._baseConfig());
    this.activePlots.add(divId);
    el.setAttribute('aria-label', title + ' phase portrait');
  },

  /**
   * Render Pareto scatter (cost vs final defoliation).
   */
  createParetoScatter(divId, strategies) {
    this.destroy(divId);
    const el = document.getElementById(divId);
    if (!el) return;

    const paletteArr = [this.palette.blue, this.palette.orange, this.palette.green,
                        this.palette.purple, this.palette.vermillion];
    const traces = strategies.map((s, i) => ({
      x: [s.J],
      y: [s.finalD],
      type: 'scatter',
      mode: 'markers+text',
      name: s.name,
      text: [s.name],
      textposition: 'top center',
      textfont: { size: 10 },
      marker: {
        color: paletteArr[i % paletteArr.length],
        size: 16,
        symbol: 'circle',
        line: { color: '#fff', width: 2 }
      },
      hovertemplate: '<b>' + s.name + '</b><br>Cost J: %{x:.2f}<br>Final D: %{y:.4f}<extra></extra>'
    }));

    const layout = Object.assign(this._baseLayout(), {
      title: { text: 'Cost vs Final Defoliation (Pareto View)', font: { size: 14, weight: 700 } },
      xaxis: Object.assign(this._baseLayout().xaxis, {
        title: { text: 'Total Cost J', font: { size: 12 } }
      }),
      yaxis: Object.assign(this._baseLayout().yaxis, {
        title: { text: 'Final Defoliation D', font: { size: 12 } }
      }),
      showlegend: true,
      legend: { x: 1, xanchor: 'right', y: 1, bgcolor: 'rgba(255,255,255,0.7)' }
    });

    Plotly.newPlot(el, traces, layout, this._baseConfig());
    this.activePlots.add(divId);
    el.setAttribute('aria-label', 'Pareto scatter plot of cost versus final defoliation for different strategies');
  },

  /**
   * Render within-season dynamics as 4-panel subplots with peak annotations.
   * @param {Object} sol - {t: number[], y: number[][]}
   * @param {Object} params - model parameters for derived rates
   * @param {number} yearLabel - year index for titles
   */
  createWithinSeasonCharts(sol, params, yearLabel) {
    const times = sol.t;
    const S = sol.y.map(s => Math.max(s[0], 0));
    const I = sol.y.map(s => Math.max(s[1], 0));
    const F = sol.y.map(s => Math.max(s[2], 0));
    const D = sol.y.map(s => s[3]);

    // Derived rates for annotation positions
    const parasitismRate = S.map((s, i) => params.beta * s * F[i] / (1 + params.h * s));
    const defoliationRate = S.map((s, i) => params.kappa * (s + I[i]));

    let peakParIdx = 0, peakDefIdx = 0;
    for (let i = 1; i < parasitismRate.length; i++) {
      if (parasitismRate[i] > parasitismRate[peakParIdx]) peakParIdx = i;
      if (defoliationRate[i] > defoliationRate[peakDefIdx]) peakDefIdx = i;
    }

    const panels = [
      { divId: 'chart-ws-S', data: S, label: 'S', fullLabel: 'Susceptible larvae',
        color: this.colors.susceptible || this.palette.blue,
        annotation: { idx: peakParIdx, text: 'Peak parasitism', color: 'red', symbol: 'triangle-down' } },
      { divId: 'chart-ws-I', data: I, label: 'I', fullLabel: 'Parasitised larvae',
        color: this.colors.infected || this.palette.orange, annotation: null },
      { divId: 'chart-ws-F', data: F, label: 'F', fullLabel: 'Parasitoid flies',
        color: this.colors.flies || this.palette.green, annotation: null },
      { divId: 'chart-ws-D', data: D, label: 'D', fullLabel: 'Cumulative defoliation',
        color: this.colors.defol || this.palette.vermillion,
        annotation: { idx: peakDefIdx, text: 'Peak defol. rate', color: 'orange', symbol: 'triangle-up' } }
    ];

    panels.forEach(panel => {
      this.destroy(panel.divId);
      const el = document.getElementById(panel.divId);
      if (!el) return;

      const traces = [{
        x: times, y: panel.data, type: 'scatter', mode: 'lines',
        name: panel.fullLabel, line: { color: panel.color, width: 2 },
        hovertemplate: 'Day %{x:.1f}<br>' + panel.label + ': %{y:.4f}<extra></extra>'
      }];

      if (panel.annotation && panel.annotation.idx < times.length) {
        const ai = panel.annotation.idx;
        traces.push({
          x: [times[ai]], y: [panel.data[ai]], type: 'scatter', mode: 'markers+text',
          marker: { size: 10, color: panel.annotation.color, symbol: panel.annotation.symbol },
          text: [panel.annotation.text], textposition: 'top center',
          textfont: { size: 10 }, showlegend: false,
          hovertemplate: panel.annotation.text + '<br>Day %{x:.1f}<br>Value: %{y:.4f}<extra></extra>'
        });
      }

      const layout = Object.assign(this._baseLayout(), {
        title: { text: panel.fullLabel + ' (Year ' + yearLabel + ')', font: { size: 13, weight: 700 } },
        xaxis: Object.assign(this._baseLayout().xaxis, {
          title: { text: 'Day (\u03c4)', font: { size: 11 } }
        }),
        yaxis: Object.assign(this._baseLayout().yaxis, {
          title: { text: panel.label + ' density', font: { size: 11 } },
          rangemode: 'tozero'
        }),
        showlegend: false,
        margin: { t: 40, b: 40, l: 50, r: 20 }
      });

      Plotly.newPlot(el, traces, layout, this._baseConfig());
      this.activePlots.add(panel.divId);
    });
  },

  /**
   * Re-render all active plots when theme changes (updates colors).
   */
  refreshTheme() {
    this.activePlots.forEach(id => {
      const el = document.getElementById(id);
      if (el && el.data) {
        const layout = this._baseLayout();
        Plotly.relayout(el, {
          'paper_bgcolor': layout.paper_bgcolor,
          'plot_bgcolor': layout.plot_bgcolor,
          'font.color': layout.font.color,
          'xaxis.gridcolor': layout.xaxis.gridcolor,
          'yaxis.gridcolor': layout.yaxis.gridcolor,
          'xaxis.zerolinecolor': layout.xaxis.zerolinecolor,
          'yaxis.zerolinecolor': layout.yaxis.zerolinecolor
        });
      }
    });
  }
};
