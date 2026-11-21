const offerText = document.getElementById("offerText");
const homeView = document.getElementById("homeView");
const reportView = document.getElementById("reportView");
const investigatingView = document.getElementById("investigatingView");
const resultView = document.getElementById("resultView");
const homeTab = document.getElementById("homeTab");
const reportTab = document.getElementById("reportTab");
const modalBackdrop = document.getElementById("modalBackdrop");
const sourcesDrawer = document.getElementById("sourcesDrawer");
const overlay = document.getElementById("overlay");
let selectedLanguage = "simple_english";
let currentReport = null;
let activeDemoPreset = "fee";
let attachedFile = null;
let attachmentPreviewUrl = null;
let analysisRunning = false;
let reportAvailable = false;
let gmailReturnMessage = "";
let currentGmailMessageId = null;

const gmailErrorMessages = {
  not_configured: "Gmail isn't configured yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to your local .env.",
  session_secret_missing: "Session signing is not configured. Restart OfferCheck to generate SESSION_SECRET.",
  state_invalid: "Google sign-in expired or could not be verified. Please try connecting again.",
  cancelled: "Google sign-in was cancelled.",
  authorization_failed: "Google did not return an authorization code. Please try again.",
  token_exchange_failed: "Could not finish Google sign-in. Check the OAuth client and redirect URI settings.",
};
const gmailErrorCode = new URLSearchParams(window.location.search).get("gmail_error");
if (gmailErrorCode) {
  gmailReturnMessage = gmailErrorMessages[gmailErrorCode] || "Gmail could not connect. Please try again.";
  window.history.replaceState({}, "", window.location.pathname);
}

const presets = {
  fee: {
    text: offerText.value,
    company: "Infosys",
    recruiter: "Rohit",
    role: "Remote AI Internship",
    url: "https://www.infosys.com",
    domain: "infosys.com"
  },
  whatsapp: {
    text: "A recruiter on WhatsApp says Infosys is hiring for Data Entry. Pay Rs 2,499 registration fee by UPI today to start. No interview. Contact HR on Telegram.",
    company: "Infosys",
    recruiter: "",
    role: "Data Entry",
    url: "https://www.infosys.com",
    domain: "infosys.com"
  },
  no_fee: {
    text: "Infosys invited me to interview for the Product Analyst role listed on its careers page. No fee is required.",
    company: "Infosys",
    recruiter: "",
    role: "Product Analyst",
    url: "https://www.infosys.com",
    domain: "infosys.com"
  }
};

function setActiveView(view) {
  const activeView = view === "report" && reportAvailable ? "report" : "home";
  homeView.classList.toggle("hidden", activeView !== "home");
  reportView.classList.toggle("hidden", activeView !== "report");
  homeTab.classList.toggle("active", activeView === "home");
  reportTab.classList.toggle("active", activeView === "report");
  reportTab.disabled = !reportAvailable;
  homeTab.setAttribute("aria-current", activeView === "home" ? "page" : "false");
  reportTab.setAttribute("aria-current", activeView === "report" ? "page" : "false");
}

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = value;
  return element.innerHTML;
}

function sourceLabel(source) {
  return `${source.domain} · ${source.source_type[0].toUpperCase()}${source.source_type.slice(1)}`;
}

function highlightOffer(text, claims) {
  let html = escapeHtml(text);
  [...claims]
    .filter(claim => claim.highlight)
    .sort((a, b) => b.highlight.length - a.highlight.length)
    .forEach(claim => {
      const escaped = claim.highlight.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      html = html.replace(new RegExp(`(${escaped})`, "i"), `<mark class="highlight ${claim.status.toLowerCase()}">$1</mark>`);
    });
  return html;
}

function verdictName(level) {
  if (level === "HIGH_RISK") return "HIGH RISK";
  if (level === "NO_RED_FLAGS_FOUND") return "NO RED FLAGS FOUND";
  return "COULD NOT VERIFY";
}

