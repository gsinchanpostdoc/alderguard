# Data Format Specification

This document specifies the CSV data formats accepted by AlderIPM-Sim for model fitting, early warning analysis, and simulation validation.

---

## 1. Annual Monitoring Data

Use this format for between-year population surveys (one row per year).

### Required columns

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `year` | integer | calendar year | Observation year. Must be strictly increasing. |
| `beetle_density` | float | individuals / ha | Mean density of *Agelastica alni* beetle larvae per hectare. |

### Optional columns

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `parasitoid_density` | float | individuals / ha | Density of *Meigenia mutabilis* adult flies, estimated from trap catches scaled to per-hectare. |
| `defoliation` | float | fraction, 0.0 -- 1.0 | Fraction of canopy area lost to beetle feeding. 0.0 = no damage, 1.0 = complete defoliation. |
| `carrying_capacity` | float | relative units, 0.0 -- 2.0 | Site quality index derived from canopy cover or foliage biomass. Default baseline K_0 = 1.712. |

### Example: `annual_data.csv`

```csv
year,beetle_density,parasitoid_density,defoliation
2018,95,12,0.05
2019,130,18,0.08
2020,210,22,0.14
2021,185,25,0.11
2022,310,20,0.22
2023,480,15,0.35
2024,620,10,0.41
```

### Column mapping

When loading data, AlderIPM-Sim maps columns to internal state variables:

| CSV column | Internal variable | Symbol |
|------------|------------------|--------|
| `beetle_density` | A (annual beetle recruitment) | $A_t$ |
| `parasitoid_density` | F (parasitoid fly density) | $F_t$ |
| `defoliation` | D (cumulative defoliation) | $D_t$ |
| `carrying_capacity` | K (site carrying capacity) | $K_t$ |

You can override these mappings using the `--state-cols` CLI argument or the `state_columns` parameter in `prepare_data()`.

---

## 2. Seasonal (Within-Year) Monitoring Data

Use this format for within-season larval surveys (multiple observations during the spring-summer vulnerability window).

### Required columns

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `day` | float | days from season start | Day within the larval season. Day 0 = start of larval activity (typically early May in Central Europe). Must be strictly increasing. |
| `S` | float | individuals / ha | Density of susceptible (unparasitised) beetle larvae. |

### Optional columns

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `I` | float | individuals / ha | Density of parasitised beetle larvae. Distinguishable by dissection or rearing. |
| `F` | float | individuals / ha | Density of adult parasitoid flies, from sweep-net or sticky-trap sampling. |
| `D` | float | fraction, 0.0 -- 1.0 | Cumulative defoliation at this point in the season. |

### Example: `seasonal_data.csv`

```csv
day,S,I,F,D
0,200,0,15,0.00
7,185,12,14,0.02
14,160,28,16,0.05
21,130,40,20,0.09
28,95,45,25,0.13
35,65,38,28,0.16
42,40,25,22,0.18
49,22,12,15,0.19
```

---

## 3. Units Reference

| Measurement | Common field units | Required AlderIPM-Sim units | Conversion |
|-------------|-------------------|--------------------------|------------|
| Beetle larvae | count per tree | individuals / ha | Multiply by stem density (trees/ha) |
| Beetle larvae | count per branch | individuals / ha | Multiply by branches/tree x trees/ha |
| Parasitoid flies | trap catch per trap-day | individuals / ha | Multiply by trapping efficiency factor and area correction |
| Defoliation | percent canopy loss | fraction 0--1 | Divide by 100 |
| Defoliation | leaf area index (LAI) | fraction 0--1 | (LAI_max - LAI_current) / LAI_max |
| Carrying capacity | canopy cover (%) | relative units | Divide by max canopy cover, multiply by K_0 |
| Time (annual) | calendar year | calendar year | No conversion |
| Time (seasonal) | calendar date | days from season start | Subtract the date of first larval observation |

---

## 4. Handling Missing Data

### Missing years (annual data)

If you are missing data for some years, **do not include empty rows or fill with zeros**. Simply omit the missing years. The fitting algorithm handles irregular time spacing.

```csv
year,beetle_density,defoliation
2018,95,0.05
2019,130,0.08
2021,185,0.11
2023,480,0.35
```

Note: Years 2020 and 2022 are missing. The model will still fit, though accuracy improves with more complete series.

### Missing columns (partial observations)

If you only have beetle counts and not parasitoid or defoliation data, include only the columns you have:

```csv
year,beetle_density
2018,95
2019,130
2020,210
2021,185
```

The fitting algorithm uses only the available state variables for the residual computation.

### Missing values within a column

**NaN or blank values within a column are not supported.** If a column is present, every row must have a valid numeric value. If you have intermittent observations for a variable, either:

1. Omit that column entirely and fit without it, or
2. Interpolate the missing values before loading (linear interpolation is acceptable for small gaps), or
3. Split your data into contiguous segments and fit each separately

---

## 5. Data Quality Checklist

Before loading your data, verify:

- [ ] Time column (`year` or `day`) is strictly increasing (no duplicates, no decreasing values)
- [ ] No NaN, blank, or non-numeric values in any column
- [ ] Beetle density values are positive (> 0); zero counts should be recorded as a small positive number (e.g., 0.1) to avoid numerical issues
- [ ] Defoliation values are in the range [0, 1], not [0, 100]
- [ ] Units match the specification above (individuals/ha, not individuals/tree)
- [ ] At least 3 data points for annual fitting, 5+ recommended
- [ ] At least 5 data points for early warning analysis, 10+ recommended
- [ ] Column names match exactly (case-sensitive): `year`, `beetle_density`, `parasitoid_density`, `defoliation`, `carrying_capacity`, `day`, `S`, `I`, `F`, `D`

---

## 6. Loading Data

### Command line

```bash
# Annual data fitting
alder-ipm-sim fit --data annual_data.csv --timestep annual

# Seasonal data fitting
alder-ipm-sim fit --data seasonal_data.csv --timestep seasonal

# Early warning analysis
alder-ipm-sim warn --data annual_data.csv --column beetle_density
```

### Python API

```python
import pandas as pd
from alder_ipm_sim.fitting import ModelFitter

df = pd.read_csv("annual_data.csv")
fitter = ModelFitter()
fitter.prepare_data(df, timestep="annual")
result = fitter.fit(method="dual")
```

### Streamlit app

Navigate to the **Data Fitting** tab and use the file uploader to select your CSV file. The app auto-detects the timestep based on column names (`year` = annual, `day` = seasonal).

### R package

```r
library(alderIPMSim)

df <- read.csv("annual_data.csv")
prepared <- prepare_data(df)
result <- fit_model(prepared, method = "optim")
```
