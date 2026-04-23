# Forest Manager Quick Start Guide

This guide is for forest managers and field practitioners who want to use AlderIPM-Sim to monitor alder leaf beetle (*Agelastica alni*) outbreaks and choose the best management response. No mathematical background is required.

---

## What Does AlderIPM-Sim Do?

AlderIPM-Sim is a decision-support tool that:

1. **Predicts beetle outbreaks** using your field data (beetle counts, defoliation surveys, parasitoid trapping, bird indices).
2. **Warns you early** when conditions are shifting toward an uncontrollable outbreak, using a traffic-light alert system (GREEN / YELLOW / RED).
3. **Compares management strategies** so you can pick the most cost-effective response before the canopy is lost.

Think of it as a weather forecast for your forest: it takes current measurements, runs them through an ecological model, and tells you what is likely to happen next -- and what you can do about it.

---

## Step-by-Step: Entering Your Field Data

AlderIPM-Sim accepts data as CSV files (comma-separated spreadsheets). You need at minimum one column of beetle density over time. More columns give better predictions.

### Annual monitoring data

Create a CSV file with these columns:

| Column | What to measure | Units | Required? |
|--------|----------------|-------|-----------|
| `year` | Calendar year | e.g. 2019, 2020 | Yes |
| `beetle_density` | Average beetle larvae per hectare | individuals / ha | Yes |
| `parasitoid_density` | Parasitoid flies caught in traps per hectare | individuals / ha | Optional |
| `defoliation` | Fraction of canopy lost | 0.0 to 1.0 | Optional |
| `carrying_capacity` | Site quality index (from canopy cover surveys) | relative (0-2) | Optional |

### Seasonal (within-year) monitoring data

If you sample more frequently during the spring-summer larval window:

| Column | What to measure | Units | Required? |
|--------|----------------|-------|-----------|
| `day` | Day of season (day 0 = start of larval activity) | days | Yes |
| `S` | Susceptible (unparasitised) larvae density | individuals / ha | Yes |
| `I` | Parasitised larvae density | individuals / ha | Optional |
| `F` | Adult parasitoid fly density | individuals / ha | Optional |
| `D` | Cumulative defoliation to date | 0.0 to 1.0 | Optional |

Save your file as e.g. `my_site_data.csv` and load it into the Streamlit app or pass it to the command line.

**Tip:** If your beetle counts are in larvae per tree rather than per hectare, multiply by your stem density (trees/ha) before entering.

---

## What Each Parameter Means (Plain Language)

AlderIPM-Sim uses 23 parameters. The defaults are calibrated from published field studies, but you can adjust them for your site. Here are the most important ones:

### How effectively natural enemies attack beetles

| Parameter | What it controls | Practical meaning |
|-----------|-----------------|-------------------|
| **beta** | Parasitoid attack rate | How aggressively parasitoid wasps attack beetle larvae. Higher values mean more effective biological control. |
| **h** | Parasitoid handling time | How long each parasitoid needs to attack one larva before moving on. Lower values mean faster, more efficient parasitoids. |
| **c_B** | Bird consumption rate | How quickly insectivorous birds eat beetle larvae. Higher values mean birds are more helpful. |
| **B_index** | Bird abundance index | How many insectivorous birds are in your area. Based on regional bird survey data. Higher is better for pest control. |

### How fast beetles and parasitoids die naturally

| Parameter | What it controls | Practical meaning |
|-----------|-----------------|-------------------|
| **mu_S** | Beetle background mortality | Fraction of healthy larvae that die each day from natural causes (weather, disease, starvation). |
| **mu_I** | Parasitised larva mortality | Fraction of parasitised larvae that die each day. Higher than mu_S because parasites weaken them. |
| **delta** | Parasitoid emergence kill rate | How quickly parasitoid larvae kill their beetle host by emerging. |
| **mu_F** | Parasitoid adult mortality | How quickly adult parasitoid flies die naturally. |

### Season timing and canopy damage

| Parameter | What it controls | Practical meaning |
|-----------|-----------------|-------------------|
| **T** | Larval season length | Number of days beetles are active as larvae (spring-summer window). Warmer climates = longer season. |
| **kappa** | Defoliation rate | How much canopy each larva eats per day. Higher values mean more destructive beetles. |
| **phi** | Canopy feedback strength | How strongly last year's damage reduces this year's tree quality. High phi means damage compounds over years. |

### Population dynamics between years

| Parameter | What it controls | Practical meaning |
|-----------|-----------------|-------------------|
| **R_B** | Beetle reproduction rate | Average number of offspring per surviving adult. Higher = faster population growth. |
| **sigma_A** | Beetle winter survival | Fraction of beetle pupae surviving through winter. Mild winters = higher survival. |
| **sigma_F** | Parasitoid winter survival | Fraction of parasitoid pupae surviving through winter. |
| **K_0** | Baseline site quality | Maximum beetle population your site can support when canopy is fully intact. |

### Management controls

| Parameter | What it controls | Practical meaning |
|-----------|-----------------|-------------------|
| **u_P_max** | Maximum parasitoid release rate | How many parasitoid flies you can release per hectare per day. |
| **u_C_max** | Maximum direct removal rate | How many larvae you can remove per hectare per day (mechanical collection or Bt application). |
| **u_B_max** | Maximum bird habitat effort | How much you can boost bird populations (nest boxes, hedgerow planting). |

---

## How to Read the Traffic-Light Early Warning System

AlderIPM-Sim monitors your time series data for statistical signatures of an approaching tipping point. The system tracks two key indicators:

