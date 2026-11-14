import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/chromium",
            args=["--no-sandbox","--disable-dev-shm-usage","--headless=new"])
        page = await b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36")
        await page.goto("https://www.flashscore.com/badminton/", timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)
        seq = await page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('#fs-body > div, [id*="fs-body"] > div').forEach(el => {
                const c = el.className || '';
                const t = el.textContent.replace(/\\s+/g,' ').trim().slice(0,50);
                out.push(c.slice(0,70) + ' || ' + t);
            });
            return out.slice(0, 30);
        }""")
        for s in seq: print(s)
        await b.close()

asyncio.run(main())
