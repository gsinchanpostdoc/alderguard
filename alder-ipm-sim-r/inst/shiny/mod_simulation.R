# Module: Simulation & Forecast
# Time series, phase portraits, within-season dynamics, equilibrium analysis with R1/R2

mod_simulation_ui <- function(id) {
  ns <- NS(id)
  tabItem(tabName = "simulation",
    fluidRow(
      box(width = 4, title = "Initial Conditions", status = "primary", solidHeader = TRUE,
        numericInput(ns("sim_A0"), "A0 (beetle density)", value = 0.8, min = 0, step = 0.1),
        numericInput(ns("sim_F0"), "F0 (parasitoid density)", value = 0.1, min = 0, step = 0.05),
        numericInput(ns("sim_K0"), "K0 (carrying capacity)", value = 1.712, min = 0.1, step = 0.1),
        numericInput(ns("sim_D0"), "D0 (defoliation)", value = 0, min = 0, step = 0.1),
        sliderInput(ns("sim_years"), "Simulation years", min = 5, max = 200, value = 50, step = 5),
        actionButton(ns("run_sim"), "Run Simulation", icon = icon("play"),
                     class = "btn-success btn-block"),
        helpText("Set initial conditions and run a multi-year simulation of the annual map.",
                 "The phase portrait shows trajectories in the A-F state space.")
      ),
      box(width = 8, title = "Time Series", status = "success", solidHeader = TRUE,
        plotlyOutput(ns("sim_plot"), height = "500px")
      )
    ),
    fluidRow(
      box(width = 6, title = "Phase Portrait (A vs F)", status = "info", solidHeader = TRUE,
        plotlyOutput(ns("phase_plot"), height = "400px"),
        helpText("Trajectory of beetle (A) vs parasitoid (F) densities.",
                 "Filled circle = start, star = end state.")
      ),
      box(width = 6, title = "Within-Season Dynamics", status = "info",
          solidHeader = TRUE,
        fluidRow(
          column(8,
            sliderInput(ns("ws_year"), "Select year:", min = 0, max = 49, value = 0, step = 1)
          ),
          column(4,
            actionButton(ns("ws_view"), "View Season", icon = icon("eye"),
                         class = "btn-info", style = "margin-top:25px;")
          )
        ),
        plotlyOutput(ns("within_season_plot"), height = "400px"),
        helpText("Select a year to view intra-seasonal dynamics (S, I, F, D).",
                 "Annotations show peak parasitism and peak defoliation rate events.")
      )
    ),
    fluidRow(
      box(width = 6, title = "Equilibrium Analysis (with R1 & R2)", status = "warning",
          solidHeader = TRUE,
        DTOutput(ns("eq_table")),
        helpText("R1 = resistance (how little the system deviates after perturbation).",
                 "R2 = resilience (how quickly it recovers).",
                 "rho* < 1 indicates local stability.")
      ),
      box(width = 6, title = "Regime Forecast", status = "warning", solidHeader = TRUE,
        uiOutput(ns("sim_regime_alert"))
      )
    )
  )
}

