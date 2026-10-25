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
let sidebarView;
let pollHandle;
let currentContext;
let sweepRunning = false;
let outcomeState;
let outcomeTimer;
let popupAnimationState;
let sidebarAnimationState;

function activate(context) {
  currentContext = context;
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("watchcat.panel", new WatchcatViewProvider(context)),
  );
  statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 1000);
  statusItem.name = "Watchcat";
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
  if (context.extensionMode === vscode.ExtensionMode.Development) {
    setTimeout(() => openPopup(context), 700);
  }
}

function deactivate() {
  stopPolling();
  if (outcomeTimer) clearTimeout(outcomeTimer);
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

function projectRoot() {
  const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (workspaceRoot) return workspaceRoot;
  if (currentContext?.extensionMode === vscode.ExtensionMode.Development) {
    return path.resolve(currentContext.extensionPath, "..");
  }
  return undefined;
}

class WatchcatViewProvider {
  constructor(context) {
    this.context = context;
  }

  resolveWebviewView(view) {
    sidebarView = view;
    const uiRoot = uiRootFor(this.context);
    const initialState = displayState();
    sidebarAnimationState = initialState.state;
    view.webview.options = { enableScripts: true, localResourceRoots: [uiRoot] };
    view.webview.onDidReceiveMessage((message) => {
      if (message?.type === "runSweep") runSweep(this.context);
      if (message?.type === "openWigner") openWigner();
      if (message?.type === "explainReport") explainReport(this.context);
      if (message?.type === "speakAlert") speakAlert(this.context);
    });
    view.onDidDispose(() => {
      if (sidebarView === view) {
        sidebarView = undefined;
        sidebarAnimationState = undefined;
      }
    });
    view.webview.html = popupHtml(view.webview, uiRoot, initialState);
  }
}

function reportPath() {
  const configured = vscode.workspace.getConfiguration("watchcat").get("reportPath", "watchcat_report.json");
  const root = projectRoot();
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

function displayState() {
  const reportState = normaliseReport(readReport());
  if (sweepRunning) {
    return {
      ...reportState,
      state: "watching",
      label: "Watching",
      status: "running",
      detail: "I'm watching the sweep and comparing the observables.",
    };
  }
  if (outcomeState) {
    return { ...reportState, state: outcomeState, label: STATE_LABELS[outcomeState] };
  }
  if (reportState.status === "idle") {
    return { ...reportState, state: "idle", label: "Idle", detail: "Ready for a cat-qubit simulation." };
  }
  return {
    ...reportState,
    state: "idle",
    label: "Idle",
    detail: `Ready. Last result: ${reportState.detail}`,
  };
}

function showOutcome(state) {
  outcomeState = STATE_FILES[state] ? state : "idle";
  if (outcomeTimer) clearTimeout(outcomeTimer);
  outcomeTimer = setTimeout(() => {
    outcomeState = undefined;
    outcomeTimer = undefined;
    refreshStatus();
  }, 12000);
}

function refreshStatus() {
  const state = displayState();
  if (!statusItem) return;
  statusItem.text = "$(eye) Watchcat";
  statusItem.tooltip = `Watchcat: ${state.label} · ${state.status} — click to open`;
  statusItem.backgroundColor = state.state === "worried"
    ? new vscode.ThemeColor("statusBarItem.warningBackground")
    : undefined;
  if (popup) updatePopup(state);
  if (sidebarView) updateSidebar(state);
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
  const root = projectRoot();
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
  outcomeState = undefined;
  postPanelMessage({ type: "running", running: true });
  const watchingState = {
    ...normaliseReport(readReport()),
    state: "watching",
    label: "Watching",
    status: "running",
    detail: "I'm checking the truncations and comparing the observables.",
  };
  postStateToPanels(watchingState);
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
    showOutcome(normaliseReport(readReport()).state);
    postPanelMessage({
      type: "complete",
      success: true,
      text: "I'm done — I checked the truncations. Read the result below.",
    });
    vscode.window.showInformationMessage("Watchcat sweep complete; the cat and math have been refreshed.");
  } catch (error) {
    output.show(true);
    postPanelMessage({
      type: "complete",
      success: false,
      text: "I couldn't finish the sweep. Open the Watchcat output for details.",
    });
    vscode.window.showErrorMessage(`Watchcat sweep failed: ${error.message}`);
  } finally {
    sweepRunning = false;
    refreshStatus();
    postPanelMessage({ type: "running", running: false });
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
  const root = projectRoot();
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
  const root = projectRoot();
  const destination = reportPath();
  if (!root || !destination) {
    vscode.window.showErrorMessage("Watchcat needs an open workspace and report to speak.");
    return;
  }
  try {
    const result = await runIntegrationModule(root, ["speak", "--report", destination, "--out", "watchcat_alert.mp3", "--play"]);
    const speech = JSON.parse(result.stdout);
    if (speech.spoken) {
      vscode.window.showInformationMessage("Watchcat alert played with your configured ElevenLabs voice.");
    } else if (!speech.configured) {
      vscode.window.showWarningMessage("ElevenLabs is not configured. Add ELEVENLABS_API_KEY to the project .env file.");
    } else {
      vscode.window.showErrorMessage(`ElevenLabs could not create the alert: ${speech.error || "check the API key, voice ID, and Text to Speech permission"}`);
    }
  } catch (error) {
    vscode.window.showErrorMessage(`Watchcat voice alert failed: ${error.message}`);
  }
}

async function openWigner() {
  const root = projectRoot();
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
    const initialState = displayState();
    popupAnimationState = initialState.state;
    popup.onDidDispose(() => {
      popup = undefined;
      popupAnimationState = undefined;
    }, null, context.subscriptions);
    popup.webview.onDidReceiveMessage((message) => {
      if (message?.type === "runSweep") runSweep(context);
      if (message?.type === "openWigner") openWigner();
      if (message?.type === "explainReport") explainReport(context);
      if (message?.type === "speakAlert") speakAlert(context);
    }, null, context.subscriptions);
    popup.webview.html = popupHtml(popup.webview, uiRoot, initialState);
  } else {
    popup.reveal(undefined, true);
    updatePopup(displayState());
  }
}

function updatePopup(state) {
  if (!popup) return;
  const uiRoot = uiRootFor(currentContext);
  const animationChanged = popupAnimationState !== state.state;
  popupAnimationState = state.state;
  popup.webview.postMessage(stateMessage(uiRoot, state, animationChanged));
}

function updateSidebar(state) {
  if (!sidebarView) return;
  const uiRoot = uiRootFor(currentContext);
  const animationChanged = sidebarAnimationState !== state.state;
  sidebarAnimationState = state.state;
  sidebarView.webview.postMessage(stateMessage(uiRoot, state, animationChanged));
}

function postPanelMessage(message) {
  popup?.webview.postMessage(message);
  sidebarView?.webview.postMessage(message);
}

function postStateToPanels(state) {
  updatePopup(state);
  updateSidebar(state);
}

function stateMessage(uiRoot, state, includeAnimation) {
  const message = {
    type: "state",
    state: state.state,
    label: state.label,
    status: state.status,
    detail: state.detail,
    metrics: state.metrics,
    math: state.math,
    comparisons: state.comparisons,
  };
  if (includeAnimation) {
    message.animationScript = animationScript(uiRoot, state.state);
    message.showReplay = state.state === "happy" || state.state === "sleeping";
  }
  return message;
}

function animationScript(uiRoot, state) {
  const source = path.join(uiRoot.fsPath, STATE_FILES[state]);
  try {
    const html = fs.readFileSync(source, "utf8");
    const scripts = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)];
    return scripts.map((match) => match[1]).find((script) => /\bconst\s+W\s*=/.test(script)) || "";
  } catch {
    return "";
  }
}

