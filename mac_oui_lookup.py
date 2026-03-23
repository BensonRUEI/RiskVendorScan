import csv
import re
import os
import getIEEEOUI

# =========================
# 檔案路徑
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SWITCH_OUI_CSV = os.path.join(BASE_DIR, "data", "oui_min.csv")        # IEEE OUI 對照表（由 getIEEEOUI.py 產生）
ARP_CSV = os.path.join(BASE_DIR, "data", "arptable.csv")               # 輸入來源：ARP 表，格式為 IP,MAC
KEYWORDS_TXT = os.path.join(BASE_DIR, "data", "keywords.txt")          # 廠牌篩選清單（命中則列入）
EXCLUDE_KEYWORDS_TXT = os.path.join(BASE_DIR, "data", "exclude_keywords.txt")  # 廠牌排除清單（命中則剔除）

OUT_CSV_CN = os.path.join(BASE_DIR, "output", "RiskVendorScan.csv")     # 輸出：完整欄位的 CSV 報表
OUT_TXT_CN = os.path.join(BASE_DIR, "output", "RiskVendorScan.txt")     # 輸出：僅 IP 位址的純文字清單

# =========================
# Regex / Helpers
# =========================
HEX6_RE = re.compile(r"^[0-9A-F]{6}$")
HEX12_RE = re.compile(r"^[0-9A-F]{12}$")


def load_keywords(path: str) -> list:
    """從 txt 檔載入關鍵字清單，忽略以 # 開頭的注釋行與空行。"""
    if not os.path.exists(path):
        return []
    keywords = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                keywords.append(line)
    return keywords


def like_to_regex(pattern):  # type: (str) -> object
    """將 SQL LIKE pattern 轉成 Python regex（不分大小寫）。
    % -> .*
    _ -> .
    """
    esc = ""
    for c in pattern:
        if c == "%":
            esc += ".*"
        elif c == "_":
            esc += "."
        else:
            esc += re.escape(c)
    return re.compile(esc, re.IGNORECASE)


def normalize_mac(mac: str) -> str:
    """把 MAC 轉成純 12 碼十六進位大寫；若格式不對則回傳空字串。

    支援格式：
      40EE15D00000          (無分隔)
      40:EE:15:D0:00:00     (冒號)
      40-EE-15-D0-00-00     (連字號)
      40EE.15D0.0000        (Cisco dot)
      40 EE 15 D0 00 00     (空白)
    """
    if not mac:
        return ""
    s = mac.upper()
    for ch in ["-", ":", ".", " "]:
        s = s.replace(ch, "")
    if not HEX12_RE.fullmatch(s):
        return ""
    return s


def load_oui_map(path: str = SWITCH_OUI_CSV) -> dict:
    """載入 oui_min.csv：base16 -> (vendor, country)
    自動跳過 header / 髒資料，只保留 base16 為 6 碼 hex 的行。
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"OUI CSV not found: {path}")

    mapping = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for r in reader:
            if not r:
                continue
            base16 = (r[0] or "").strip().upper()
            if base16 == "BASE16":
                # header
                continue
            if not HEX6_RE.fullmatch(base16):
                # 跳過非 6 碼 hex
                continue

            vendor = (r[1] or "").strip() if len(r) > 1 else ""
            country = (r[2] or "").strip() if len(r) > 2 else ""
            mapping[base16] = (vendor, country)

    return mapping


IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def read_arp_csv(path: str = ARP_CSV):
    """讀取 arptable.csv（欄位：IP,MAC），回傳 list of (mac, ip) tuple。

    自動相容有 header（IP,MAC）與無 header 兩種格式，
    判斷依據：第一欄是否為 IP 位址。
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"ARP table CSV not found: {path}")

    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if len(row) < 2:
                continue
            ip_field = row[0].strip()
            mac_field = row[1].strip()
            # 第一行若不像 IP（例如 header "IP"），跳過
            if not IP_RE.match(ip_field):
                continue
            if ip_field and mac_field:
                rows.append((mac_field, ip_field))
    return rows


def main():
    os.makedirs(os.path.join(BASE_DIR, "output"), exist_ok=True)
    print("=== 更新 OUI 資料庫 ===")
    getIEEEOUI.main()
    print()
    mapping = load_oui_map()
    rows = read_arp_csv()
    print(f"Read {len(rows)} rows from {ARP_CSV}")

    # 建立 out_rows：加上 OUI 查表結果
    out_rows = []
    for mac, ip in rows:
        if not ip:
            continue
        macnorm = normalize_mac(mac)
        if not macnorm:
            continue

        base16 = macnorm[:6]
        base16_colon = ":".join([base16[i : i + 2] for i in range(0, 6, 2)])
        vendor, country = mapping.get(base16, ("Unknown", ""))

        out_rows.append((macnorm, ip, base16_colon, vendor, country))

    print(f"Processed {len(out_rows)} rows")

    # 篩選：只要 vendor 命中 KEYWORDS 就列入
    keywords = load_keywords(KEYWORDS_TXT)
    exclude_keywords = load_keywords(EXCLUDE_KEYWORDS_TXT)
    print(f"Loaded {len(keywords)} keywords, {len(exclude_keywords)} exclude keywords")

    include_regexes = [like_to_regex(p) for p in keywords] if keywords else []
    exclude_regexes = [like_to_regex(p) for p in exclude_keywords] if exclude_keywords else []

    filtered_rows = []
    for macnorm, ip, base16_colon, vendor, country in out_rows:
        lv = vendor or ""

        # KEYWORDS 必須命中（若 KEYWORDS 空，這裡預設不產生清單）
        if include_regexes:
            if not any(rx.search(lv) for rx in include_regexes):
                continue
        else:
            continue

        # EXCLUDE 命中則排除
        if exclude_regexes and any(rx.search(lv) for rx in exclude_regexes):
            continue

        filtered_rows.append((macnorm, ip, base16_colon, vendor, country))

    # 輸出 CSV（Excel 友善）
    with open(OUT_CSV_CN, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["mac_address", "ipv4", "base16", "vendor", "country"])
        for r in filtered_rows:
            writer.writerow([r[0], r[1], r[2], r[3], r[4]])
    print(f"Wrote {len(filtered_rows)} filtered rows to {OUT_CSV_CN}")

    # 輸出 TXT：每行一個 IP
    with open(OUT_TXT_CN, "w", encoding="utf-8") as tf:
        for macnorm, ip, base16_colon, vendor, country in filtered_rows:
            tf.write(f"{ip}\n")
    print(f"Wrote {len(filtered_rows)} IPs to {OUT_TXT_CN}")


if __name__ == "__main__":
    main()
