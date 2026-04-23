# Eco-Epidemiologist Research Guide

This guide is for ecologists, mathematical biologists, and epidemiologists who want to understand the full model specification, fit it to field data, perform sensitivity analyses, and extend the framework.

---

## 1. Mathematical Model Description

AlderIPM-Sim implements a hybrid continuous-discrete dynamical system for the *Agelastica alni* (alder leaf beetle) -- *Meigenia mutabilis* (tachinid parasitoid) -- generalist avian predator interaction, coupled to canopy defoliation dynamics.

### 1.1 Within-Season Continuous Dynamics (Equations 1--4)

During the larval vulnerability window $[0, T]$ days, the system evolves according to four coupled ODEs:

**Susceptible (unparasitised) beetle larvae:**

$$\frac{dS}{dt} = -\frac{\beta S F}{1 + h S} - \frac{c_B B_t (S + I)}{1 + a_B (S + I)} - (\mu_S + u_C) S$$

**Parasitised beetle larvae:**

$$\frac{dI}{dt} = \frac{\beta S F}{1 + h S} - \frac{c_B B_t (S + I)}{1 + a_B (S + I)} - (\mu_I + \delta + u_C) I$$

**Adult parasitoid flies:**

$$\frac{dF}{dt} = \eta \delta I - \mu_F F + u_P$$

**Cumulative defoliation:**

$$\frac{dD}{dt} = \kappa (S + I)$$

where:
- The first term in dS/dt and dI/dt is a **Holling Type II functional response** for parasitism, with attack rate $\beta$ and handling time $h$
- The second term is a **Holling Type II generalist predation** response, with bird consumption rate $c_B$, half-saturation $a_B$, and bird abundance index $B_t = \rho \cdot B_\text{index}$
- $u_C$ is the direct larval removal control input (individuals/ha/day)
- $u_P$ is the parasitoid augmentation control input (individuals/ha/day)
- Non-negativity is enforced via clamping: $\max(0, \cdot)$ on all state derivatives when the corresponding state is at zero

**Initial conditions for each season:**

$$S(0) = A_t, \quad I(0) = 0, \quad F(0) = F_t, \quad D(0) = 0$$

### 1.2 Between-Season Discrete Map (Equations 5--8)

After integrating the within-season ODE to obtain terminal values $(S_T, I_T, F_T, D_T)$, the annual map updates:

**Beetle recruitment** (Beverton-Holt):

$$A_{t+1} = \frac{R_B \cdot \sigma_A \cdot S_T}{1 + \sigma_A \cdot S_T / K_t}$$

**Parasitoid carryover:**

$$F_{t+1} = \sigma_F \cdot F_T$$

**Carrying capacity feedback:**

$$K_{t+1} = K_0 \cdot \exp(-\phi \cdot D_T)$$

**Defoliation carryover:**

$$D_{t+1} = D_T$$

The Beverton-Holt form ensures density-dependent recruitment saturating at carrying capacity $K_t$, which itself declines exponentially with cumulative defoliation through the phytochemical defence feedback coefficient $\phi$.

### 1.3 Parasitoid Invasion Reproduction Number

The basic reproduction number for parasitoid establishment is:

$$R_P = \frac{\eta \delta \beta A^*}{\mu_F (1 + h A^*) (\mu_I + \delta)}$$

where $A^*$ is the pest-only (parasitoid-free) equilibrium beetle density. When $R_P > 1$, parasitoids can invade and persist; when $R_P < 1$, the parasitoid population collapses and the system converges to the parasitoid-free equilibrium.

---

## 2. Equilibrium Analysis

### 2.1 Fixed Points

The `find_fixed_points()` method searches for fixed points of the annual map $\mathbf{x}_{t+1} = \mathbf{G}(\mathbf{x}_t)$ using `scipy.optimize.fsolve` from 24 initial conditions (20 Latin Hypercube samples + 4 special cases: trivial, high-pest, coexistence, parasitoid-dominated).

Fixed points are classified as:
- **Trivial**: $A^* < \epsilon$
- **Canopy only**: $F^* < \epsilon$ and $D^* < \epsilon$
- **Parasitoid-free**: $F^* < \epsilon$ (but $D^*$ may be large)
- **Coexistence**: all state variables present

### 2.2 Stability (Jacobian Eigenvalues)

