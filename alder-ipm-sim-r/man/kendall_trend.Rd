\name{kendall_trend}
\alias{kendall_trend}
\title{Kendall Tau Trend Test for an EWS Indicator}
\description{
Compute Kendall's rank correlation between time and an early warning
signal indicator. A significantly positive tau for variance or
autocorrelation is the canonical test for critical slowing down.
}
\usage{
kendall_trend(indicator)
}
\arguments{
\item{indicator}{Numeric vector of a rolling EWS indicator.}
}
\value{
A list with components \code{tau} (numeric) and \code{p_value}
(numeric).
}
\examples{
result <- kendall_trend(cumsum(rnorm(30)))
result$tau
result$p_value
}
