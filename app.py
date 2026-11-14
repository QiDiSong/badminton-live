# -*- coding: utf-8 -*-
"""
羽毛球实时比分 APP 后端
数据源: Flashscore（无头浏览器渲染 + 静态页解析）
"""
import asyncio
import os
import re
import shutil
import threading
import time
from datetime import datetime, timezone, timedelta

import requests
from flask import Flask, jsonify, send_from_directory
from playwright.async_api import async_playwright

# ---------------- 配置 ----------------
REFRESH_INTERVAL = 20          # 比分刷新周期(秒)
ROUND_CACHE_TTL = 3600         # 轮次缓存(秒)


def find_chrome():
    """跨平台自动查找 Chrome/Chromium 可执行文件"""
    env = os.environ.get("CHROME_PATH")
    if env and os.path.exists(env):
        return env
    candidates = [
        "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    found = shutil.which("chrome") or shutil.which("chromium") or shutil.which("google-chrome")
    return found or "/usr/bin/chromium"


CHROME_PATH = find_chrome()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

DATA = {"matches": [], "updated_at": None, "tournaments": []}
DATA_LOCK = threading.Lock()

_round_cache = {}   # match_url -> {"round":..., "ts":...}
_round_lock = threading.Lock()

TZ = timezone(timedelta(hours=8))

ROUND_CN = {
    "Final": "决赛",
    "Semi-finals": "半决赛",
    "Quarter-finals": "1/4决赛",
    "1/8-finals": "1/8决赛",
    "1/16-finals": "1/32决赛",
    "3rd place final": "季军赛",
}

FLAG_EMOJI = {
    "China": "🇨🇳", "Japan": "🇯🇵", "South Korea": "🇰🇷", "Korea": "🇰🇷",
    "Indonesia": "🇮🇩", "India": "🇮🇳", "Thailand": "🇹🇭", "Malaysia": "🇲🇾",
    "Chinese Taipei": "🇹🇼", "Taiwan": "🇹🇼", "Denmark": "🇩🇰", "Denmark 2": "🇩🇰",
    "Singapore": "🇸🇬", "Hong Kong": "🇭🇰", "France": "🇫🇷", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "USA": "🇺🇸", "Canada": "🇨🇦", "Australia": "🇦🇺", "Germany": "🇩🇪",
    "Netherlands": "🇳🇱", "Vietnam": "🇻🇳", "Philippines": "🇵🇭", "Ireland": "🇮🇪",
}


def flag(country):
    return FLAG_EMOJI.get(country, "🏳️")


def round_cn(r):
    if not r:
        return ""
    if r in ROUND_CN:
        return ROUND_CN[r]
    return r.replace("-finals", "决赛").replace("final", "决赛")


def parse_participants(raw):
    """选手字段可能包含双打组合（选手间用逗号或 & 分隔），做基本清洗"""
    return raw.strip()


# ---------------- Playwright 抓取 ----------------
JS_EXTRACT = """() => {
    const out = {groups: []};
    let cur = null;
    document.querySelectorAll('.headerLeague__wrapper, .event__match').forEach(el => {
        if (el.classList.contains('headerLeague__wrapper')) {
            const t = el.textContent.replace(/\\s+/g, ' ').trim();
            let name = t;
            const m = t.match(/([A-Za-z0-9 .&\\'’-]+\\([^)]+\\))/);
            if (m) name = m[1];
            cur = {name: name, matches: []};
            out.groups.push(cur);
        } else {
            const txt = e => e ? e.textContent.trim() : '';
            const name = side => {
                const p = el.querySelector('.event__participant--' + side) ||
                          el.querySelector('.event__' + side + 'Participant');
                if (!p) return '';
                const sp = p.querySelector('span[data-testid="wcl-simple-text-01"]');
                return (sp ? sp.textContent : p.textContent).trim();
            };
            const fl = side => {
                const logo = el.querySelector('.event__logo--' + side);
                if (logo && logo.title) return logo.title;
                const img = el.querySelector('.event__' + side + 'Participant img, .event__participant--' + side + ' img');
                return img ? (img.title || '') : '';
            };
            const parts = {};
            ['home','away'].forEach(side => {
                parts[side] = [];
                for (let i = 1; i <= 5; i++) {
                    const s = el.querySelector('.event__part--' + side + '.event__part--' + i);
                    parts[side].push(s ? s.textContent.trim() : null);
                }
            });
            const prim = {};
            ['home','away'].forEach(side => {
                const s = el.querySelector('.event__score--' + side);
                prim[side] = s ? s.textContent.trim() : '';
            });
            const link = el.querySelector('a.eventRowLink');
            const stage = el.querySelector('.event__stageTime') ||
                          el.querySelector('.event__stage--block') ||
                          el.querySelector('.event__stage') ||
                          el.querySelector('.event__time');
            const cls = el.className;
            if (!cur) { cur = {name: '其他', matches: []}; out.groups.push(cur); }
            cur.matches.push({
                id: el.id || '',
                live: cls.includes('--live'),
                sched: cls.includes('--schedul') || cls.includes('--scheduled'),
                home: name('home'), homeFlag: fl('home'),
                away: name('away'), awayFlag: fl('away'),
                primary: prim,
                parts,
                stage: txt(stage),
                url: link ? link.href : ''
            });
        }
    });
    return out;
}"""


async def scrape_home(page):
    """渲染首页, 提取所有赛事分组的比赛"""
    await page.goto("https://www.flashscore.com/badminton/", timeout=60000,
                    wait_until="domcontentloaded")
    try:
        await page.wait_for_selector(".event__match", timeout=25000)
    except Exception:
        pass
    await page.wait_for_timeout(7000)   # 等待 websocket 实时数据
    return await page.evaluate(JS_EXTRACT)


async def scrape_loop():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME_PATH,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--headless=new"])
        page = await browser.new_page(user_agent=UA)
        while True:
            t0 = time.time()
            try:
                raw = await scrape_home(page)
                matches = []
                seen = set()
                for g in raw.get("groups", []):
                    gname = g.get("name", "")
                    for m in g.get("matches", []):
                        if not m.get("home") or not m.get("away"):
                            continue
                        mid = m["id"]
                        if mid in seen:
                            continue
                        seen.add(mid)
                        live = bool(m.get("live"))
                        sched = bool(m.get("sched"))
                        stage = m.get("stage", "")
                        if live:
                            status = "live"
                        elif sched or (stage and re.match(r"^\d{1,2}[:.]\d{2}", stage)):
                            status = "upcoming"
                        else:
                            status = "finished"
                        row = {
                            "id": mid,
                            "tournament": gname,
                            "live": live,
                            "stage": stage,
                            "home": parse_participants(m["home"]),
                            "away": parse_participants(m["away"]),
                            "homeFlag": flag(m.get("homeFlag", "")),
                            "awayFlag": flag(m.get("awayFlag", "")),
                            "homeScore": m["primary"].get("home", ""),
                            "awayScore": m["primary"].get("away", ""),
                            "homeParts": m["parts"]["home"],
                            "awayParts": m["parts"]["away"],
                            "url": m.get("url", ""),
                            "round": "",
                            "status": status,
                        }
                        if live:
                            row["round"] = get_round_cached(m.get("url", ""))
                        matches.append(row)
                # 排序: live 优先, 然后按赛事
                matches.sort(key=lambda x: (0 if x["status"] == "live" else
                                            (1 if x["status"] == "upcoming" else 2),
                                            x["tournament"]))
                with DATA_LOCK:
                    DATA["matches"] = matches
                    DATA["updated_at"] = datetime.now(TZ).strftime("%H:%M:%S")
                print(f"[refresh] {len(matches)} matches in {time.time()-t0:.1f}s, "
                      f"live={sum(1 for m in matches if m['status']=='live')}", flush=True)
            except Exception as e:
                print("[refresh] error:", e, flush=True)
            await asyncio.sleep(max(5, REFRESH_INTERVAL - (time.time() - t0)))


# ---------------- 轮次(来自比赛详情页静态 HTML) ----------------
def get_round_cached(url):
    if not url:
        return ""
    with _round_lock:
        c = _round_cache.get(url)
        if c and time.time() - c["ts"] < ROUND_CACHE_TTL:
            return c["round"]
    r = ""
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=10)
        m = re.search(r'og:description" content="([^"]+)"', resp.text)
        if m:
            segs = m.group(1).split(" - ")
            r = segs[-1].strip()
    except Exception:
        pass
    with _round_lock:
        _round_cache[url] = {"round": r, "ts": time.time()}
    return r


# ---------------- 后台线程 ----------------
def start_background():
    loop = asyncio.new_event_loop()

    def runner():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(scrape_loop())

    t = threading.Thread(target=runner, daemon=True)
    t.start()


# ---------------- Flask ----------------
app = Flask(__name__)


@app.route("/api/live")
def api_live():
    with DATA_LOCK:
        data = {
            "matches": DATA["matches"],
            "updated_at": DATA["updated_at"],
            "count_live": sum(1 for m in DATA["matches"] if m["status"] == "live"),
        }
    return jsonify(data)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


if __name__ == "__main__":
    start_background()
    app.run(host="0.0.0.0", port=8000, threaded=True)