function renderVerdict(report) {
  const card = document.getElementById("verdictCard");
  const sourceCount = Array.isArray(report.sources) ? report.sources.length : 0;
  const stateClass = report.verdict_level === "UNVERIFIED"
    ? "unverified"
    : report.verdict_level === "NO_RED_FLAGS_FOUND"
      ? "no-red-flags"
      : "";
  card.className = `verdict-card ${stateClass}`;
  card.innerHTML = `
    <div>
      <div class="verdict-meta">
        <span class="badge ${stateClass}">${verdictName(report.verdict_level)}</span>
        <span class="source-count">${sourceCount} source${sourceCount === 1 ? "" : "s"}</span>
      </div>
      <h2>${escapeHtml(report.headline)}</h2>
      <p>${escapeHtml(report.summary)}</p>
      ${report.verdict_level === "NO_RED_FLAGS_FOUND" ? '<span class="not-guarantee">Not a guarantee.</span>' : ""}
    </div>
    <div class="verdict-actions">
      <button class="primary-button" id="doNowButton">Do this now</button>
      <button class="secondary-button" id="shareButton">Share result</button>
    </div>
  `;
  document.getElementById("doNowButton").addEventListener("click", () => {
    document.querySelector(".action-grid").scrollIntoView({ behavior: "smooth" });
  });
  document.getElementById("shareButton").addEventListener("click", shareResult);
}

function renderClaims(report) {
  const ledger = document.getElementById("claimLedger");
  ledger.innerHTML = report.claims.map(claim => {
    const statusClass = claim.status.toLowerCase();
    const label = claim.status === "SUPPORTED" ? "Confirmed"
      : claim.status === "CONTRADICTED" ? "Contradicted"
        : "Could not confirm";
    const sources = claim.evidence_ids
      .map(id => report.sources.find(source => source.id === id))
      .filter(Boolean);
    const sourceMarkup = sources.length
      ? sources.map(source => `<a class="source-chip" href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(sourceLabel(source))}</a>`).join(" ")
      : '<span class="no-source">No matching source returned</span>';
    return `
      <div class="claim-row">
        <span class="status-dot ${statusClass}"></span>
        <div>
          <span class="claim-label ${statusClass}">${label}</span>
          <strong>${escapeHtml(claim.text)}</strong>
          <p>${escapeHtml(claim.reason)}</p>
          ${sourceMarkup}
        </div>
      </div>
    `;
  }).join("");

}

function renderActions(report) {
  document.getElementById("doNowList").innerHTML = report.do_this
    .map(step => `<li>${escapeHtml(step)}</li>`).join("");
  document.getElementById("cantVerifyList").innerHTML = report.cant_verify
    .map(item => `<li>${escapeHtml(item)}</li>`).join("");
  document.getElementById("askList").innerHTML = report.ask_them
    .map(question => `
      <div class="ask-item">
        <span>${escapeHtml(question)}</span>
        <button class="copy-button" data-copy="${escapeHtml(question)}">Copy</button>
      </div>
    `).join("");
  document.querySelectorAll("[data-copy]").forEach(button => {
    button.addEventListener("click", async () => {
      await navigator.clipboard.writeText(button.dataset.copy);
      button.textContent = "Copied";
    });
  });
}

async function showReport(file = attachedFile) {
  if (analysisRunning) return;
  const errorNote = document.getElementById("errorNote");
  errorNote.classList.add("hidden");
  document.getElementById("captureStatus").classList.add("hidden");
  currentReport = null;
  reportAvailable = true;
  resultView.classList.add("hidden");
  setActiveView("report");
  setAnalysisRunning(true);
  try {
    const text = offerText.value.trim();
    if (file) showFileAttachment(file, "extracting");
    investigatingView.classList.remove("hidden");
    document.getElementById("investigationOffer").textContent =
      text || (file ? "Text will be extracted from the attachment." : "");
    renderProgress();
    const body = new FormData();
    body.append("text", text);
    body.append("language", selectedLanguage);
    if (currentGmailMessageId) body.append("gmail_message_id", currentGmailMessageId);
    for (const [field, id] of Object.entries({
      company: "companyInput",
      recruiter: "recruiterInput",
      role: "roleInput",
      url: "urlInput",
      domain: "domainInput"
    })) {
      const value = document.getElementById(id).value.trim();
      if (value) body.append(field, value);
    }
    if (file) body.append("file", file);
    const response = await fetch("/analyze", { method: "POST", body });
    if (!response.ok) throw new Error("Could not start analysis");
    const job = await response.json();
    connectLiveSteps(job.job_id);
  } catch (error) {
    errorNote.textContent = "We could not load the report. Check the connection and try again.";
    errorNote.classList.remove("hidden");
    setAnalysisRunning(false);
    if (file) updateFileAttachmentStatus("Upload failed · try again");
    investigatingView.classList.add("hidden");
    reportAvailable = false;
    setActiveView("home");
  }
}