function popupHtml(webview, uiRoot, initialState, nonce = String(Date.now())) {
  const initialStateJson = JSON.stringify({
    ...initialState,
    animationScript: animationScript(uiRoot, initialState.state),
    showReplay: initialState.state === "happy" || initialState.state === "sleeping",
  }).replace(/</g, "\\u003c");
  const csp = [
    `default-src 'none'`,
    `style-src 'nonce-${nonce}'`,
    `script-src 'nonce-${nonce}'`,
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
    .bar { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; border-bottom: 1px solid #20201f; font-size: 11px; font-weight: 800; letter-spacing: .06em; }
    .bar-right { display: flex; align-items: center; gap: 7px; }
    .dot { width: 8px; height: 8px; margin-right: 5px; display: inline-block; border-radius: 50%; background: #f0b429; }
    .dot.good { background: #4aa564; }
    .dot.bad { background: #df5d5d; }
    .pet-stage { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; width: 100%; height: 330px; overflow: hidden; background: #fbfbf8; }
    #c { display: block; width: 300px; height: auto; max-width: 100%; max-height: 315px; image-rendering: pixelated; }
    .pet-replay { flex: 0 0 auto; padding: 3px 8px; border: 1px solid #ddd9d0; border-radius: 5px; background: #fff; color: #20201f; font-size: 9px; }
    .pet-replay[hidden] { display: none; }
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
    .bar .info-button { flex: 0 0 auto; width: 18px; height: 18px; padding: 0; border: 1px solid #77736d; border-radius: 50%; background: #fff; color: #20201f; font-family: Georgia, serif; font-size: 12px; line-height: 16px; }
    .bar .info-button:hover, .bar .info-button:focus-visible { background: #20201f; color: #fff; outline: none; }
    .completion { padding: 7px 10px 8px; border-top: 1px solid #ddd9d0; color: #625e57; font-size: 10px; line-height: 1.4; }
    .completion:empty { display: none; }
    .completion.done { color: #277a43; font-weight: 800; }
    .completion.error { color: #b44040; font-weight: 800; }
    .how { padding: 9px 10px 10px; border-top: 1px solid #ddd9d0; background: #fffdf5; font-size: 10px; line-height: 1.45; }
    .how[hidden] { display: none; }
    .how-title { margin-bottom: 4px; font-weight: 800; }
    .how p { margin: 4px 0; }
    .how ol { margin: 5px 0 2px 18px; padding: 0; }
    .how li { margin: 3px 0; }
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
    <div class="bar"><span>WATCHCAT</span><span class="bar-right"><button id="info" class="info-button" type="button" aria-label="How Watchcat works" aria-expanded="false">i</button><span><span id="dot" class="dot"></span><span id="status"></span></span></span></div>
    <div id="pet-stage" class="pet-stage" aria-label="Watchcat pixel animation">
      <canvas id="c" aria-label="Watchcat"></canvas>
      <button id="rp" class="pet-replay" type="button" hidden>Replay</button>
    </div>
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
    <div id="completion" class="completion" aria-live="polite"></div>
    <section id="how" class="how" hidden>
      <div class="how-title">How Watchcat works</div>
      <p>Watchcat is a numerical trust advisor for the Alice &amp; Bob cat-qubit simulation. The cat makes the result easy to notice; the measurements make the decision.</p>
      <ol>
        <li>Run the same experiment at several memory Hilbert-space sizes, <b>Nₐ×Nᵦ</b>.</li>
        <li>Compare observables over time against the highest-resolution reference.</li>
        <li>Check convergence, trace drift, and population at the truncation boundary.</li>
        <li>Recommend a smaller setting only when the measured checks pass.</li>
      </ol>
      <p>Green means the run finished; the result below still tells you whether the physics is validated or needs review.</p>
    </section>
    <details>
      <summary>Explain this result</summary>
      <div id="explanation">Click Explain for a concise reading of the measured evidence.</div>
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
    const cspNonce = document.currentScript.nonce;
    const number = (value, digits) => typeof value === "number" ? value.toFixed(digits ?? 4) : "—";
    const pair = (na, nb) => na && nb ? na + "×" + nb : "—";
    const installAnimation = (source) => {
      (window.__watchcatTimers || []).forEach((timer) => window.clearInterval(timer));
      const timers = [];
      const originalSetInterval = window.setInterval;
      window.setInterval = (callback, delay, ...args) => {
        const timer = originalSetInterval(callback, delay, ...args);
        timers.push(timer);
        return timer;
      };
      const script = document.createElement("script");
      script.nonce = cspNonce;
      script.textContent = "(() => {\\n" + source + "\\n})();";
      document.body.appendChild(script);
      script.remove();
      window.setInterval = originalSetInterval;
      window.__watchcatTimers = timers;
    };
    const setState = (data) => {
      if (typeof data.animationScript === "string") installAnimation(data.animationScript);
      if (typeof data.showReplay === "boolean") document.getElementById("rp").hidden = !data.showReplay;
      document.getElementById("state").textContent = data.label;
      document.getElementById("status").textContent = data.status;
      document.getElementById("detail").textContent = data.detail;
      const dot = document.getElementById("dot");
      dot.className = "dot " + (data.status === "needs_review" ? "bad" : data.status === "validated" || data.status === "optimized" ? "good" : "");
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
    document.getElementById("info").addEventListener("click", () => {
      const panel = document.getElementById("how");
      const open = !panel.hidden;
      panel.hidden = open;
      document.getElementById("info").setAttribute("aria-expanded", String(!open));
    });
    window.addEventListener("message", (event) => {
      if (event.data?.type === "state") setState(event.data);
      if (event.data?.type === "running") {
        const button = document.getElementById("run");
        button.disabled = event.data.running;
        button.textContent = event.data.running ? "Running…" : "Run sweep";
        if (event.data.running) {
          const completion = document.getElementById("completion");
          completion.className = "completion";
          completion.textContent = "I'm working — checking the truncations and comparing the observables…";
        }
      }
      if (event.data?.type === "complete") {
        const completion = document.getElementById("completion");
        completion.className = "completion " + (event.data.success ? "done" : "error");
        completion.textContent = event.data.text;
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
    setState(${initialStateJson});
  </script>
</body>
</html>`;
}

module.exports = { activate, deactivate };
