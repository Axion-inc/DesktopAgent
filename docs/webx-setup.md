# WebX Setup Guide (Phase 5)

## クイックスタート

### 1. Native Host インストール

```bash
# 自動インストールスクリプト実行
./scripts/install_native_host.sh

# 手動でChromeに拡張をインストール
# 1. Chrome → chrome://extensions/
# 2. Developer mode ON 
# 3. Load unpacked → webx-extension フォルダ選択
# 4. 表示されたExtension IDをメモ
```

### 2. 設定ファイル更新

`configs/web_engine.yaml` を編集：

```yaml
engine: "extension"  # 拡張エンジンを使用

extension:
  id: "実際のExtension ID"  # ChromeでメモしたIDに置換
  handshake_token: "your-secure-token"  # プロダクション用に変更
  timeout_ms: 15000
  enable_debugger_upload: false  # DoD要件: 既定OFF
```

### 3. 動作確認

```bash
# 契約テスト実行
python -m pytest tests/contract/test_webx_protocol.py -v

# 拡張エンジンで既存テンプレート実行
./cli.py run plans/templates/csv_to_form.yaml --var engine=extension

# メトリクス確認
curl localhost:8000/metrics | jq '{
  webx_steps_24h,
  webx_failures_24h,
  webx_engine_share_24h,
  webx_upload_success_24h
}'
```

## セットアップ詳細

### Native Messaging Host 登録

**macOS:**
```bash
# マニフェスト配置先
~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.desktopagent.webx.json

# 実行ファイル配置先
/usr/local/bin/desktopagent-webx-host
```

**Linux:**
```bash
# マニフェスト配置先
~/.config/google-chrome/NativeMessagingHosts/com.desktopagent.webx.json

# 実行ファイル配置先  
/usr/local/bin/desktopagent-webx-host
```

### 権限設定

#### 必須権限（manifest.json）
```json
{
  "permissions": [
    "nativeMessaging",
    "activeTab",
    "scripting", 
    "storage",
    "downloads"
  ]
}
```

#### オプション権限（必要時のみ要求）
```json
{
  "optional_permissions": [
    "debugger"  // enable_debugger_upload=true 時のみ
  ]
}
```

### セキュリティ設定

#### 拡張ID Allowlist
```yaml
# configs/web_engine.yaml
extension:
  security:
    allowed_extension_ids:
      - "actual_extension_id_here"
```

#### ハンドシェイク認証
```yaml
extension:
  handshake_token: "change-me-production"
```

## DSL使用例

### エンジン指定方法

#### 1. グローバル設定
```yaml
# configs/web_engine.yaml
engine: "extension"
```

#### 2. テンプレート指定
```yaml
dsl_version: "1.1"
name: "Extension Engine Demo"
execution:
  web_engine: "extension"  # テンプレート全体に適用

steps:
  - open_browser:
      url: "https://example.com"
      # engine: extension (継承)
```

#### 3. ステップ別指定
```yaml
steps:
  - open_browser:
      url: "https://example.com"
      engine: "playwright"  # このステップのみPlaywright
      
  - fill_by_label:
      label: "氏名"
      text: "{{name}}"
      engine: "extension"   # このステップのみ拡張
```

### 証跡保存 (DoD要件)

```yaml
steps:
  # 各ステップ後にスクショ・DOMスキーマが自動保存される
  - open_browser:
      url: "https://form.example.com"
      engine: "extension"
      # → artifacts/screenshots/{run_id}_step_0_web.png
      # → artifacts/schemas/{run_id}_step_0_dom.json
      
  - capture_screen_schema:
      where: "web"  # DOM schema 明示的キャプチャ
```

## トラブルシュート

### よくあるエラー

#### 1. Native Host が見つからない
```bash
# 解決方法
ls -la /usr/local/bin/desktopagent-webx-host
chmod +x /usr/local/bin/desktopagent-webx-host

# マニフェスト確認
cat ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/com.desktopagent.webx.json
```

#### 2. ハンドシェイク失敗
```bash
# 拡張IDが一致しているか確認
# chrome://extensions/ で実際のIDをコピー
# configs/web_engine.yaml の extension.id を更新
```

#### 3. Permission Denied エラー
```yaml
# enable_debugger_upload が必要なテンプレートの場合
extension:
  enable_debugger_upload: true  # 一時的にON
```

### デバッグモード

```yaml
# configs/web_engine.yaml
development:
  log_engine_selection: true
  mock_extension_responses: false  # true = 拡張無しでテスト
  force_engine: "extension"        # エンジン強制指定
```

### ログ確認

```bash
# Native Host ログ
tail -f /tmp/webx_native_host.log

# 拡張ログ (Chrome Developer Tools)
# 1. chrome://extensions/
# 2. Desktop Agent WebX → Details → Inspect views: background page
# 3. Console タブでログ確認
```

## メトリクス監視

### DoD 要件指標

```bash
# メトリクス取得
curl localhost:8000/metrics | jq '{
  webx_steps_24h: .webx_steps_24h,
  webx_failures_24h: .webx_failures_24h,
  webx_engine_share_24h: .webx_engine_share_24h,
  webx_upload_success_24h: .webx_upload_success_24h
}'
```

### KPI 目標値
- `webx_engine_share_24h.extension ≥ 0.80`
- `webx_upload_success_24h ≥ 0.95`
- `webx_failures_24h / webx_steps_24h ≤ 0.05`
- 誤送信 = 0（承認ゲート維持）

### ダッシュボード

Web UI でメトリクス確認：
```bash
# ダッシュボード表示
open http://localhost:8000/public/dashboard

# Phase 5 カード確認
# - WebX Engine Distribution
# - Extension Success Rate
# - DOM Schema Captures
# - Native Messaging Health
```

## 運用ガイドライン

### プロダクション配備

1. **セキュリティ設定**
   ```yaml
   extension:
     handshake_token: "$(openssl rand -hex 32)"
     enable_debugger_upload: false
   ```

2. **拡張配布**
   - 組織内でExtension IDを統一
   - Managed Policyでの配布推奨

3. **監査ログ**
   ```bash
   # RPC呼び出し履歴確認
   grep "webx\." logs/desktop-agent.log
   ```

### パフォーマンス最適化

```yaml
# タイムアウト調整
extension:
  timeout_ms: 10000  # 高速環境では短縮

# 同期処理制限
global:
  max_concurrent: 3  # 拡張エンジン使用時
```

### バックアップ戦略

```yaml
# フォールバック設定
engine: "extension"
fallback_engine: "playwright"  # 拡張接続失敗時

auto_selection:
  fallback_to_playwright: true
  check_extension_health: true
```

## 移行ガイド

### Playwright → Extension

```bash
# 1. 段階的移行（特定テンプレートのみ）
./cli.py run template.yaml --var engine=extension

# 2. メトリクス比較
curl localhost:8000/metrics | jq '{
  playwright: .web_step_success_rate_24h,
  extension: .extension_engine_success_rate_24h
}'

# 3. 全体移行
# configs/web_engine.yaml
engine: "extension"
```

### 移行チェックリスト

- [ ] Native Host インストール完了
- [ ] Extension ID 設定済み
- [ ] 契約テストパス
- [ ] サンプルテンプレート実行成功
- [ ] メトリクス出力確認
- [ ] 承認ゲート動作確認
- [ ] エラーハンドリング確認
- [ ] パフォーマンス比較実施

---

**Phase 5 WebX完全セットアップガイド完了**

問題が発生した場合は、GitHub Issues または docs/phase5_webx.md の詳細ガイドを参照してください。