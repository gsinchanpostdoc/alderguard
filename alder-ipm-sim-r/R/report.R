#' @title HTML Report Generation
#' @description Generate a standalone HTML report summarising AlderIPM-Sim analysis.

#' Generate an HTML report from analysis results.
#'
#' Collects parameter settings, simulation output, equilibrium analysis,
#' early warning signals, and management recommendations into a single
#' self-contained HTML file for forest managers.
#'
#' @param params Named list of model parameters (from \code{\link{default_params}}).
#' @param sim_result Output from \code{\link{simulate}} (list with A, F, K, D vectors), or NULL.
#' @param fixed_points Output from \code{\link{find_fixed_points}}, or NULL.
#' @param R_P Numeric parasitoid reproduction number, or NULL.
#' @param R1 Numeric resistance metric, or NULL.
#' @param R2 Numeric resilience metric, or NULL.
#' @param ews_result Output from \code{\link{detect_warnings}}, or NULL.
#' @param control_results Output from \code{\link{compare_strategies}}, or NULL.
#' @param scenario_name Character label for the scenario (default "Custom").
#' @param output_file Character path for the output HTML file, or NULL to return
#'   the HTML string.
#' @return If \code{output_file} is NULL, returns the HTML string invisibly.
#'   Otherwise writes to the file and returns the path invisibly.
#' @examples
#' p <- default_params()
#' sim <- simulate(p, A0 = 0.8, F0 = 0.1, K0 = 1.712, D0 = 0, n_years = 20)
#' html <- generate_report(p, sim_result = sim)
#' @export
generate_report <- function(params,
                            sim_result = NULL,
                            fixed_points = NULL,
                            R_P = NULL,
                            R1 = NULL,
                            R2 = NULL,
                            ews_result = NULL,
                            control_results = NULL,
                            scenario_name = "Custom",
                            output_file = NULL) {
  esc <- function(x) {
    x <- gsub("&", "&amp;", as.character(x), fixed = TRUE)
    x <- gsub("<", "&lt;", x, fixed = TRUE)
    x <- gsub(">", "&gt;", x, fixed = TRUE)
    x <- gsub('"', "&quot;", x, fixed = TRUE)
    x
  }

  today <- Sys.Date()
  reg <- param_registry()
  defaults <- default_params()

  # Section 1: Parameters
  param_rows <- ""
  for (nm in sort(names(params))) {
    meta <- NULL
    for (r in reg) { if (r$name == nm) { meta <- r; break } }
    if (is.null(meta)) next
    val <- params[[nm]]
    def_val <- defaults[[nm]]
    changed <- !is.null(def_val) && abs(val - def_val) > 1e-12
    cls <- if (changed) ' class="changed"' else ""
    desc <- if (nchar(meta$description) > 80) paste0(substr(meta$description, 1, 77), "...") else meta$description
    param_rows <- paste0(param_rows,
      sprintf("<tr%s><td>%s</td><td>%s</td><td>%.6g</td><td>[%s, %s]</td><td>%s</td><td>%s</td></tr>\n",
              cls, esc(meta$symbol), esc(nm), val,
              meta$min_val, meta$max_val, esc(meta$unit), esc(desc)))
  }
  sec_params <- paste0(
    "<h2>1. Parameter Summary</h2>",
    "<table><thead><tr><th>Symbol</th><th>Name</th><th>Value</th><th>Range</th><th>Unit</th><th>Description</th></tr></thead><tbody>",
    param_rows, "</tbody></table>",
    '<p class="note">Rows highlighted indicate values changed from defaults.</p>')

  # Section 2: Simulation
  sec_sim <- "<h2>2. Simulation Trajectories</h2>"
  if (!is.null(sim_result)) {
    n <- length(sim_result$A)
    years <- seq_len(n) - 1
    labels <- list(
      list(key = "A", label = "Beetle Larvae (A)", color = "#E69F00"),
      list(key = "F", label = "Parasitoid Flies (F)", color = "#56B4E9"),
      list(key = "K", label = "Canopy Capacity (K)", color = "#009E73"),
      list(key = "D", label = "Cumulative Defoliation (D)", color = "#D55E00")
    )
    sec_sim <- paste0(sec_sim, '<div class="chart-grid">')
    for (info in labels) {
      sec_sim <- paste0(sec_sim, .svg_timeseries(years, sim_result[[info$key]], info$label, info$color))
    }
    sec_sim <- paste0(sec_sim, "</div>")
    sec_sim <- paste0(sec_sim, sprintf("<h3>End State (Year %d)</h3>", n - 1))
    sec_sim <- paste0(sec_sim, "<table><thead><tr><th>Variable</th><th>Value</th></tr></thead><tbody>")
    for (key in c("A", "F", "K", "D")) {
      sec_sim <- paste0(sec_sim, sprintf("<tr><td>%s</td><td>%.6f</td></tr>", key, sim_result[[key]][n]))
    }
    sec_sim <- paste0(sec_sim, "</tbody></table>")
  } else {
    sec_sim <- paste0(sec_sim, "<p>No simulation data available.</p>")
  }

  # Section 3: Equilibrium
  sec_eq <- "<h2>3. Equilibrium Analysis</h2>"
  if (!is.null(R_P)) {
    status <- if (R_P > 1) "Coexistence possible" else "Parasitoid cannot persist"
    col <- if (R_P > 1) "#009E73" else "#D55E00"
    sec_eq <- paste0(sec_eq, sprintf(
      '<p><strong>R<sub>P</sub> = %.6f</strong> &mdash; <span style="color:%s">%s</span></p>',
      R_P, col, status))
  }
  if (!is.null(R1) || !is.null(R2)) {
    sec_eq <- paste0(sec_eq, "<h3>Resistance &amp; Resilience</h3><ul>")
    if (!is.null(R1)) sec_eq <- paste0(sec_eq, sprintf("<li><strong>R1 (Resistance):</strong> %.4f</li>", R1))
    if (!is.null(R2)) sec_eq <- paste0(sec_eq, sprintf("<li><strong>R2 (Resilience):</strong> %.4f</li>", R2))
    sec_eq <- paste0(sec_eq, "</ul>")
  }
  if (!is.null(fixed_points) && length(fixed_points) > 0) {
    sec_eq <- paste0(sec_eq,
      "<table><thead><tr><th>Class</th><th>Stable</th><th>A*</th><th>F*</th><th>K*</th><th>D*</th>",
      "<th>|&lambda;<sub>dom</sub>|</th><th>Bifurcation</th></tr></thead><tbody>")
    for (fp in fixed_points) {
      cls <- if (isTRUE(fp$stable)) "stable" else "unstable"
      sec_eq <- paste0(sec_eq, sprintf(
        '<tr class="%s"><td>%s</td><td>%s</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%s</td></tr>',
        cls, esc(fp$class), if (isTRUE(fp$stable)) "Yes" else "No",
        fp$A, fp$F, fp$K, fp$D,
        if (!is.null(fp$dominant_eigenvalue)) fp$dominant_eigenvalue else 0,
        esc(if (!is.null(fp$bifurcation_type)) fp$bifurcation_type else "")))
    }
    sec_eq <- paste0(sec_eq, "</tbody></table>")
  } else {
    sec_eq <- paste0(sec_eq, "<p>No fixed points computed.</p>")
  }

  # Section 4: EWS
  sec_ews <- "<h2>4. Early Warning Signals</h2>"
  if (!is.null(ews_result)) {
    alert_colors <- c(green = "#009E73", yellow = "#E69F00", red = "#D55E00")
    al <- ews_result$alert_level
    col <- if (al %in% names(alert_colors)) alert_colors[[al]] else "#999"
    sec_ews <- paste0(sec_ews, sprintf(
      '<div class="alert-box" style="border-left:4px solid %s; padding:12px; margin:12px 0;"><strong>Alert Level: <span style="color:%s">%s</span></strong></div>',
      col, col, toupper(al)))
    if (!is.null(ews_result$interpretation) && nchar(ews_result$interpretation) > 0) {
      sec_ews <- paste0(sec_ews, sprintf("<p><em>%s</em></p>", esc(ews_result$interpretation)))
    }
    if (!is.null(ews_result$kendall_results)) {
      sec_ews <- paste0(sec_ews, "<table><thead><tr><th>Indicator</th><th>Kendall &tau;</th><th>p-value</th><th>Trend</th></tr></thead><tbody>")
      for (nm in names(ews_result$kendall_results)) {
        res <- ews_result$kendall_results[[nm]]
        tau <- res$tau
        pval <- res$p_value
        sig <- if (pval < 0.05 && tau > 0) "Significant" else "Not significant"
        sec_ews <- paste0(sec_ews, sprintf(
          "<tr><td>%s</td><td>%+.4f</td><td>%.4f</td><td>%s</td></tr>",
          esc(nm), tau, pval, sig))
      }
      sec_ews <- paste0(sec_ews, "</tbody></table>")
    }
  } else {
    sec_ews <- paste0(sec_ews, "<p>No EWS data available.</p>")
  }

  # Section 5: Management
  sec_mgmt <- "<h2>5. Management Recommendation</h2>"
  if (!is.null(control_results) && length(control_results) > 0) {
    # Find best feasible
    feasible <- Filter(function(r) isTRUE(r$feasible), control_results)
    if (length(feasible) > 0) {
      costs <- sapply(feasible, function(r) r$cost)
      best <- feasible[[which.min(costs)]]
      sec_mgmt <- paste0(sec_mgmt, sprintf(
        '<div class="recommendation"><strong>Recommended:</strong> Scenario %s (cost J = %.4f)</div>',
        esc(best$scenario), best$cost))
    }
    sec_mgmt <- paste0(sec_mgmt,
      "<table><thead><tr><th>Scenario</th><th>Cost (J)</th><th>D*</th><th>K*</th><th>&rho;*</th>",
      "<th>u<sub>P</sub></th><th>u<sub>C</sub></th><th>u<sub>B</sub></th><th>Feasible</th></tr></thead><tbody>")
    for (r in control_results) {
      cls <- if (isTRUE(r$feasible)) "stable" else "unstable"
      uc <- r$optimal_controls
      sec_mgmt <- paste0(sec_mgmt, sprintf(
        '<tr class="%s"><td>%s</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%s</td></tr>',
        cls, esc(r$scenario), r$cost, r$D_star, r$K_star, r$rho_star,
        if (!is.null(uc[["u_P"]])) uc[["u_P"]] else 0,
        if (!is.null(uc[["u_C"]])) uc[["u_C"]] else 0,
        if (!is.null(uc[["u_B"]])) uc[["u_B"]] else 0,
        if (isTRUE(r$feasible)) "Yes" else "No"))
    }
    sec_mgmt <- paste0(sec_mgmt, "</tbody></table>")
  } else {
    sec_mgmt <- paste0(sec_mgmt, "<p>No control analysis available.</p>")
  }

  # Section 6: Technical appendix
  appendix_rows <- ""
  for (r in reg) {
    appendix_rows <- paste0(appendix_rows, sprintf(
      "<tr><td>%s</td><td>%s</td><td>[%s, %s]</td><td>%s</td><td>%s</td></tr>\n",
      esc(r$symbol), esc(r$name), r$min_val, r$max_val, esc(r$unit), esc(r$description)))
  }
  sec_appendix <- paste0(
    "<h2>6. Technical Appendix</h2>",
    "<h3>Model Equations</h3>",
    "<p><strong>Within-season ODE system (Eqs. 1&ndash;4):</strong></p>",
    "<pre>",
    "dS/dt = -(&beta; S F)/(1 + h S) - (c_B B S)/(1 + a_B S) - &mu;_S S\n",
    "dI/dt =  (&beta; S F)/(1 + h S) - &mu;_I I\n",
    "dF/dt =  &delta; &eta; I(t - &tau;) - &mu;_F F\n",
    "dD/dt =  &kappa; S\n",
    "</pre>",
    "<p><strong>Annual map (Eqs. 5&ndash;8):</strong></p>",
    "<pre>",
    "A(t+1)  = R_B A(t) &sigma;_A exp(-A(t)/K(t))\n",
    "F(t+1)  = &sigma;_F (F_end(t) + u_P)\n",
    "K(t+1)  = K_0 (1 - &phi; D(t))\n",
    "&rho;(t) = spectral radius of the annual-map Jacobian\n",
    "</pre>",
    "<h3>Full Parameter Reference</h3>",
    "<table><thead><tr><th>Symbol</th><th>Name</th><th>Range</th><th>Unit</th><th>Description</th></tr></thead><tbody>",
    appendix_rows, "</tbody></table>")

  body <- paste0(sec_params, sec_sim, sec_eq, sec_ews, sec_mgmt, sec_appendix)

  html <- sprintf(.REPORT_TEMPLATE, esc(as.character(today)), esc(scenario_name), body)

  if (!is.null(output_file)) {
    writeLines(html, output_file, useBytes = TRUE)
    message("Report written to ", output_file)
    invisible(output_file)
  } else {
    invisible(html)
  }
}


