# Module: Data Fitting
# CSV upload, model fitting, overlay plots, regime forecast

mod_fitting_ui <- function(id) {
  ns <- NS(id)
  tabItem(tabName = "fitting",
    fluidRow(
      box(width = 4, title = "Data & Settings", status = "primary", solidHeader = TRUE,
        fileInput(ns("fit_csv"), "Upload CSV", accept = ".csv"),
        uiOutput(ns("fit_col_mapping")),
        selectInput(ns("fit_timestep"), "Timestep", choices = c("annual", "seasonal"),
                    selected = "annual"),
        selectizeInput(ns("fit_params_select"), "Parameters to Fit",
                       choices = names(param_registry()),
                       selected = c("beta", "mu_S", "delta", "R_B", "phi", "kappa"),
                       multiple = TRUE),
        actionButton(ns("run_fit"), "Fit Model", icon = icon("cogs"),
                     class = "btn-success btn-block"),
        helpText("Upload a CSV with time-series data of beetle density, parasitoid density,",
                 "carrying capacity, or defoliation. Map columns and select parameters to estimate.")
      ),
      box(width = 8, title = "Fitting Results", status = "success", solidHeader = TRUE,
        DTOutput(ns("fit_params_table")),
        tags$hr(),
        fluidRow(
          column(3, uiOutput(ns("fit_r2_box"))),
          column(3, uiOutput(ns("fit_aic_box"))),
          column(3, uiOutput(ns("fit_bic_box"))),
          column(3, uiOutput(ns("fit_dw_box")))
        ),
        plotlyOutput(ns("fit_overlay_plot"), height = "400px"),
        tags$hr(),
        fluidRow(
          column(6, plotlyOutput(ns("fit_acf_plot"), height = "300px")),
          column(6, plotlyOutput(ns("fit_qq_plot"), height = "300px"))
        ),
        tags$hr(),
        plotlyOutput(ns("fit_corr_plot"), height = "400px"),
        tags$hr(),
        uiOutput(ns("fit_convergence_info")),
        tags$hr(),
        uiOutput(ns("fit_regime_alert"))
      )
    )
  )
}

