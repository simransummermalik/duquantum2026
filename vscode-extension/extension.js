const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const vscode = require("vscode");

const STATE_FILES = {
  idle: "watchcat_idle.html",
  watching: "watchcat_watching.html",
  worried: "watchcat_worried.html",
  happy: "watchcat_happy.html",
  celebrating: "watchcat_super_excited.html",
  sleeping: "watchcat_bedtime.html",
};

const STATE_LABELS = {
  idle: "Idle",
  watching: "Watching",
  worried: "Worried",
  happy: "Happy",
  celebrating: "Celebrating",
  sleeping: "Sleeping",
};

let statusItem;
let popup;
let pollHandle;
let currentContext;
let sweepRunning = false;

function activate(context) {
  currentContext = context;
  statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusItem.command = "watchcat.openPopup";
  statusItem.tooltip = "Open Watchcat's corner popup";
  statusItem.show();
  context.subscriptions.push(statusItem);

  context.subscriptions.push(
    vscode.commands.registerCommand("watchcat.openPopup", () => openPopup(context)),
    vscode.commands.registerCommand("watchcat.runSweep", () => runSweep(context)),
    vscode.commands.registerCommand("watchcat.explainReport", () => explainReport(context)),
    vscode.commands.registerCommand("watchcat.speakAlert", () => speakAlert(context)),
    vscode.commands.registerCommand("watchcat.openWigner", () => openWigner()),
    { dispose: () => stopPolling() },
  );

  refreshStatus();
  pollHandle = setInterval(refreshStatus, 1000);
}

function deactivate() {
  stopPolling();
  if (popup) {
    popup.dispose();
    popup = undefined;
  }
}

function stopPolling() {
  if (pollHandle) {
    clearInterval(pollHandle);
    pollHandle = undefined;
  }
}

function reportPath() {
  const configured = vscode.workspace.getConfiguration("watchcat").get("reportPath", "watchcat_report.json");
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  return root ? path.resolve(root, configured) : undefined;
}

function readReport() {
  const file = reportPath();
  if (!file) return undefined;
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return undefined;
  }
}

function normaliseReport(payload) {
  const report = payload?.report || {};
  const state = STATE_FILES[report.pet_state] ? report.pet_state : "idle";
  const metrics = report.metrics || {};
  const diagnostic = report.diagnostics?.[0];
  return {
    state,
    label: STATE_LABELS[state],
    status: report.status || "idle",
    detail: diagnostic?.message || `Na ${metrics.Na ?? "—"} · Nb ${metrics.Nb ?? "—"}`,
    metrics,
    math: payload?.math || {},
    comparisons: report.comparisons || [],
  };
}

function refreshStatus() {
  const state = normaliseReport(readReport());
  if (!statusItem) return;
  statusItem.text = `$(eye) Watchcat: ${state.label}`;
  statusItem.backgroundColor = state.state === "worried"
    ? new vscode.ThemeColor("statusBarItem.warningBackground")
    : undefined;
  if (popup) updatePopup(state);
}

function uiRootFor(context) {
  const bundled = path.join(context.extensionPath, "ui");
  return vscode.Uri.file(fs.existsSync(bundled) ? bundled : path.resolve(context.extensionPath, "..", "ui"));
}

function pythonExecutable(root) {
  const candidates = process.platform === "win32"
    ? [path.join(root, ".venv", "Scripts", "python.exe"), "python"]
    : [path.join(root, ".venv", "bin", "python"), "python3"];
  return candidates.find((candidate) => candidate === "python" || candidate === "python3" || fs.existsSync(candidate));
}

async function runSweep(context) {
  if (sweepRunning) return;
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const output = vscode.window.createOutputChannel("Watchcat");
  if (!root) {
    vscode.window.showErrorMessage("Watchcat needs an open workspace to run the sweep.");
    return;
  }
  const destination = reportPath();
  const executable = pythonExecutable(root);
  if (!destination || !executable) {
    vscode.window.showErrorMessage("Watchcat could not find a Python interpreter or report path.");
    return;
  }

  sweepRunning = true;
  popup?.webview.postMessage({ type: "running", running: true });
  const args = ["-m", "qpet.run_sweep", "--out", destination];
  output.appendLine(`Running: ${executable} ${args.join(" ")}`);
  try {
    await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Watchcat: running convergence sweep" },
      () => new Promise((resolve, reject) => {
        const child = spawn(executable, args, { cwd: root });
        let errorText = "";
        child.stdout.on("data", (chunk) => output.append(chunk.toString()));
        child.stderr.on("data", (chunk) => {
          const text = chunk.toString();
          errorText += text;
          output.append(text);
        });
        child.on("error", reject);
        child.on("close", (code) => {
          if (code === 0) resolve();
          else reject(new Error(errorText.trim() || `Sweep exited with code ${code}`));
        });
      }),
    );
    refreshStatus();
    vscode.window.showInformationMessage("Watchcat sweep complete; the cat and math have been refreshed.");
  } catch (error) {
    output.show(true);
    vscode.window.showErrorMessage(`Watchcat sweep failed: ${error.message}`);
  } finally {
    sweepRunning = false;
    popup?.webview.postMessage({ type: "running", running: false });
  }
}