mod_simulation_server <- function(id, rv) {
  moduleServer(id, function(input, output, session) {

    observeEvent(input$run_sim, {
      p <- as.list(rv$params)
      withProgress(message = "Running simulation...", {
        sim <- tryCatch(
          simulate(p, A0 = input$sim_A0, F0 = input$sim_F0,
                   K0 = input$sim_K0, D0 = input$sim_D0,
                   n_years = input$sim_years),
          error = function(e) { showNotification(e$message, type = "error"); NULL }
        )
        rv$sim_result <- sim

        # Update the year slider range based on simulation length
        if (!is.null(sim)) {
          max_yr <- max(sim$year) - 1  # can't view last year (no annual map step)
          updateSliderInput(session, "ws_year", max = max(max_yr, 0), value = max(max_yr, 0))
          # Compute within-season trajectory for the last available year
          tryCatch({
            yr <- max(max_yr, 0)
            ws_data <- season_trajectory(p, sim, year = yr)
            rv$within_season_traj <- ws_data
          }, error = function(e) {
            rv$within_season_traj <- NULL
          })
        }
      })
    })

    # Time series plot
    output$sim_plot <- renderPlotly({
      req(rv$sim_result)
      df <- rv$sim_result
      p1 <- plot_ly(df, x = ~year, y = ~A, type = "scatter", mode = "lines",
                    name = "A (Beetle)", line = list(color = CB_PALETTE$beetle)) %>%
        layout(yaxis = list(title = "Beetle density (A)"))
      p2 <- plot_ly(df, x = ~year, y = ~F, type = "scatter", mode = "lines",
                    name = "F (Parasitoid)", line = list(color = CB_PALETTE$parasitoid)) %>%
        layout(yaxis = list(title = "Parasitoid (F)"))
      p3 <- plot_ly(df, x = ~year, y = ~K, type = "scatter", mode = "lines",
                    name = "K (Capacity)", line = list(color = CB_PALETTE$capacity)) %>%
        layout(yaxis = list(title = "Capacity (K)"))
      p4 <- plot_ly(df, x = ~year, y = ~D, type = "scatter", mode = "lines",
                    name = "D (Defoliation)", line = list(color = CB_PALETTE$defoliation)) %>%
        layout(yaxis = list(title = "Defoliation (D)"))
      subplot(p1, p2, p3, p4, nrows = 2, shareX = TRUE, titleY = TRUE) %>%
        layout(title = "Multi-Year Simulation",
               xaxis = list(title = "Year"), xaxis2 = list(title = "Year"))
    })

    # Phase portrait
    output$phase_plot <- renderPlotly({
      req(rv$sim_result)
      df <- rv$sim_result
      n <- nrow(df)
      plot_ly() %>%
        add_trace(x = df$A, y = df$F, type = "scatter", mode = "lines",
                  name = "Trajectory", line = list(color = CB_PALETTE$dark, width = 1.5)) %>%
        add_trace(x = df$A[1], y = df$F[1], type = "scatter", mode = "markers",
                  name = "Start", marker = list(color = CB_PALETTE$capacity, size = 12,
                                                 symbol = "circle")) %>%
        add_trace(x = df$A[n], y = df$F[n], type = "scatter", mode = "markers",
                  name = "End", marker = list(color = CB_PALETTE$defoliation, size = 14,
                                               symbol = "star")) %>%
        layout(title = "Phase Portrait: Beetle vs Parasitoid",
               xaxis = list(title = "Beetle density (A)"),
               yaxis = list(title = "Parasitoid density (F)"))
    })

    # Re-compute within-season trajectory when user clicks "View Season"
    observeEvent(input$ws_view, {
      req(rv$sim_result)
      p <- as.list(rv$params)
      yr <- input$ws_year
      tryCatch({
        ws_data <- season_trajectory(p, rv$sim_result, year = yr)
        rv$within_season_traj <- ws_data
      }, error = function(e) {
        showNotification(paste("Within-season error:", e$message), type = "error")
      })
    })

    # Within-season dynamics
    output$within_season_plot <- renderPlotly({
      req(rv$within_season_traj)
      ws <- rv$within_season_traj
      traj <- ws$trajectory

      p1 <- plot_ly(traj, x = ~time, y = ~S, type = "scatter", mode = "lines",
                    name = "S (Susceptible)", line = list(color = CB_PALETTE$beetle))
      p1 <- p1 %>%
        add_trace(x = traj$time, y = traj$I, name = "I (Parasitised)",
                  line = list(color = CB_PALETTE$accent))
      # Annotate peak parasitism
      p1 <- p1 %>%
        add_trace(x = ws$peak_parasitism_day, y = traj$S[which.min(abs(traj$time - ws$peak_parasitism_day))],
                  type = "scatter", mode = "markers+text",
                  marker = list(size = 10, color = "red", symbol = "triangle-down"),
                  text = "Peak parasitism", textposition = "top center",
                  showlegend = FALSE)

      p2 <- plot_ly(traj, x = ~time, y = ~F, type = "scatter", mode = "lines",
                    name = "F (Parasitoid)", line = list(color = CB_PALETTE$parasitoid))

      p3 <- plot_ly(traj, x = ~time, y = ~D, type = "scatter", mode = "lines",
                    name = "D (Defoliation)", line = list(color = CB_PALETTE$defoliation))
      # Annotate peak defoliation rate
      p3 <- p3 %>%
        add_trace(x = ws$peak_defoliation_rate_day,
                  y = traj$D[which.min(abs(traj$time - ws$peak_defoliation_rate_day))],
                  type = "scatter", mode = "markers+text",
                  marker = list(size = 10, color = "orange", symbol = "triangle-up"),
                  text = "Peak defol. rate", textposition = "top center",
                  showlegend = FALSE)

      subplot(p1, p2, p3, nrows = 3, shareX = TRUE, titleY = TRUE) %>%
        layout(title = paste0("Within-Season Dynamics (Year ", input$ws_year, ")"),
               xaxis = list(title = "Day (\u03c4)"))
    })

    # Equilibrium table with R1 and R2
    output$eq_table <- renderDT({
      req(rv$sim_result)
      p <- as.list(rv$params)
      fps <- tryCatch(find_fixed_points(p), error = function(e) NULL)
      req(fps)
      fps$R1 <- NA_real_
      fps$R2 <- NA_real_
      for (i in seq_len(nrow(fps))) {
        tryCatch({
          fps$R1[i] <- compute_R1(p, fps$A_star[i], fps$F_star[i],
                                  fps$K_star[i], fps$D_star[i])
          fps$R2[i] <- compute_R2(p, fps$A_star[i], fps$F_star[i],
                                  fps$K_star[i], fps$D_star[i])
        }, error = function(e) NULL)
      }
      datatable(fps, options = list(pageLength = 10, scrollX = TRUE),
                rownames = FALSE) %>%
        formatRound(columns = c("A_star", "F_star", "K_star", "D_star",
                                 "rho_star", "R1", "R2"), digits = 4)
    })

    # Regime forecast
    output$sim_regime_alert <- renderUI({
      req(rv$sim_result)
      df <- rv$sim_result
      n <- nrow(df)
      p <- as.list(rv$params)

      rp <- tryCatch(compute_RP(p), error = function(e) NA)
      A_end <- df$A[n]; F_end <- df$F[n]
      tol <- 1e-6
      if (A_end < tol) {
        eq_class <- "trivial"
      } else if (F_end < tol) {
        eq_class <- "parasitoid_free"
      } else {
        eq_class <- "coexistence"
      }

      clr <- regime_color(eq_class)
      tagList(
        alert_div(
          paste0("Regime: ", toupper(eq_class),
                 " | R_P = ", if (is.na(rp)) "N/A" else sprintf("%.4f", rp)),
          clr
        ),
        tags$p(
          if (eq_class == "coexistence")
            "The parasitoid persists and provides biological control."
          else if (eq_class == "parasitoid_free")
            "The parasitoid cannot persist (R_P < 1). Consider augmentation."
          else
            "Both populations collapse. Verify parameters."
        )
      )
    })
  })
}
