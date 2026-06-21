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
import json
import re
import sys
import time
from datetime import datetime
from html import unescape
from urllib.parse import quote, unquote
from zoneinfo import ZoneInfo

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


def _b64pad(s):
    return s + "=" * (-len(s) % 4)


def add_time_prefix(cfg, prefix):
    """افزودن زمانِ آپدیت به ابتدای اسمِ نمایشیِ (remark) هر کانفیگ."""
    try:
        scheme = cfg.split("://", 1)[0].lower()
        if scheme == "vmess":
            raw = base64.b64decode(_b64pad(cfg[8:])).decode("utf-8", "ignore")
            j = json.loads(raw)
            j["ps"] = prefix + str(j.get("ps", ""))
            new = base64.b64encode(
                json.dumps(j, ensure_ascii=False).encode("utf-8")
            ).decode()
            return "vmess://" + new
        # vless / trojan / ss / ssr / tuic / hysteria(2) → remark در fragment بعد از #
        if "#" in cfg:
            base, frag = cfg.split("#", 1)
            return base + "#" + quote(prefix + unquote(frag))
        return cfg + "#" + quote(prefix.strip())
    except Exception:
        return cfg


def main():
    pools = {}
    for i, ch in enumerate(CHANNELS):
        need = CH1_TARGET + 15 if i == 0 else 40
        pools[ch] = fetch_configs(ch, need)
        print(f"{ch:20s} collected={len(pools[ch])}")

    final, (n1, n2, n3) = select_configs(pools)
    print(f"Selected {len(final)} configs -> ch1={n1} ch2={n2} ch3={n3}")

    # زمانِ آپدیت — هم برای فایلِ updated.txt و هم برای اسمِ کانفیگ‌ها
    now_teh = datetime.now(ZoneInfo("Asia/Tehran"))
    now_utc = datetime.now(ZoneInfo("UTC"))
    name_prefix = f"🕒{now_teh:%m/%d %H:%M} | "          # کنارِ اسمِ هر سرور
    final = [add_time_prefix(c, name_prefix) for c in final]

    blob = "\n".join(final)
    sub_b64 = base64.b64encode(blob.encode()).decode()
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(sub_b64)
    # نسخه‌ی متنی هم برای بازبینی
    with open("configs.txt", "w", encoding="utf-8") as f:
        f.write(blob)

    # فایلِ زمانِ آخرین آپدیت (وقتِ تهران + UTC)
    stamp = (
        "=== v2ray subscription — last update ===\n"
        f"به وقت تهران : {now_teh:%Y-%m-%d %H:%M:%S} (+03:30)\n"
        f"UTC          : {now_utc:%Y-%m-%d %H:%M:%S}\n"
        f"تعداد کانفیگ : {len(final)}  (کانال۱={n1} | کانال۲={n2} | کانال۳={n3})\n"
    )
    with open("updated.txt", "w", encoding="utf-8") as f:
        f.write(stamp)

    print(f"Wrote {OUTPUT} ({len(sub_b64)} chars)")
    print(stamp)


if __name__ == "__main__":
    main()
