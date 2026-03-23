# RiskVendorScan

識別組織內網中使用**高風險廠牌**的資通訊設備，協助網管人員建立設備清單並採取後續處置。

透過 ARP 表的 MAC 位址比對 [IEEE OUI](https://standards-oui.ieee.org/) 廠牌資料庫，篩選出符合指定廠牌關鍵字的設備，並輸出報表供後續處置使用。

---

## 使用流程

```
data/arptable.csv       ──┐
data/oui_min.csv        ──┼──▶  mac_oui_lookup.py  ──▶  output/RiskVendorScan.csv
data/keywords.txt       ──┘                         └──▶  output/RiskVendorScan.txt
```

1. 從網路設備匯出 ARP 表，存為 `data/arptable.csv`
2. 執行 `mac_oui_lookup.py`（自動更新 OUI 資料庫後進行比對）
3. 查看輸出的 `RiskVendorScan.csv` / `RiskVendorScan.txt`

---

## 檔案說明

| 檔案 | 說明 |
|------|------|
| `mac_oui_lookup.py` | 主程式：更新 OUI 資料庫 → 比對 ARP 表 → 輸出報表 |
| `getIEEEOUI.py` | 從 IEEE 官網下載最新 OUI 資料，產生 `data/oui_min.csv` |
| `data/arptable.csv` | **輸入**：ARP 表，格式為 `IP,MAC`（無須 header） |
| `data/keywords.txt` | 廠牌篩選清單，命中則列入報表 |
| `data/exclude_keywords.txt` | 廠牌排除清單，命中則從報表剔除 |
| `data/oui_min.csv` | IEEE OUI 對照表（執行時自動產生，勿手動編輯） |
| `output/RiskVendorScan.csv` | **輸出**：完整欄位報表（MAC、IP、OUI、廠牌、國家） |
| `output/RiskVendorScan.txt` | **輸出**：僅含 IP 位址的純文字清單，可直接匯入防火牆或 ACL |

---

## 安裝

需要 Python 3.8 以上。

```bash
pip install requests
```

---

## 使用方式

### 1. 準備 ARP 表

將網路設備匯出的 ARP 資料整理成 `arptable.csv`，每行一筆，格式為：

```
IP,MAC
```

MAC 支援多種常見格式，無須事先統一：

| 格式 | 範例 |
|------|------|
| 無分隔 | `40EE15D00000` |
| 冒號 | `40:EE:15:D0:00:00` |
| 連字號 | `40-EE-15-D0-00-00` |
| Cisco dot | `40EE.15D0.0000` |
| 空白 | `40 EE 15 D0 00 00` |

範例：

```
172.16.15.22,40EE15D00000
172.16.17.210,00-23-63-01-00-00
192.168.1.100,a4:c3:f0:11:22:33
```

### 2. 設定篩選關鍵字

編輯 `data/keywords.txt`，每行一個廠牌關鍵字（`#` 開頭為注釋）：

```
# 中國資通訊廠牌
Xiaomi
Hikvision
TP-LINK
Dahua
```

支援 SQL LIKE 語法：`%` 代表任意字串、`_` 代表任一字元。

> **大小寫不敏感**：關鍵字不區分大小寫，`TP-LINK`、`tp-link`、`Tp-Link` 效果完全相同，無須統一格式。

如需排除特定廠牌，編輯 `data/exclude_keywords.txt`，格式與規則相同。

### 3. 執行

```bash
python mac_oui_lookup.py
```

執行時會自動：
1. 從 IEEE 下載最新 OUI 資料庫並更新 `oui_min.csv`
2. 讀取 `arptable.csv` 進行 OUI 比對
3. 依 `keywords.txt` 篩選，輸出 `RiskVendorScan.csv` 與 `RiskVendorScan.txt`

---

## 輸出格式

### RiskVendorScan.csv

| 欄位 | 說明 |
|------|------|
| `mac_address` | 正規化後的 MAC（12 碼大寫，無分隔） |
| `ipv4` | IP 位址 |
| `base16` | OUI 前三碼（冒號格式） |
| `vendor` | 廠牌全名（來自 IEEE） |
| `country` | 國家代碼 |

### RiskVendorScan.txt

每行一個 IP，可直接匯入防火牆、交換器 ACL 或其他自動化工具。

---

## 注意事項

- `data/arptable.csv` 內含組織內網資產資訊，請妥善控管存取權限，**勿上傳至公開儲存庫**
- `output/RiskVendorScan.csv` / `RiskVendorScan.txt` 同樣屬於敏感資料，請比照辦理
- OUI 廠牌比對以 MAC 前 6 碼為準，無法識別 MAC 偽造的情況

---

## 如何更新 OUI 資料庫（手動）

若僅需更新 OUI 資料庫而不執行比對，更新結果存於 `data/oui_min.csv`：

```bash
python getIEEEOUI.py
```

---

## .gitignore 建議

```gitignore
arptable.csv
data/
output/
```
