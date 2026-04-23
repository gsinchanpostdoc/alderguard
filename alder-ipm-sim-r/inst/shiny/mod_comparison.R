# Module: Scenario Comparison
# Side-by-side scenario comparison, 1-D and 2-D parameter sweeps

mod_comparison_ui <- function(id) {
  ns <- NS(id)
  tabItem(tabName = "comparison",
    fluidRow(
      box(width = 12, title = "Save Current Parameters as Scenario",
          status = "primary", solidHeader = TRUE,
        fluidRow(
          column(8, textInput(ns("sc_name"), "Scenario name:", value = "Scenario 1")),
          column(4, actionButton(ns("btn_save"), "Save Scenario",
                                  icon = icon("save"), class = "btn-success",
                                  style = "margin-top: 25px;"))
        ),
        uiOutput(ns("saved_list")),
        actionButton(ns("btn_clear"), "Clear All", icon = icon("trash"),
                     class = "btn-danger btn-sm", style = "margin-top:5px;")
      )
    ),
    fluidRow(
      box(width = 12, title = "Compare Scenarios Side-by-Side",
          status = "success", solidHeader = TRUE,
        uiOutput(ns("select_scenarios_ui")),
        fluidRow(
          column(4, sliderInput(ns("cmp_years"), "Simulation years:",
                                min = 10, max = 200, value = 50, step = 5)),
          column(4, numericInput(ns("cmp_A0"), "A0:", value = 0.8, min = 0, step = 0.1)),
          column(4, actionButton(ns("btn_compare"), "Run Comparison",
                                  icon = icon("play"), class = "btn-success",
                                  style = "margin-top: 25px;"))
        ),
        plotlyOutput(ns("cmp_ts_A"), height = "300px"),
        plotlyOutput(ns("cmp_ts_F"), height = "300px"),
        plotlyOutput(ns("cmp_ts_K"), height = "300px"),
        plotlyOutput(ns("cmp_ts_D"), height = "300px"),
        DTOutput(ns("cmp_table")),
        plotlyOutput(ns("cmp_radar"), height = "450px")
      )
    ),
    fluidRow(
      box(width = 6, title = "1-D Parameter Sweep", status = "info",
          solidHeader = TRUE,
        selectInput(ns("sw1_param"), "Parameter to sweep:",
                    choices = names(default_params())),
        fluidRow(
          column(6, numericInput(ns("sw1_lo"), "Min value:", value = 0.01)),
          column(6, numericInput(ns("sw1_hi"), "Max value:", value = 0.1))
        ),
        sliderInput(ns("sw1_n"), "Resolution:", min = 10, max = 60, value = 25),
        actionButton(ns("btn_sw1"), "Run Sweep", icon = icon("play"),
                     class = "btn-info"),
        plotlyOutput(ns("sw1_plot"), height = "500px")
      ),
      box(width = 6, title = "2-D Parameter Sweep", status = "warning",
          solidHeader = TRUE,
        fluidRow(
          column(6, selectInput(ns("sw2_p1"), "Parameter 1:",
                                choices = names(default_params()))),
          column(6, selectInput(ns("sw2_p2"), "Parameter 2:",
                                choices = names(default_params()), selected = "phi"))
        ),
        fluidRow(
          column(3, numericInput(ns("sw2_lo1"), "P1 min:", value = 0.01)),
          column(3, numericInput(ns("sw2_hi1"), "P1 max:", value = 0.1)),
          column(3, numericInput(ns("sw2_lo2"), "P2 min:", value = 0.01)),
          column(3, numericInput(ns("sw2_hi2"), "P2 max:", value = 0.1))
        ),
        sliderInput(ns("sw2_n"), "Grid resolution:", min = 5, max = 25, value = 12),
        actionButton(ns("btn_sw2"), "Run 2-D Sweep", icon = icon("play"),
                     class = "btn-warning"),
        plotlyOutput(ns("sw2_heatmap"), height = "500px")
      )
    )
  )
}

