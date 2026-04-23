# Conservation Planner Guide

This guide is for conservation planners and land managers who need to assess regime shift risk, plan long-term management strategies, and adapt those strategies as new monitoring data arrives.

---

## 1. Assessing Regime Shift Risk for a Specific Forest Site

A **regime shift** occurs when the beetle-parasitoid-tree system crosses a tipping point and moves from a controlled state (coexistence, where parasitoids and birds keep beetle populations in check) to an uncontrolled state (parasitoid-free, where beetles defoliate the canopy unchecked).

### Step 1: Gather site data

Collect as much of the following as possible:

| Data type | Minimum requirement | Ideal |
|-----------|-------------------|-------|
| Beetle density | 3+ years annual counts | 5--10+ years, seasonal within-year samples |
| Defoliation | Visual canopy assessments | Quantitative measurements (fraction 0--1) |
| Parasitoid density | Not required | Trap data, even intermittent |
| Bird abundance | Regional index (PECBMS or equivalent) | Site-specific point count surveys |

### Step 2: Fit the model to your site

```bash
alder-ipm-sim fit --data my_site.csv --time-col year --state-cols beetle_density,defoliation \
    --fit-params beta,mu_S,delta,R_B,phi,kappa --timestep annual --output fitted.json
```

Or use the Streamlit app: go to the **Data Fitting** tab, upload your CSV, select the identifiable parameters, and click "Fit Model."

This calibrates the model to your site's specific ecology, giving you site-specific parameter estimates rather than literature defaults.

### Step 3: Check the equilibrium analysis

```bash
alder-ipm-sim equilibrium --params fitted.json --verbose
```

Look for:
- **How many equilibria exist?** If only one (coexistence), your system has a single attractor and is relatively safe. If two or more coexist (e.g., coexistence + parasitoid-free), a regime shift is possible.
- **R_P value**: The parasitoid invasion number. If R_P is close to 1.0 from above, the system is near the tipping point where parasitoids can no longer persist.
- **Dominant eigenvalue**: Values close to 1.0 indicate slow recovery from perturbations (reduced resilience).

### Step 4: Run early warning analysis

```bash
alder-ipm-sim warn --data my_site.csv --column beetle_density --window 3
```

The traffic-light alert system tells you whether statistical signatures of an approaching tipping point are present in your data. See the [Forest Manager Guide](user_guide_managers.md) for how to interpret GREEN / YELLOW / RED alerts.

### Interpreting regime shift risk

| Indicator | Low risk | Medium risk | High risk |
|-----------|----------|-------------|-----------|
| R_P | > 2.0 | 1.0 -- 2.0 | < 1.5 and declining |
| Dominant eigenvalue | < 0.7 | 0.7 -- 0.9 | > 0.9 |
| Early warning alert | GREEN | YELLOW | RED |
| Number of equilibria | 1 (coexistence) | 2 (bistable) | 1 (parasitoid-free only) |

---

## 2. Incorporating Climate Projections

Climate change affects the beetle-parasitoid-tree system primarily through two mechanisms:

1. **Phenological shifts**: Warmer temperatures extend the larval season and alter parasitoid-host synchrony
2. **Overwinter survival**: Milder winters increase beetle survival; effects on parasitoid survival are less clear

### Mapping climate scenarios to parameters

| Climate scenario | Parameter changes | Rationale |
|-----------------|-------------------|-----------|
| **Warmer springs** (+2C) | T: 50 -> 60 days; sigma_A: +10% | Longer larval window; more beetles survive mild winters |
| **Warmer springs** (+4C) | T: 50 -> 70 days; sigma_A: +15%; mu_F: +20% | Extended season; parasitoid adults may desiccate faster in heat |
| **Drier summers** | mu_S: +30%; kappa: -10% | More larval desiccation; reduced feeding rate on stressed foliage |
| **Phenological mismatch** | beta: -30%; eta: -20% | Parasitoids emerge too early/late relative to host larvae; reduced conversion efficiency |

### Running climate scenario analysis

1. Create parameter files for each scenario:

```json
{
  "T": 60,
  "sigma_A": 0.859,
  "comment": "RCP4.5 mid-century scenario"
}
```

2. Run the equilibrium and control analysis for each:

```bash
alder-ipm-sim equilibrium --params scenario_rcp45.json --verbose
alder-ipm-sim control --params scenario_rcp45.json --years 30
```

3. Compare: Does the regime shift risk increase under warming? Does the recommended management strategy change?

---

## 3. Evaluating Long-Term Management Costs vs. Ecological Outcomes

### Cost-effectiveness analysis

The control optimizer computes a total cost functional that balances:

