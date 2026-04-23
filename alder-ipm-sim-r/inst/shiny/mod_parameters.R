# Module: Parameter Setup
# UI and server for parameter sliders, presets, JSON upload/download

# Colorblind-safe palette (Okabe-Ito)
CB_PALETTE <- list(
  beetle     = "#E69F00",
  parasitoid = "#56B4E9",
  capacity   = "#009E73",
  defoliation = "#D55E00",
  accent     = "#CC79A7",
  dark       = "#0072B2",
  grey       = "#999999",
  black      = "#000000"
)

CATEGORY_LABELS <- list(
  within_season_biotic_rate = "Within-Season Biotic Rates",
  within_season_mortality   = "Mortality Rates",
  within_season_phenology   = "Phenology",
  annual_biotic_rate        = "Annual Dynamics",
  annual_mortality          = "Annual Mortality",
  annual_control            = "Control",
  annual_threshold          = "Thresholds",
  annual_phenology          = "Annual Phenology"
)

# Build presets from the package's preset_scenarios() function
.build_shiny_presets <- function() {
  scenarios <- preset_scenarios()
  presets <- list("Baseline" = NULL)
  for (sc in scenarios) {
    presets[[sc$name]] <- sc$params
  }
  presets
}
PARAM_PRESETS <- .build_shiny_presets()

# Lookup table for preset descriptions
.build_preset_descriptions <- function() {
  descs <- list()
  for (sc in preset_scenarios()) {
    descs[[sc$name]] <- paste0(sc$description, " (Expected regime: ",
                                sc$expected_regime, "; Ref: ",
                                sc$manuscript_ref, ")")
  }
  descs
}
.PRESET_DESCRIPTIONS <- .build_preset_descriptions()

group_params <- function(reg) {
  groups <- list()
  for (nm in names(reg)) {
    meta <- reg[[nm]]
    key <- paste0(meta$module, "_", meta$category)
    label <- CATEGORY_LABELS[[key]]
    if (is.null(label)) label <- paste(meta$module, meta$category)
    if (is.null(groups[[label]])) groups[[label]] <- list()
    groups[[label]][[nm]] <- meta
  }
  groups
}

regime_color <- function(eq_class) {
  switch(eq_class,
    coexistence     = "#009E73",
    parasitoid_free = "#D55E00",
    canopy_only     = "#D55E00",
    trivial         = "#D55E00",
    "#E69F00"
  )
}

alert_div <- function(text, color) {
  bg <- paste0(color, "22")
  tags$div(
    style = sprintf(
      "border-left:5px solid %s; background:%s; padding:12px 16px; border-radius:4px; margin:10px 0;",
      color, bg
    ),
    tags$strong(style = sprintf("color:%s;", color), text)
  )
}

ews_alert_color <- function(level) {
  switch(level,
    green = "#009E73",
    yellow = "#E69F00",
    red = "#D55E00",
    "#999999")
}

mod_parameters_ui <- function(id) {
  ns <- NS(id)
  tabItem(tabName = "params",
    fluidRow(
      valueBoxOutput(ns("rp_box"), width = 4),
      box(width = 8, title = "Actions", status = "primary", solidHeader = TRUE,
        fluidRow(
          column(3, selectInput(ns("preset"), "Parameter Preset",
                                choices = names(PARAM_PRESETS), selected = "Baseline")),
          column(3, fileInput(ns("json_upload"), "Upload JSON", accept = ".json")),
          column(3,
            actionButton(ns("reset_params"), "Reset to Defaults", icon = icon("undo"),
                         class = "btn-warning", style = "margin-top:25px;"),
            actionButton(ns("load_calibrated"), "Load Calibrated", icon = icon("flask"),
                         class = "btn-info", style = "margin-top:25px;")
          ),
          column(3, downloadButton(ns("download_params"), "Download Parameters",
                                   style = "margin-top:25px;"))
        ),
        helpText("Select a preset scenario or upload a JSON file to quickly configure parameters.",
                 "Use 'Download Parameters' to save your current configuration."),
        uiOutput(ns("preset_desc"))
      )
    ),
    uiOutput(ns("param_sliders"))
  )
}

