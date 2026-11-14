import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/chromium",
            args=["--no-sandbox","--disable-dev-shm-usage","--headless=new"])
        page = await b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36")
        await page.goto("https://www.flashscore.com/badminton/", timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)
        seq = await page.evaluate("""() => {
            const first = document.querySelector('.event__match');
            if (!first) return ['NO MATCH'];
            const parent = first.parentElement;
            const out = ['PARENT: ' + parent.id + ' ' + parent.className];
            [...parent.children].slice(0, 18).forEach(el => {
                out.push((el.className||'').toString().slice(0,60) + ' || ' + el.textContent.replace(/\\s+/g,' ').trim().slice(0,55));
            });
            return out;
        }""")
        for s in seq: print(s)
        await b.close()

asyncio.run(main())