mod_fitting_server <- function(id, rv) {
  moduleServer(id, function(input, output, session) {

    observeEvent(input$fit_csv, {
      req(input$fit_csv)
      rv$fit_raw_df <- tryCatch(
        read.csv(input$fit_csv$datapath, stringsAsFactors = FALSE),
        error = function(e) { showNotification(e$message, type = "error"); NULL }
      )
    })

    output$fit_col_mapping <- renderUI({
      req(rv$fit_raw_df)
      cols <- names(rv$fit_raw_df)
      ns <- session$ns
      tagList(
        selectInput(ns("fit_time_col"), "Time column", choices = cols, selected = cols[1]),
        selectInput(ns("fit_col_A"), "Beetle (A) column",
                    choices = c("(none)", cols), selected = "A"),
        selectInput(ns("fit_col_F"), "Parasitoid (F) column",
                    choices = c("(none)", cols), selected = "F"),
        selectInput(ns("fit_col_K"), "Capacity (K) column",
                    choices = c("(none)", cols), selected = "K"),
        selectInput(ns("fit_col_D"), "Defoliation (D) column",
                    choices = c("(none)", cols), selected = "D")
      )
    })

    observeEvent(input$run_fit, {
      req(rv$fit_raw_df)
      df <- rv$fit_raw_df

      state_cols <- c()
      for (sv in c("A", "F", "K", "D")) {
        col_id <- paste0("fit_col_", sv)
        val <- input[[col_id]]
        if (!is.null(val) && val != "(none)" && val %in% names(df)) {
          state_cols[sv] <- val
        }
      }

      withProgress(message = "Fitting model...", {
        tryCatch({
          prepared <- prepare_data(df, time_col = input$fit_time_col,
                                   state_cols = state_cols,
                                   timestep = input$fit_timestep)
          p <- as.list(rv$params)
          result <- fit_model(prepared, fit_params = input$fit_params_select,
                              params = p, method = "nls")
          rv$fit_data   <- prepared
          rv$fit_result <- result
          showNotification("Fitting complete.", type = "message")
        }, error = function(e) {
          showNotification(paste("Fitting error:", e$message), type = "error")
        })
      })
    })

    output$fit_params_table <- renderDT({
      req(rv$fit_result)
      fr <- rv$fit_result
      fp <- fr$fitted_params
      ci <- fr$conf_intervals
      tbl <- data.frame(
        Parameter = names(fp),
        Value     = as.numeric(fp),
        CI_Lower  = vapply(names(fp), function(n) ci[[n]][1], numeric(1)),
        CI_Upper  = vapply(names(fp), function(n) ci[[n]][2], numeric(1)),
        stringsAsFactors = FALSE
      )
      datatable(tbl, options = list(pageLength = 10, dom = "t"), rownames = FALSE) %>%
        formatRound(columns = c("Value", "CI_Lower", "CI_Upper"), digits = 6)
    })

    output$fit_r2_box <- renderUI({
      req(rv$fit_result)
      tags$div(class = "small-box bg-green",
        tags$div(class = "inner",
          tags$h3(sprintf("%.4f", rv$fit_result$r_squared)),
          tags$p("R-squared")
        )
      )
    })

    output$fit_aic_box <- renderUI({
      req(rv$fit_result)
      tags$div(class = "small-box bg-blue",
        tags$div(class = "inner",
          tags$h3(sprintf("%.1f", rv$fit_result$AIC)),
          tags$p("AIC")
        )
      )
    })

    output$fit_bic_box <- renderUI({
      req(rv$fit_result)
      tags$div(class = "small-box bg-purple",
        tags$div(class = "inner",
          tags$h3(sprintf("%.1f", rv$fit_result$BIC)),
          tags$p("BIC")
        )
      )
    })

    output$fit_dw_box <- renderUI({
      req(rv$fit_result)
      resid <- rv$fit_result$residuals
      dw <- if (length(resid) > 1) sum(diff(resid)^2) / max(sum(resid^2), 1e-30) else 2.0
      tags$div(class = "small-box bg-yellow",
        tags$div(class = "inner",
          tags$h3(sprintf("%.3f", dw)),
          tags$p("Durbin-Watson")
        )
      )
    })

    output$fit_acf_plot <- renderPlotly({
      req(rv$fit_result)
      resid <- rv$fit_result$residuals
      n <- length(resid)
      if (n < 4) return(NULL)
      acf_obj <- stats::acf(resid, lag.max = min(20, n - 1), plot = FALSE)
      acf_vals <- as.numeric(acf_obj$acf)
      lags <- as.numeric(acf_obj$lag)
      ci_bound <- 1.96 / sqrt(n)
      plot_ly() %>%
        add_bars(x = lags, y = acf_vals, name = "ACF",
                 marker = list(color = CB_PALETTE$beetle)) %>%
        layout(title = "Residual Autocorrelation",
               xaxis = list(title = "Lag"),
               yaxis = list(title = "ACF"),
               shapes = list(
                 list(type = "line", x0 = min(lags), x1 = max(lags),
                      y0 = ci_bound, y1 = ci_bound,
                      line = list(color = "red", dash = "dash")),
                 list(type = "line", x0 = min(lags), x1 = max(lags),
                      y0 = -ci_bound, y1 = -ci_bound,
                      line = list(color = "red", dash = "dash"))
               ))
    })

    output$fit_qq_plot <- renderPlotly({
      req(rv$fit_result)
      resid <- rv$fit_result$residuals
      qq <- stats::qqnorm(resid, plot.it = FALSE)
      qq_range <- range(c(qq$x, qq$y), na.rm = TRUE)
      plot_ly() %>%
        add_markers(x = qq$x, y = qq$y, name = "Residuals",
                    marker = list(color = CB_PALETTE$beetle)) %>%
        add_lines(x = qq_range, y = qq_range, name = "Reference",
                  line = list(color = "red", dash = "dash")) %>%
        layout(title = "Normal Q-Q Plot",
               xaxis = list(title = "Theoretical Quantiles"),
               yaxis = list(title = "Sample Quantiles"))
    })

    output$fit_corr_plot <- renderPlotly({
      req(rv$fit_result)
      fr <- rv$fit_result
      pnames <- names(fr$fitted_params)
      if (length(pnames) < 2) return(NULL)

      # Compute parameter correlation from numerical Jacobian
      resid_fn <- function(x) {
        p <- as.list(rv$params)
        for (i in seq_along(pnames)) p[[pnames[i]]] <- x[i]
        .compute_residuals(p, rv$fit_data)
      }
      x_opt <- as.numeric(fr$fitted_params)
      k <- length(x_opt)
      r0 <- resid_fn(x_opt)
      jac <- matrix(0, nrow = length(r0), ncol = k)
      for (j in seq_len(k)) {
        h <- 1e-7 * max(abs(x_opt[j]), 1)
        dx <- rep(0, k); dx[j] <- h
        jac[, j] <- (resid_fn(x_opt + dx) - resid_fn(x_opt - dx)) / (2 * h)
      }
      corr_mat <- tryCatch({
        cov_mat <- solve(crossprod(jac)) * (sum(r0^2) / max(length(r0) - k, 1))
        d <- sqrt(pmax(diag(cov_mat), 1e-30))
        cm <- cov_mat / outer(d, d)
        diag(cm) <- 1.0
        cm
      }, error = function(e) diag(k))

      plot_ly(z = corr_mat, x = pnames, y = pnames, type = "heatmap",
              colorscale = "RdBu", zmid = 0, zmin = -1, zmax = 1,
              text = round(corr_mat, 2), texttemplate = "%{text}") %>%
        layout(title = "Parameter Correlation Heatmap")
    })

    output$fit_convergence_info <- renderUI({
      req(rv$fit_result)
      conv <- rv$fit_result$convergence
      tags$div(
        tags$h4("Convergence Info"),
        tags$table(class = "table table-condensed",
          tags$tr(tags$td("Optimizer"), tags$td(conv$optimizer)),
          tags$tr(tags$td("Convergence code"), tags$td(as.character(conv$convergence_code))),
          tags$tr(tags$td("Cost"), tags$td(sprintf("%.6f", conv$cost))),
          tags$tr(tags$td("Message"), tags$td(as.character(conv$message))),
          if (!is.null(conv$gradient_norm))
            tags$tr(tags$td("Gradient norm"), tags$td(sprintf("%.2e", conv$gradient_norm)))
        )
      )
    })

    output$fit_overlay_plot <- renderPlotly({
      req(rv$fit_result, rv$fit_data, rv$fit_raw_df)
      fr <- rv$fit_result
      data <- rv$fit_data
      p <- as.list(rv$params)
      for (n in names(fr$fitted_params)) p[[n]] <- fr$fitted_params[[n]]

      obs <- data$obs
      ic <- list(A = p[["K_0"]] * 0.5, F = 0.1, K = p[["K_0"]], D = 0)
      for (s in names(obs)) ic[[s]] <- obs[[s]][1]

      sim <- tryCatch(
        simulate(p, A0 = ic[["A"]], F0 = ic[["F"]], K0 = ic[["K"]], D0 = ic[["D"]],
                 n_years = data$n_obs - 1),
        error = function(e) NULL
      )
      req(sim)

      pal <- c(A = CB_PALETTE$beetle, F = CB_PALETTE$parasitoid,
               K = CB_PALETTE$capacity, D = CB_PALETTE$defoliation)
      plots <- list()
      idx <- 1
      for (sv in names(obs)) {
        obs_vals <- obs[[sv]]
        sim_vals <- sim[[sv]][seq_len(data$n_obs)]
        col <- if (!is.null(pal[[sv]])) pal[[sv]] else CB_PALETTE$dark
        pl <- plot_ly() %>%
          add_trace(x = data$times, y = obs_vals, type = "scatter", mode = "markers",
                    name = paste(sv, "observed"), marker = list(size = 8, color = col)) %>%
          add_trace(x = data$times, y = sim_vals, type = "scatter", mode = "lines",
                    name = paste(sv, "fitted"), line = list(color = col)) %>%
          layout(yaxis = list(title = sv))
        plots[[idx]] <- pl
        idx <- idx + 1
      }

      if (length(plots) == 1) {
        plots[[1]] %>% layout(title = "Observed vs Fitted")
      } else {
        nr <- ceiling(length(plots) / 2)
        subplot(plots, nrows = nr, shareX = TRUE, titleY = TRUE) %>%
          layout(title = "Observed vs Fitted")
      }
    })

    output$fit_regime_alert <- renderUI({
      req(rv$fit_result)
      regime <- tryCatch(forecast_regime(rv$fit_result), error = function(e) NULL)
      req(regime)
      clr <- regime_color(regime$equilibrium_class)
      tagList(
        tags$h4("Regime Forecast"),
        alert_div(
          paste0(toupper(regime$equilibrium_class),
                 " | R_P = ", sprintf("%.4f", regime$R_P)),
          clr
        ),
        tags$p(regime$interpretation)
      )
    })
  })
}
