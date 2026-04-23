/**
 * AlderIPM-Sim - Cross-language panels & supplementary analysis helpers.
 *
 * Provides:
 *   - openRPanel()      : renders a modal showing how to install the R package
 *                         (alder-ipm-sim-r in the monorepo) and gives a quick-start
 *                         snippet that mirrors the current web parameters.
 *   - openPythonPanel() : same for the Python package (alder-ipm-sim-py).
 *   - basinStability()  : Monte-Carlo fraction of initial conditions that
 *                         converge to each fixed point (mirrors model.basin_stability
 *                         in alder-ipm-sim-py).
 *
 * GitHub ownership is hard-coded to gsinchanpostdoc/alder-ipm-sim (monorepo with
 * alder-ipm-sim-py/, alder-ipm-sim-r/, alder-ipm-sim-web/ subfolders) per user request.
 */

const CrossLang = (function () {

  const REPO_OWNER = 'gsinchanpostdoc';
  const REPO_NAME = 'alder-ipm-sim';
  const REPO_URL = `https://github.com/${REPO_OWNER}/${REPO_NAME}`;

  // ───────────────────────────────────────────────── helpers ──
  function paramDict(keys, paramsObj) {
    // Return a JS object snapshot of only the keys that exist.
    const out = {};
    keys.forEach(k => { if (paramsObj[k] !== undefined) out[k] = paramsObj[k]; });
    return out;
  }

  function formatParamsForPython(p) {
    const lines = Object.keys(p).map(k => `    "${k}": ${Number(p[k]).toPrecision(6)}`);
    return `{\n${lines.join(',\n')}\n}`;
  }

  function formatParamsForR(p) {
    const lines = Object.keys(p).map(k => `    ${k} = ${Number(p[k]).toPrecision(6)}`);
    return `list(\n${lines.join(',\n')}\n  )`;
  }

  // ───────────────────────────────────────────────── modal chrome ──
  function openModal(title, bodyHTML) {
    closeModal();
    const overlay = document.createElement('div');
    overlay.className = 'cl-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', title);
    overlay.innerHTML = `
      <div class="cl-modal">
        <div class="cl-header">
          <h2>${title}</h2>
          <button class="cl-close" aria-label="Close">&times;</button>
        </div>
        <div class="cl-body">${bodyHTML}</div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('.cl-close').addEventListener('click', closeModal);
    overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
    // enable tabs inside the modal
    overlay.querySelectorAll('.cl-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        const tabId = btn.dataset.cltab;
        overlay.querySelectorAll('.cl-tab').forEach(b => b.classList.toggle('active', b === btn));
        overlay.querySelectorAll('.cl-panel').forEach(p => p.style.display = p.dataset.cltab === tabId ? 'block' : 'none');
      });
    });
    // wire copy buttons
    overlay.querySelectorAll('.cl-copy').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = overlay.querySelector(btn.dataset.copyTarget);
        if (target) {
          navigator.clipboard.writeText(target.innerText).then(() => {
            btn.textContent = 'Copied!';
            setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
          });
        }
      });
    });
    // Esc to close
    document.addEventListener('keydown', escClose);
  }

  function escClose(e) { if (e.key === 'Escape') closeModal(); }

  function closeModal() {
    const o = document.querySelector('.cl-overlay');
    if (o) o.remove();
    document.removeEventListener('keydown', escClose);
  }

  // ───────────────────────────────────────────────── Python panel ──
  function openPythonPanel(currentParams) {
    const keys = Object.keys(currentParams || {});
    const snapshot = paramDict(keys, currentParams || {});
    const paramBlock = formatParamsForPython(snapshot);

    const html = `
      <p class="cl-lede">
        Prefer a scriptable workflow? The same AlderIPM-Sim model is available as a
        Python 3 package with a CLI and a Streamlit dashboard, maintained at
        <a href="${REPO_URL}" target="_blank" rel="noopener">${REPO_OWNER}/${REPO_NAME}</a>.
      </p>

      <div class="cl-tabs">
        <button class="cl-tab active" data-cltab="py-install">1. Install</button>
        <button class="cl-tab" data-cltab="py-quickstart">2. Quick start</button>
        <button class="cl-tab" data-cltab="py-currentcfg">3. Use these parameters</button>
        <button class="cl-tab" data-cltab="py-cli">4. CLI</button>
      </div>

      <div class="cl-panel" data-cltab="py-install" style="display:block;">
        <h3>Install from GitHub (monorepo)</h3>
        <p>Requires Python 3.9 or newer.</p>
        <div class="cl-code-wrap">
          <button class="cl-copy" data-copy-target="#py-install-cmd">Copy</button>
          <pre id="py-install-cmd">pip install "git+https://github.com/${REPO_OWNER}/${REPO_NAME}.git#subdirectory=alder-ipm-sim-py"</pre>
        </div>
        <p>Or clone and install in editable mode with the Streamlit dashboard extras:</p>
        <div class="cl-code-wrap">
          <button class="cl-copy" data-copy-target="#py-install-dev">Copy</button>
<pre id="py-install-dev">git clone https://github.com/${REPO_OWNER}/${REPO_NAME}.git
cd ${REPO_NAME}/alder-ipm-sim-py
pip install -e ".[app,dev]"</pre>
        </div>
      </div>

      <div class="cl-panel" data-cltab="py-quickstart" style="display:none;">
        <h3>Reproduce the web app's simulation in Python</h3>
        <div class="cl-code-wrap">
          <button class="cl-copy" data-copy-target="#py-quick">Copy</button>
<pre id="py-quick">from alder_ipm_sim.model import AlderIPMSimModel

model = AlderIPMSimModel()                # uses default parameters
traj  = model.multi_year_sim(years=50)
print(f"Year 50 canopy K = {traj[-1]['K']:.3f}")
print(f"R_P             = {model.compute_R_P():.3f}")</pre>
        </div>
      </div>

      <div class="cl-panel" data-cltab="py-currentcfg" style="display:none;">
        <h3>Run the current web parameter set in Python</h3>
        <p>This snippet encodes exactly the parameters currently loaded in your browser:</p>
        <div class="cl-code-wrap">
          <button class="cl-copy" data-copy-target="#py-currentcfg-code">Copy</button>
<pre id="py-currentcfg-code">from alder_ipm_sim.model import AlderIPMSimModel

params = ${paramBlock}

model = AlderIPMSimModel(params=params)
traj  = model.multi_year_sim(years=50, A0=1.0, F0=0.5, K0=params["K_0"], D0=0.0)

# Equilibria and early warnings
eq = model.find_fixed_points()
print("Fixed points:", eq)

from alder_ipm_sim.warnings import EarlyWarningDetector
ewd = EarlyWarningDetector()
alert = ewd.detect_regime_shift([pt["A"] for pt in traj])
print("Alert level:", alert.level)</pre>
        </div>
      </div>

      <div class="cl-panel" data-cltab="py-cli" style="display:none;">
        <h3>Command-line interface</h3>
        <div class="cl-code-wrap">
          <button class="cl-copy" data-copy-target="#py-cli-code">Copy</button>
<pre id="py-cli-code">alder-ipm-sim simulate --years 50 --output trajectory.csv
alder-ipm-sim equilibrium --verbose
alder-ipm-sim fit --data field_data.csv --fit-params beta c_B phi
alder-ipm-sim warn --data canopy_series.csv --column K --window 15
alder-ipm-sim control --years 30
alder-ipm-sim dashboard               # opens the Streamlit UI</pre>
        </div>
        <p class="cl-hint">
          Full documentation lives in
          <a href="${REPO_URL}/tree/main/alder-ipm-sim-py#readme" target="_blank" rel="noopener">alder-ipm-sim-py/README.md</a>.
        </p>
      </div>
    `;

    openModal('Use AlderIPM-Sim in Python', html);
  }

  // ───────────────────────────────────────────────── R panel ──
  function openRPanel(currentParams) {
    const keys = Object.keys(currentParams || {});
    const snapshot = paramDict(keys, currentParams || {});
    const paramBlock = formatParamsForR(snapshot);

    const html = `
      <p class="cl-lede">
        Need to run AlderIPM-Sim inside R, Rmd, or a Shiny app? The R package
        mirrors every web-app capability and adds a Shiny dashboard. It lives
        alongside the Python package at
        <a href="${REPO_URL}" target="_blank" rel="noopener">${REPO_OWNER}/${REPO_NAME}</a>.
      </p>

      <div class="cl-tabs">
        <button class="cl-tab active" data-cltab="r-install">1. Install</button>
        <button class="cl-tab" data-cltab="r-quickstart">2. Quick start</button>
        <button class="cl-tab" data-cltab="r-currentcfg">3. Use these parameters</button>
        <button class="cl-tab" data-cltab="r-shiny">4. Shiny app</button>
      </div>

      <div class="cl-panel" data-cltab="r-install" style="display:block;">
        <h3>Install from GitHub (monorepo)</h3>
        <p>Requires R &ge; 4.1. The package lives in the <code>alder-ipm-sim-r/</code> subfolder, so use the <code>subdir</code> argument:</p>
        <div class="cl-code-wrap">
          <button class="cl-copy" data-copy-target="#r-install-cmd">Copy</button>
<pre id="r-install-cmd"># one-time:
install.packages("remotes")
remotes::install_github(
  "${REPO_OWNER}/${REPO_NAME}",
  subdir = "alder-ipm-sim-r"
)</pre>
        </div>
        <p>Or with <code>devtools</code>:</p>
        <div class="cl-code-wrap">
          <button class="cl-copy" data-copy-target="#r-install-dt">Copy</button>
<pre id="r-install-dt">devtools::install_github("${REPO_OWNER}/${REPO_NAME}", subdir = "alder-ipm-sim-r")</pre>
        </div>
      </div>

      <div class="cl-panel" data-cltab="r-quickstart" style="display:none;">
        <h3>Reproduce the web app's simulation in R</h3>
        <div class="cl-code-wrap">
          <button class="cl-copy" data-copy-target="#r-quick">Copy</button>
<pre id="r-quick">library(alderIPMSim)

params &lt;- as.list(default_params())
traj   &lt;- simulate(params, A0 = 1.0, F0 = 0.5, K0 = 1.712, D0 = 0, n_years = 50)
cat("R_P =", round(compute_RP(params), 3), "\n")

plot(traj$year, traj$A, type = "l",
     xlab = "Year", ylab = "Beetle density")</pre>
        </div>
      </div>

      <div class="cl-panel" data-cltab="r-currentcfg" style="display:none;">
        <h3>Run the current web parameter set in R</h3>
        <p>This snippet encodes exactly the parameters currently loaded in your browser:</p>
        <div class="cl-code-wrap">
          <button class="cl-copy" data-copy-target="#r-currentcfg-code">Copy</button>
<pre id="r-currentcfg-code">library(alderIPMSim)

params &lt;- ${paramBlock}

traj     &lt;- simulate(params, A0 = 1.0, F0 = 0.5, K0 = params$K_0, D0 = 0, n_years = 50)
eq       &lt;- find_fixed_points(params)
warnings &lt;- detect_warnings(traj$A)
cat("Alert level:", warnings$alert_level, "\n")</pre>
        </div>
      </div>

      <div class="cl-panel" data-cltab="r-shiny" style="display:none;">
        <h3>Launch the Shiny dashboard</h3>
        <div class="cl-code-wrap">
          <button class="cl-copy" data-copy-target="#r-shiny-code">Copy</button>
<pre id="r-shiny-code">library(alderIPMSim)
run_app()</pre>
        </div>
        <p class="cl-hint">
          Full documentation lives in
          <a href="${REPO_URL}/tree/main/alder-ipm-sim-r#readme" target="_blank" rel="noopener">alder-ipm-sim-r/README.md</a>.
        </p>
      </div>
    `;

    openModal('Use AlderIPM-Sim in R', html);
  }

  // ───────────────────────────────────────────────── basin stability ──
  /**
   * Monte-Carlo basin stability: sample n random initial conditions within
   * (A0 ∈ [0, 3·K0], F0 ∈ [0, 2], K0 fixed at params.K_0, D0 ∈ [0, 1])
   * and classify each trajectory's terminal regime after nYears. Returns
   * the fraction of the basin that flows to each regime.
   */
  function basinStability(params, nSamples, nYears) {
    nSamples = nSamples || 200;
    nYears = nYears || 80;
    const counts = {};
    const K0 = params.K_0 !== undefined ? params.K_0 : 1.712;

    function rand(a, b) { return a + Math.random() * (b - a); }

    for (let i = 0; i < nSamples; i++) {
      const A0 = rand(0, 3 * K0);
      const F0 = rand(0, 2);
      const D0 = rand(0, 0.5);
      const regime = FittingModule.forecastRegime(
        params, { A0, F0, K0, D0 }, nYears
      );
      const label = regime.label;
      counts[label] = counts[label] || { count: 0, color: regime.color };
      counts[label].count++;
    }
    const out = Object.keys(counts).map(label => ({
      label,
      fraction: counts[label].count / nSamples,
      color: counts[label].color
    }));
    out.sort((a, b) => b.fraction - a.fraction);
    return { nSamples, basins: out };
  }

  // ───────────────────────────────────────────────── public API ──
  return {
    REPO_OWNER,
    REPO_NAME,
    REPO_URL,
    openPythonPanel,
    openRPanel,
    closeModal,
    basinStability
  };

})();

if (typeof window !== 'undefined') window.CrossLang = CrossLang;
