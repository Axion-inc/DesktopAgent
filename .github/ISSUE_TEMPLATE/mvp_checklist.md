---
name: "MVP 完成チェックリスト（macOS）"
about: "macOS向けMVP（Finder + PDF + Mail下書き + リプレイ + 公開ダッシュボード）の完成判定用チェックリスト"
title: "[MVP] 完成チェック: YYYY-MM-DD"
labels: ["mvp", "qa", "acceptance"]
assignees: []
---

## 概要
このIssueは、**macOS向けMVP（Finder + PDF + Mail下書き + リプレイ + 公開ダッシュボード）** が完成しているかを判定するための受け入れチェックリストです。  
**合格ライン（Pass/Fail）** は文末の「🎯 最終判定」を参照してください。

---

## テスト情報
- テスト実施者: <!-- your name -->
- 日付: <!-- YYYY-MM-DD -->
- 対象ブランチ/コミット: <!-- e.g., main / abc1234 -->
- macOS バージョン: <!-- e.g., 14.5 -->
- Python バージョン: <!-- e.g., 3.11.x -->
- 実行環境/マシン: <!-- e.g., Apple Silicon / Intel -->

---

## ✅ A. 環境 & 起動
- [ ] `README.md` の手順だけで **30分以内** に初回セットアップが完了する
- [ ] `uvicorn app.main:app --reload` でサーバ起動、`/` のヘルス表示が出る
- [ ] `pip install -r requirements.txt` がエラー/ビルド失敗なしで通る

## ✅ B. macOS 権限
- [ ] 初回に **Screen Recording / Automation** の許可状態を診断し、ガイド表示がある
- [ ] 権限未付与時は落ちず、**権限待ちの案内**が出て実行はブロックされる

## ✅ C. DSL & テンプレ
- [ ] `/plans/new` にYAMLエディタがあり、**構文検証**で行番号つきエラー表示が出る
- [ ] **Dry-run** で「対象操作/推定時間/破壊的操作の有無」を含む **計画書** が生成される
- [ ] `plans/templates/weekly_report.yaml` を読み込み、**承認→Run作成** ができる

## ✅ D. Finder（ファイル操作）
- [ ] `find_files`：複数 `roots`・`limit` が動作し、0件時は **警告** を返す
- [ ] `rename`：`{{date}}_{{index}}_{{basename}}` 形式で一括リネーム（上書き回避）
- [ ] `move_to`：宛先が無ければ **自動作成**。権限エラーは分かりやすく表示

## ✅ E. PDFユーティリティ
- [ ] `pdf_merge`：指定順に結合し、**ページ数が期待通り**
- [ ] `pdf_extract_pages`：`"1,3-5"` の範囲指定が正しく機能（逆順/重複の扱いを明記）
- [ ] 壊れ/暗号化PDFで、**失敗段階を特定** できるエラーメッセージ

## ✅ F. Mail.app 下書き（送信なし）
- [ ] `compose_mail`：宛先/件名/本文の **ドラフト作成** ができる
- [ ] `attach_files`：フルパス添付（存在しないファイルは **検出して失敗**）
- [ ] `save_draft`：Mail.app の「下書き」に保存（手動確認可）
- [ ] AppleScriptエラーは **番号 + 対処ヒント** を含む整形出力

## ✅ G. リプレイ & ログ
- [ ] `/runs`：実行履歴（ステータス/所要時間/計画名/作成者）が一覧表示
- [ ] `/runs/{id}`：**タイムライン**（各ステップの入出力・結果・所要時間・**スクショ**）
- [ ] スクショは `runId_stepIndex.png` 命名で欠損なく保存/表示
- [ ] **共有リンク** `/public/runs/{public_id}` が未ログインでも閲覧可（読み取り専用）

## ✅ H. 公開ダッシュボード & /metrics
- [ ] `/public/dashboard`：直近24hの **成功率 / 中央値所要時間 / 失敗理由Top3 / 実行本数** を表示
- [ ] `/metrics`：上記内容をJSONで返す（Shields バッジ等から参照可能）

## ✅ I. セキュリティ / PII マスキング
- [ ] 共有ページで **メール/人名/電話/絶対パス** をデフォルトでマスク
- [ ] 外部送信（外部API/LLM/トラッキング）が **一切ない**（コード検索で確認）
- [ ] 破壊的操作（上書き/削除）は未実装、または **新規出力** で回避

## ✅ J. エラーハンドリング & UX
- [ ] 失敗時に **最初に読む1枚**（原因/対処/再現リンク）が上部に表示
- [ ] 代表的エラー（0件ヒット/権限未付与/パス不正/PDF破損）の **再現テスト** が通る
- [ ] クラッシュせず、詳細は `logs/app.log` に記録

## ✅ K. 安定性テスト（耐久）
- [ ] 同一テンプレを **20回連続実行** して **19/20以上成功**
- [ ] 実行所要時間の **95%タイル** をダッシュボード表示

## ✅ L. OSS & Build in Public 体裁
- [ ] **MIT LICENSE / CODE_OF_CONDUCT.md / CONTRIBUTING.md / SECURITY.md** が揃っている
- [ ] `.github/workflows/ci.yml` で **pytest + flake8** が通る
- [ ] Issue/PR テンプレあり（スクショ・`/public/runs/<id>` 記入欄）
- [ ] `CHANGELOG.md` に公開後の変更履歴（週1以上）
- [ ] `sample_data/` にダミーPDF（ライセンス明記）

## ✅ M. Windows 将来対応の布石
- [ ] `os_adapters/base.py` に **Mail/Preview 抽象IF** が定義済み
- [ ] `os_adapters/macos.py` は実装、`os_adapters/windows.py` は **スタブ** がありテスト通過
- [ ] `scripts/dev_setup_windows.ps1` に **設計方針/TODO** を記載

---

## 🔎 受け入れテスト手順（短縮版）
1. **サンプル実行**  
   `plans/templates/weekly_report.yaml` を `/plans/new` で読み込み → **検証** → **Dry-run** → **承認** → **実行**  
   期待結果：`~/Reports/weekly_YYYYMMDD.pdf` 作成、Preview起動、Mailに **下書き** 生成
2. **リプレイ確認**  
   `/runs/{id}` の **スクショ**・入出力を確認。共有リンク `/public/runs/{public_id}` をプライベートウィンドウで表示し、**PIIマスク** を確認
3. **ダッシュボード確認**  
   `/public/dashboard` のメトリクス表示、`/metrics` のJSONスキーマを確認
4. **耐久**  
   同テンプレを20回連続実行 → **19回以上成功**。失敗時は **整形エラー** を確認
5. **代表エラー**  
   空の入力、壊れPDF混在、権限未付与でそれぞれ適切なエラー/ガイドが出る

---

## 📎 証跡（リンク/添付）
- リプレイ共有URL: <!-- /public/runs/xxxx -->
- ダッシュボードURL: <!-- /public/dashboard -->
- `/metrics` JSONサンプル: <!-- 添付 or ペースト -->
- スクリーンショット/ログ: <!-- 画像/ログを添付 -->

---

## 🎯 最終判定（Maintainer用）
- [ ] **機能**：D〜H の各項目が **すべて Pass**
- [ ] **品質**：K の耐久条件（20回中19回成功）を満たす
- [ ] **公開性**：L のOSS体裁とダッシュボード公開が揃う
- [ ] **安全**：I のマスキングと外部送信ゼロが確認できる

**結論:** <!-- Pass / Fail（理由も記載） -->

