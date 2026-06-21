#!/usr/bin/env python3
"""
v2ray config aggregator
------------------------
هر اجرا: ۳ کانال پابلیک تلگرام را می‌خواند، جدیدترین کانفیگ‌ها را برمی‌دارد و
۱۵۰ کانفیگ را با اولویتِ کانال اول انتخاب کرده و به‌صورت لینک اشتراک Base64
در فایل sub.txt ذخیره می‌کند (سازگار با v2rayNG / NekoBox / Hiddify).

نسبت انتخاب:
  - کانال اول (اولویت بالا): ۹۰ تا ۱۰۰ کانفیگ
  - باقی‌مانده تا ۱۵۰: به‌طور مساوی بین کانال دوم و سوم
"""
import base64
import re
import sys
import time
from html import unescape

import requests

# ---- تنظیمات ----
CHANNELS = ["JetConfigsAuto", "BigSmoke_Config", "v2ray_free_conf"]  # کانال اول = اولویت
TOTAL = 150
CH1_TARGET = 95            # هدف برای کانال اول (بین ۹۰ تا ۱۰۰ نگه داشته می‌شود)
OUTPUT = "sub.txt"
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

PAT = re.compile(
    r'(vmess://[A-Za-z0-9+/=]+'
    r'|vless://[^\s<"\']+'
    r'|trojan://[^\s<"\']+'
    r'|ss://[^\s<"\']+'
    r'|ssr://[^\s<"\']+'
    r'|hysteria2?://[^\s<"\']+'
    r'|tuic://[^\s<"\']+)'
)
MSGID = re.compile(r'data-post="[^"/]+/(\d+)"')


def fetch_configs(channel, need, max_pages=15):
    """جدیدترین کانفیگ‌های یک کانال را با صفحه‌بندی به‌سمت عقب جمع می‌کند."""
    collected, seen = [], set()
    before = None
    for _ in range(max_pages):
        url = f"https://t.me/s/{channel}" + (f"?before={before}" if before else "")
        try:
            r = requests.get(url, headers=HEAD, timeout=25)
        except requests.RequestException as e:
            print(f"  [warn] {channel}: {e}", file=sys.stderr)
            break
        if r.status_code != 200:
            break
        html = unescape(r.text)
        # ترتیب پیام‌ها در صفحه قدیمی→جدید است؛ برعکس می‌کنیم تا جدیدترین اول بیاید
        for c in reversed(PAT.findall(html)):
            c = c.strip()
            if c not in seen:
                seen.add(c)
                collected.append(c)
        ids = MSGID.findall(html)
        if not ids:
            break
        before = min(int(i) for i in ids)  # صفحه‌ی قدیمی‌تر
        if len(collected) >= need:
            break
        time.sleep(0.5)
    return collected


def select_configs(pools, total=TOTAL, ch1_target=CH1_TARGET):
    c1, c2, c3 = CHANNELS
    p1, p2, p3 = pools[c1], pools[c2], pools[c3]

    take1 = min(max(min(ch1_target, len(p1)), 0), 100)  # محدود به سقف ۱۰۰
    sel1 = p1[:take1]

    remaining = total - len(sel1)
    half = remaining // 2
    take2 = min(half, len(p2))
    take3 = min(remaining - take2, len(p3))
    sel2, sel3 = p2[:take2], p3[:take3]

    chosen = sel1 + sel2 + sel3
    # اگر کم آمد (کانالی خالی شد) از بقیه با اولویت کانال اول پر می‌کنیم
    short = total - len(chosen)
    if short > 0:
        seen = set(chosen)
        for pool in (p1, p2, p3):
            for c in pool:
                if short <= 0:
                    break
                if c not in seen:
                    chosen.append(c)
                    seen.add(c)
                    short -= 1
    return chosen, (len(sel1), len(sel2), len(sel3))


def main():
    pools = {}
    for i, ch in enumerate(CHANNELS):
        need = CH1_TARGET + 15 if i == 0 else 40
        pools[ch] = fetch_configs(ch, need)
        print(f"{ch:20s} collected={len(pools[ch])}")

    final, (n1, n2, n3) = select_configs(pools)
    print(f"Selected {len(final)} configs -> ch1={n1} ch2={n2} ch3={n3}")

    blob = "\n".join(final)
    sub_b64 = base64.b64encode(blob.encode()).decode()
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(sub_b64)
    # نسخه‌ی متنی هم برای بازبینی
    with open("configs.txt", "w", encoding="utf-8") as f:
        f.write(blob)
    print(f"Wrote {OUTPUT} ({len(sub_b64)} chars)")


if __name__ == "__main__":
    main()