mod_comparison_server <- function(id, rv) {
  moduleServer(id, function(input, output, session) {

    scenarios <- reactiveValues(saved = list())
    colors <- c("#E69F00", "#56B4E9", "#009E73", "#CC79A7")
    dashes <- c("solid", "dash", "dot", "dashdot")

    # Save scenario
    observeEvent(input$btn_save, {
      name <- trimws(input$sc_name)
      if (nchar(name) == 0) name <- paste0("Scenario_", length(scenarios$saved) + 1)
      scenarios$saved[[name]] <- as.list(rv$params)
      showNotification(paste("Saved:", name), type = "message")
    })

    # Clear all
    observeEvent(input$btn_clear, {
      scenarios$saved <- list()
      showNotification("All scenarios cleared", type = "warning")
    })

    # Display saved scenarios
    output$saved_list <- renderUI({
      nms <- names(scenarios$saved)
      if (length(nms) == 0) return(tags$em("No scenarios saved yet."))
      tags$p(tags$strong("Saved: "), paste(nms, collapse = ", "))
    })

    # Dynamic scenario selector
    output$select_scenarios_ui <- renderUI({
      ns <- session$ns
      nms <- names(scenarios$saved)
      if (length(nms) < 2) return(helpText("Save at least 2 scenarios to compare."))
      checkboxGroupInput(ns("cmp_select"), "Select scenarios (up to 4):",
                         choices = nms, selected = head(nms, 4), inline = TRUE)
    })

    # Run comparison
    observeEvent(input$btn_compare, {
      req(input$cmp_select)
      sel <- head(input$cmp_select, 4)
      n_years <- input$cmp_years
      A0 <- input$cmp_A0

      results <- list()
      for (nm in sel) {
        p <- scenarios$saved[[nm]]
        sim <- tryCatch(
          simulate(p, A0 = A0, F0 = 0.1, K0 = p[["K_0"]], D0 = 0, n_years = n_years),
          error = function(e) NULL
        )
        rp <- tryCatch(compute_RP(p), error = function(e) NA)
        r1 <- tryCatch(compute_R1(p, sim$A[nrow(sim)], sim$F[nrow(sim)],
                                   sim$K[nrow(sim)], sim$D[nrow(sim)]),
                        error = function(e) NA)
        r2 <- tryCatch(compute_R2(p, sim$A[nrow(sim)], sim$F[nrow(sim)],
                                   sim$K[nrow(sim)], sim$D[nrow(sim)]),
                        error = function(e) NA)
        fps <- tryCatch(find_fixed_points(p), error = function(e) list())
        eq_class <- "unknown"
        rho <- NA
        if (length(fps) > 0) {
          stable_fps <- Filter(function(fp) fp$stable, fps)
          best <- if (length(stable_fps) > 0) stable_fps[[1]] else fps[[1]]
          eq_class <- best$equilibrium_class
          rho <- best$dominant_eigenvalue
        }
        results[[nm]] <- list(
          sim = sim, R_P = rp, R1 = r1, R2 = r2,
          eq_class = eq_class, rho = rho,
          D_star = sim$D[nrow(sim)], K_star = sim$K[nrow(sim)]
        )
      }

      # Time series plots
      for (var in c("A", "F", "K", "D")) {
        local({
          v <- var
          plot_id <- paste0("cmp_ts_", v)
          output[[plot_id]] <- renderPlotly({
            fig <- plotly::plot_ly(type = "scatter", mode = "lines")
            for (i in seq_along(sel)) {
              nm <- sel[i]
              sim <- results[[nm]]$sim
              fig <- plotly::add_trace(fig, x = sim$year, y = sim[[v]],
                                       name = nm,
                                       line = list(color = colors[i],
                                                   dash = dashes[i], width = 2))
            }
            labels <- c(A = "Beetle Density A", F = "Parasitoid Density F",
                        K = "Carrying Capacity K", D = "Defoliation D")
            fig <- plotly::layout(fig, title = labels[v],
                                  xaxis = list(title = "Year"),
                                  yaxis = list(title = labels[v]),
                                  legend = list(orientation = "h"))
            fig
          })
        })
      }

      # Comparison table
      output$cmp_table <- DT::renderDT({
        df <- data.frame(
          Scenario = sel,
          Equilibrium = sapply(sel, function(n) gsub("_", " ", results[[n]]$eq_class)),
          rho = sapply(sel, function(n) round(results[[n]]$rho, 4)),
          R_P = sapply(sel, function(n) round(results[[n]]$R_P, 4)),
          R1 = sapply(sel, function(n) round(results[[n]]$R1, 4)),
          R2 = sapply(sel, function(n) round(results[[n]]$R2, 4)),
          D_star = sapply(sel, function(n) round(results[[n]]$D_star, 4)),
          K_star = sapply(sel, function(n) round(results[[n]]$K_star, 4)),
          stringsAsFactors = FALSE
        )
        DT::datatable(df, options = list(dom = "t", pageLength = 4), rownames = FALSE)
      })

      # Radar chart
      output$cmp_radar <- renderPlotly({
        fig <- plotly::plot_ly(type = "scatterpolar", fill = "toself")
        cats <- c("R_P", "R1", "R2", "K*", "1-D*")
        for (i in seq_along(sel)) {
          nm <- sel[i]
          r <- results[[nm]]
          vals <- c(min(r$R_P, 3, na.rm = TRUE),
                    max(ifelse(is.na(r$R1), 0, r$R1), 0),
                    max(ifelse(is.na(r$R2), 0, r$R2), 0),
                    min(r$K_star, 3),
                    max(1 - r$D_star, 0))
          fig <- plotly::add_trace(fig, r = c(vals, vals[1]),
                                    theta = c(cats, cats[1]),
                                    name = nm,
                                    line = list(color = colors[i]),
                                    opacity = 0.6)
        }
        fig <- plotly::layout(fig,
          polar = list(radialaxis = list(visible = TRUE, range = c(0, 3))),
          title = "Scenario Comparison Radar"
        )
        fig
      })
    })

    # -- 1-D Sweep --
    observeEvent(input$btn_sw1, {
      p_name <- input$sw1_param
      vals <- seq(input$sw1_lo, input$sw1_hi, length.out = input$sw1_n)
      base <- as.list(rv$params)

      D_arr <- numeric(length(vals))
      K_arr <- numeric(length(vals))
      RP_arr <- numeric(length(vals))

      withProgress(message = paste("Sweeping", p_name, "..."), {
        for (i in seq_along(vals)) {
          incProgress(1 / length(vals))
          p <- base
          p[[p_name]] <- vals[i]
          sim <- tryCatch(
            simulate(p, A0 = 0.8, F0 = 0.1, K0 = p[["K_0"]], D0 = 0, n_years = 50),
            error = function(e) NULL
          )
          if (!is.null(sim)) {
            D_arr[i] <- sim$D[nrow(sim)]
            K_arr[i] <- sim$K[nrow(sim)]
          } else {
            D_arr[i] <- NA
            K_arr[i] <- NA
          }
          RP_arr[i] <- tryCatch(compute_RP(p), error = function(e) NA)
        }
      })

      output$sw1_plot <- renderPlotly({
        fig <- plotly::subplot(
          plotly::plot_ly(x = vals, y = D_arr, type = "scatter", mode = "lines+markers",
                          name = "D*", line = list(color = "#CC79A7")) %>%
            plotly::layout(yaxis = list(title = "D*")),
          plotly::plot_ly(x = vals, y = K_arr, type = "scatter", mode = "lines+markers",
                          name = "K*", line = list(color = "#009E73")) %>%
            plotly::layout(yaxis = list(title = "K*")),
          plotly::plot_ly(x = vals, y = RP_arr, type = "scatter", mode = "lines+markers",
                          name = "R_P", line = list(color = "#E69F00")) %>%
            plotly::layout(yaxis = list(title = "R_P"),
                           shapes = list(list(type = "line", x0 = min(vals), x1 = max(vals),
                                              y0 = 1, y1 = 1, line = list(dash = "dash", color = "red")))),
          nrows = 3, shareX = TRUE, titleY = TRUE
        ) %>% plotly::layout(title = paste("1-D Sweep:", p_name),
                              xaxis3 = list(title = p_name))
        fig
      })
    })

    # -- 2-D Sweep --
    observeEvent(input$btn_sw2, {
      p1 <- input$sw2_p1
      p2 <- input$sw2_p2
      v1 <- seq(input$sw2_lo1, input$sw2_hi1, length.out = input$sw2_n)
      v2 <- seq(input$sw2_lo2, input$sw2_hi2, length.out = input$sw2_n)
      base <- as.list(rv$params)

      D_grid <- matrix(NA, nrow = length(v1), ncol = length(v2))

      withProgress(message = paste("2-D sweep:", p1, "x", p2, "..."), {
        total <- length(v1) * length(v2)
        k <- 0
        for (i in seq_along(v1)) {
          for (j in seq_along(v2)) {
            k <- k + 1
            incProgress(1 / total)
            p <- base
            p[[p1]] <- v1[i]
            p[[p2]] <- v2[j]
            sim <- tryCatch(
              simulate(p, A0 = 0.8, F0 = 0.1, K0 = p[["K_0"]], D0 = 0, n_years = 50),
              error = function(e) NULL
            )
            if (!is.null(sim)) {
              D_grid[i, j] <- sim$D[nrow(sim)]
            }
          }
        }
      })

      output$sw2_heatmap <- renderPlotly({
        plotly::plot_ly(x = v1, y = v2, z = t(D_grid), type = "heatmap",
                        colorscale = "Viridis",
                        colorbar = list(title = "D*")) %>%
          plotly::add_trace(x = c(base[[p1]]), y = c(base[[p2]]),
                            type = "scatter", mode = "markers",
                            marker = list(size = 14, color = "white",
                                          symbol = "star",
                                          line = list(width = 2, color = "black")),
                            name = "Current", inherit = FALSE) %>%
          plotly::layout(title = paste("D*:", p1, "vs", p2),
                         xaxis = list(title = p1),
                         yaxis = list(title = p2))
      })
    })

  })
}
