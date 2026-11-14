import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/chromium",
            args=["--no-sandbox","--disable-dev-shm-usage","--headless=new"])
        page = await b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36")
        await page.goto("https://www.flashscore.com/badminton/", timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(9000)
        html = await page.evaluate("""() => {
            const r = document.querySelector('.event__match--live, .event__match');
            return r ? r.outerHTML.slice(0, 3500) : 'NONE';
        }""")
        print(html)
        # 分组头
        heads = await page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('.event__leagueHeader, [class*="leagueHeader"], [class*="event__header"]').forEach(h => out.push(h.className + ' || ' + h.textContent.trim().slice(0,60)));
            return out.slice(0,5);
        }""")
        print("HEADERS:", heads)
        await b.close()

asyncio.run(main())
