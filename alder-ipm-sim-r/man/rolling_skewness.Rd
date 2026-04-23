\name{rolling_skewness}
\alias{rolling_skewness}
\title{Rolling Skewness of a Time Series}
\description{
Compute rolling-window skewness. Increased skewness can indicate
flickering between basins of attraction near a regime shift.
}
\usage{
rolling_skewness(ts, window = NULL)
}
\arguments{
\item{ts}{Numeric vector, the raw time series.}
\item{window}{Integer window size. If \code{NULL}, defaults to 50
  percent of series length.}
}
\value{
Numeric vector of rolling skewness values.
}
\examples{
rs <- rolling_skewness(rnorm(50), window = 10)
}
