\name{simulate}
\alias{simulate}
\title{Multi-Year Simulation of the Annual Map}
\description{
Run the annual map for multiple years, recording the state trajectory
(beetle density, parasitoid density, carrying capacity, defoliation)
at each annual step.
}
\usage{
simulate(params, A0, F0, K0, D0, n_years)
}
\arguments{
\item{params}{Named list of parameters.}
\item{A0}{Initial adult beetle density.}
\item{F0}{Initial parasitoid fly density.}
\item{K0}{Initial carrying capacity.}
\item{D0}{Initial defoliation.}
\item{n_years}{Number of annual cycles to simulate.}
}
\value{
A data.frame with columns: \code{year}, \code{A}, \code{F}, \code{K},
\code{D}.
}
\examples{
params <- as.list(default_params())
params$u_C <- 0
params$u_P <- 0
traj <- simulate(params, A0 = 0.8, F0 = 0.1, K0 = 1.712, D0 = 0, n_years = 10)
plot(traj$year, traj$A, type = "l", xlab = "Year", ylab = "Beetle density")
}
