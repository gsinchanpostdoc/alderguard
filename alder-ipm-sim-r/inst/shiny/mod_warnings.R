# Module: Early Warning Signals
# EWS analysis with PRCC bar chart

mod_warnings_ui <- function(id) {
  ns <- NS(id)
  tabItem(tabName = "ews",
    fluidRow(
      box(width = 4, title = "EWS Settings", status = "primary", solidHeader = TRUE,
        radioButtons(ns("ews_source"), "Data Source",
                     choices = c("Upload CSV" = "upload", "Use fitted data" = "fitted")),
        conditionalPanel(
          condition = paste0("input['", ns("ews_source"), "'] == 'upload'"),
          fileInput(ns("ews_csv"), "Upload CSV", accept = ".csv")
        ),
        uiOutput(ns("ews_col_select")),
        uiOutput(ns("ews_window_slider")),
        selectInput(ns("ews_detrend"), "Detrend Method",
                    choices = c("gaussian", "linear", "loess"), selected = "gaussian"),
        actionButton(ns("run_ews"), "Run EWS Analysis", icon = icon("search"),
                     class = "btn-success btn-block"),
        helpText("Early warning signals (EWS) detect critical slowing down before a regime shift.",
                 "Rising variance and autocorrelation indicate the system is losing resilience."),
        tags$hr(),
        tags$h4("LHS-PRCC Sensitivity Analysis"),
        sliderInput(ns("prcc_n_samples"), "Number of LHS samples",
                    min = 20, max = 500, value = 100, step = 10),
        numericInput(ns("prcc_seed"), "Random seed", value = 42, step = 1),
        actionButton(ns("run_prcc"), "Run PRCC Analysis", icon = icon("chart-bar"),
                     class = "btn-primary btn-block"),
        helpText("Latin Hypercube Sampling with Partial Rank Correlation Coefficients (PRCC)",
                 "identifies which parameters most strongly influence the dominant eigenvalue",
                 "and hence the risk of regime shift.")
      ),
      box(width = 8, title = "Early Warning Signals", status = "success", solidHeader = TRUE,
        plotlyOutput(ns("ews_plot"), height = "500px"),
        tags$hr(),
        DTOutput(ns("ews_kendall_table")),
        tags$hr(),
        uiOutput(ns("ews_alert_box")),
        uiOutput(ns("ews_recommendations")),
        tags$hr(),
        tags$h3("LHS-PRCC Sensitivity Analysis"),
        uiOutput(ns("prcc_regime_box")),
        plotlyOutput(ns("prcc_bar_plot"), height = "400px"),
        helpText("Bars show the PRCC of each parameter with the dominant eigenvalue (rho*).",
                 "Red bars = significant (|PRCC| > 0.3, p < 0.05).",
                 "Positive PRCC means increasing the parameter destabilises the system."),
        DTOutput(ns("prcc_table")),
        plotlyOutput(ns("prcc_eq_pie"), height = "300px")
      )
    )
  )
}