function setAnalysisRunning(running) {
  analysisRunning = running;
  document.getElementById("checkButton").disabled = running;
  document.getElementById("checkButton").textContent = running ? "Checking..." : "Check this offer";
  document.getElementById("removeAttachment").disabled = running;
}

function showCaptureStatus(message, kind = "info") {
  const status = document.getElementById("captureStatus");
  status.textContent = message;
  status.className = `capture-status ${kind}`;
}

function stopCaptureTracks(stream) {
  if (stream) stream.getTracks().forEach(track => track.stop());
}

async function captureDisplayFrame(stream) {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.autoplay = true;
  const videoTrack = stream.getVideoTracks()[0];
  if (!videoTrack) throw new Error("The selected share has no video track.");

  try {
    await new Promise((resolve, reject) => {
      let timeoutId;
      const cleanup = () => {
        clearTimeout(timeoutId);
        video.removeEventListener("loadeddata", onLoaded);
        video.removeEventListener("error", onError);
        videoTrack.removeEventListener("ended", onEnded);
      };
      const onLoaded = () => {
        cleanup();
        resolve();
      };
      const onError = () => {
        cleanup();
        reject(new Error("The selected screen could not be read."));
      };
      const onEnded = () => {
        cleanup();
        reject(new DOMException("Screen sharing ended before a frame was captured.", "AbortError"));
      };

      video.addEventListener("loadeddata", onLoaded);
      video.addEventListener("error", onError);
      videoTrack.addEventListener("ended", onEnded);
      timeoutId = setTimeout(() => {
        cleanup();
        reject(new Error("Timed out waiting for a screen frame."));
      }, 10000);
      video.srcObject = stream;
    });
    await video.play();
    await new Promise(resolve => requestAnimationFrame(resolve));
    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) throw new Error("The selected share did not provide a video frame.");

    const scale = Math.min(1, 1280 / Math.max(width, height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Could not prepare the screenshot.");
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob(
        image => image ? resolve(image) : reject(new Error("Could not encode the screenshot.")),
        "image/jpeg",
        0.8
      );
    });
    stopCaptureTracks(stream);
    window.focus();
    return new File([blob], "shared-tab.jpg", { type: "image/jpeg" });
  } finally {
    video.pause();
    video.srcObject = null;
  }
}

async function captureScreen() {
  const mediaDevices = navigator.mediaDevices;
  if (!mediaDevices || typeof mediaDevices.getDisplayMedia !== "function") {
    showCaptureStatus("Screen capture is unavailable here. Paste or upload a screenshot instead.", "error");
    return;
  }

  let stream = null;
  try {
    showCaptureStatus("Choose a tab, window, or screen to capture…");
    stream = await mediaDevices.getDisplayMedia({ video: true });
    const file = await captureDisplayFrame(stream);
    stopCaptureTracks(stream);
    if (file.size > 10 * 1024 * 1024) {
      showCaptureStatus("Captured screenshot exceeds the 10 MB limit. Nothing was uploaded.", "error");
      return;
    }
    showCaptureStatus("Screenshot captured. Sending it for analysis…", "success");
    processFile(file);
  } catch (error) {
    stopCaptureTracks(stream);
    if (error.name === "NotSupportedError") {
      showCaptureStatus("Screen capture is unavailable here. Paste or upload a screenshot instead.", "error");
      return;
    }
    if (["NotAllowedError", "AbortError", "NotFoundError", "SecurityError"].includes(error.name)) {
      showCaptureStatus("Screen capture was canceled or blocked. Nothing was uploaded.");
      return;
    }
    console.error("Screen capture failed", error);
    showCaptureStatus("Could not capture the screen. Paste or upload a screenshot instead.", "error");
  }
}