| Cost component | Weight | Meaning |
|----------------|--------|---------|
| Defoliation damage (w_D) | 10.0 | Ecological cost of canopy loss (ecosystem services, biodiversity, timber value) |
| Pest density (w_S) | 1.0 | Direct cost of beetle presence (aesthetic, secondary pest risk) |
| Terminal defoliation (w_T) | 5.0 | Cost of end-of-season damage (determines next year's carrying capacity) |
| Parasitoid releases (c_P) | 2.0 | Per-unit cost of rearing and releasing parasitoids |
| Direct removal (c_C) | 5.0 | Per-unit cost of mechanical collection or Bt application |
| Bird habitat (c_B) | 3.0 | Annual cost of nest boxes, hedgerow maintenance |

### Adjusting cost weights for your context

The default weights reflect a balanced ecological-economic perspective. Adjust them to match your priorities:

- **Timber-focused management**: Increase w_D (defoliation cost is primary concern)
- **Biodiversity-focused conservation**: Decrease c_B (bird habitat investment has co-benefits you value beyond pest control)
- **Budget-constrained sites**: Increase c_P, c_C, c_B to penalise expensive interventions more heavily
- **High-value riparian buffer**: Increase w_T (terminal cost) because canopy loss has downstream consequences for water quality and bank stability

### Comparing strategies over different time horizons

Run the control comparison with different planning horizons:

```bash
alder-ipm-sim control --params fitted.json --years 10
alder-ipm-sim control --params fitted.json --years 30
alder-ipm-sim control --params fitted.json --years 50
```

Short-horizon analysis (10 years) favours cheaper strategies. Long-horizon analysis (50 years) may favour more expensive strategies that build lasting resilience (e.g., bird habitat enhancement pays off over decades).

---

## 4. Interpreting Basin Stability Results

### What is basin stability?

Basin stability measures the probability that the system reaches a particular equilibrium when started from a random initial condition. Unlike local stability (eigenvalue analysis), basin stability accounts for the full nonlinear dynamics and tells you how robust each regime is to large perturbations.

- **Basin stability of coexistence = 0.85** means that 85% of random initial conditions converge to the coexistence equilibrium. The system is robust.
- **Basin stability of coexistence = 0.45** means the system is near a 50/50 tipping point. Small disturbances (drought, windthrow, management lapse) could push it into the parasitoid-free regime.

### Practical interpretation

| Coexistence basin stability | Risk level | Management implication |
|-----------------------------|------------|----------------------|
| > 0.8 | Low | System is resilient. Routine monitoring sufficient. |
| 0.5 -- 0.8 | Moderate | System is sensitive to perturbations. Proactive management recommended. |
| 0.2 -- 0.5 | High | System is near a tipping point. Active intervention needed. |
| < 0.2 | Critical | Coexistence regime is nearly inaccessible. Aggressive restoration required. |

### How perturbations map to initial conditions

In practice, "random initial conditions" correspond to different disturbance scenarios:

- **High A, low F**: Beetle outbreak after parasitoid population crash (e.g., harsh winter, pesticide drift)
- **Low A, high F**: Strong biological control; transient after successful parasitoid augmentation
- **High D**: Legacy defoliation from previous years; reduced carrying capacity
- **Low K**: Degraded site quality from compounding damage

Basin stability tells you: given where your system could plausibly end up after a shock, how likely is it to return to the good state?

---

## 5. Adaptive Management: Annual Re-fitting

Ecological systems change over time. Parameters that were accurate last year may not hold this year due to weather variation, land-use change, or management effects. AlderIPM-Sim supports an annual adaptive management cycle.

### Annual workflow

```
Year N: Collect field data (beetle counts, defoliation, parasitoid traps, bird surveys)
  |
  v
Update your CSV with the new year's data
  |
  v
Re-fit the model:
  alder-ipm-sim fit --data updated_site.csv --timestep annual --output fitted_yearN.json
  |
  v
Compare fitted parameters to previous years:
  - Is phi increasing? (canopy feedback strengthening -> higher risk)
  - Is beta decreasing? (parasitoid effectiveness declining -> phenological mismatch?)
  - Is R_B increasing? (beetle fecundity rising -> warmer conditions?)
  |
  v
Run equilibrium and early warning analysis with updated parameters
  |
  v
Adjust management strategy if alert level or recommended strategy has changed
  |
  v
Implement management actions for the upcoming season
  |
  v
Repeat next year
```

### Tracking parameter trends

Maintain a record of fitted parameter values over time:

| Year | beta | phi | R_B | R_P | Alert | Strategy |
|------|------|-----|-----|-----|-------|----------|
| 2021 | 0.031 | 0.035 | 8.5 | 2.3 | GREEN | None |
| 2022 | 0.029 | 0.038 | 9.0 | 2.0 | GREEN | None |
| 2023 | 0.027 | 0.042 | 9.8 | 1.6 | YELLOW | A |
| 2024 | 0.025 | 0.048 | 10.2 | 1.3 | YELLOW | B |
| 2025 | 0.022 | 0.055 | 10.5 | 1.1 | RED | C |

This table reveals trends: declining parasitoid effectiveness (beta), strengthening canopy feedback (phi), and increasing beetle fecundity (R_B) are driving the system toward a tipping point.

### When to escalate

Escalate your management response when:

1. **R_P drops below 1.5** and is trending downward
2. **Alert level upgrades** from GREEN to YELLOW, or YELLOW to RED
3. **Fitted phi exceeds 0.06** (strong canopy feedback creating a positive defoliation spiral)
4. **The recommended strategy changes** from A to B, or B to C
5. **Cross-validation reliability drops below 0.7** (model may need structural revision; consult the research guide)

### Incorporating management effectiveness data

After implementing a strategy, track its effectiveness:

- Did beetle density decline as predicted?
- Did parasitoid density increase after augmentation releases?
- Did bird abundance increase after nest box installation?

If observed outcomes diverge from predictions, the model may need recalibration or structural modification. Consult the [Research Guide](user_guide_researchers.md) for guidance on model extension.

---

## 6. Multi-Site Planning

For landscape-level conservation planning across multiple forest sites:

1. **Fit each site independently** -- parameter values vary with local conditions
2. **Compare regime shift risk** across sites to prioritise intervention
3. **Allocate management budgets** to sites with the highest risk and highest conservation value
4. **Consider connectivity** -- parasitoid dispersal between nearby sites can provide natural insurance. Sites near source populations of parasitoids may have lower augmentation needs.

### Prioritisation matrix

| Site | Conservation value | Regime shift risk | Priority |
|------|-------------------|-------------------|----------|
| A | High (riparian buffer) | High (RED alert) | Immediate action |
| B | High (protected area) | Low (GREEN) | Monitor |
| C | Medium (production forest) | High (RED) | Cost-benefit analysis |
| D | Low (degraded) | High (RED) | Consider if restoration is feasible |