mod_warnings_server <- function(id, rv) {
  moduleServer(id, function(input, output, session) {

    ews_data_reactive <- reactive({
      if (input$ews_source == "upload") {
        req(input$ews_csv)
        tryCatch(
          read.csv(input$ews_csv$datapath, stringsAsFactors = FALSE),
          error = function(e) NULL
        )
      } else {
        req(rv$fit_raw_df)
        rv$fit_raw_df
      }
    })

    output$ews_col_select <- renderUI({
      df <- ews_data_reactive()
      req(df)
      num_cols <- names(df)[vapply(df, is.numeric, logical(1))]
      selectInput(session$ns("ews_column"), "Variable to Analyze", choices = num_cols)
    })

    output$ews_window_slider <- renderUI({
      df <- ews_data_reactive()
      req(df, input$ews_column)
      n <- nrow(df)
      def_win <- max(as.integer(n * 0.5), 3)
      sliderInput(session$ns("ews_window"), "Window Size", min = 3, max = n - 1,
                  value = min(def_win, n - 1), step = 1)
    })

    observeEvent(input$run_ews, {
      df <- ews_data_reactive()
      req(df, input$ews_column, input$ews_window)
      ts_vec <- as.numeric(df[[input$ews_column]])
      ts_vec <- ts_vec[is.finite(ts_vec)]

      withProgress(message = "Computing EWS...", {
        tryCatch({
          result <- detect_warnings(ts_vec, window = input$ews_window,
                                    detrend = input$ews_detrend)
          rv$ews_data <- list(ts = ts_vec, result = result)
          showNotification("EWS analysis complete.", type = "message")
        }, error = function(e) {
          showNotification(paste("EWS error:", e$message), type = "error")
        })
      })
    })

    output$ews_plot <- renderPlotly({
      req(rv$ews_data)
      ts_vec <- rv$ews_data$ts
      ind    <- rv$ews_data$result$indicators

      p1 <- plot_ly(x = seq_along(ts_vec), y = ts_vec, type = "scatter", mode = "lines",
                    name = "Original", line = list(color = CB_PALETTE$dark)) %>%
        layout(yaxis = list(title = "Value"))
      p2 <- plot_ly(x = ind$time, y = ind$variance, type = "scatter", mode = "lines",
                    name = "Variance", line = list(color = CB_PALETTE$beetle)) %>%
        layout(yaxis = list(title = "Variance"))
      p3 <- plot_ly(x = ind$time, y = ind$autocorrelation, type = "scatter", mode = "lines",
                    name = "AR(1)", line = list(color = CB_PALETTE$capacity)) %>%
        layout(yaxis = list(title = "Autocorrelation"))
      p4 <- plot_ly(x = ind$time, y = ind$skewness, type = "scatter", mode = "lines",
                    name = "Skewness", line = list(color = CB_PALETTE$defoliation)) %>%
        layout(yaxis = list(title = "Skewness"))
      subplot(p1, p2, p3, p4, nrows = 4, shareX = TRUE, titleY = TRUE) %>%
        layout(title = "Early Warning Signal Indicators")
    })

    output$ews_kendall_table <- renderDT({
      req(rv$ews_data)
      kr <- rv$ews_data$result$kendall_results
      tbl <- data.frame(
        Indicator = c("Variance", "Autocorrelation", "Skewness"),
        Tau       = c(kr$variance$tau, kr$autocorrelation$tau, kr$skewness$tau),
        P_Value   = c(kr$variance$p_value, kr$autocorrelation$p_value, kr$skewness$p_value),
        Significant = c(
          kr$variance$p_value < 0.05,
          kr$autocorrelation$p_value < 0.05,
          kr$skewness$p_value < 0.05
        ),
        stringsAsFactors = FALSE
      )
      datatable(tbl, options = list(dom = "t", pageLength = 3), rownames = FALSE) %>%
        formatRound(columns = c("Tau", "P_Value"), digits = 4)
    })

    output$ews_alert_box <- renderUI({
      req(rv$ews_data)
      result <- rv$ews_data$result
      clr <- ews_alert_color(result$alert_level)
      alert_div(
        paste0(toupper(result$alert_level), " ALERT: ", result$interpretation),
        clr
      )
    })

    output$ews_recommendations <- renderUI({
      req(rv$ews_data)
      level <- rv$ews_data$result$alert_level
      recs <- switch(level,
        green = list(
          "Continue routine annual monitoring.",
          "Maintain current management practices.",
          "Archive data for long-term trend analysis."
        ),
        yellow = list(
          "Increase monitoring frequency to biannual or quarterly.",
          "Prepare contingency plans for parasitoid augmentation.",
          "Review bird habitat conditions and nesting box occupancy.",
          "Compare current beetle densities against historical baselines."
        ),
        red = list(
          "Initiate emergency management response.",
          "Evaluate integrated control Strategy C (parasitoid + bird + larval removal).",
          "Deploy early parasitoid augmentation releases.",
          "Install additional nesting boxes and hedgerow planting.",
          "Consider targeted larval removal in outbreak hotspots."
        )
      )
      tagList(
        tags$h4("Recommended Monitoring Actions"),
        tags$ul(lapply(recs, tags$li))
      )
    })

    # PRCC analysis
    observeEvent(input$run_prcc, {
      p <- as.list(rv$params)
      withProgress(message = "Running LHS-PRCC analysis...", {
        tryCatch({
          result <- lhs_prcc(params = p,
                             n_samples = input$prcc_n_samples,
                             n_years = 50,
                             seed = input$prcc_seed)
          rv$prcc_result <- result
          showNotification("PRCC analysis complete.", type = "message")
        }, error = function(e) {
          showNotification(paste("PRCC error:", e$message), type = "error")
        })
      })
    })

    output$prcc_regime_box <- renderUI({
      req(rv$prcc_result)
      prob <- rv$prcc_result$regime_shift_prob
      pct <- sprintf("%.1f%%", prob * 100)
      clr <- if (prob > 0.5) CB_PALETTE$defoliation else if (prob > 0.2) CB_PALETTE$beetle else CB_PALETTE$capacity
      msg <- if (prob > 0.5) {
        paste0("High regime shift probability (", pct,
               "): a large fraction of parameter space leads to non-coexistence.")
      } else if (prob > 0.2) {
        paste0("Moderate regime shift probability (", pct,
               "): some parameter combinations lead to regime shift.")
      } else {
        paste0("Low regime shift probability (", pct,
               "): the system is robust across sampled parameter space.")
      }
      alert_div(msg, clr)
    })

    # PRCC bar chart (replacing tornado plot)
    output$prcc_bar_plot <- renderPlotly({
      req(rv$prcc_result)
      tbl <- rv$prcc_result$prcc_table
      # Sort by absolute PRCC
      tbl <- tbl[order(abs(tbl$prcc)), ]
      colors <- ifelse(abs(tbl$prcc) > 0.3 & tbl$p_value < 0.05, CB_PALETTE$defoliation,
                ifelse(abs(tbl$prcc) > 0.15 & tbl$p_value < 0.05, CB_PALETTE$beetle,
                       CB_PALETTE$grey))
      plot_ly(tbl, y = ~parameter, x = ~prcc, type = "bar", orientation = "h",
              marker = list(color = colors),
              text = ~sprintf("PRCC=%.3f (p=%.3f)", prcc, p_value),
              hoverinfo = "text") %>%
        layout(title = "PRCC with dominant eigenvalue (rho*)",
               xaxis = list(title = "PRCC", range = c(-1, 1)),
               yaxis = list(title = ""),
               shapes = list(
                 list(type = "line", x0 = 0.3, x1 = 0.3, y0 = -0.5,
                      y1 = nrow(tbl) - 0.5, line = list(dash = "dash", color = CB_PALETTE$defoliation, width = 1)),
                 list(type = "line", x0 = -0.3, x1 = -0.3, y0 = -0.5,
                      y1 = nrow(tbl) - 0.5, line = list(dash = "dash", color = CB_PALETTE$defoliation, width = 1))
               ))
    })

    output$prcc_table <- renderDT({
      req(rv$prcc_result)
      tbl <- rv$prcc_result$prcc_table
      tbl$significant <- ifelse(tbl$p_value < 0.05, "Yes", "No")
      datatable(tbl, options = list(dom = "t", pageLength = 15), rownames = FALSE) %>%
        formatRound(columns = c("prcc", "p_value"), digits = 4)
    })

    output$prcc_eq_pie <- renderPlotly({
      req(rv$prcc_result)
      eq_classes <- rv$prcc_result$eq_classes
      counts <- table(eq_classes)
      colors <- ifelse(names(counts) == "coexistence", CB_PALETTE$capacity,
                ifelse(names(counts) %in% c("parasitoid_free", "trivial"),
                       CB_PALETTE$defoliation, CB_PALETTE$beetle))
      plot_ly(labels = names(counts), values = as.numeric(counts),
              type = "pie", marker = list(colors = colors)) %>%
        layout(title = "Equilibrium classes across LHS samples")
    })
  })
}
