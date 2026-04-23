\name{forecast_regime}
\alias{forecast_regime}
\title{Forecast Regime Class from Fitted Parameters}
\description{
Classify the long-term equilibrium regime implied by fitted parameter
values. Computes R_P and the spectral radius, and returns a
plain-language interpretation.
}
\usage{
forecast_regime(fit_result)
}
\arguments{
\item{fit_result}{List returned by \code{\link{fit_model}}.}
}
\value{
A list with components: \code{equilibrium_class} (character),
\code{R_P} (numeric), \code{rho_star} (numeric), and
\code{interpretation} (character string).
}
\examples{
\dontrun{
fit <- fit_model(prepared, fit_params = c("beta", "phi"))
regime <- forecast_regime(fit)
cat(regime$interpretation)
}
}
