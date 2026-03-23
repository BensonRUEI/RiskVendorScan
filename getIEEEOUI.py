import re
import csv
import os
import time

try:
    import requests
except ImportError:
    print("[錯誤] 缺少必要套件 requests，請先執行：")
    print("  pip install requests")
    raise SystemExit(1)

TXT_URL = "https://standards-oui.ieee.org/oui/oui.txt"
CSV_URL = "https://standards-oui.ieee.org/oui/oui.csv"

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(_BASE_DIR, "data", "oui_min.csv")

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    ),
    "Accept": "text/plain, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"
}

HEAD_RE = re.compile(r"^([0-9A-F]{6})\s+\(base 16\)\s+(.+)$")
COUNTRY_RE = re.compile(r"^[A-Z]{2}$")

def http_get(url, is_text=True, tries=3, timeout=30):
    last_err = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
            # 某些 edge case 會回 418/403，重試前稍等
            if r.status_code == 418 or r.status_code == 403:
                last_err = requests.HTTPError(f"{r.status_code} {r.reason}")
                time.sleep(1.2 * (i + 1))
                continue
            r.raise_for_status()
            if is_text:
                r.encoding = r.encoding or "utf-8"
                return r.text
            else:
                return r.content
        except Exception as e:
            last_err = e
            time.sleep(1.2 * (i + 1))
    raise last_err

def parse_txt(txt: str):
    """解析 oui.txt -> 產生 (base16, vendor, country)"""
    lines = txt.splitlines()
    i, n = 0, len(lines)
    while i < n:
        m = HEAD_RE.match(lines[i])
        if not m:
            i += 1
            continue
        base16 = m.group(1)
        vendor = m.group(2).strip()
        i += 1

        addr = []
        while i < n and lines[i].strip() != "" and not HEAD_RE.match(lines[i]):
            addr.append(lines[i].strip())
            i += 1

        country = ""
        if addr:
            last = addr[-1].strip()
            if COUNTRY_RE.match(last):
                country = last

        yield base16, vendor, country

        while i < n and lines[i].strip() == "":
            i += 1

def parse_csv(text: str):
    """
    解析 oui.csv：
    依 IEEE 公開 CSV，常見欄：
      Assignment (六碼HEX)、Organization Name、Organization Address
    我們取 Assignment -> base16、vendor=Organization Name、
    country=Address 最末行若為兩碼大寫。
    """
    import io
    f = io.StringIO(text)
    reader = csv.DictReader(f)
    for row in reader:
        base16 = (row.get("Assignment") or "").strip().upper()
        vendor = (row.get("Organization Name") or "").strip()
        address = (row.get("Organization Address") or "").strip()
        country = ""
        if address:
            last = address.splitlines()[-1].strip()
            if COUNTRY_RE.match(last):
                country = last
        if re.fullmatch(r"[0-9A-F]{6}", base16):
            yield base16, vendor, country

def main():
    rows = []
    try:
        # 先試 txt
        txt = http_get(TXT_URL, is_text=True, tries=3)
        rows = list(parse_txt(txt))
    except Exception:
        # txt 抓不到就換 csv
        csv_text = http_get(CSV_URL, is_text=True, tries=3)
        rows = list(parse_csv(csv_text))

    # 去重複（以 base16 為主，保留第一筆）
    seen = set()
    dedup = []
    for b, v, c in rows:
        if b not in seen:
            seen.add(b)
            dedup.append((b, v, c))

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["base16", "vendor", "country"])
        w.writerows(dedup)

    print(f"完成，共 {len(dedup)} 筆，已輸出 {OUT_CSV}")

if __name__ == "__main__":
    main()