# Internal: SVG sparkline chart for report
.svg_timeseries <- function(x, y, title, color, width = 400, height = 150) {
  esc <- function(s) gsub('"', "&quot;", gsub(">", "&gt;", gsub("<", "&lt;", gsub("&", "&amp;", as.character(s), fixed = TRUE), fixed = TRUE), fixed = TRUE), fixed = TRUE)
  if (length(y) == 0) {
    return(sprintf('<div class="chart-cell"><h4>%s</h4><p>No data</p></div>', esc(title)))
  }
  pad <- 40
  plot_w <- width - 2 * pad
  plot_h <- height - 2 * pad
  y_min <- min(y, na.rm = TRUE)
  y_max <- max(y, na.rm = TRUE)
  y_range <- if (y_max > y_min) (y_max - y_min) else 1
  x_max <- max(x, na.rm = TRUE)
  if (x_max == 0) x_max <- 1

  pts <- vapply(seq_along(x), function(i) {
    px <- pad + (x[i] / x_max) * plot_w
    py <- pad + plot_h - ((y[i] - y_min) / y_range) * plot_h
    sprintf("%.1f,%.1f", px, py)
  }, character(1))

  polyline <- paste(pts, collapse = " ")

  sprintf(paste0(
    '<div class="chart-cell"><h4>%s</h4>',
    '<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg"',
    ' style="width:100%%; max-width:%dpx; background:#fafafa; border:1px solid #ddd;">',
    '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#999" stroke-width="1"/>',
    '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#999" stroke-width="1"/>',
    '<text x="%d" y="%d" text-anchor="end" font-size="9" fill="#666">%.3g</text>',
    '<text x="%d" y="%d" text-anchor="end" font-size="9" fill="#666">%.3g</text>',
    '<text x="%d" y="%d" text-anchor="start" font-size="9" fill="#666">0</text>',
    '<text x="%d" y="%d" text-anchor="end" font-size="9" fill="#666">%d</text>',
    '<polyline points="%s" fill="none" stroke="%s" stroke-width="2"/>',
    '</svg></div>'),
    esc(title), width, height, width,
    pad, pad, pad, pad + plot_h,
    pad, pad + plot_h, pad + plot_w, pad + plot_h,
    pad - 4, pad + 4, y_max,
    pad - 4, pad + plot_h, y_min,
    pad, pad + plot_h + 14,
    pad + plot_w, pad + plot_h + 14, as.integer(x_max),
    polyline, color)
}