function showFileAttachment(file, statusText) {
  const sameFile = attachedFile === file;
  if (!sameFile) {
    clearFileAttachment();
    attachedFile = file;
  }

  const attachment = document.getElementById("fileAttachment");
  const icon = document.getElementById("fileAttachmentIcon");
  const image = document.getElementById("fileAttachmentImage");
  document.getElementById("fileAttachmentName").textContent = file.name || "Attached file";
  document.getElementById("fileAttachmentDetails").textContent = formatFileSize(file.size);
  updateFileAttachmentStatus(statusText);

  if (file.type.startsWith("image/")) {
    if (!sameFile) {
      attachmentPreviewUrl = URL.createObjectURL(file);
      image.src = attachmentPreviewUrl;
    }
    icon.classList.add("hidden");
    image.classList.remove("hidden");
  } else {
    if (attachmentPreviewUrl) URL.revokeObjectURL(attachmentPreviewUrl);
    attachmentPreviewUrl = null;
    image.removeAttribute("src");
    image.classList.add("hidden");
    icon.classList.remove("hidden");
  }
  attachment.classList.remove("hidden");
}

function updateFileAttachmentStatus(statusText) {
  const attachment = document.getElementById("fileAttachment");
  const status = document.getElementById("fileAttachmentStatus");
  const skeleton = document.getElementById("fileAttachmentSkeleton");
  const isExtracting = statusText === "extracting";

  status.textContent = isExtracting ? "" : statusText;
  status.className = "file-attachment-status";
  if (/^Text extracted/i.test(statusText)) status.classList.add("success");
  if (/^(No offer|Could not finish|Upload failed)/i.test(statusText)) status.classList.add("error");
  skeleton.classList.toggle("hidden", !isExtracting);
  attachment.setAttribute("aria-label", isExtracting ? "Reading attached file" : statusText);
}

