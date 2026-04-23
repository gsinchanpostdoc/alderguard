#' @title Launch the AlderIPM-Sim Shiny Application
#' @description Start the interactive Shiny web dashboard for simulating,
#'   fitting, analysing early warnings, and evaluating management strategies
#'   for the Alnus-beetle-parasitoid-bird ecoepidemic system.
#'
#' @param port Integer port number (default 3838).
#' @param launch.browser Logical; open the app in the default browser
#'   (default \code{TRUE}).
#' @return Called for its side effect of launching the Shiny app. Returns
#'   invisibly.
#' @examples
#' \dontrun{
#' run_app()
#' }
#' @export
run_app <- function(port = 3838, launch.browser = TRUE) {
  if (!requireNamespace("shiny", quietly = TRUE))
    stop("Package 'shiny' is required. Install with install.packages('shiny').")
  app_dir <- system.file("shiny", package = "alder-ipm-sim")
  if (app_dir == "")
    stop("Could not find the Shiny app directory. Try re-installing 'alder-ipm-sim'.")
  shiny::runApp(app_dir, port = port, launch.browser = launch.browser)
}