function runIntegrationModule(root, args) {
  const executable = pythonExecutable(root);
  if (!executable) return Promise.reject(new Error("No Python interpreter found."));
  return new Promise((resolve, reject) => {
    const child = spawn(executable, ["-m", "qpet.integrations", ...args], { cwd: root });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(stderr.trim() || `Integration exited with code ${code}`));
    });
  });
}

async function explainReport(context) {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const destination = reportPath();
  if (!root || !destination) {
    vscode.window.showErrorMessage("Watchcat needs an open workspace and report to explain.");
    return;
  }
  popup?.webview.postMessage({ type: "explanationRunning", running: true });
  try {
    const result = await runIntegrationModule(root, ["explain", "--report", destination]);
    const explanation = JSON.parse(result.stdout);
    popup?.webview.postMessage({ type: "explanation", ...explanation });
    if (!popup) vscode.window.showInformationMessage(explanation.text);
  } catch (error) {
    vscode.window.showErrorMessage(`Watchcat explanation failed: ${error.message}`);
  } finally {
    popup?.webview.postMessage({ type: "explanationRunning", running: false });
  }
}

async function speakAlert(context) {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const destination = reportPath();
  if (!root || !destination) {
    vscode.window.showErrorMessage("Watchcat needs an open workspace and report to speak.");
    return;
  }
  try {
    const result = await runIntegrationModule(root, ["speak", "--report", destination, "--out", "watchcat_alert.mp3", "--play"]);
    const speech = JSON.parse(result.stdout);
    vscode.window.showInformationMessage(speech.spoken ? "Watchcat alert played." : "ElevenLabs is not configured; Watchcat generated the local alert text.");
  } catch (error) {
    vscode.window.showErrorMessage(`Watchcat voice alert failed: ${error.message}`);
  }
}

async function openWigner() {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const payload = readReport();
  const configured = payload?.report?.metrics?.wigner_snapshot_path;
  if (!root || !configured) {
    vscode.window.showInformationMessage("Run a sweep first to create Wigner snapshots.");
    return;
  }
  const target = path.isAbsolute(configured) ? configured : path.resolve(root, configured);
  if (!fs.existsSync(target)) {
    vscode.window.showInformationMessage(`Wigner artifact not found yet: ${target}`);
    return;
  }
  await vscode.commands.executeCommand("vscode.open", vscode.Uri.file(target));
}

function openPopup(context) {
  const uiRoot = uiRootFor(context);
  const options = {
    enableScripts: true,
    retainContextWhenHidden: true,
    localResourceRoots: [uiRoot],
  };

  if (!popup) {
    popup = vscode.window.createWebviewPanel(
      "watchcat.popup",
      "Watchcat",
      { viewColumn: vscode.ViewColumn.Beside, preserveFocus: true },
      options,
    );
    popup.onDidDispose(() => { popup = undefined; }, null, context.subscriptions);
    popup.webview.onDidReceiveMessage((message) => {
      if (message?.type === "runSweep") runSweep(context);
      if (message?.type === "openWigner") openWigner();
      if (message?.type === "explainReport") explainReport(context);
      if (message?.type === "speakAlert") speakAlert(context);
    }, null, context.subscriptions);
    popup.webview.html = popupHtml(popup.webview, uiRoot, normaliseReport(readReport()));
  } else {
    popup.reveal(undefined, true);
    updatePopup(normaliseReport(readReport()));
  }
}

