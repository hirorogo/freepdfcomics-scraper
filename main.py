import asyncio
import os
import logging
from typing import List

import aiofiles
import bs4
from curl_cffi import AsyncSession, Response

# ログの設定
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# 並列タスクを制限
semaphore = asyncio.Semaphore(10)
semaphore2 = asyncio.Semaphore(10)


async def downloadPdf(pdfUrl: str):
    async with semaphore2:
        _, _, _, _, name, numberAndExt = pdfUrl.split("/")
        if os.path.exists(f"./pdfs/{name}-{numberAndExt}"):
            return

        logger.info(f"Downloading {name}-{numberAndExt}")
        logger.info(f"Url is {pdfUrl}")

        while True:
            try:
                async with AsyncSession(
                    headers={
                        "Origin": "https://freepdfcomic.com/",
                        "Referer": "https://freepdfcomic.com/",
                    },
                ) as client:
                    response: Response = await client.get(
                        pdfUrl,
                    )
                    if response.status_code == 404:
                        logger.error("File is not found :(")
                        return

                    response.raise_for_status()

                    async with aiofiles.open(
                        f"./pdfs/{name}-{numberAndExt}", "wb"
                    ) as f:
                        await f.write(response.content)
                break
            except Exception as e:
                logger.error(f"Error downloading {name}-{numberAndExt} Re-fetching...")
                logger.error(f"Because {e}")
                await asyncio.sleep(60)
                continue

        logger.info(f"Downloaded {name}-{numberAndExt}")


async def getNovel(novelUrl: str):
    async with semaphore:
        while True:
            try:
                async with AsyncSession(
                    headers={
                        "Origin": "https://freepdfcomic.com/",
                        "Referer": "https://freepdfcomic.com/",
                    },
                ) as client:
                    response: Response = await client.get(novelUrl)
                    soup = bs4.BeautifulSoup(response.text, "html.parser")
                    select = soup.select_one("select#selector.vi13")
                    pdfUrls: List[str] = []
                    for option in select.select("option"):
                        _, url = option.attrs["value"].split("?file=")
                        if isinstance(url, list):
                            url = "?file=".join(url)
                        pdfUrls.append(url)
                    break
            except Exception as e:
                logger.error(f"{novelUrl} info fetch failed. Re-fetching...")
                logger.error(f"Because {e}")
                await asyncio.sleep(60)
                continue

        # PDF ダウンロードを並列実行
        await asyncio.gather(*(downloadPdf(pdfUrl) for pdfUrl in pdfUrls))


async def fetchPage(pageNumber: int):
    """特定のページのURLリストを取得"""
    logger.info(f"Fetching Page {pageNumber}")
    async with AsyncSession(
        headers={
            "Origin": "https://freepdfcomic.com/",
            "Referer": "https://freepdfcomic.com/",
        },
    ) as client:
        response: Response = await client.get(
            f"https://freepdfcomic.com/archives/category/%E3%83%8E%E3%83%99%E3%83%AB/page/{pageNumber}"
        )
        soup = bs4.BeautifulSoup(response.text, "html.parser")
        posts = soup.select(".post")
        novelUrls: List[str] = []

        for post in posts:
            if post.attrs.get("style"):
                continue
            content = post.select_one("div[class='entry-content']")
            novelUrls.append(content.select_one("a[class='more-link']").attrs["href"])

    # ノベルの詳細取得を並列実行
    await asyncio.gather(*(getNovel(novelUrl) for novelUrl in novelUrls))


async def main():
    async with AsyncSession(
        headers={
            "Origin": "https://freepdfcomic.com/",
            "Referer": "https://freepdfcomic.com/",
        },
    ) as client:
        response: Response = await client.get(
            "https://freepdfcomic.com/archives/category/%E3%83%8E%E3%83%99%E3%83%AB"
        )
        soup = bs4.BeautifulSoup(response.text, "html.parser")

    # 全ページ数を取得
    allPages = int(soup.select("a[class='page-numbers']")[-1].getText(strip=True))

    os.makedirs("./pdfs/", exist_ok=True)

    # ページを並列取得
    await asyncio.gather(*(fetchPage(i) for i in range(1, allPages + 1)))


asyncio.run(main())
