# Watchcat for VS Code

Watchcat adds a small status-bar companion to VS Code for the Alice & Bob
cat-qubit simulation. The status item stays in the bottom-right corner while
you code. Click it, or run **Watchcat: Open Corner Popup**, to open the tiny
white animated cat popup.

## Run during development

1. Open this repository in VS Code.
2. Press `F5` and choose **Extension Development Host**.
3. Open the repository in the new VS Code window.
4. Run the real sweep from the repository root:

   ```bash
   .venv/bin/python -m qpet.run_sweep
   ```

5. Click `Watchcat` in the bottom-right status bar.

The extension reads `watchcat_report.json` from the first workspace folder and
refreshes once per second. Click **Run convergence sweep** inside the popup to
launch the real Dynamiqs calculation from VS Code. The popup then shows the
derived target `α²`, final and peak memory photon number, boundary population,
tested/reference truncations, and the per-candidate maximum error.

Set `watchcat.reportPath` if the report lives somewhere else.

VS Code does not provide a supported API for arbitrary always-on-top floating
HTML windows. The status-bar corner item plus a small Webview panel is the
native extension equivalent and keeps the cat attached to the coding session.
