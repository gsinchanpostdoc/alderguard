\name{detect_warnings}
\alias{detect_warnings}
\title{Full Early Warning Signal Detection Pipeline}
\description{
Detrend the time series, compute all rolling-window EWS indicators,
test each for an increasing trend via Kendall's tau, and assign a
traffic-light alert level (green / yellow / red) based on joint
significance.
}
\usage{
detect_warnings(ts, window = NULL, detrend = "gaussian",
                var_threshold = 0.3, ac_threshold = 0.3)
}
\arguments{
\item{ts}{Numeric vector, 1-D time series of a state variable
  (typically beetle density A_t).}
\item{window}{Integer window size. If \code{NULL}, defaults to 50
  percent of series length.}
\item{detrend}{Character detrending method (default \code{"gaussian"}).}
\item{var_threshold}{Numeric minimum Kendall tau to flag variance
  (default 0.3).}
\item{ac_threshold}{Numeric minimum Kendall tau to flag
  autocorrelation (default 0.3).}
}
\value{
A list with components: \code{indicators} (data.frame from
\code{\link{compute_ews}}), \code{kendall_results} (named list of
tau/p_value lists), \code{alert_level} (\code{"green"},
\code{"yellow"}, or \code{"red"}), and \code{interpretation}
(character string).
}
\examples{
\dontrun{
warnings <- detect_warnings(beetle_density_ts)
cat(warnings$interpretation)
}
}
