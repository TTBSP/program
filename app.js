
const viewer = document.getElementById("viewer");
const errorView = document.getElementById("errorView");
const routePill = document.getElementById("routePill");
const pageTitle = document.getElementById("pageTitle");
const pageDescription = document.getElementById("pageDescription");
const codeBlock = document.getElementById("codeBlock");
const lineNumbers = document.getElementById("lineNumbers");
const languageLabel = document.getElementById("languageLabel");
const copyButton = document.getElementById("copyButton");
const copyLabel = document.getElementById("copyLabel");
const downloadButton = document.getElementById("downloadButton");
const toast = document.getElementById("toast");

let loadedCode = "";

function getRouteName() {
  return decodeURIComponent(location.pathname.replace(/^\/+|\/+$/g, ""));
}

function showError() {
  viewer.classList.add("hidden");
  errorView.classList.remove("hidden");
  document.title = "Not Found | TTBSP CODE";
}

function renderLineNumbers(code) {
  const count = Math.max(1, code.split("\n").length);
  lineNumbers.textContent = Array.from({ length: count }, (_, i) => i + 1).join("\n");
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 1500);
}

async function loadViewer() {
  const route = getRouteName();

  // Root page is intentionally simple. Add a route to routes.json and open /route-name.
  if (!route) {
    pageTitle.textContent = "TTBSP CODE";
    pageDescription.textContent = "研究・資料用のソースコード共有ビューア";
    routePill.textContent = "/";
    codeBlock.textContent = "# ttbsp.click/<route>\n# 公開URLからコードを表示します。";
    renderLineNumbers(codeBlock.textContent);
    if (window.hljs) hljs.highlightElement(codeBlock);
    return;
  }

  routePill.textContent = "/" + route;

  try {
    const routeResponse = await fetch("/data/routes.json", { cache: "no-store" });
    if (!routeResponse.ok) throw new Error("routes.json could not be loaded");

    const routes = await routeResponse.json();
    const config = routes[route];

    if (!config || !config.file) {
      showError();
      return;
    }

    const codeResponse = await fetch(config.file, { cache: "no-store" });
    if (!codeResponse.ok) throw new Error("source file could not be loaded");

    loadedCode = await codeResponse.text();

    // Deliberately do NOT display the original .py filename.
    pageTitle.textContent = config.title || "Research Code";
    pageDescription.textContent = config.description || "研究・資料用に公開されたソースコードです。";
    languageLabel.textContent = (config.language || "python").toUpperCase();

    codeBlock.className = `language-${config.language || "python"}`;
    codeBlock.textContent = loadedCode;
    renderLineNumbers(loadedCode);

    if (window.hljs) hljs.highlightElement(codeBlock);

    copyButton.disabled = false;
    downloadButton.classList.remove("disabled");
    downloadButton.removeAttribute("aria-disabled");
    downloadButton.href = config.file;

    // Download name can be neutral too, so the original filename is not exposed in UI.
    downloadButton.setAttribute("download", config.downloadName || "research-code.py");

    document.title = `${config.title || "Research Code"} | TTBSP CODE`;
  } catch (error) {
    console.error(error);
    showError();
  }
}

copyButton.addEventListener("click", async () => {
  if (!loadedCode) return;

  try {
    await navigator.clipboard.writeText(loadedCode);
    copyLabel.textContent = "コピー済み";
    showToast("コードをコピーしました");
    setTimeout(() => copyLabel.textContent = "コピー", 1400);
  } catch {
    const area = document.createElement("textarea");
    area.value = loadedCode;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    copyLabel.textContent = "コピー済み";
    showToast("コードをコピーしました");
    setTimeout(() => copyLabel.textContent = "コピー", 1400);
  }
});

loadViewer();