Stability is assessed via the Jacobian $\mathbf{J}$ of the annual map, computed by finite differences. A fixed point is locally stable if $\max|\lambda_i| < 1$ (spectral radius less than unity).

### 2.3 Bifurcation Detection

The `detect_bifurcation()` method sweeps a parameter over a specified range and tracks:
- Number and type of fixed points
- Dominant eigenvalue crossing the unit circle
- Bifurcation classification: saddle-node (fold), transcritical, or Neimark-Sacker (discrete Hopf)

Key bifurcation parameters: $\phi$ (foliage feedback), $R_B$ (beetle fecundity), $\beta$ (parasitoid attack rate).

---

## 3. Parameter Estimation

### 3.1 Fitting Module

The `ModelFitter` class supports three optimization backends:

| Method | Algorithm | Use case |
|--------|-----------|----------|
| `least_squares` | Trust Region Reflective (TRF) | Fast local optimization; good when starting near the minimum |
| `differential_evolution` | Stochastic global search | Robust to multimodality; slower but finds global minimum |
| `dual` | DE followed by TRF refinement | Best overall: global search + local convergence |

**Default identifiable parameter subset:** `[beta, mu_S, delta, R_B, phi, kappa]`

These six parameters were selected based on structural identifiability analysis (see Section 3.2). Other parameters are held at literature values or require independent estimation from targeted experiments.

### 3.2 Profile Likelihood and Identifiability

```python
from alder_ipm_sim.fitting import ModelFitter

fitter = ModelFitter()
fitter.prepare_data(df, timestep="annual")
result = fitter.fit(method="dual")

# Profile likelihood for a single parameter
profile = fitter.profile_likelihood(
    fitted_params=result.fitted_params,
    profile_param="phi",
    n_points=50
)
```

The `profile_likelihood()` method fixes one parameter at $n$ values across its feasible range and re-optimises all remaining identifiable parameters. A well-identified parameter produces a profile with a clear, sharp minimum. Flat or multi-modal profiles indicate structural or practical non-identifiability.

**Confidence intervals** are computed from the Jacobian covariance matrix at the optimum (asymptotic 95% CI), reported in `result.confidence_intervals`.

### 3.3 Cross-Validation

```python
cv = fitter.cross_validate(n_folds=5)
# cv["fold_rmse"]: per-fold RMSE
# cv["reliability_score"]: 1 - mean(normalised_error)
```

Uses expanding-window temporal cross-validation: train on years $[0, k]$, predict year $k+1$.

---

## 4. Sensitivity Analysis (LHS-PRCC)

AlderIPM-Sim includes Latin Hypercube Sampling with Partial Rank Correlation Coefficients for global sensitivity analysis.

### 4.1 Running PRCC

Via the early warning module:

```python
from alder_ipm_sim.warnings import EarlyWarningDetector

detector = EarlyWarningDetector()
sensitive_params = detector.candidate_warning_parameters(
    model=model,
    n_samples=500,
    threshold_prcc=0.25,
    threshold_shift=0.2
)
```

This samples parameter space via LHS, runs the model for each sample, and computes PRCC of each parameter against key outputs (e.g., final defoliation $D^*$, dominant eigenvalue $|\lambda_1|$, regime class).

### 4.2 Interpreting PRCC Values

| |PRCC| | Interpretation |
|--------|----------------|
| > 0.5 | Strong influence; parameter drives model behaviour |
| 0.25 -- 0.5 | Moderate influence; worth including in analysis |
| < 0.25 | Weak influence; can be fixed at nominal value |

Sign indicates direction: positive PRCC means increasing the parameter increases the output.

---

## 5. Interpreting Bifurcation Diagrams

### 5.1 Parameter vs. Equilibrium State

A bifurcation diagram plots a bifurcation parameter (e.g., $\phi$) on the x-axis against the equilibrium values of a state variable on the y-axis. Key features:

- **Solid branches**: stable equilibria
- **Dashed branches**: unstable equilibria
- **Fold (saddle-node) point**: two branches collide and annihilate; the system jumps discontinuously to an alternative attractor
- **Transcritical point**: two branches exchange stability; no discontinuous jump

### 5.2 Eigenvalue Spectra

The dominant eigenvalue $|\lambda_1|$ of the annual-map Jacobian indicates:

