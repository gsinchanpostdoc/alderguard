\name{default_params}
\alias{default_params}
\title{Default Parameter Values}
\description{
Return a named numeric vector of default parameter values extracted from
the parameter registry.
}
\usage{
default_params()
}
\value{
A named numeric vector mapping parameter names to their default values.
}
\examples{
params <- default_params()
params[["beta"]]
params[["phi"]]
}
