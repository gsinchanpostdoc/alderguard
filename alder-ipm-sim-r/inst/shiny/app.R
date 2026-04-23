# AlderIPM-Sim Shiny Application
# Modular dashboard for the Alnus-beetle-parasitoid-bird ecoepidemic system

library(shiny)
library(shinydashboard)
library(plotly)
library(DT)
library(jsonlite)
library(alderIPMSim)

# Source modules
source("mod_parameters.R", local = TRUE)
source("mod_simulation.R", local = TRUE)
source("mod_fitting.R", local = TRUE)
source("mod_warnings.R", local = TRUE)
source("mod_control.R", local = TRUE)
source("mod_bifurcation.R", local = TRUE)
source("mod_comparison.R", local = TRUE)

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

ui <- dashboardPage(
  skin = "green",
  dashboardHeader(title = "AlderIPM-Sim"),
  dashboardSidebar(
    sidebarMenu(
      id = "tabs",
      menuItem("Parameter Setup",      tabName = "params",     icon = icon("sliders-h")),
      menuItem("Simulation & Forecast", tabName = "simulation", icon = icon("chart-line")),
      menuItem("Data Fitting",          tabName = "fitting",    icon = icon("bullseye")),
      menuItem("Early Warning Signals", tabName = "ews",        icon = icon("exclamation-triangle")),
      menuItem("Management Strategies", tabName = "management", icon = icon("leaf")),
      menuItem("Bifurcation Analysis", tabName = "bifurcation", icon = icon("project-diagram")),
      menuItem("Scenario Comparison", tabName = "comparison", icon = icon("exchange-alt"))
    ),
    tags$hr(),
    downloadButton("export_report", "Export HTML Report", class = "btn-success btn-block",
                   style = "margin: 10px 15px; width: calc(100% - 30px);"),
    tags$hr(),
    tags$div(
      style = "padding:10px; font-size:12px; color:#aaa;",
      tags$p("Decision-support toolkit for the Alnus glutinosa beetle-parasitoid-bird system."),
      tags$p("Simulate, fit, detect early warnings, and evaluate management strategies."),
      tags$p(style = "margin-top:10px;", tags$em("Uses colorblind-safe Okabe-Ito palette."))
    )
  ),

  dashboardBody(
    tags$head(tags$style(HTML("
      .small-box .inner h3 { font-size: 28px; }
      .param-group { margin-bottom: 15px; }
      .ews-panel { padding: 10px; }
    "))),

    tabItems(
      mod_parameters_ui("params"),
      mod_simulation_ui("sim"),
      mod_fitting_ui("fit"),
      mod_warnings_ui("ews"),
      mod_control_ui("mgmt"),
      mod_bifurcation_ui("bif"),
      mod_comparison_ui("cmp")
    )
  )
)

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

server <- function(input, output, session) {
  # Shared reactive values across all modules
  rv <- reactiveValues(
    params         = default_params(),
    sim_result     = NULL,
    within_season  = NULL,
    fit_data       = NULL,
    fit_result     = NULL,
    fit_raw_df     = NULL,
    ews_data       = NULL,
    prcc_result    = NULL,
    mgmt_result    = NULL
  )

  # Call module servers
  mod_parameters_server("params", rv)
  mod_simulation_server("sim", rv)
  mod_fitting_server("fit", rv)
  mod_warnings_server("ews", rv)
  mod_control_server("mgmt", rv)
  mod_bifurcation_server("bif", rv)
  mod_comparison_server("cmp", rv)

  # Export HTML report handler
  output$export_report <- downloadHandler(
    filename = function() {
      paste0("alder-ipm-sim_report_", Sys.Date(), ".html")
    },
    content = function(file) {
      p <- rv$params
      sim <- rv$sim_result
      fps <- tryCatch(find_fixed_points(p), error = function(e) NULL)
      rp <- tryCatch(compute_RP(p), error = function(e) NULL)
      r1 <- tryCatch(compute_R1(p), error = function(e) NULL)
      r2 <- tryCatch(compute_R2(p), error = function(e) NULL)
      ews <- rv$ews_data
      mgmt <- rv$mgmt_result
      generate_report(
        params = p,
        sim_result = sim,
        fixed_points = fps,
        R_P = rp,
        R1 = r1,
        R2 = r2,
        ews_result = ews,
        control_results = mgmt,
        scenario_name = "Shiny Session",
        output_file = file
      )
    },
    contentType = "text/html"
  )
}

# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

shinyApp(ui = ui, server = server)
