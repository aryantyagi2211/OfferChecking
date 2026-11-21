const offerText = document.getElementById("offerText");
const homeView = document.getElementById("homeView");
const investigatingView = document.getElementById("investigatingView");
const resultView = document.getElementById("resultView");
const modalBackdrop = document.getElementById("modalBackdrop");
const sourcesDrawer = document.getElementById("sourcesDrawer");
const overlay = document.getElementById("overlay");
let selectedLanguage = "simple_english";

const presets = {
  fee: offerText.value,
  whatsapp: "Congratulations! WhatsApp job offer. Pay Rs 2,499 to start work. No interview. Role: data entry. Contact HR on Telegram.",
  real: "We invite you to interview for the listed Product Analyst role. Review the details on the company careers page. No fee is required."
};

async function loadReport() {
  const response = await fetch("mock/report.json");
  if (!response.ok) throw new Error("Could not load report");
  return response.json();
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
  const stateClass = report.verdict_level === "UNVERIFIED"
    ? "unverified"
    : report.verdict_level === "NO_RED_FLAGS_FOUND"
      ? "no-red-flags"
      : "";
  card.className = `verdict-card ${stateClass}`;
  card.innerHTML = `
    <div>
      <span class="badge ${stateClass}">${verdictName(report.verdict_level)}</span>
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
      ? sources.map(source => `<button class="source-chip" data-source="${source.id}">${sourceLabel(source)}</button>`).join(" ")
      : '<span class="no-source">No source found</span>';
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

  ledger.querySelectorAll("[data-source]").forEach(button => {
    button.addEventListener("click", () => openSources(button.dataset.source));
  });
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

async function showReport(file = null) {
  const errorNote = document.getElementById("errorNote");
  errorNote.classList.add("hidden");
  try {
    const text = offerText.value.trim();
    homeView.classList.add("hidden");
    investigatingView.classList.remove("hidden");
    document.getElementById("investigationOffer").textContent = text;
    renderProgress();
    const body = new FormData();
    body.append("text", text);
    body.append("language", selectedLanguage);
    if (file) body.append("file", file);
    const response = await fetch("/analyze", { method: "POST", body });
    if (!response.ok) throw new Error("Could not start analysis");
    const job = await response.json();
    connectLiveSteps(job.job_id);
  } catch (error) {
    errorNote.textContent = "We could not load the report. Check the connection and try again.";
    errorNote.classList.remove("hidden");
  }
}

function renderProgress() {
  const steps = [
    ["Reading the offer", "Done", "done"],
    ["Finding Northgate's official site and careers page", 'Searched: "Northgate Technologies careers"', "done"],
    ["Looking for Northgate's fraud warning page", 'Searched: "Northgate recruitment fraud"', "running"],
    ["Searching scam reports", "Waiting", "waiting"],
    ["Writing your result", "Waiting", "waiting"]
  ];
  document.getElementById("progressSteps").innerHTML = steps.map(([label, detail, status], index) => `
    <div class="progress-step" data-step="${["reading","official","fraud_notice","scam_reports","writing"][index]}">
      <span class="step-icon ${status}">${status === "done" ? "✓" : ""}</span>
      <div><strong>${label}</strong><small class="step-detail">${detail}</small></div>
    </div>
  `).join("");
  document.getElementById("progressFill").style.width = "60%";
}

function connectLiveSteps(jobId) {
  if (!jobId || !window.EventSource) return;
  const stream = new EventSource(`/stream/${encodeURIComponent(jobId)}`);
  stream.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    if (message.type === "error") {
      stream.close();
      document.getElementById("errorNote").textContent = message.message;
      document.getElementById("errorNote").classList.remove("hidden");
      investigatingView.classList.add("hidden");
      homeView.classList.remove("hidden");
      return;
    }
    if (message.type === "step") {
      const existing = document.querySelector(`[data-step="${message.id}"]`);
      if (existing) {
        existing.dataset.status = message.status;
        const icon = existing.querySelector(".step-icon");
        icon.className = `step-icon ${message.status}`;
        icon.textContent = message.status === "done" ? "✓" : "";
        existing.querySelector(".step-detail").textContent =
          message.query ? `Searched: "${message.query}"` : message.label;
      }
    }
    if (message.type === "report") {
      stream.close();
      renderLiveReport(message);
    }
  });
}

function renderLiveReport(report) {
  investigatingView.classList.add("hidden");
  resultView.classList.remove("hidden");
  document.getElementById("highlightedOffer").innerHTML = highlightOffer(offerText.value.trim(), report.claims);
  renderVerdict(report);
  renderClaims(report);
  renderActions(report);
}

function openSources(sourceId) {
  loadReport().then(report => {
    document.getElementById("sourceList").innerHTML = report.sources.map(source => `
      <article class="source-card">
        <span class="source-tag">${source.source_type[0].toUpperCase()}${source.source_type.slice(1)}</span>
        <h3>${escapeHtml(source.title)}</h3>
        <p>${escapeHtml(source.domain)}</p>
        <p>${escapeHtml(source.snippet)}</p>
        <a href="${escapeHtml(source.url)}" target="_blank" rel="noopener">Open source</a>
      </article>
    `).join("");
    if (sourceId) {
      const match = report.sources.find(source => source.id === sourceId);
      if (match) document.querySelector(`[data-source="${sourceId}"]`)?.scrollIntoView();
    }
  });
  sourcesDrawer.classList.remove("hidden");
  overlay.classList.remove("hidden");
}

function closeSources() {
  sourcesDrawer.classList.add("hidden");
  overlay.classList.add("hidden");
}

async function shareResult() {
  const report = await loadReport();
  const text = `${verdictName(report.verdict_level)}\n${report.headline}\n${report.summary}`;
  await navigator.clipboard.writeText(text);
  document.getElementById("shareButton").textContent = "Copied";
}

document.getElementById("checkButton").addEventListener("click", () => {
  if (!offerText.value.trim()) {
    document.getElementById("errorNote").textContent = "Paste an offer or add a file first.";
    document.getElementById("errorNote").classList.remove("hidden");
    offerText.focus();
    return;
  }
  showReport();
});

document.querySelectorAll("[data-preset]").forEach(button => {
  button.addEventListener("click", () => {
    offerText.value = presets[button.dataset.preset];
  });
});

document.getElementById("brandButton").addEventListener("click", () => {
  resultView.classList.add("hidden");
  investigatingView.classList.add("hidden");
  homeView.classList.remove("hidden");
});

function openModal(tab = "upload") {
  modalBackdrop.classList.remove("hidden");
  selectTab(tab);
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
modalBackdrop.addEventListener("click", event => {
  if (event.target === modalBackdrop) closeModal();
});
document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => selectTab(tab.dataset.tab)));
document.getElementById("dropZone").addEventListener("click", () => document.getElementById("fileInput").click());
document.getElementById("pasteScreenshot").addEventListener("click", () => openModal("upload"));
document.getElementById("closeSources").addEventListener("click", closeSources);
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
  offerText.value = "Extracting text from screenshot...";
  showReport(file);
}

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
