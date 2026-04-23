# Module: Management Strategies
# Strategy comparison with Pareto frontier plot

mod_control_ui <- function(id) {
  ns <- NS(id)
  tabItem(tabName = "management",
    fluidRow(
      box(width = 4, title = "Settings", status = "primary", solidHeader = TRUE,
        numericInput(ns("mgmt_A0"), "A0 (beetle density)", value = 0.8, min = 0, step = 0.1),
        numericInput(ns("mgmt_F0"), "F0 (parasitoid density)", value = 0.1, min = 0, step = 0.05),
        numericInput(ns("mgmt_K0"), "K0 (carrying capacity)", value = 1.712, min = 0.1, step = 0.1),
        numericInput(ns("mgmt_D0"), "D0 (defoliation)", value = 0, min = 0, step = 0.1),
        sliderInput(ns("mgmt_horizon"), "Planning horizon (years)", min = 10, max = 100,
                    value = 50, step = 5),
        actionButton(ns("run_mgmt"), "Compare Strategies", icon = icon("balance-scale"),
                     class = "btn-success btn-block"),
        helpText("Compares three integrated pest management strategies:",
                 tags$b("A"), "= parasitoid augmentation only;",
                 tags$b("B"), "= parasitoid + bird habitat;",
                 tags$b("C"), "= full integrated control (+ larval removal).",
                 "Optimisation may take a few minutes."),
        tags$hr(),
        checkboxInput(ns("use_custom"), "Custom Strategy"),
        conditionalPanel(
          condition = sprintf("input['%s'] == true", ns("use_custom")),
          numericInput(ns("custom_u_P"), "u_P (parasitoid augmentation)", value = 0.1, min = 0, step = 0.01),
          numericInput(ns("custom_u_C"), "u_C (larval removal)", value = 0.1, min = 0, step = 0.01),
          numericInput(ns("custom_u_B"), "u_B (bird habitat)", value = 0.1, min = 0, step = 0.01),
          actionButton(ns("run_custom"), "Evaluate Custom", icon = icon("cogs"),
                       class = "btn-info btn-block")
        )
      ),
      box(width = 8, title = "Strategy Comparison", status = "success", solidHeader = TRUE,
        DTOutput(ns("mgmt_table")),
        tags$hr(),
        plotlyOutput(ns("mgmt_traj_plot"), height = "500px"),
        tags$hr(),
        plotlyOutput(ns("pareto_plot"), height = "350px"),
        helpText("Pareto frontier: strategies closer to the bottom-left are preferred",
                 "(lower cost AND lower defoliation). Feasible strategies shown as filled circles."),
        tags$hr(),
        plotlyOutput(ns("pareto_frontier_plot"), height = "350px"),
        helpText("Pareto frontier sweep: cost and defoliation as control budget scales from 0% to 100%."),
        tags$hr(),
        plotlyOutput(ns("temporal_plot"), height = "400px"),
        helpText("Temporal allocation: per-year cost breakdown for the recommended (or custom) strategy."),
        tags$hr(),
        DTOutput(ns("cost_table")),
        tags$hr(),
        uiOutput(ns("mgmt_recommendation")),
        uiOutput(ns("mgmt_feasibility"))
      )
    )
  )
}

