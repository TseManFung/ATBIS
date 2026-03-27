# Python 簡單帳單管理系統 開發文件

**版本**：1.0  
**日期**：2026 年 3 月  
**編寫者**：AT
**編碼**：UTF-8  
**部署基底路徑**：`https://ip:43255/atbis/`  
**注意事項**：  
- 未來可能開發手機版本（響應式設計需優先考慮 Bootstrap 移動端相容性）。  
- 所有頁面（除登入頁外）必須先登入才能存取。  
- 索引頁（index）為登入頁面。  

---

## 1. 系統概述

本系統為一個輕量級的群組帳單管理工具，專為小群組（如社團、家庭、朋友聚會）設計，可即時追蹤收入、支出與成員餘額。系統支援多群組管理、角色權限控制（全局管理員、群組管理員、金錢保管人、普通成員），並提供簡單的帳單記錄與餘額計算功能。

系統目標：
- 簡易操作（Bootstrap 介面 + 中文 zh-hk 顯示）。
- 資料即時更新（使用 SQLite 交易確保一致性）。
- 安全登入與密碼管理。

---

## 2. 技術堆疊與部署環境

| 項目          | 規格 |
|---------------|------|
| 作業系統      | Ubuntu 24.04 |
| 程式語言      | Python 3.12（必須使用 `venv` 建立虛擬環境） |
| 資料庫        | SQLite（單檔案資料庫） |
| HTTPS 憑證    | OpenSSL 自簽或正式憑證 |
| 前端框架      | Bootstrap 5（全站使用 zh-hk 繁體中文） |
| 部署路徑      | `https://ip:43255/atbis/`（所有路由皆以此為基底） |
| 其他          | bcrypt 雜湊密碼、Bootstrap-table（表格顯示與篩選） |

**部署注意**：
- 使用 `python -m venv venv` 建立虛擬環境。
- 所有靜態檔案與 API 路由皆置於 `/atbis/` 之下。
- 生產環境需設定 systemd service 確保持續運行。

---

## 3. 資料庫設計

系統使用 SQLite，共有 5 張表格。所有表格均使用 UTF-8 編碼。

### 3.1 users 表（使用者）
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT UNIQUE NOT NULL,
password TEXT NOT NULL,          -- bcrypt 雜湊
display_name TEXT,               -- 可修改
is_admin INTEGER DEFAULT 0,      -- 1 = 全局管理員
created_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

### 3.2 groups 表（群組）
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT UNIQUE NOT NULL,
created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
created_by INTEGER REFERENCES users(id)
```

### 3.3 group_members 表（群組成員）
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT,
group_id INTEGER REFERENCES groups(id),
user_id INTEGER REFERENCES users(id),
role TEXT DEFAULT 'member',      -- member / group_admin / treasurer
balance REAL DEFAULT 0.0,
joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
UNIQUE(group_id, user_id)
```

### 3.4 bills 表（帳單）
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT,
group_id INTEGER REFERENCES groups(id),
bill_type TEXT NOT NULL,         -- income / expense
total_amount REAL > 0,
is_equal_split INTEGER DEFAULT 1,-- 1=平分，0=自訂
remark TEXT,                     -- 可選
created_by INTEGER REFERENCES users(id),
created_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

