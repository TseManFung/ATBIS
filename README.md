# ATBIS - Python 簡單帳單管理系統

本專案為小群組帳單管理系統，使用 Flask + SQLite，頁面語系為 zh-HK，資料編碼為 UTF-8。

## 1. 系統與部署資訊
- 基底路徑: /atbis
- API 前綴: /atbis/api
- 開發啟動位址: http://127.0.0.1:43255/atbis
- 目標部署位址: https://ip:43255/atbis/
- 目標部署環境: Ubuntu 24.04 + OpenSSL HTTPS 憑證

說明:
- run.py 目前為本機開發啟動設定（HTTP）。
- 生產環境請以 HTTPS 憑證與服務管理（例如 systemd + reverse proxy）部署。

## 2. 環境需求
- Python 3.12+
- SQLite（Python 內建）
- 套件: Flask 3.1.1、bcrypt 4.2.1

## 3. 安裝與啟動

Windows:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Linux/macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

如果 venv 內 pip 異常（例如 pip._internal 模組錯誤），可先執行:
```bash
python -m ensurepip --upgrade
```

## 4. 預設管理員與環境變數
系統首次啟動會自動建立一個全局管理員。

預設帳號密碼:
- username: admin
- password: Admin12345

可用環境變數覆蓋:
- ATBIS_ADMIN_USERNAME
- ATBIS_ADMIN_PASSWORD
- SECRET_KEY

## 5. 主要頁面路由
- 登入頁（index）: /atbis
- 查看帳目: /atbis/bills
- 修改個人資料: /atbis/profile
- 增加帳單: /atbis/add-bill
- 新增成員（全局管理員）: /atbis/admin/add-user
- 新建群組: /atbis/groups/new
- 群組管理: /atbis/groups/manage
- 登出頁面路由: /atbis/logout

## 6. API 一覽

驗證與個人:
- POST /atbis/api/login
- POST /atbis/api/logout
- GET /atbis/api/profile
- PUT /atbis/api/profile

群組與成員:
- GET /atbis/api/groups
- POST /atbis/api/groups
- GET /atbis/api/groups/manage?group_id=xxx
- PUT /atbis/api/groups/members
- PUT /atbis/api/groups/treasurer

帳單:
- GET /atbis/api/bills?group_id=xxx
- POST /atbis/api/bills

管理員:
- POST /atbis/api/admin/users

回應格式:
- 成功: {"success": true, "data": {...}}
- 失敗: {"success": false, "message": "錯誤訊息"}

## 7. 權限規則（目前實作）

角色:
- admin: 全局管理員
- group_admin: 群組管理員
- treasurer: 金錢保管人
- member: 一般成員

權限摘要:
- 查看 /add-bill 頁面: admin、group_admin、treasurer 可進入；member 不可
- 新增帳單 API: admin、group_admin、treasurer 可執行；member 不可
- 群組管理資訊與成員管理 API: 僅 admin、group_admin 可執行
- 新增系統成員 API: 僅 admin 可執行

## 8. 資料一致性與安全
- 新增帳單使用 SQLite transaction，一次完成:
	- INSERT bills
	- INSERT bill_splits
	- UPDATE group_members.balance
- 密碼使用 bcrypt 雜湊儲存
- 除登入頁外，所有頁面都要求已登入

## 9. 前端行為補充
- Bootstrap-table 已設定 zh-HK locale（以 zh-TW locale 做相容映射）
- add-bill 表單支援:
	- 切換群組自動載入成員
	- 自訂分攤總額前端驗證
	- 送出防重複提交
- 導覽列登出按鈕優先呼叫 POST /api/logout，失敗時回退到 /atbis/logout

## 10. 四角色回歸測試
專案提供自動化回歸腳本，會建立臨時測試資料庫並驗證:
- 四角色登入
- 頁面守門
- API 權限
- 新增帳單交易一致性
- logout API 行為

執行方式（Windows）:
```bash
.venv\Scripts\python.exe scripts/role_regression.py
```

執行成功會顯示 PASS 清單與完成訊息。