# HTML template
.REPORT_TEMPLATE <- '<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>AlderIPM-Sim Analysis Report</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    max-width: 960px; margin: 0 auto; padding: 20px;
    color: #1a1a1a; line-height: 1.6; font-size: 14px;
  }
  h1 { color: #2d6a4f; border-bottom: 3px solid #2d6a4f; padding-bottom: 8px; }
  h2 { color: #40916c; margin-top: 2em; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
  h3 { color: #52b788; }
  .header-meta { color: #666; margin-bottom: 1em; }
  table {
    border-collapse: collapse; width: 100%%; margin: 12px 0; font-size: 13px;
  }
  th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; }
  thead { background: #2d6a4f; color: #fff; }
  tr:nth-child(even) { background: #f8f8f8; }
  tr.changed { background: #fff3cd; }
  tr.stable td:first-child { border-left: 4px solid #009E73; }
  tr.unstable td:first-child { border-left: 4px solid #D55E00; }
  .chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 12px 0; }
  .chart-cell { padding: 8px; }
  .chart-cell h4 { margin: 0 0 4px; font-size: 13px; color: #444; }
  .recommendation {
    background: #d4edda; border: 1px solid #c3e6cb; padding: 12px; border-radius: 4px; margin: 12px 0;
  }
  .alert-box { background: #f8f9fa; border-radius: 4px; }
  .note { font-size: 12px; color: #888; font-style: italic; }
  pre { background: #f4f4f4; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 13px; }
  @media print {
    body { font-size: 11pt; }
    h1 { font-size: 18pt; }
    table { font-size: 9pt; }
    .chart-grid { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<h1>AlderIPM-Sim Analysis Report</h1>
<div class="header-meta">
  <strong>Date:</strong> %s &nbsp;|&nbsp;
  <strong>Scenario:</strong> %s
</div>
%s
<hr/>
<p class="note">Generated by AlderIPM-Sim &mdash; Decision-support toolkit for the
Alnus-beetle-parasitoid-bird ecoepidemic system.</p>
</body>
</html>'