### 3.5 bill_splits 表（帳單分攤）
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT,
bill_id INTEGER REFERENCES bills(id),
user_id INTEGER REFERENCES users(id),
amount REAL NOT NULL             -- 正=收入，負=支出
```

**資料一致性**：新增帳單時必須使用 **transaction** 同時執行：
- INSERT INTO bills
- INSERT INTO bill_splits（依據是否平分計算）
- UPDATE group_members.balance

---

## 4. 系統功能模組與頁面

### 4.1 登入頁面（`/` 或 `/atbis/`）
- 帳號 + 密碼登入。
- 登入成功後跳轉至「查看帳目」頁面。

### 4.2 修改個人資料頁面（`/profile`）
- 顯示 `username`（唯讀）
- 可修改 `display_name`
- 可修改密碼（限制：至少 8 位元，且不可與舊密碼相同）

### 4.3 查看帳目頁面（`/bills`）
- 先選擇群組（下拉選單）
- 使用 **Bootstrap-table** 顯示：
  - 自己及參與群組的即時餘額（預設顯示全部）
  - 自己的帳單細項（收入/支出用顏色區分）
- 支援 Bootstrap-table filter：可篩選特定群組或全部總和
- **權限**：
  - 全局管理員：可看任何成員/群組
  - 群組管理員：可看本群組內任何成員/群組
  - 普通成員：僅看自己

### 4.4 增加帳單記錄（`/add-bill`）**僅限管理員 / 群組管理員**
流程：
1. 先選群組
2. 顯示成員清單 + 多選方格 +「全選」按鈕
3. 選擇「增值」（income）或「支出」（expense）
4. 選擇是否「平分到每個人」
5. 輸入金額（>0）
6. 選填備註（remark）
7. 確認記錄（使用 transaction 更新資料庫）

### 4.5 新增成員（`/admin/add-user`）**僅限全局管理員**
- 輸入新成員的 `username` 與 `display_name`
- 後端自動生成密碼，並以 Modal 彈窗顯示「帳號 + 密碼」，方便複製分發

### 4.6 新建群組（`/groups/new`）
- 輸入群組名稱
- 新建者自動成為該群組的 **group_admin**

### 4.7 群組管理（`/groups/manage`）**僅限全局管理員 / 群組管理員**
選擇要管理的群組後：
- **7.1 增加成員**：必須輸入完整 `username`
- **7.2 修改金錢保管人**（treasurer）：
  - 若群組原本無 treasurer，則由群組管理員負責
  - 若已有 treasurer，則原本 treasurer 降為 member

---

## 5. API 設計（預期前端呼叫）

前端將使用 JavaScript（Fetch / Axios）呼叫以下 RESTful API。所有 API 皆位於基底路徑 `/atbis/api/` 下，並使用 JWT 或 Session Cookie 進行驗證。

| 方法 | 端點 | 說明 | 權限 | 主要 Request / Response 欄位 |
|------|------|------|------|-------------------------------|
| POST | `/api/login` | 帳號密碼登入 | 公開 | `{username, password}` → `{token, user_info}` |
| GET  | `/api/profile` | 取得個人資料 | 已登入 | - |
| PUT  | `/api/profile` | 更新 display_name / 密碼 | 已登入 | `{display_name?, password?, old_password}` |
| GET  | `/api/groups` | 取得使用者可見群組清單 | 已登入 | - |
| GET  | `/api/bills?group_id=xxx` | 取得帳單與餘額（支援 filter） | 已登入 | - |
| POST | `/api/bills` | 新增帳單 | 管理員 / 群組管理員 | `{group_id, bill_type, total_amount, is_equal_split, remark, selected_members[]}` |
| POST | `/api/admin/users` | 新增成員 | 全局管理員 | `{username, display_name}` → 回傳新密碼 |
| POST | `/api/groups` | 新建群組 | 已登入 | `{name}` |
| GET  | `/api/groups/manage?group_id=xxx` | 取得群組管理資訊 | 群組管理員以上 | - |
| PUT  | `/api/groups/members` | 群組內新增成員 | 群組管理員以上 | `{group_id, username}` |
| PUT  | `/api/groups/treasurer` | 修改金錢保管人 | 群組管理員以上 | `{group_id, user_id}` |

**API 共通規範**：
- 所有回應使用 JSON。
- 錯誤統一格式：`{success: false, message: "錯誤訊息"}`
- 成功：`{success: true, data: {...}}`
- 所有敏感操作需檢查登入狀態與角色權限。

---

## 6. 安全與注意事項

- 密碼一律使用 bcrypt 雜湊儲存。
- 所有頁面（除登入頁）必須檢查登入狀態。
- 新增帳單使用資料庫 transaction 確保餘額與分攤資料一致。
- 未來手機版本：Bootstrap 已內建響應式，建議測試 iOS / Android 瀏覽器相容性。
- 部署時請使用 OpenSSL 啟用 HTTPS（port 43255）。

---

## 7. 未來擴展建議

- 手機 App 版本（PWA 或 React Native）。
- 匯出 Excel / PDF 報表。
- 通知功能（email / LINE）。
- 多語言支援（目前固定 zh-hk）。

本文件作為開發、測試與後續維護之用。如有任何調整，請同步更新此文件。