function updatePopup(state) {
  if (!popup) return;
  const uiRoot = uiRootFor(currentContext);
  const uri = vscode.Uri.file(path.join(uiRoot.fsPath, STATE_FILES[state.state]));
  popup.webview.postMessage({
    type: "state",
    state: state.state,
    label: state.label,
    status: state.status,
    detail: state.detail,
    metrics: state.metrics,
    math: state.math,
    comparisons: state.comparisons,
    stateUri: popup.webview.asWebviewUri(uri).toString(),
  });
}

function popupHtml(webview, uiRoot, initialState) {
  const nonce = String(Date.now());
  const uri = vscode.Uri.file(path.join(uiRoot.fsPath, STATE_FILES[initialState.state]));
  const stateUri = webview.asWebviewUri(uri).toString();
  const csp = [
    `default-src 'none'`,
    `style-src 'nonce-${nonce}'`,
    `script-src 'nonce-${nonce}'`,
    `frame-src ${webview.cspSource}`,
    `img-src ${webview.cspSource} data:`,
  ].join("; ");
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <style nonce="${nonce}">
    :root { color-scheme: light; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #20201f; background: #f4f4f1; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; background: #f4f4f1; }
    .watchcat { width: 340px; max-width: calc(100vw - 24px); margin: 14px auto; overflow: hidden; border: 1px solid #20201f; border-radius: 10px; background: #fff; box-shadow: 3px 3px 0 #20201f; }
    .bar { display: flex; justify-content: space-between; padding: 8px 10px; border-bottom: 1px solid #20201f; font-size: 11px; font-weight: 800; letter-spacing: .06em; }
    .dot { width: 8px; height: 8px; margin-right: 5px; display: inline-block; border-radius: 50%; background: #f0b429; }
    .dot.good { background: #4aa564; }
    .dot.bad { background: #df5d5d; }
    iframe { display: block; width: 340px; height: 270px; border: 0; background: #fbfbf8; }
    .info { padding: 8px 10px 10px; border-top: 1px solid #20201f; font-size: 11px; line-height: 1.45; }
    .state { font-weight: 800; }
    .detail { display: block; color: #77736d; }
    .math { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; padding: 8px 10px; border-top: 1px solid #ddd9d0; }
    .metric { padding: 5px 6px; border: 1px solid #ddd9d0; border-radius: 5px; }
    .metric small { display: block; color: #77736d; font-size: 9px; }
    .metric strong { font-size: 12px; }
    .actions { display: flex; flex-wrap: wrap; gap: 5px; padding: 0 10px 8px; }
    button { flex: 1 1 70px; border: 1px solid #20201f; border-radius: 5px; padding: 6px 4px; background: #20201f; color: #fff; font: inherit; font-size: 9px; cursor: pointer; }
    button:disabled { cursor: wait; opacity: .55; }
    details { border-top: 1px solid #ddd9d0; padding: 7px 10px 9px; font-size: 10px; }
    summary { cursor: pointer; font-weight: 800; }
    .equation { margin-top: 6px; color: #625e57; line-height: 1.5; }
    .comparison { display: flex; justify-content: space-between; gap: 8px; padding-top: 4px; }
    .pass { color: #277a43; }
    .fail { color: #b44040; }
    #explanation { margin-top: 6px; color: #625e57; line-height: 1.5; }
  </style>
</head>
<body>
  <main class="watchcat">
    <div class="bar"><span>WATCHCAT</span><span><span id="dot" class="dot"></span><span id="status"></span></span></div>
    <iframe id="pet" title="Watchcat animation" src="${stateUri}"></iframe>
    <div class="info"><span id="state" class="state"></span><span id="detail" class="detail"></span></div>
    <div class="math">
      <div class="metric"><small>target α²</small><strong id="target">—</strong></div>
      <div class="metric"><small>final nₐ</small><strong id="final">—</strong></div>
      <div class="metric"><small>peak nₐ</small><strong id="peak">—</strong></div>
      <div class="metric"><small>edge population</small><strong id="edge">—</strong></div>
      <div class="metric"><small>parity final</small><strong id="parity">—</strong></div>
      <div class="metric"><small>memory purity</small><strong id="purity">—</strong></div>
      <div class="metric"><small>even-cat F</small><strong id="catFidelity">—</strong></div>
      <div class="metric"><small>reference</small><strong id="reference">—</strong></div>
      <div class="metric"><small>selected</small><strong id="selected">—</strong></div>
    </div>
    <div class="actions"><button id="run" type="button">Run sweep</button><button id="wigner" type="button">Wigner</button><button id="explain" type="button">Explain</button><button id="speak" type="button">Speak</button></div>
    <details>
      <summary>Explain this result</summary>
      <div id="explanation">Click Explain for a constrained Gemini explanation, or use the local fallback.</div>
    </details>
    <details>
      <summary>Show convergence math</summary>
      <div id="parameters" class="equation"></div>
      <div class="equation">Compare every observable across time. A candidate passes when<br><b>max |candidate − reference| ≤ abs + rel × max |reference|</b>.</div>
      <div id="comparisons"></div>
    </details>
  </main>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const number = (value, digits) => typeof value === "number" ? value.toFixed(digits ?? 4) : "—";
    const pair = (na, nb) => na && nb ? na + "×" + nb : "—";
    const setState = (data) => {
      document.getElementById("pet").src = data.stateUri;
      document.getElementById("state").textContent = data.label;
      document.getElementById("status").textContent = data.status;
      document.getElementById("detail").textContent = data.detail;
      const dot = document.getElementById("dot");
      dot.className = "dot " + (data.state === "worried" ? "bad" : data.state === "happy" || data.state === "celebrating" ? "good" : "");
      const metrics = data.metrics || {};
      const math = data.math || {};
      document.getElementById("target").textContent = number(metrics.target_memory_photons ?? math.alpha_squared, 3);
      document.getElementById("final").textContent = number(metrics.memory_photon_final, 3);
      document.getElementById("peak").textContent = number(metrics.memory_photon_peak, 3);
      document.getElementById("edge").textContent = number(metrics.peak_memory_edge_population, 5);
      document.getElementById("parity").textContent = number(metrics.memory_parity_final, 3);
      document.getElementById("purity").textContent = number(metrics.memory_purity_final, 3);
      document.getElementById("catFidelity").textContent = number(metrics.memory_cat_even_fidelity_final, 3);
      document.getElementById("reference").textContent = pair(metrics.reference_Na, metrics.reference_Nb);
      document.getElementById("selected").textContent = pair(metrics.selected_Na, metrics.selected_Nb);
      const g2Ratio = math.g2 && math.kappa_b ? math.g2 / math.kappa_b : undefined;
      const driveRatio = math.eps_d && math.kappa_b ? math.eps_d / math.kappa_b : undefined;
      const incoherentParity = metrics.incoherent_pm_alpha_parity;
      const logical = incoherentParity === undefined ? "" : " · incoherent ±α parity = " + number(incoherentParity, 5);
      document.getElementById("parameters").textContent = g2Ratio === undefined
        ? "Model parameters are not in this report yet."
        : "g₂/κᵦ = " + number(g2Ratio, 3) + " · εd/κᵦ = " + number(driveRatio, 3) + " · κ₂ = " + number(math.kappa_2_effective, 3) + logical;
      document.getElementById("comparisons").innerHTML = (data.comparisons || []).map((item) => {
        const cls = item.passed ? "pass" : "fail";
        const mark = item.passed ? "✓" : "×";
        return '<div class="comparison ' + cls + '"><span>' + mark + ' ' + item.candidate_label + '</span><span>Δ ' + number(item.max_abs_error, 3) + '</span></div>';
      }).join("") || "<div class=equation>No convergence comparisons yet.</div>";
    };
    document.getElementById("run").addEventListener("click", () => vscode.postMessage({ type: "runSweep" }));
    document.getElementById("wigner").addEventListener("click", () => vscode.postMessage({ type: "openWigner" }));
    document.getElementById("explain").addEventListener("click", () => vscode.postMessage({ type: "explainReport" }));
    document.getElementById("speak").addEventListener("click", () => vscode.postMessage({ type: "speakAlert" }));
    window.addEventListener("message", (event) => {
      if (event.data?.type === "state") setState(event.data);
      if (event.data?.type === "running") {
        const button = document.getElementById("run");
        button.disabled = event.data.running;
        button.textContent = event.data.running ? "Running…" : "Run sweep";
      }
      if (event.data?.type === "explanation") {
        document.getElementById("explanation").textContent = event.data.text;
      }
      if (event.data?.type === "explanationRunning") {
        const button = document.getElementById("explain");
        button.disabled = event.data.running;
        button.textContent = event.data.running ? "Thinking…" : "Explain";
      }
    });
    setState(${JSON.stringify({ ...initialState, stateUri })});
  </script>
</body>
</html>`;
}

module.exports = { activate, deactivate };