| $|\lambda_1|$ | System behaviour |
|----------------|-----------------|
| $< 1$ | Locally stable; perturbations decay |
| $= 1$ | Bifurcation point (marginal stability) |
| $> 1$ | Unstable; perturbations grow |

Plot $|\lambda_1|$ vs. a bifurcation parameter to identify the critical parameter value at which the system transitions.

### 5.3 Practical Significance

The key management-relevant bifurcation is the **transcritical bifurcation in $\phi$**: when the foliage-feedback penalty exceeds a critical value $\phi_c$, the coexistence equilibrium loses stability and the system collapses to the parasitoid-free regime with runaway defoliation.

---

## 6. Extending the Model

### 6.1 Adding State Variables

To add a new state variable (e.g., egg density $E$):

1. Add the parameter(s) to `PARAM_REGISTRY` in `parameters.py`
2. Modify `within_season_rhs()` in `model.py`:
   - Extend the state vector unpacking from `S, I, F, D = y` to `S, I, F, D, E = y`
   - Add the new ODE: `dE = ...`
   - Return the extended derivative vector
3. Update `integrate_season()` initial conditions (`y0`)
4. Update `annual_map()` to handle the new state in the between-season transition
5. Update `find_fixed_points()` search dimensions and classification logic

### 6.2 Alternative Functional Responses

**Replacing Holling Type II with linear (mass-action) parasitism:**

In `within_season_rhs()`, change:

```python
# Holling II
parasitism = beta * S * F / (1.0 + h * S)

# Linear (mass-action)
parasitism = beta * S * F
```

This removes the saturating effect of handling time. Appropriate when parasitoid search time dominates and handler interference is negligible.

**Replacing Holling Type II with Beddington-DeAngelis:**

```python
# Add parameter 'm' (mutual interference) to PARAM_REGISTRY
parasitism = beta * S * F / (1.0 + h * S + m * F)
```

This adds parasitoid mutual interference, relevant when parasitoid density is high enough for conspecific encounters to reduce search efficiency.

### 6.3 Swapping Beverton-Holt for Ricker Recruitment

In `annual_map()`, replace:

```python
# Beverton-Holt
A_next = R_B * sigma_A * S_T / (1.0 + sigma_A * S_T / K_t)

# Ricker
A_next = R_B * sigma_A * S_T * np.exp(-sigma_A * S_T / K_t)
```

The Ricker model can produce overcompensatory dynamics (oscillations and chaos at high $R_B$), while Beverton-Holt always converges monotonically. Choose based on the biological system: Beverton-Holt for contest competition, Ricker for scramble competition.

### 6.4 Structural Robustness Testing

To systematically test robustness to model structure:

1. Implement both functional forms as options (e.g., `recruitment_type="beverton_holt"` or `"ricker"`)
2. Fit both variants to your data using `ModelFitter`
3. Compare AIC/BIC for model selection
4. Check whether the qualitative bifurcation structure (number and type of equilibria) is preserved

---

## 7. Integration Method Details

- ODE solver: `scipy.integrate.solve_ivp` with RK45 (explicit Runge-Kutta 4(5))
- Relative tolerance: $10^{-8}$
- Absolute tolerance: $10^{-10}$
- Dense output enabled for interpolation
- Fixed-point search: `scipy.optimize.fsolve` (hybrid Powell method)
- Optimisation: `scipy.optimize.least_squares` (TRF), `scipy.optimize.differential_evolution`

---

## 8. Citation

If you use AlderIPM-Sim in your research, please cite:

> [Authors]. Ecological dynamics and pest management of alder leaf beetle: a coupled within-season and annual modelling framework with early warning signals and optimal control. [Journal], [Year]. DOI: [pending]

BibTeX:

```bibtex
@article{alderipmsim2026,
  title={Ecological dynamics and pest management of alder leaf beetle:
         a coupled within-season and annual modelling framework with
         early warning signals and optimal control},
  author={[Authors]},
  journal={[Journal]},
  year={2026},
  note={Manuscript under review}
}
```

Software citation:

```bibtex
@software{alderipmsim_software,
  title={AlderIPM-Sim: Pest--Tree--Bird Interaction Modelling Toolkit},
  version={0.1.0},
  url={https://github.com/[repo]},
  year={2026}
}
```
