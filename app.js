const BASE = "/program";

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


/*
--------------------------------
URLからルーティング名を取得
--------------------------------
例:

/program/GzYGL
↓
GzYGL
*/

function getRouteName() {

  let path = location.pathname;

  if (path.startsWith(BASE)) {
    path = path.slice(BASE.length);
  }

  path = path.replace(/^\/+|\/+$/g, "");

  return decodeURIComponent(path);
}


/*
--------------------------------
404画面
--------------------------------
*/

function showError() {

  viewer.classList.add("hidden");

  errorView.classList.remove("hidden");

  document.title = "Not Found | TTBSP CODE";
}


/*
--------------------------------
行番号生成
--------------------------------
*/

function renderLineNumbers(code) {

  const count = Math.max(
    1,
    code.split("\n").length
  );

  lineNumbers.textContent =
    Array.from(
      { length: count },
      (_, i) => i + 1
    ).join("\n");
}


/*
--------------------------------
通知
--------------------------------
*/

function showToast(message) {

  toast.textContent = message;

  toast.classList.add("show");

  clearTimeout(showToast.timer);

  showToast.timer = setTimeout(() => {

    toast.classList.remove("show");

  }, 1500);
}


/*
--------------------------------
コード読み込み
--------------------------------
*/

async function loadViewer() {

  const route = getRouteName();


  /*
  ------------------------------
  /program/ を開いた場合
  ------------------------------
  */

  if (!route) {

    routePill.textContent = "/";

    pageTitle.textContent =
      "TTBSP CODE";

    pageDescription.textContent =
      "研究・資料用のソースコード共有ビューア";

    codeBlock.textContent =
`# TTBSP CODE

# 公開されたURLから
# ソースコードを表示します。`;

    renderLineNumbers(
      codeBlock.textContent
    );

    if (window.hljs) {

      hljs.highlightElement(
        codeBlock
      );

    }

    return;
  }


  /*
  ------------------------------
  ルーティング表示
  ------------------------------
  */

  routePill.textContent =
    "/" + route;


  try {


    /*
    ----------------------------
    routes.json取得
    ----------------------------
    */

    const routeResponse =
      await fetch(
        `${BASE}/data/routes.json`,
        {
          cache: "no-store"
        }
      );


    if (!routeResponse.ok) {

      throw new Error(
        "routes.json could not be loaded"
      );

    }


    const routes =
      await routeResponse.json();


    const config =
      routes[route];


    /*
    ----------------------------
    ルーティングが存在しない
    ----------------------------
    */

    if (
      !config ||
      !config.file
    ) {

      showError();

      return;
    }


    /*
    ----------------------------
    Pythonファイル取得
    ----------------------------
    */

    const codeResponse =
      await fetch(
        config.file,
        {
          cache: "no-store"
        }
      );


    if (!codeResponse.ok) {

      throw new Error(
        "source file could not be loaded"
      );

    }


    loadedCode =
      await codeResponse.text();


    /*
    ----------------------------
    ページ情報
    ----------------------------
    */

    pageTitle.textContent =
      config.title ||
      "Research Code";


    pageDescription.textContent =
      config.description ||
      "研究・資料用に公開されたソースコードです。";


    languageLabel.textContent =
      (
        config.language ||
        "python"
      ).toUpperCase();


    /*
    ----------------------------
    コード表示
    ----------------------------
    */

    codeBlock.className =
      `language-${config.language || "python"}`;


    codeBlock.textContent =
      loadedCode;


    renderLineNumbers(
      loadedCode
    );


    /*
    ----------------------------
    シンタックスハイライト
    ----------------------------
    */

    if (window.hljs) {

      hljs.highlightElement(
        codeBlock
      );

    }


    /*
    ----------------------------
    コピーボタン有効化
    ----------------------------
    */

    copyButton.disabled =
      false;


    /*
    ----------------------------
    ダウンロード
    ----------------------------
    */

    downloadButton.classList.remove(
      "disabled"
    );


    downloadButton.removeAttribute(
      "aria-disabled"
    );


    downloadButton.href =
      config.file;


    /*
    元の shinsi_1.py という名前は
    画面には表示しない
    */

    downloadButton.setAttribute(
      "download",
      config.downloadName ||
      "research-code.py"
    );


    /*
    ----------------------------
    ブラウザタイトル
    ----------------------------
    */

    document.title =
      `${config.title || "Research Code"} | TTBSP CODE`;


  }

  catch (error) {

    console.error(error);

    showError();

  }

}


/*
--------------------------------
コピー処理
--------------------------------
*/

copyButton.addEventListener(
  "click",
  async () => {

    if (!loadedCode) {
      return;
    }


    try {

      await navigator.clipboard.writeText(
        loadedCode
      );


      copyLabel.textContent =
        "コピー済み";


      showToast(
        "コードをコピーしました"
      );


      setTimeout(() => {

        copyLabel.textContent =
          "コピー";

      }, 1400);

    }


    catch {

      /*
      Clipboard APIが使えない場合
      */

      const area =
        document.createElement(
          "textarea"
        );


      area.value =
        loadedCode;


      document.body.appendChild(
        area
      );


      area.select();


      document.execCommand(
        "copy"
      );


      area.remove();


      copyLabel.textContent =
        "コピー済み";


      showToast(
        "コードをコピーしました"
      );


      setTimeout(() => {

        copyLabel.textContent =
          "コピー";

      }, 1400);

    }

  }
);


/*
--------------------------------
起動
--------------------------------
*/

loadViewer();
