# Module: Bifurcation Analysis
# 1-D bifurcation diagrams and 2-D R_P boundary contours

mod_bifurcation_ui <- function(id) {
  ns <- NS(id)
  tabItem(tabName = "bifurcation",
    fluidRow(
      box(width = 4, title = "1-D Bifurcation Sweep", status = "primary",
          solidHeader = TRUE,
        selectInput(ns("bif_param"), "Parameter to sweep",
                    choices = c("phi", "beta", "c_B", "R_B", "sigma_A",
                                "sigma_F", "T", "B_index", "delta", "eta",
                                "mu_S", "mu_F", "kappa", "h", "a_B", "K_0",
                                "mu_I"),
                    selected = "phi"),
        numericInput(ns("bif_lo"), "Range start", value = 0.01, step = 0.001),
        numericInput(ns("bif_hi"), "Range end", value = 0.15, step = 0.001),
        sliderInput(ns("bif_npts"), "Number of sweep points",
                    min = 10, max = 100, value = 40, step = 5),
        actionButton(ns("run_bif"), "Compute Bifurcation Diagram",
                     icon = icon("project-diagram"),
                     class = "btn-success btn-block"),
        helpText("Sweep a parameter across its range and compute all equilibria,",
                 "R_P, and dominant eigenvalue at each value.",
                 "Reproduces manuscript Figures 2-3.")
      ),
      box(width = 8, title = "D* vs Parameter", status = "success",
          solidHeader = TRUE,
        plotlyOutput(ns("bif_dstar_plot"), height = "420px"),
        helpText("Equilibrium defoliation D* coloured by class.",
                 "Circles = stable, crosses = unstable.")
      )
    ),
    fluidRow(
      box(width = 6, title = "R_P vs Parameter", status = "info",
          solidHeader = TRUE,
        plotlyOutput(ns("bif_rp_plot"), height = "380px"),
        helpText("R_P = 1 (dashed red) is the parasitoid invasion threshold.")
      ),
      box(width = 6, title = "|lambda| vs Parameter", status = "info",
          solidHeader = TRUE,
        plotlyOutput(ns("bif_rho_plot"), height = "380px"),
        helpText("|lambda| = 1 (dashed red) is the stability boundary.")
      )
    ),
    fluidRow(
      box(width = 4, title = "2-D R_P Boundary", status = "primary",
          solidHeader = TRUE,
        selectInput(ns("bif2_p1"), "Parameter 1 (x-axis)",
                    choices = c("beta", "c_B", "R_B", "phi", "sigma_F",
                                "T", "B_index", "delta"),
                    selected = "beta"),
        numericInput(ns("bif2_lo1"), "P1 range start", value = 0.005, step = 0.001),
        numericInput(ns("bif2_hi1"), "P1 range end", value = 0.04, step = 0.001),
        selectInput(ns("bif2_p2"), "Parameter 2 (y-axis)",
                    choices = c("c_B", "beta", "R_B", "phi", "sigma_F",
                                "T", "B_index", "delta"),
                    selected = "c_B"),
        numericInput(ns("bif2_lo2"), "P2 range start", value = 0.01, step = 0.001),
        numericInput(ns("bif2_hi2"), "P2 range end", value = 0.03, step = 0.001),
        sliderInput(ns("bif2_grid"), "Grid resolution per axis",
                    min = 10, max = 50, value = 25, step = 5),
        actionButton(ns("run_bif2d"), "Compute 2-D Boundary",
                     icon = icon("th"),
                     class = "btn-info btn-block"),
        helpText("Compute R_P over a 2-D parameter grid.",
                 "The R_P = 1 contour marks the transcritical",
                 "bifurcation boundary.")
      ),
      box(width = 8, title = "R_P Boundary Contour", status = "success",
          solidHeader = TRUE,
        plotlyOutput(ns("bif2d_plot"), height = "500px"),
        helpText("Green = R_P > 1 (coexistence possible).",
                 "Red = R_P < 1 (parasitoid cannot persist).",
                 "Black contour = R_P = 1.")
      )
    )
  )
}

