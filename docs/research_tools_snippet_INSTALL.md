# Embedding AlderIPM-Sim on `Profile/apps.html`

Three components as you requested — card at top, iframe below, subdomain queued for later.

## 1. Paste the snippet

Open <https://github.com/gsinchanpostdoc/Profile/blob/main/apps.html> in your browser. Click the pencil (*Edit this file*). Scroll to the location where you want AlderIPM-Sim to appear — recommended spot is **directly below the Forage Energy Meta-Database section**, before the page footer. Paste the contents of `docs/research_tools_snippet.html` (the file I just created) there.

Scroll to the bottom of the GitHub edit view, type a short commit message like `Add AlderIPM-Sim to Research Tools`, and click **Commit changes**. Your Research Tools page redeploys in ~60 seconds. Reload <https://gsinchanpostdoc.github.io/Profile/apps.html> with **Ctrl+F5** and the AlderIPM-Sim card appears with the full app embedded inline.

## 2. Why this works without configuration

Both your Profile site and AlderIPM-Sim live under the same domain (`gsinchanpostdoc.github.io`), so the iframe is **same-origin**. No CORS headers to set, no X-Frame-Options to worry about, no certificate mismatch. The Plotly CDN and Leaflet CDN loaded by AlderIPM-Sim also work from inside the iframe.

The card adopts your existing classes (`.tool-section`, `.badge--primary`, `.section-title`, `.btn--primary`), so it gets the same typography, spacing, and colour palette as the Scandinavian SDM and Forage Energy cards without any new CSS.

## 3. Card-only / iframe-only variants

If the iframe makes the page feel heavy, delete the `<div style="margin-top:28px; …"><iframe …></iframe></div>` block. The card with the two "Open Application" / "Source code" buttons stays. Visitors click *Open Application* and use AlderIPM-Sim in a fresh tab.

Conversely, if you want only the iframe (no card), delete the entire `<div class="tool-intro">…</div>` block.

## 4. Subdomain mirror (optional, later)

This step only becomes useful if you buy a custom domain (e.g. `sinchanghosh.com`). Until then, <https://gsinchanpostdoc.github.io/alder-ipm-sim/> is already a permanent URL.

When you do have a custom domain:

1. In your DNS provider's control panel, create a **CNAME** record:
   - Name: `alder-ipm-sim` (so the result is `alder-ipm-sim.sinchanghosh.com`)
   - Value: `gsinchanpostdoc.github.io`
   - TTL: 3600
2. In the AlderIPM-Sim repo, go to *Settings → Pages → Custom domain*. Type `alder-ipm-sim.sinchanghosh.com`. Save. Wait for GitHub to verify DNS (~10 min) and tick *Enforce HTTPS*.
3. Update the `href` and `src` values in the snippet from `https://gsinchanpostdoc.github.io/alder-ipm-sim/` to `https://alder-ipm-sim.sinchanghosh.com/` and recommit.

No other code changes are needed; the AlderIPM-Sim app is domain-agnostic.

## 5. Local preview before you commit

To see the card in place without touching the live site: clone the Profile repo, paste the snippet into `apps.html`, and open the file in your browser (`file:///C:/Users/sinch/OneDrive/Desktop/Profile/apps.html`). The iframe loads AlderIPM-Sim from the public URL, so a local Profile preview is enough to verify layout and spacing.
