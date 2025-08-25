# Desktop Agent Phase 4 運用ガイド

Phase 4で追加された新機能の運用方法について説明します。

## 📋 目次

- [Queue Management (キュー管理)](#queue-management)
- [RBAC (Role-Based Access Control)](#rbac)
- [Scheduler & Triggers](#scheduler--triggers)
- [Secrets Management](#secrets-management)  
- [Failure Clustering](#failure-clustering)
- [HITL (Human-in-the-Loop)](#hitl)
- [監視・メトリクス](#monitoring)
- [トラブルシューティング](#troubleshooting)

---

## Queue Management

### 概要
キューシステムにより、複数の実行要求を効率的に処理し、リソースを適切に管理できます。

### 基本設定

**設定ファイル**: `configs/orchestrator.yaml`

```yaml
queues:
  default:
    max_concurrent: 3
    priority_levels: 9
    retry_policy:
      max_attempts: 3
      backoff_multiplier: 1.5
      
  high_priority:
    max_concurrent: 5
    priority_levels: 9
    
  background:
    max_concurrent: 1
```

### APIでの使用

```python
# 高優先度でキューに追加
queue_manager = get_queue_manager()
run_id = queue_manager.enqueue_run({
    "template": "important_task.yaml",
    "variables": {"target": "production"},
    "queue": "high_priority",
    "priority": 1  # 1が最高優先度
})
```

### 運用のポイント

1. **並列数調整**: システムリソースに応じて `max_concurrent` を調整
2. **優先度設定**: 重要なタスクは priority 1-3、通常は 5、バックグラウンドは 7-9
3. **キュー分離**: 用途別にキューを分けてリソース競合を回避

---

## RBAC (Role-Based Access Control)

### 概要
役割ベースのアクセス制御により、ユーザーごとに適切な権限を付与できます。

### 役割の種類

| 役割 | 権限 | 用途 |
|------|------|------|
| **Admin** | 全権限 | システム管理者 |
| **Editor** | 実行・一時停止・承認 | プロジェクトマネージャー |
| **Runner** | 実行・参照 | 実行担当者 |
| **Viewer** | 参照のみ | 監視・レポート担当者 |

### ユーザー管理

```bash
# 管理者でユーザー作成
curl -X POST http://localhost:8000/api/admin/users \
  -u admin:password \
  -H "Content-Type: application/json" \
  -d '{
    "username": "project_manager",
    "password": "secure_password",
    "active": true
  }'
```

### エンドポイント保護

実装例：
```python
from app.middleware.auth import require_editor

@app.post("/api/runs/{run_id}/pause")
@require_editor
async def pause_run(run_id: int, current_user: RBACUser = Depends(get_current_user)):
    # Editor以上の権限が必要
    pass
```

### セキュリティ考慮事項

1. **パスワード管理**: 強力なパスワードを使用
2. **定期監査**: 監査ログを定期的に確認
3. **最小権限の原則**: 必要最小限の権限のみ付与

---

## Scheduler & Triggers

### 概要
自動実行のためのスケジューラーと各種トリガー機能。

### Cron Scheduler

**設定ファイル**: `configs/schedules.yaml`

```yaml
schedules:
  - id: "daily_report" 
    name: "日次レポート生成"
    cron: "0 9 * * *"  # 毎日9時
    template: "daily_report.yaml"
    queue: "background"
    priority: 5
    enabled: true
    variables:
      report_type: "daily"

  - id: "weekly_backup"
    name: "週次バックアップ"  
    cron: "0 2 * * 0"  # 毎週日曜2時
    template: "backup.yaml"
    queue: "default"
    priority: 3
```

### Folder Watcher

フォルダ監視による自動実行：

```python
from app.orchestrator.watcher import get_watcher

watcher = get_watcher()
watcher.add_watcher(WatchConfig(
    id="invoice_processor",
    name="請求書処理",
    watch_path="/path/to/invoices",
    template="process_invoice.yaml",
    patterns=["*.pdf"],
    events=["created"],
    debounce_ms=5000,
    queue="default",
    priority=5
))
```

### Webhook

外部システムからの通知による実行：

```python
from app.orchestrator.webhook import get_webhook_service

webhook_service = get_webhook_service()
webhook_service.add_webhook(WebhookConfig(
    id="github_deploy",
    name="GitHub Deploy Hook", 
    endpoint="/webhooks/deploy",
    template="deploy.yaml",
    secret="your_webhook_secret",
    allowed_ips=["192.30.252.0/22"],  # GitHub IP range
    extract_variables=["repository.name", "head_commit.id"]
))
```

---

## Secrets Management

### 概要
機密情報を安全に管理・利用するシステム。

### 設定方法

#### 1. Keychain/Keyring (推奨)

```bash
# macOS Keychain
security add-generic-password -s "com.axion.desktop-agent" \
  -a "api_key" -w "your_secret_value"

# Linux keyring
secret-tool store --label="Desktop Agent API Key" \
  service com.axion.desktop-agent account api_key
```

#### 2. 環境変数

```bash
export DESKTOP_AGENT_SECRET_API_KEY="your_secret_value"
export DESKTOP_AGENT_SECRET_DB_PASSWORD="db_password"
```

#### 3. 暗号化ファイル

```python
from app.security.secrets import store_secret

store_secret("api_key", "your_secret_value", "external_api")
```

### DSLでの使用

```yaml
dsl_version: "1.1"
name: "API Call with Secrets"
steps:
  - make_request:
      url: "https://api.example.com/data"
      headers:
        Authorization: "Bearer {{secrets://api_key}}"
        # または service/key形式
        X-API-Key: "{{secrets://external_api/api_key}}"
```

### セキュリティベストプラクティス

1. **秘密情報の保護**
   - ログに出力されない
   - エラーメッセージにマスク適用
   - メモリから適切にクリア

2. **アクセス制御**
   - 必要最小限のアクセス権限
   - 定期的な秘密情報のローテーション

3. **監査**
   - 秘密情報アクセスログの監視
   - 異常なアクセスパターンの検出

---

## Failure Clustering

### 概要
失敗パターンを自動分析し、対処方法を提案するシステム。

### 設定

失敗分析は自動実行されますが、カスタムルールも追加可能：

```python
from app.analytics.failure_clustering import get_failure_analyzer

analyzer = get_failure_analyzer()

# カスタムルール追加例
custom_rules = {
    "NETWORK_TIMEOUT": {
        "patterns": [r"timeout.*network", r"connection.*timed out"],
        "display_name": "ネットワークタイムアウト",
        "recommended_actions": [
            "ネットワーク接続を確認",
            "タイムアウト値の調整を検討",
            "プロキシ設定の確認"
        ],
        "severity": "medium"
    }
}
```

### ダッシュボードでの確認

メトリクスエンドポイントで失敗クラスターを確認：

```bash
curl http://localhost:8000/metrics | jq '.top_failure_clusters_24h'
```

### 対応フロー

1. **失敗検知**: 自動的にエラーパターンを分析
2. **分類**: 既知のパターンにマッチング
3. **推奨アクション**: 具体的な対処方法を提示
4. **トレンド分析**: 失敗傾向の可視化

---

## HITL (Human-in-the-Loop)

### 概要
重要な操作で人間の確認・承認を求める機能。

### DSLでの設定

```yaml
dsl_version: "1.1"
name: "Production Deployment"
steps:
  - prepare_deployment:
      target: "production"
  
  - human_confirm:
      message: "本番環境へのデプロイを実行しますか？"
      timeout_minutes: 30
      auto_action: "deny"  # タイムアウト時は自動拒否
      required_role: "Editor"  # Editor以上の権限が必要
      risk_level: "high"
      
  - deploy_to_production:
      target: "production"
```

### 承認フロー

1. **一時停止**: `human_confirm` ステップで実行が一時停止
2. **通知**: 承認者にWebUI経由で通知
3. **確認**: `/hitl/approve/{run_id}` で承認画面を表示
4. **判断**: 承認(approve)または拒否(deny)
5. **継続**: 承認されれば次ステップへ、拒否されれば終了

### 承認画面アクセス

```bash
# 承認画面URL
http://localhost:8000/hitl/approve/{run_id}
```

---

## 監視・メトリクス

### Phase 4 新メトリクス

#### キュー関連
- `queue_depth_peak_24h`: 24時間のキュー深度ピーク
- `runs_per_hour_24h`: 時間あたり実行数
- `retry_rate_24h`: 再試行率

#### RBAC関連  
- `rbac_denied_24h`: 権限拒否数
- `user_active_sessions`: アクティブユーザーセッション数

#### 失敗分析
- `top_failure_clusters_24h`: 上位失敗クラスター
- `failure_cluster_diversity`: 失敗パターンの多様性

### ダッシュボード

メトリクスは以下で確認：

```bash
# JSON形式
curl http://localhost:8000/metrics

# Web Dashboard  
open http://localhost:8000/public/dashboard
```

### アラート設定例

```bash
# 高い失敗率の検知
if [ "$(curl -s http://localhost:8000/metrics | jq '.success_rate_24h < 0.8')" = "true" ]; then
  echo "Alert: Success rate below 80%" | mail -s "Desktop Agent Alert" admin@company.com
fi
```

---

## トラブルシューティング

### よくある問題と対処法

#### 1. キューが詰まる

**症状**: 実行が開始されない
**原因**: 並列実行数の上限に達している

**対処法**:
```bash
# 現在のキュー状況確認
curl http://localhost:8000/metrics | jq '.queue_depth_peak_24h'

# 設定調整 (configs/orchestrator.yaml)
max_concurrent: 5  # 増加
```

#### 2. RBAC認証エラー

**症状**: 403 Forbidden エラー
**原因**: 権限不足

**対処法**:
```bash
# 監査ログ確認
curl -u admin:password http://localhost:8000/api/admin/audit

# ユーザー権限確認
curl -u admin:password http://localhost:8000/api/admin/users
```

#### 3. Secrets が解決されない

**症状**: Template variable not found
**原因**: Secrets backend設定不備

**対処法**:
```python
from app.security.secrets import get_secrets_manager

# Secrets利用可能性確認
manager = get_secrets_manager()
print(manager.get_metrics())
```

#### 4. Scheduler が動かない

**症状**: Cron jobが実行されない
**原因**: Cron式の設定ミス

**対処法**:
```bash
# Scheduler状況確認
curl http://localhost:8000/metrics | jq '.scheduler_metrics'

# Cron式検証 (https://crontab.guru/ 等で確認)
```

### ログの確認

```bash
# アプリケーションログ
tail -f logs/desktop-agent.log

# 各コンポーネント別確認
grep "Queue" logs/desktop-agent.log
grep "RBAC" logs/desktop-agent.log  
grep "Secrets" logs/desktop-agent.log
```

### パフォーマンス最適化

1. **キュー設定調整**
   - CPU・メモリに応じて並列数調整
   - 優先度の適切な設定

2. **Secrets最適化**  
   - キャッシュ設定の調整
   - Backend選択の最適化

3. **監視間隔調整**
   - Scheduler check間隔の調整
   - Watcher debounce設定の最適化

---

## サポート

技術的な問題や質問については以下を参照：

- **Issue報告**: [GitHub Issues](https://github.com/Axion-inc/DesktopAgent/issues)
- **設定例**: `examples/` ディレクトリ
- **API仕様**: `/docs` エンドポイント (FastAPI自動生成)

---

*Phase 4 Desktop Agent - Enterprise Automation Platform*