function formatFileSize(size) {
  return size < 1024 * 1024
    ? `${Math.max(1, Math.round(size / 1024))} KB`
    : `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function clearFileAttachment() {
  attachedFile = null;
  if (attachmentPreviewUrl) URL.revokeObjectURL(attachmentPreviewUrl);
  attachmentPreviewUrl = null;
  const attachment = document.getElementById("fileAttachment");
  const icon = document.getElementById("fileAttachmentIcon");
  const image = document.getElementById("fileAttachmentImage");
  image.removeAttribute("src");
  image.classList.add("hidden");
  icon.classList.remove("hidden");
  attachment.classList.add("hidden");
  document.getElementById("fileAttachmentName").textContent = "";
  document.getElementById("fileAttachmentDetails").textContent = "";
  updateFileAttachmentStatus("");
}

function renderProgress() {
  const steps = [
    ["Reading the offer", "Waiting", "running"],
    ["Finding the company's official site", "Waiting", "waiting"],
    ["Checking careers and the role", "Waiting", "waiting"],
    ["Looking for fraud notices and reports", "Waiting", "waiting"],
    ["Checking company registration and news", "Waiting", "waiting"],
    ["Writing your result", "Waiting", "waiting"]
  ];
  document.getElementById("progressSteps").innerHTML = steps.map(([label, detail, status], index) => `
    <div class="progress-step" data-step="${["reading","search_official","search_careers","search_fraud_notice","search_registration_news","writing"][index]}">
      <span class="step-icon ${status}">${status === "done" ? "✓" : ""}</span>
      <div><strong>${label}</strong><small class="step-detail">${detail}</small></div>
    </div>
  `).join("");
  document.getElementById("progressFill").style.width = "5%";
}

function connectLiveSteps(jobId) {
  if (!jobId || !window.EventSource) {
    setAnalysisRunning(false);
    document.getElementById("errorNote").textContent = "Live updates are not available in this browser.";
    document.getElementById("errorNote").classList.remove("hidden");
    investigatingView.classList.add("hidden");
    reportAvailable = Boolean(currentReport);
    setActiveView("home");
    return;
  }
  const stream = new EventSource(`/stream/${encodeURIComponent(jobId)}`);
  stream.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    if (message.type === "error") {
      stream.close();
      setAnalysisRunning(false);
      if (showCachedDemoFallback(message.message)) return;
      if (attachedFile) {
        updateFileAttachmentStatus(message.message.includes("No job, internship, or freelance offer")
          ? "No offer detected"
          : "Could not finish · try again");
      }
      document.getElementById("errorNote").textContent = message.message;
      document.getElementById("errorNote").classList.remove("hidden");
      investigatingView.classList.add("hidden");
      reportAvailable = Boolean(currentReport);
      setActiveView("home");
      return;
    }
    if (message.type === "step") {
      if (message.id === "reading" && attachedFile) {
        updateFileAttachmentStatus(message.status === "done"
          ? "Text extracted · analysis continuing"
          : "extracting");
      }
      const existing = document.querySelector(`[data-step="${message.id}"]`);
      if (existing) {
        existing.dataset.status = message.status;
        const icon = existing.querySelector(".step-icon");
        icon.className = `step-icon ${message.status}`;
        icon.textContent = message.status === "done" ? "✓" : "";
        existing.querySelector(".step-detail").textContent =
          message.query ? `Searched: "${message.query}"` : message.label;
      }
      const completed = document.querySelectorAll(".progress-step[data-status='done']").length;
      document.getElementById("progressFill").style.width =
        `${Math.max(5, Math.round((completed / 6) * 100))}%`;
    }
    if (message.type === "report") {
      stream.close();
      renderLiveReport(message);
    }
  });
}

function renderLiveReport(report) {
  currentReport = report;
  reportAvailable = true;
  setActiveView("report");
  setAnalysisRunning(false);
  clearFileAttachment();
  document.getElementById("captureStatus").classList.add("hidden");
  const fallbackNote = document.getElementById("demoFallbackNote");
  const sources = Array.isArray(report.sources) ? report.sources : [];
  const sourceCount = sources.length;
  const modeText = report.cached_fallback
    ? "Cached report · citations are from the earlier live check"
    : `${report.evidence_mode === "live" ? "Live You.com search" : "Search mode unknown"} · ${sourceCount} source${sourceCount === 1 ? "" : "s"}`;
  const fallbackDetails = [];
  if (report.demo_fallback) fallbackDetails.push("cached preset extraction");
  if (report.used_rule_based_report) fallbackDetails.push("rule-based wording");
  fallbackNote.textContent = fallbackDetails.length
    ? `${modeText} · Gemini fallback: ${fallbackDetails.join(" + ")}`
    : modeText;
  fallbackNote.className = `result-source-status ${report.cached_fallback || fallbackDetails.length ? "fallback" : "live"}`;
  if (!report.cached_fallback && activeDemoPreset) saveDemoReport(report);
  investigatingView.classList.add("hidden");
  resultView.classList.remove("hidden");
  document.getElementById("highlightedOffer").innerHTML =
    highlightOffer(report.offer_text || offerText.value.trim(), report.claims);
  renderVerdict(report);
  renderClaims(report);
  renderActions(report);
}

function demoCacheKey() {
  return activeDemoPreset
    ? `offercheck-demo-report:${activeDemoPreset}:${selectedLanguage}`
    : null;
}

function saveDemoReport(report) {
  const key = demoCacheKey();
  if (!key) return;
  try {
    localStorage.setItem(key, JSON.stringify({
      offerText: offerText.value.trim(),
      report
    }));
  } catch (error) {
    console.warn("Could not cache the demo report", error);
  }
}

function showCachedDemoFallback(message) {
  if (!activeDemoPreset || !(/\b(?:429|5\d{2})\b|timeout|timed out|could not be reached/i.test(message))) {
    return false;
  }
  const key = demoCacheKey();
  if (!key) return false;
  try {
    const cached = JSON.parse(localStorage.getItem(key) || "null");
    if (!cached || cached.offerText !== offerText.value.trim()) return false;
    renderLiveReport({ ...cached.report, cached_fallback: true });
    return true;
  } catch (error) {
    console.warn("Could not load the cached demo report", error);
    return false;
  }
}

function openSources() {
  const report = currentReport;
  if (!report) return;
  document.getElementById("sourceList").innerHTML = report.sources.map(source => `
    <article class="source-card">
      <span class="source-tag">${source.source_type[0].toUpperCase()}${source.source_type.slice(1)}</span>
      <h3>${escapeHtml(source.title)}</h3>
      <p>${escapeHtml(source.domain)}</p>
      <p>${escapeHtml(source.snippet)}</p>
      <a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">Open source</a>
    </article>
  `).join("");
  sourcesDrawer.classList.remove("hidden");
  overlay.classList.remove("hidden");
}

function closeSources() {
  sourcesDrawer.classList.add("hidden");
  overlay.classList.add("hidden");
}

async function shareResult() {
  const report = currentReport;
  if (!report) return;
  const text = `${verdictName(report.verdict_level)}\n${report.headline}\n${report.summary}`;
  await navigator.clipboard.writeText(text);
  document.getElementById("shareButton").textContent = "Copied";
}

document.getElementById("checkButton").addEventListener("click", () => {
  if (!offerText.value.trim() && !attachedFile) {
    document.getElementById("errorNote").textContent = "Paste an offer or add a file first.";
    document.getElementById("errorNote").classList.remove("hidden");
    offerText.focus();
    return;
  }
  showReport(attachedFile);
});

document.querySelectorAll("[data-preset]").forEach(button => {
  button.addEventListener("click", () => {
    if (analysisRunning) return;
    clearFileAttachment();
    currentGmailMessageId = null;
    activeDemoPreset = button.dataset.preset;
    const preset = presets[activeDemoPreset];
    offerText.value = preset.text;
    for (const [field, value] of Object.entries({
      companyInput: preset.company,
      recruiterInput: preset.recruiter,
      roleInput: preset.role,
      urlInput: preset.url,
      domainInput: preset.domain
    })) {
      document.getElementById(field).value = value;
    }
  });
});
offerText.addEventListener("input", () => {
  activeDemoPreset = null;
  currentGmailMessageId = null;
});
document.querySelectorAll(".optional-fields input").forEach(input => {
  input.addEventListener("input", () => { activeDemoPreset = null; });
});

document.getElementById("brandButton").addEventListener("click", () => {
  setActiveView("home");
});
homeTab.addEventListener("click", () => setActiveView("home"));
reportTab.addEventListener("click", () => setActiveView("report"));

function openModal(tab = "upload") {
  modalBackdrop.classList.remove("hidden");
  selectTab(tab);
  if (tab === "gmail") refreshGmailStatus();
}
function closeModal() { modalBackdrop.classList.add("hidden"); }

function selectTab(tabName) {
  document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.tab === tabName));
  document.getElementById("uploadTab").classList.toggle("hidden", tabName !== "upload");
  document.getElementById("gmailTab").classList.toggle("hidden", tabName !== "gmail");
}

document.getElementById("uploadButton").addEventListener("click", () => openModal("upload"));
document.getElementById("gmailButton").addEventListener("click", () => openModal("gmail"));
document.getElementById("closeModal").addEventListener("click", closeModal);
document.getElementById("gmailConnectAction").addEventListener("click", () => {
  window.location.assign("/auth/google/start");
});
document.getElementById("gmailRefreshAction").addEventListener("click", loadGmailMessages);
document.getElementById("gmailDisconnectAction").addEventListener("click", disconnectGmail);
modalBackdrop.addEventListener("click", event => {
  if (event.target === modalBackdrop) closeModal();
});
document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => selectTab(tab.dataset.tab)));

function setGmailStatus(message, kind = "info") {
  const status = document.getElementById("gmailStatus");
  status.textContent = message;
  status.className = `gmail-status ${kind}`;
}

function setGmailButtonLabel(connected) {
  document.getElementById("gmailButtonLabel").textContent = connected ? "Gmail" : "Connect Gmail";
}

async function responseError(response) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : "Gmail could not complete that request.";
  } catch {
    return "Gmail could not complete that request.";
  }
}

async function refreshGmailButtonLabel() {
  try {
    const response = await fetch("/api/gmail/status");
    if (!response.ok) throw new Error(await responseError(response));
    const status = await response.json();
    setGmailButtonLabel(status.connected === true);
  } catch (error) {
    setGmailButtonLabel(false);
    console.warn(error.message || "Could not check the Gmail connection.");
  }
}

async function refreshGmailStatus() {
  const connectButton = document.getElementById("gmailConnectAction");
  const refreshButton = document.getElementById("gmailRefreshAction");
  const disconnectButton = document.getElementById("gmailDisconnectAction");
  const messageList = document.getElementById("gmailMessageList");
  messageList.replaceChildren();
  setGmailStatus("Checking Gmail connection...");
  try {
    const response = await fetch("/api/gmail/status");
    if (!response.ok) throw new Error(await responseError(response));
    const status = await response.json();
    setGmailButtonLabel(status.connected === true);
    connectButton.classList.toggle("hidden", status.connected);
    connectButton.disabled = !status.configured;
    refreshButton.classList.toggle("hidden", !status.connected);
    disconnectButton.classList.toggle("hidden", !status.connected);
    if (!status.configured) {
      setGmailStatus(
        gmailReturnMessage || "Gmail is not configured. Add Google OAuth credentials to the local .env.",
        "error"
      );
      return;
    }
    if (!status.connected) {
      setGmailStatus(gmailReturnMessage || "Connect your account to choose a recent job-related email.", gmailReturnMessage ? "error" : "info");
      return;
    }
    if (gmailReturnMessage) {
      setGmailStatus(gmailReturnMessage, "error");
      gmailReturnMessage = "";
    } else {
      setGmailStatus("Gmail connected. Loading recent job-related emails...");
    }
    await loadGmailMessages();
  } catch (error) {
    setGmailButtonLabel(false);
    connectButton.classList.remove("hidden");
    connectButton.disabled = false;
    refreshButton.classList.add("hidden");
    disconnectButton.classList.add("hidden");
    setGmailStatus(error.message || "Could not check the Gmail connection.", "error");
  }
}

refreshGmailButtonLabel();

function renderGmailMessages(messages) {
  const messageList = document.getElementById("gmailMessageList");
  messageList.replaceChildren();
  for (const message of messages) {
    const card = document.createElement("article");
    card.className = "email-card";
    const heading = document.createElement("strong");
    heading.textContent = message.subject || "(no subject)";
    const details = document.createElement("div");
    details.className = "email-meta";
    details.textContent = [message.sender, message.date].filter(Boolean).join(" · ");
    const snippet = document.createElement("p");
    snippet.textContent = message.snippet || message.body || "";
    const useButton = document.createElement("button");
    useButton.className = "secondary-button";
    useButton.type = "button";
    useButton.textContent = "Use this email";
    useButton.addEventListener("click", () => importGmailMessage(message));
    card.append(heading, details, snippet, useButton);
    messageList.append(card);
  }
}

async function loadGmailMessages() {
  const refreshButton = document.getElementById("gmailRefreshAction");
  refreshButton.disabled = true;
  setGmailStatus("Loading recent job-related emails...");
  try {
    const response = await fetch("/api/gmail/messages");
    if (response.status === 401) {
      await refreshGmailStatus();
      return;
    }
    if (!response.ok) throw new Error(await responseError(response));
    const data = await response.json();
    const messages = Array.isArray(data.messages) ? data.messages : [];
    renderGmailMessages(messages);
    setGmailStatus(
      messages.length
        ? `Gmail connected · ${messages.length} recent email${messages.length === 1 ? "" : "s"} found.`
        : "Gmail connected · no recent job-related emails found.",
      "success"
    );
  } catch (error) {
    setGmailStatus(error.message || "Could not load Gmail messages. Please try again.", "error");
  } finally {
    refreshButton.disabled = false;
  }
}

async function disconnectGmail() {
  const button = document.getElementById("gmailDisconnectAction");
  button.disabled = true;
  try {
    const response = await fetch("/api/gmail/disconnect", { method: "POST" });
    if (!response.ok) throw new Error(await responseError(response));
    gmailReturnMessage = "";
    await refreshGmailStatus();
  } catch (error) {
    setGmailStatus(error.message || "Could not disconnect Gmail.", "error");
  } finally {
    button.disabled = false;
  }
}

function importGmailMessage(message) {
  const formattedHeaders = [
    message.subject ? `Subject: ${message.subject}` : "",
    message.sender ? `From: ${message.sender}` : "",
  ].filter(Boolean);
  const body = message.body || message.snippet || "";
  offerText.value = (
    message.offer_text
    || `${formattedHeaders.join("\n")}${formattedHeaders.length && body ? "\n\n" : ""}${body}`
  ).trim();
  currentGmailMessageId = message.id;
  activeDemoPreset = null;
  clearFileAttachment();
  for (const id of ["companyInput", "recruiterInput", "roleInput", "urlInput", "domainInput"]) {
    document.getElementById(id).value = "";
  }
  document.getElementById("errorNote").classList.add("hidden");
  closeModal();
  setActiveView("home");
  offerText.focus();
}

document.getElementById("dropZone").addEventListener("click", () => document.getElementById("fileInput").click());
document.getElementById("pasteScreenshot").addEventListener("click", captureScreen);
document.getElementById("closeSources").addEventListener("click", closeSources);
document.getElementById("viewSourcesButton").addEventListener("click", openSources);
overlay.addEventListener("click", closeSources);
document.getElementById("howButton").addEventListener("click", () => alert("OfferCheck compares offer claims with live public evidence."));
document.querySelectorAll("[data-language]").forEach(button => {
  button.addEventListener("click", () => {
    selectedLanguage = button.dataset.language;
    document.querySelectorAll("[data-language]").forEach(item => {
      item.classList.toggle("active", item === button);
    });
  });
});

function processFile(file) {
  if (!file) return;
  if (analysisRunning) {
    showCaptureStatus("An analysis is already running. This file was not attached.");
    return;
  }
  currentGmailMessageId = null;
  if (activeDemoPreset) {
    offerText.value = "";
    for (const id of ["companyInput", "recruiterInput", "roleInput", "urlInput", "domainInput"]) {
      document.getElementById(id).value = "";
    }
  }
  activeDemoPreset = null;
  if (file.size > 10 * 1024 * 1024) {
    document.getElementById("errorNote").textContent = "File exceeds 10 MB.";
    document.getElementById("errorNote").classList.remove("hidden");
    return;
  }
  const allowed = file.type.startsWith("image/")
    || file.type === "application/pdf"
    || file.type === "message/rfc822"
    || file.name.toLowerCase().endsWith(".eml");
  if (!allowed) {
    document.getElementById("errorNote").textContent = "Choose a screenshot, PDF or .eml file.";
    document.getElementById("errorNote").classList.remove("hidden");
    return;
  }
  closeModal();
  showFileAttachment(file, "Ready to analyze");
  showReport(file);
}

document.getElementById("removeAttachment").addEventListener("click", clearFileAttachment);
document.getElementById("fileInput").addEventListener("change", event => {
  processFile(event.target.files[0]);
});

const dropZone = document.getElementById("dropZone");
dropZone.addEventListener("dragover", event => {
  event.preventDefault();
});
dropZone.addEventListener("drop", event => {
  event.preventDefault();
  processFile(event.dataTransfer.files[0]);
});

document.addEventListener("paste", event => {
  const image = [...event.clipboardData.items].find(item => item.type.startsWith("image/"));
  if (!image) return;
  event.preventDefault();
  processFile(image.getAsFile());
});
