\name{validate_params}
\alias{validate_params}
\title{Validate Parameter Values Against Registry Bounds}
\description{
Check that each parameter value falls within the registered minimum and
maximum bounds. Issues warnings for out-of-range values.
}
\usage{
validate_params(params)
}
\arguments{
\item{params}{Named list or named numeric vector of parameter values.}
}
\value{
Character vector of warning messages (empty if all valid), returned
invisibly.
}
\examples{
params <- default_params()
params[["beta"]] <- 999
validate_params(params)
}
