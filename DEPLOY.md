# Deploying AlderIPM-Sim — step-by-step

This guide takes the contents of this folder, publishes it as the GitHub repo `gsinchanpostdoc/alder-ipm-sim`, serves the web app on GitHub Pages, and makes both the Python and R packages installable directly from the repository.

## 1. Create the GitHub repository

Either via the browser (<https://github.com/new>) or the `gh` CLI. Recommended name: **`alder-ipm-sim`**, owner **`gsinchanpostdoc`**, visibility **public**, no README / .gitignore / license auto-added (those already exist in this folder).

With the `gh` CLI:

```bash
gh repo create gsinchanpostdoc/alder-ipm-sim \
  --public \
  --description "AlderIPM-Sim: hybrid ecoepidemic toolkit (web app, Python package, R package)" \
  --homepage "https://gsinchanpostdoc.github.io/alder-ipm-sim/" \
  --disable-wiki
```

## 2. Initialise and push the monorepo

From inside this folder (`C:\Users\sinch\OneDrive\Desktop\pest-tree-bird` — or wherever it lives on your disk):

```bash
git init
git add .
git commit -m "Initial commit: web app, Python package, R package"
git branch -M main
git remote add origin https://github.com/gsinchanpostdoc/alder-ipm-sim.git
git push -u origin main
```

If the folder is already a git repo (it is — a `.git` directory is present), skip `git init` and adapt the remaining commands:

```bash
git add .
git commit -m "Publish monorepo: alder-ipm-sim-web + alder-ipm-sim-py + alder-ipm-sim-r"
git branch -M main
git remote add origin https://github.com/gsinchanpostdoc/alder-ipm-sim.git   # or: git remote set-url origin ...
git push -u origin main
```

## 3. Enable GitHub Pages

The repo already ships a Pages workflow at `.github/workflows/pages.yml` that deploys `alder-ipm-sim-web/` automatically on every push to `main`. One-time switch to turn it on:

1. Go to <https://github.com/gsinchanpostdoc/alder-ipm-sim/settings/pages>.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
3. Save. The first deploy will run automatically. Subsequent pushes to `main` that change anything under `alder-ipm-sim-web/` redeploy.

Within 1–2 minutes the live app is at:

> **<https://gsinchanpostdoc.github.io/alder-ipm-sim/>**

You can watch the deploy progress in the **Actions** tab.

## 4. Verify end-to-end

Once Pages is live, test the three install paths from a clean machine (or a fresh venv / R session):

### Web app

Open <https://gsinchanpostdoc.github.io/alder-ipm-sim/> and confirm the **Use in R** and **Use in Python** buttons in the header produce modals with install commands. Run a simulation and a parameter fit end-to-end.

### Python

```bash
pip install "git+https://github.com/gsinchanpostdoc/alder-ipm-sim.git#subdirectory=alder-ipm-sim-py"
python -c "from alder_ipm_sim.model import AlderIPMSimModel; print(AlderIPMSimModel().compute_R_P())"
```

### R

```r
install.packages("remotes")
remotes::install_github("gsinchanpostdoc/alder-ipm-sim", subdir = "alder-ipm-sim-r")
library(alderIPMSim)
compute_RP(as.list(default_params()))
```

## 5. Add the web app URL to your personal / lab site

Once live, embed the web app into your website either as (a) a direct link, (b) an `<iframe>`, or (c) a "Further research tools" card. Recommended link copy:

> **AlderIPM-Sim Web** — interactive decision-support tool for the *Alnus*–beetle–parasitoid–bird ecoepidemic model described in Ghosh et al. (2026). Runs entirely in your browser at <https://gsinchanpostdoc.github.io/alder-ipm-sim/>. Companion Python and R packages are available at <https://github.com/gsinchanpostdoc/alder-ipm-sim>.

An `<iframe>` embed example:

```html
<iframe src="https://gsinchanpostdoc.github.io/alder-ipm-sim/"
        width="100%" height="900"
        style="border:1px solid #ccc; border-radius:8px;"
        title="AlderIPM-Sim decision-support app"></iframe>
```

## 6. Maintenance

- Every push to `main` that touches `alder-ipm-sim-web/` redeploys the site automatically.
- For Python / R package version bumps, tag releases on GitHub. Users then install a specific version via:
  - `pip install "git+https://github.com/gsinchanpostdoc/alder-ipm-sim.git@v0.2.0#subdirectory=alder-ipm-sim-py"`
  - `remotes::install_github("gsinchanpostdoc/alder-ipm-sim@v0.2.0", subdir = "alder-ipm-sim-r")`
- To later publish to PyPI / CRAN, the monorepo layout stays unchanged; only the upload workflow changes.

## Troubleshooting

- **`git push` rejects with "remote has work you don't have"** — the repo was created with an initial commit. Run `git pull --rebase origin main` first.
- **Pages deploy works but the page is blank** — check the browser console for 404s on `js/*.js`. The workflow treats `alder-ipm-sim-web/` as the Pages root, so paths like `js/app.js` resolve correctly; absolute paths like `/js/app.js` would break.
- **`remotes::install_github` fails with "subdir not found"** — confirm `alder-ipm-sim-r/DESCRIPTION` is committed and that the `subdir` argument matches the folder name exactly (case-sensitive).
- **`pip install "git+...#subdirectory=alder-ipm-sim-py"` fails on older pip** — upgrade with `pip install -U pip`. The `#subdirectory=` spec needs pip ≥ 20.
