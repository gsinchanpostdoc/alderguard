#' alder-ipm-sim: Decision Support for the Alnus-Beetle-Parasitoid-Bird Ecoepidemic System
#'
#' The \pkg{alder-ipm-sim} package provides a complete toolkit for simulating, fitting,
#' and analysing the hybrid seasonal-annual ecoepidemic model governing Alnus glutinosa
#' (European alder) forests attacked by Agelastica alni (alder leaf beetle), regulated
#' by Meigenia mutabilis (tachinid parasitoid) and generalist avian predators.
#'
#' @section Core Workflow:
#' \enumerate{
#'   \item \strong{Parameters}: Use \code{\link{param_registry}} and
#'     \code{\link{default_params}} to inspect and configure the 23 ecological parameters.
#'   \item \strong{Simulation}: Run multi-year projections with \code{\link{simulate}},
#'     or step through single years with \code{\link{annual_map}}.
#'   \item \strong{Equilibrium Analysis}: Find fixed points with
#'     \code{\link{find_fixed_points}} and classify stability via
#'     \code{\link{classify_stability}}.
#'   \item \strong{Early Warning Signals}: Detect critical slowing down using
#'     \code{\link{detect_warnings}} and \code{\link{compute_ews}}.
#'   \item \strong{Data Fitting}: Fit model parameters to field data with
#'     \code{\link{fit_model}} and forecast regimes with \code{\link{forecast_regime}}.
#'   \item \strong{Management}: Compare integrated pest management strategies with
#'     \code{\link{compare_strategies}} and check feasibility with
#'     \code{\link{feasibility_check}}.
#'   \item \strong{Interactive App}: Launch the Shiny dashboard with
#'     \code{\link{run_app}}.
#' }
#'
#' @section Key Metrics:
#' \describe{
#'   \item{R_P}{Parasitoid invasion reproduction number (\code{\link{compute_RP}}).
#'     R_P > 1 means the parasitoid can establish.}
#'   \item{R1}{Resistance -- how little the system deviates after perturbation
#'     (\code{\link{compute_R1}}).}
#'   \item{R2}{Resilience -- how quickly the system recovers from perturbation
#'     (\code{\link{compute_R2}}).}
#'   \item{rho*}{Spectral radius of the Jacobian at equilibrium. rho* < 1
#'     indicates local asymptotic stability.}
#' }
#'
#' @docType package
#' @name alder-ipm-sim-package
#' @aliases alder-ipm-sim
NULL
