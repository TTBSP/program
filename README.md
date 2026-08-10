コードビューア。

## 使い方

1. この一式を GitHub Pages のリポジトリ直下へ配置
2. `python/shinsi_1.py` を実際のPythonファイルに置き換える
3. GitHub Pagesを公開
4. `https://ttbsp.click/GzYGL` にアクセス

## ルートを追加する

`data/routes.json` に項目を追加します。

```json
{
  "GzYGL": {
    "title": "Research Code",
    "description": "研究・資料用に公開されたPythonコードです。",
    "language": "python",
    "file": "/python/shinsi_1.py",
    "downloadName": "research-code.py"
  },
  "ABC123": {
    "title": "Simulation",
    "description": "シミュレーション用コードです。",
    "language": "python",
    "file": "/python/simulation.py",
    "downloadName": "simulation.py"
  }
}
```

## 注意

GitHub Pagesは静的サイトなので、サイト上の管理画面から安全にGitHubへ直接保存するには
GitHub API用の認証や別バックエンドが必要です。
この初期版では `routes.json` を編集してルートを追加する方式です。
