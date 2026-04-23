\name{annual_map}
\alias{annual_map}
\title{One Step of the Annual Discrete Map}
\description{
Integrate the within-season ODE then apply Beverton-Holt recruitment,
overwinter survival, and carrying capacity update to produce the next
year's state.
}
\usage{
annual_map(params, A_t, F_t, K_t, D_t)
}
\arguments{
\item{params}{Named list of parameters.}
\item{A_t}{Adult beetle density entering the season.}
\item{F_t}{Parasitoid fly density entering the season.}
\item{K_t}{Current carrying capacity.}
\item{D_t}{Defoliation from previous year.}
}
\value{
A named list with components \code{A_next}, \code{F_next},
\code{K_next}, \code{D_next}, and \code{within_season} (trajectory
data.frame).
}
\examples{
params <- as.list(default_params())
params$u_C <- 0
params$u_P <- 0
res <- annual_map(params, A_t = 0.8, F_t = 0.1, K_t = 1.712, D_t = 0)
res$A_next
}
