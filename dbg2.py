import asyncio, json, sys
sys.path.insert(0, '.')
from app import JS_EXTRACT
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/chromium",
            args=["--no-sandbox","--disable-dev-shm-usage","--headless=new"])
        page = await b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36")
        await page.goto("https://www.flashscore.com/badminton/", timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(9000)
        try:
            raw = await page.evaluate(JS_EXTRACT)
            for g in raw["groups"]:
                print("GROUP:", g["name"][:60], "| matches:", len(g["matches"]))
                for m in g["matches"][:3]:
                    print("   ", m["live"], m["home"], m["primary"], m["stage"])
        except Exception as e:
            print("EXTRACT ERROR:", type(e).__name__, str(e)[:500])
        await b.close()

asyncio.run(main())