- **Rising variance** -- the beetle population swings are getting wider
- **Rising autocorrelation** -- the population is slower to recover from each disturbance

### Alert levels

| Alert | Meaning | What to do |
|-------|---------|------------|
| **GREEN** | System is stable. No signs of approaching a tipping point. | Continue routine annual monitoring. No intervention needed. |
| **YELLOW** | One warning indicator is trending upward. The system may be losing resilience. | Increase monitoring frequency (e.g., move from annual to seasonal sampling). Review your management options. Prepare contingency plans. |
| **RED** | Both indicators are trending upward. The system is approaching a regime shift where natural enemies can no longer control the beetle. | Act now. Run the control comparison to identify the best strategy. Implement management actions before the next larval season. |

---

## How to Read the Management Strategy Comparison

AlderIPM-Sim evaluates three management strategies and recommends the most cost-effective one:

### Strategy A -- Parasitoid augmentation only
Release laboratory-reared parasitoid flies into the forest stand. Lowest cost, but only effective when beetle populations are moderate.

### Strategy B -- Parasitoid augmentation + bird habitat enhancement
Combine parasitoid releases with installing nest boxes and planting hedgerows to attract insectivorous birds. Medium cost, broader ecological benefit.

### Strategy C -- Full integrated control
Everything in Strategy B, plus direct removal of beetle larvae (mechanical collection or targeted Bt sprays). Highest cost, but most effective for severe outbreaks.

### Reading the comparison table

The tool shows you for each strategy:

| Column | What it means |
|--------|--------------|
| **Cost (J)** | Total management cost over the planning horizon. Lower is better. |
| **Final defoliation (D*)** | Predicted canopy damage at equilibrium. Below 0.5 (50%) is the safety target. |
| **Final carrying capacity (K*)** | Predicted site quality. Must stay above K_min (about 0.86) for the forest to sustain itself. |
| **Feasible?** | Does this strategy keep defoliation below critical threshold AND maintain carrying capacity? Only feasible strategies should be considered. |
| **Recommended** | The lowest-cost feasible strategy. If none are feasible, conditions may require more aggressive intervention or revised targets. |

---

## Decision Flowchart

Use this flowchart after running an analysis:

```
START: Load your field data and run the early warning analysis
  |
  v
Is the alert GREEN?
  |-- YES --> Continue routine monitoring. Re-check annually.
  |
  NO (YELLOW or RED)
  |
  v
Run the management strategy comparison
  |
  v
Is Strategy A feasible?
  |-- YES --> Is the alert YELLOW?
  |             |-- YES --> Implement Strategy A (parasitoid release only).
  |             |            Monitor more frequently.
  |             |-- NO (RED) --> Consider Strategy B for added resilience.
  |
  NO
  |
  v
Is Strategy B feasible?
  |-- YES --> Implement Strategy B:
  |            (1) Release parasitoid flies
  |            (2) Install bird nest boxes / plant hedgerows
  |
  NO
  |
  v
Is Strategy C feasible?
  |-- YES --> Implement Strategy C (all actions simultaneously):
  |            (1) Release parasitoid flies
  |            (2) Install bird nest boxes / plant hedgerows
  |            (3) Apply targeted mechanical removal or Bt sprays
  |
  NO
  |
  v
EMERGENCY: No standard strategy is sufficient.
  Consider: site-level canopy protection, expanded treatment area,
  or consulting regional forest health authorities.
```

---

## Example Workflow

### Scenario: Annual monitoring of an alder riparian corridor

**Step 1: Collect field data**

You have five years of annual beetle surveys:

```csv
year,beetle_density,defoliation
2021,120,0.08
2022,185,0.12
2023,310,0.22
2024,480,0.35
2025,620,0.41
```

Save this as `riparian_site.csv`.

**Step 2: Launch the tool**

Option A -- Web app:
```bash
streamlit run -m alder-ipm-sim.app
```
Then open your browser to the displayed URL.

Option B -- Command line:
```bash
alder-ipm-sim warn --data riparian_site.csv --column beetle_density --window 3
```

**Step 3: Check the early warning alert**

The tool reports:
- Variance trend: tau = 0.80 (p = 0.02) -- **significant increase**
- Autocorrelation trend: tau = 0.60 (p = 0.08) -- **marginal increase**
- Alert level: **YELLOW**

Interpretation: One indicator is rising. The beetle population is losing stability but has not yet crossed the tipping point.

**Step 4: Compare management strategies**

```bash
alder-ipm-sim control --params site_params.json --years 10
```

Results:

| Strategy | Cost | D* | K* | Feasible |
|----------|------|-----|-----|----------|
| A | 142 | 0.31 | 1.18 | Yes |
| B | 198 | 0.19 | 1.42 | Yes |
| C | 287 | 0.09 | 1.61 | Yes |

**Recommendation: Strategy A** (lowest cost that keeps defoliation below 50%).

**Step 5: Take action**

Begin parasitoid augmentation releases at the start of the next larval season. Increase monitoring to seasonal sampling to track the response.

**Step 6: Re-assess next year**

Load your updated data and re-run the analysis. If the alert upgrades to RED, escalate to Strategy B or C.

---

## Getting Help

- **Parameter tuning:** If you are unsure which parameters to adjust for your site, start with the defaults and use the fitting module to calibrate from your data.
- **Data format questions:** See `docs/data_format.md` for detailed CSV specifications.
- **Technical support:** Contact the development team or consult the researcher guide (`docs/user_guide_researchers.md`) for methodology details.