mod_parameters_server <- function(id, rv) {
  moduleServer(id, function(input, output, session) {
    reg <- param_registry()
    grouped <- group_params(reg)

    # Build slider UI from registry
    output$param_sliders <- renderUI({
      param_panels <- lapply(names(grouped), function(grp_label) {
        grp <- grouped[[grp_label]]
        sliders <- lapply(names(grp), function(nm) {
          meta <- grp[[nm]]
          val <- isolate(rv$params[[nm]])
          if (is.null(val)) val <- meta$default
          step <- (meta$max - meta$min) / 100
          sliderInput(
            inputId = session$ns(paste0("p_", nm)),
            label = tags$span(
              paste0(nm, " (", meta$symbol, ")"),
              tags$small(style = "color:#888;", paste0(" [", meta$unit, "]"))
            ),
            min = meta$min, max = meta$max, value = val, step = step,
            width = "100%"
          )
        })
        box(
          title = grp_label, status = "info", solidHeader = FALSE,
          collapsible = TRUE, collapsed = FALSE, width = 12,
          fluidRow(lapply(sliders, function(s) column(4, s))),
          tags$div(
            style = "font-size:11px; color:#999; padding:0 15px 5px;",
            lapply(names(grp), function(nm) {
              tags$p(tags$b(nm), ": ", grp[[nm]]$description)
            })
          )
        )
      })
      do.call(tagList, param_panels)
    })

    # Observe all param sliders
    observe({
      for (nm in names(reg)) {
        local({
          pnm <- nm
          val <- input[[paste0("p_", pnm)]]
          if (!is.null(val)) rv$params[[pnm]] <- val
        })
      }
    })

    # Preset description display
    output$preset_desc <- renderUI({
      preset_name <- input$preset
      desc <- .PRESET_DESCRIPTIONS[[preset_name]]
      if (is.null(desc)) return(NULL)
      tags$div(
        style = "border-left:4px solid #0072B2; background:#e8f4fd; padding:10px 14px; border-radius:4px; margin:8px 0; font-size:13px;",
        tags$strong(preset_name), tags$br(),
        desc
      )
    })

    # Preset selection
    observeEvent(input$preset, {
      preset_name <- input$preset
      if (preset_name == "Baseline") {
        defs <- default_params()
        for (nm in names(defs)) {
          rv$params[[nm]] <- defs[[nm]]
          updateSliderInput(session, paste0("p_", nm), value = defs[[nm]])
        }
        showNotification("Baseline parameters loaded.", type = "message")
      } else {
        preset_vals <- PARAM_PRESETS[[preset_name]]
        if (!is.null(preset_vals)) {
          # Start from defaults
          defs <- default_params()
          for (nm in names(defs)) {
            rv$params[[nm]] <- defs[[nm]]
            updateSliderInput(session, paste0("p_", nm), value = defs[[nm]])
          }
          # Apply preset overrides
          for (nm in names(preset_vals)) {
            rv$params[[nm]] <- preset_vals[[nm]]
            updateSliderInput(session, paste0("p_", nm), value = preset_vals[[nm]])
          }
          showNotification(paste0("Preset '", preset_name, "' loaded."), type = "message")
        }
      }
    }, ignoreInit = TRUE)

    # R_P value box
    output$rp_box <- renderValueBox({
      p <- as.list(rv$params)
      rp <- tryCatch(compute_RP(p), error = function(e) NA)
      color <- if (!is.na(rp) && rp > 1) "green" else "red"
      label <- if (!is.na(rp) && rp > 1) "Parasitoid can invade" else "Parasitoid cannot invade"
      valueBox(
        value = if (is.na(rp)) "N/A" else sprintf("%.4f", rp),
        subtitle = label,
        icon = icon("bug"),
        color = color
      )
    })

    # JSON upload
    observeEvent(input$json_upload, {
      req(input$json_upload)
      tryCatch({
        j <- fromJSON(input$json_upload$datapath)
        key_map <- c(K0 = "K_0", uP_max = "u_P_max", uC_max = "u_C_max",
                     uB_max = "u_B_max", Dcrit = "D_crit", Kmin = "K_min",
                     Bidx = "B_index", B_idx = "B_index")
        for (k in names(j)) {
          mapped <- if (k %in% names(key_map)) key_map[[k]] else k
          if (mapped %in% names(reg)) {
            rv$params[[mapped]] <- as.numeric(j[[k]])
            updateSliderInput(session, paste0("p_", mapped), value = as.numeric(j[[k]]))
          }
        }
        showNotification("Parameters loaded from JSON.", type = "message")
      }, error = function(e) {
        showNotification(paste("Error loading JSON:", e$message), type = "error")
      })
    })

    # Reset to defaults
    observeEvent(input$reset_params, {
      defs <- default_params()
      for (nm in names(defs)) {
        rv$params[[nm]] <- defs[[nm]]
        updateSliderInput(session, paste0("p_", nm), value = defs[[nm]])
      }
      updateSelectInput(session, "preset", selected = "Baseline")
      showNotification("Parameters reset to defaults.", type = "message")
    })

    # Load calibrated (with notification on failure)
    observeEvent(input$load_calibrated, {
      cal_path <- system.file("extdata", "baseline_params_calibrated.json",
                              package = "alder-ipm-sim")
      if (cal_path == "") {
        cal_path <- file.path(getwd(), "baseline_params_calibrated.json")
      }
      if (file.exists(cal_path)) {
        tryCatch({
          j <- fromJSON(cal_path)
          key_map <- c(K0 = "K_0", uP_max = "u_P_max", uC_max = "u_C_max",
                       uB_max = "u_B_max", Dcrit = "D_crit", Kmin = "K_min",
                       Bidx = "B_index", B_idx = "B_index")
          for (k in names(j)) {
            mapped <- if (k %in% names(key_map)) key_map[[k]] else k
            if (mapped %in% names(reg)) {
              rv$params[[mapped]] <- as.numeric(j[[k]])
              updateSliderInput(session, paste0("p_", mapped), value = as.numeric(j[[k]]))
            }
          }
          showNotification("Calibrated parameters loaded.", type = "message")
        }, error = function(e) {
          showNotification(paste("Failed to load calibrated parameters:", e$message),
                           type = "error", duration = 8)
        })
      } else {
        showNotification(
          paste("Calibrated parameter file not found. Searched:",
                system.file("extdata", package = "alder-ipm-sim"),
                "and", getwd()),
          type = "error", duration = 8
        )
      }
    })

    # Download params
    output$download_params <- downloadHandler(
      filename = function() paste0("alder-ipm-sim_params_", Sys.Date(), ".json"),
      content  = function(file) {
        write_json(as.list(rv$params), file, auto_unbox = TRUE, pretty = TRUE)
      }
    )
  })
}
