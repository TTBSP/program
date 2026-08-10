const codeBlock = document.getElementById("codeBlock");
const copyButton = document.getElementById("copyButton");

let loadedCode = "";

async function loadCode() {
  try {
    const response = await fetch(
      "/program/python/shinsi_1.py?v=" + Date.now()
    );

    if (!response.ok) {
      throw new Error("Pythonファイルを取得できません: " + response.status);
    }

    loadedCode = await response.text();

    codeBlock.textContent = loadedCode;

    if (window.hljs) {
      codeBlock.removeAttribute("data-highlighted");
      hljs.highlightElement(codeBlock);
    }

  } catch (error) {
    console.error(error);

    codeBlock.textContent =
      "読み込みエラー\n\n" + error.message;
  }
}

copyButton.addEventListener("click", async () => {
  if (!loadedCode) return;

  await navigator.clipboard.writeText(loadedCode);

  copyButton.textContent = "Copied";

  setTimeout(() => {
    copyButton.textContent = "Copy";
  }, 1200);
});

loadCode();
