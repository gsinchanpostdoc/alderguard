\name{compute_RP}
\alias{compute_RP}
\title{Parasitoid Invasion Reproduction Number R_P}
\description{
Compute the parasitoid invasion reproduction number R_P. If
\code{S_bar} is not provided, it is estimated by iterating the
parasitoid-free annual map to steady state.
}
\usage{
compute_RP(params, S_bar = NULL)
}
\arguments{
\item{params}{Named list of parameters.}
\item{S_bar}{Equilibrium susceptible beetle density. If \code{NULL},
  computed from the parasitoid-free equilibrium.}
}
\value{
Numeric scalar R_P. Values greater than 1 indicate the parasitoid
can invade and persist.
}
\examples{
params <- as.list(default_params())
params$u_C <- 0
params$u_P <- 0
R_P <- compute_RP(params)
cat("R_P =", round(R_P, 3), "\n")
}