mod_bifurcation_server <- function(id, rv) {
  moduleServer(id, function(input, output, session) {

    bif_result <- reactiveVal(NULL)
    bif2d_result <- reactiveVal(NULL)

    # Update range defaults when parameter selection changes
    observeEvent(input$bif_param, {
      reg <- param_registry()
      meta <- reg[[input$bif_param]]
      if (!is.null(meta)) {
        updateNumericInput(session, "bif_lo", value = meta$min)
        updateNumericInput(session, "bif_hi", value = meta$max)
      }
    })

    # 1-D bifurcation
    observeEvent(input$run_bif, {
      p <- as.list(rv$params)
      sweep <- seq(input$bif_lo, input$bif_hi, length.out = input$bif_npts)

      withProgress(message = "Computing bifurcation diagram...", value = 0, {
        result <- tryCatch(
          bifurcation_diagram(p, input$bif_param, sweep),
          error = function(e) {
            showNotification(paste("Bifurcation failed:", e$message),
                             type = "error")
            NULL
          }
        )
        incProgress(1)
      })

      if (!is.null(result)) bif_result(result)
    })

    # D* vs parameter plot
    output$bif_dstar_plot <- renderPlotly({
      bd <- bif_result()
      if (is.null(bd)) return(plotly_empty())

      pvals <- bd$param_values
      class_colors <- c(trivial = "#6c757d", canopy_only = "#17a2b8",
                        parasitoid_free = "#dc3545", coexistence = "#28a745")

      fig <- plot_ly()
      for (i in seq_along(pvals)) {
        fps <- bd$equilibria[[i]]
        if (is.null(fps) || nrow(fps) == 0) next
        for (r in seq_len(nrow(fps))) {
          cls <- fps$class[r]
          stab <- fps$stable[r]
          fig <- fig %>% add_trace(
            x = pvals[i], y = fps$D_star[r],
            type = "scatter", mode = "markers",
            marker = list(
              color = class_colors[cls],
              symbol = if (stab) "circle" else "x",
              size = 8
            ),
            name = paste0(cls, if (stab) " (stable)" else " (unstable)"),
            legendgroup = paste0(cls, stab),
            showlegend = (i == 1),
            hovertext = sprintf("A*=%.4f F*=%.4f K*=%.4f D*=%.4f rho*=%.4f",
                                fps$A_star[r], fps$F_star[r],
                                fps$K_star[r], fps$D_star[r],
                                fps$rho_star[r])
          )
        }
      }
      fig %>% layout(
        xaxis = list(title = input$bif_param),
        yaxis = list(title = "Equilibrium D*"),
        title = paste("Bifurcation: D* vs", input$bif_param)
      )
    })

    # R_P vs parameter plot
    output$bif_rp_plot <- renderPlotly({
      bd <- bif_result()
      if (is.null(bd)) return(plotly_empty())

      plot_ly(x = bd$param_values, y = bd$R_P,
              type = "scatter", mode = "lines+markers",
              marker = list(size = 5), name = "R_P") %>%
        layout(
          xaxis = list(title = input$bif_param),
          yaxis = list(title = "R_P"),
          title = paste("R_P vs", input$bif_param),
          shapes = list(list(
            type = "line", x0 = min(bd$param_values),
            x1 = max(bd$param_values), y0 = 1, y1 = 1,
            line = list(color = "red", dash = "dash", width = 2)
          ))
        )
    })

    # Dominant eigenvalue plot
    output$bif_rho_plot <- renderPlotly({
      bd <- bif_result()
      if (is.null(bd)) return(plotly_empty())

      class_colors <- c(trivial = "#6c757d", canopy_only = "#17a2b8",
                        parasitoid_free = "#dc3545", coexistence = "#28a745")
      fig <- plot_ly()
      for (i in seq_along(bd$param_values)) {
        fps <- bd$equilibria[[i]]
        if (is.null(fps) || nrow(fps) == 0) next
        for (r in seq_len(nrow(fps))) {
          cls <- fps$class[r]
          stab <- fps$stable[r]
          fig <- fig %>% add_trace(
            x = bd$param_values[i], y = fps$rho_star[r],
            type = "scatter", mode = "markers",
            marker = list(
              color = class_colors[cls],
              symbol = if (stab) "circle" else "x",
              size = 6
            ),
            name = paste0(cls, if (stab) " (stable)" else " (unstable)"),
            legendgroup = paste0(cls, stab),
            showlegend = (i == 1)
          )
        }
      }
      fig %>% layout(
        xaxis = list(title = input$bif_param),
        yaxis = list(title = "|lambda|"),
        title = paste("|lambda| vs", input$bif_param),
        shapes = list(list(
          type = "line", x0 = min(bd$param_values),
          x1 = max(bd$param_values), y0 = 1, y1 = 1,
          line = list(color = "red", dash = "dash", width = 2)
        ))
      )
    })

    # 2-D R_P boundary
    observeEvent(input$run_bif2d, {
      p <- as.list(rv$params)
      r1 <- seq(input$bif2_lo1, input$bif2_hi1, length.out = input$bif2_grid)
      r2 <- seq(input$bif2_lo2, input$bif2_hi2, length.out = input$bif2_grid)

      withProgress(message = "Computing 2-D R_P boundary...", value = 0, {
        result <- tryCatch(
          rp_boundary(p, input$bif2_p1, r1, input$bif2_p2, r2),
          error = function(e) {
            showNotification(paste("2-D boundary failed:", e$message),
                             type = "error")
            NULL
          }
        )
        incProgress(1)
      })

      if (!is.null(result)) bif2d_result(result)
    })

    output$bif2d_plot <- renderPlotly({
      bd <- bif2d_result()
      if (is.null(bd)) return(plotly_empty())

      plot_ly(
        x = bd$param1_values,
        y = bd$param2_values,
        z = t(bd$R_P_grid),
        type = "heatmap",
        colorscale = list(c(0, "red"), c(0.5, "yellow"), c(1, "green")),
        colorbar = list(title = "R_P"),
        zmin = 0, zmax = max(2, max(bd$R_P_grid, na.rm = TRUE))
      ) %>%
        add_contour(
          x = bd$param1_values,
          y = bd$param2_values,
          z = t(bd$R_P_grid),
          contours = list(start = 1, end = 1, size = 0.1,
                          coloring = "none"),
          line = list(color = "black", width = 3),
          showscale = FALSE, name = "R_P = 1"
        ) %>%
        layout(
          xaxis = list(title = input$bif2_p1),
          yaxis = list(title = input$bif2_p2),
          title = paste("R_P boundary:", input$bif2_p1, "vs", input$bif2_p2)
        )
    })
  })
}
