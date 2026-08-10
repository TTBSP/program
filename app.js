const BASE = "/program";

const codeBlock = document.getElementById("codeBlock");
const copyButton = document.getElementById("copyButton");
const error = document.getElementById("error");

let loadedCode = "";


/*
URL

/program/GzYGL

↓

GzYGL
*/

function getRoute() {

  let path = location.pathname;

  if (path.startsWith(BASE)) {
    path = path.slice(BASE.length);
  }

  path = path.replace(/^\/+|\/+$/g, "");

  return decodeURIComponent(path);
}


async function loadCode() {

  const route = getRoute();


  /*
  /program/ だけ開いた場合
  */

  if (!route) {

    codeBlock.textContent =
`# TTBSP CODE`;

    hljs.highlightElement(codeBlock);

    return;
  }


  try {

    /*
    routes.json を取得
    */

    const routeResponse =
      await fetch(
        `${BASE}/data/routes.json?t=${Date.now()}`
      );


    if (!routeResponse.ok) {
      throw new Error("routes.json error");
    }


    const routes =
      await routeResponse.json();


    const config =
      routes[route];


    if (!config) {
      throw new Error("route not found");
    }


    /*
    Pythonファイル取得
    */

    const codeResponse =
      await fetch(
        `${config.file}?t=${Date.now()}`
      );


    if (!codeResponse.ok) {
      throw new Error("python file error");
    }


    loadedCode =
      await codeResponse.text();


    /*
    コードをそのまま表示
    */

    codeBlock.textContent =
      loadedCode;


    codeBlock.className =
      `language-${config.language || "python"}`;


    /*
    Python色付け
    */

    hljs.highlightElement(
      codeBlock
    );

  }

  catch (e) {

    console.error(e);

    codeBlock.classList.add(
      "hidden"
    );

    error.classList.remove(
      "hidden"
    );

  }

}


/*
コピー
*/

copyButton.addEventListener(
  "click",
  async () => {

    if (!loadedCode) {
      return;
    }

    await navigator.clipboard.writeText(
      loadedCode
    );


    copyButton.textContent =
      "Copied";


    setTimeout(() => {

      copyButton.textContent =
        "Copy";

    }, 1200);

  }
);


loadCode();