mod_control_server <- function(id, rv) {
  moduleServer(id, function(input, output, session) {

    observeEvent(input$run_mgmt, {
      p <- as.list(rv$params)
      ic <- c(A = input$mgmt_A0, F = input$mgmt_F0,
              K = input$mgmt_K0, D = input$mgmt_D0)
      withProgress(message = "Optimising strategies (this may take a few minutes)...", {
        tryCatch({
          result <- compare_strategies(p, initial_state = ic, n_years = input$mgmt_horizon)
          rv$mgmt_result <- result
          showNotification("Strategy comparison complete.", type = "message")
        }, error = function(e) {
          showNotification(paste("Optimisation error:", e$message), type = "error")
        })
      })
    })

    output$mgmt_table <- renderDT({
      req(rv$mgmt_result)
      comp <- rv$mgmt_result$comparison
      datatable(comp, options = list(dom = "t", pageLength = 5), rownames = FALSE) %>%
        formatRound(columns = c("cost", "D_star", "K_star", "rho_star"), digits = 4)
    })

    output$mgmt_traj_plot <- renderPlotly({
      req(rv$mgmt_result)
      p_base <- as.list(rv$params)
      ic <- c(A = input$mgmt_A0, F = input$mgmt_F0,
              K = input$mgmt_K0, D = input$mgmt_D0)
      comp <- rv$mgmt_result$comparison
      n_yr <- input$mgmt_horizon

      colors <- c(A = CB_PALETTE$beetle, B = CB_PALETTE$parasitoid, C = CB_PALETTE$capacity)
      scenario_labels <- c(A = "A: Parasitoid only", B = "B: Parasitoid + Bird",
                           C = "C: Full integrated")

      trajs <- list()
      for (i in seq_len(nrow(comp))) {
        sc <- comp$scenario[i]
        res <- tryCatch(
          optimize_scenario(p_base, scenario = sc, initial_state = ic, n_years = n_yr),
          error = function(e) NULL
        )
        if (!is.null(res)) {
          ctrl <- res$optimal_controls
          p_sc <- p_base
          p_sc[["u_C"]] <- ctrl[["u_C"]]
          p_sc[["u_P"]] <- ctrl[["u_P"]]
          p_sc[["B_index"]] <- p_base[["B_index"]] + ctrl[["u_B"]]
          traj <- simulate(p_sc, A0 = ic[["A"]], F0 = ic[["F"]],
                           K0 = ic[["K"]], D0 = ic[["D"]], n_years = n_yr)
          traj$scenario <- sc
          trajs[[sc]] <- traj
        }
      }

      make_panel <- function(var, title) {
        pl <- plot_ly()
        for (sc in names(trajs)) {
          df <- trajs[[sc]]
          pl <- pl %>%
            add_trace(x = df$year, y = df[[var]], type = "scatter", mode = "lines",
                      name = scenario_labels[[sc]], line = list(color = colors[[sc]]),
                      legendgroup = sc, showlegend = (var == "A"))
        }
        pl %>% layout(yaxis = list(title = title))
      }

      p1 <- make_panel("A", "Beetle (A)")
      p2 <- make_panel("F", "Parasitoid (F)")
      p3 <- make_panel("K", "Capacity (K)")
      p4 <- make_panel("D", "Defoliation (D)")

      subplot(p1, p2, p3, p4, nrows = 2, shareX = TRUE, titleY = TRUE) %>%
        layout(title = "Multi-Year Trajectories by Strategy",
               xaxis = list(title = "Year"))
    })

    # Pareto frontier plot: cost vs defoliation
    output$pareto_plot <- renderPlotly({
      req(rv$mgmt_result)
      comp <- rv$mgmt_result$comparison
      colors <- c(A = CB_PALETTE$beetle, B = CB_PALETTE$parasitoid, C = CB_PALETTE$capacity)
      symbols <- ifelse(comp$feasible, "circle", "x")
      sizes <- ifelse(comp$feasible, 14, 10)

      plot_ly(comp, x = ~cost, y = ~D_star, type = "scatter", mode = "markers+text",
              text = ~paste0("Strategy ", scenario),
              textposition = "top center",
              marker = list(
                color = vapply(comp$scenario, function(s) colors[[s]], character(1)),
                size = sizes,
                symbol = symbols,
                line = list(width = 2, color = CB_PALETTE$black)
              ),
              hovertext = ~sprintf("Strategy %s\nCost: %.2f\nD*: %.4f\nK*: %.4f\nFeasible: %s",
                                   scenario, cost, D_star, K_star,
                                   ifelse(feasible, "Yes", "No")),
              hoverinfo = "text") %>%
        layout(title = "Pareto Frontier: Cost vs Defoliation",
               xaxis = list(title = "Cost (J)"),
               yaxis = list(title = "Equilibrium Defoliation (D*)"))
    })

    output$mgmt_recommendation <- renderUI({
      req(rv$mgmt_result)
      rec <- rv$mgmt_result$recommended
      comp <- rv$mgmt_result$comparison

      if (!is.na(rec)) {
        best_row <- comp[comp$scenario == rec, ]
        clr <- CB_PALETTE$capacity
        alert_div(
          paste0("Recommended: Strategy ", rec, " (Cost J = ",
                 sprintf("%.2f", best_row$cost), ")"),
          clr
        )
      } else {
        alert_div(
          "No strategy met all feasibility criteria. Consider increasing control budgets or extending the horizon.",
          CB_PALETTE$defoliation
        )
      }
    })

    # Custom strategy evaluation
    observeEvent(input$run_custom, {
      req(input$use_custom)
      p <- as.list(rv$params)
      ic <- c(A = input$mgmt_A0, F = input$mgmt_F0,
              K = input$mgmt_K0, D = input$mgmt_D0)
      withProgress(message = "Evaluating custom strategy...", {
        tryCatch({
          res <- custom_strategy(p, u_P = input$custom_u_P, u_C = input$custom_u_C,
                                 u_B = input$custom_u_B, initial_state = ic,
                                 n_years = input$mgmt_horizon)
          rv$custom_result <- res
          showNotification("Custom strategy evaluated.", type = "message")
        }, error = function(e) {
          showNotification(paste("Custom strategy error:", e$message), type = "error")
        })
      })
    })

    # Pareto frontier sweep plot
    output$pareto_frontier_plot <- renderPlotly({
      req(rv$mgmt_result)
      p <- as.list(rv$params)
      ic <- c(A = input$mgmt_A0, F = input$mgmt_F0,
              K = input$mgmt_K0, D = input$mgmt_D0)
      pf <- tryCatch(
        pareto_frontier(p, initial_state = ic, n_points = 30, n_years = input$mgmt_horizon),
        error = function(e) NULL
      )
      req(pf)
      plot_ly(pf, x = ~cost, y = ~D_star, type = "scatter", mode = "lines+markers",
              text = ~sprintf("Budget: %.0f%%\nCost: %.2f\nD*: %.4f\nK*: %.4f",
                              fraction * 100, cost, D_star, K_star),
              hoverinfo = "text",
              marker = list(size = 6, color = CB_PALETTE$capacity),
              line = list(color = CB_PALETTE$capacity)) %>%
        layout(title = "Pareto Frontier Sweep",
               xaxis = list(title = "Total Cost (J)"),
               yaxis = list(title = "Equilibrium Defoliation (D*)"))
    })

    # Temporal allocation stacked area chart
    output$temporal_plot <- renderPlotly({
      req(rv$mgmt_result)
      p <- as.list(rv$params)
      ic <- c(A = input$mgmt_A0, F = input$mgmt_F0,
              K = input$mgmt_K0, D = input$mgmt_D0)

      # Use custom strategy controls if available, otherwise recommended
      if (isTRUE(input$use_custom) && !is.null(rv$custom_result)) {
        ctrl <- rv$custom_result$optimal_controls
        label <- "Custom"
      } else {
        rec <- rv$mgmt_result$recommended
        if (is.na(rec)) rec <- "C"
        res <- tryCatch(
          optimize_scenario(p, scenario = rec, initial_state = ic, n_years = input$mgmt_horizon),
          error = function(e) NULL
        )
        req(res)
        ctrl <- res$optimal_controls
        label <- paste("Strategy", rec)
      }

      ta <- tryCatch(
        temporal_allocation(p, controls = ctrl, initial_state = ic, n_years = input$mgmt_horizon),
        error = function(e) NULL
      )
      req(ta)
      rv$temporal_data <- ta

      plot_ly(ta, x = ~year) %>%
        add_trace(y = ~running_cost, name = "Running cost", type = "scatter",
                  mode = "none", stackgroup = "one", fillcolor = CB_PALETTE$beetle) %>%
        add_trace(y = ~terminal_cost, name = "Terminal cost", type = "scatter",
                  mode = "none", stackgroup = "one", fillcolor = CB_PALETTE$defoliation) %>%
        add_trace(y = ~control_cost, name = "Control cost", type = "scatter",
                  mode = "none", stackgroup = "one", fillcolor = CB_PALETTE$parasitoid) %>%
        layout(title = paste("Temporal Cost Allocation -", label),
               xaxis = list(title = "Year"),
               yaxis = list(title = "Cost"))
    })

    # Cost breakdown table
    output$cost_table <- renderDT({
      req(rv$temporal_data)
      ta <- rv$temporal_data
      datatable(ta, options = list(pageLength = 10, scrollX = TRUE), rownames = FALSE) %>%
        formatRound(columns = c("u_P", "u_C", "u_B", "running_cost", "terminal_cost",
                                "control_cost", "total_cost"), digits = 4)
    })

    output$mgmt_feasibility <- renderUI({
      req(rv$mgmt_result)
      comp <- rv$mgmt_result$comparison
      p_base <- as.list(rv$params)

      panels <- lapply(seq_len(nrow(comp)), function(i) {
        sc <- comp$scenario[i]
        feas <- comp$feasible[i]
        checks <- list(
          paste0("D* = ", sprintf("%.4f", comp$D_star[i]),
                 if (comp$D_star[i] < p_base[["D_crit"]]) " < " else " >= ",
                 "D_crit = ", p_base[["D_crit"]]),
          paste0("K* = ", sprintf("%.4f", comp$K_star[i]),
                 if (comp$K_star[i] > p_base[["K_min"]]) " > " else " <= ",
                 "K_min = ", p_base[["K_min"]]),
          paste0("rho* = ", sprintf("%.4f", comp$rho_star[i]),
                 if (!is.na(comp$rho_star[i]) && comp$rho_star[i] < 1.01) " < 1.01"
                 else " >= 1.01")
        )
        icon_fn <- function(ok) {
          if (ok) icon("check", style = "color:#009E73;")
          else icon("times", style = "color:#D55E00;")
        }
        check_ok <- c(
          comp$D_star[i] < p_base[["D_crit"]],
          comp$K_star[i] > p_base[["K_min"]],
          !is.na(comp$rho_star[i]) && comp$rho_star[i] < 1.01
        )
        box(
          title = paste0("Strategy ", sc, if (feas) " (Feasible)" else " (Infeasible)"),
          status = if (feas) "success" else "danger",
          solidHeader = TRUE, collapsible = TRUE, collapsed = TRUE, width = 4,
          lapply(seq_along(checks), function(j) {
            tags$p(icon_fn(check_ok[j]), " ", checks[[j]])
          })
        )
      })
      fluidRow(panels)
    })
  })
}
