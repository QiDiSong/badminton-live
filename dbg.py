import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/chromium",
            args=["--no-sandbox","--disable-dev-shm-usage","--headless=new"])
        page = await b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36")
        await page.goto("https://www.flashscore.com/badminton/", timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(9000)
        info = await page.evaluate("""() => ({
            url: location.href,
            title: document.title,
            nMatch: document.querySelectorAll('.event__match').length,
            nHeader: document.querySelectorAll('.event__header,.event__leagueHeader,.leagueHeader').length,
            bodySnippet: document.body.innerText.slice(0,300)
        })""")
        print(json.dumps(info, ensure_ascii=False, indent=1))
        await b.close()

asyncio.run(main())
