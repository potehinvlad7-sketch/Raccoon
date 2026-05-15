from __future__ import annotations

import asyncio

import httpx
from dotenv import load_dotenv
import os


async def check_direct() -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.telegram.org")
            return resp.status_code in (200, 301, 302)
    except Exception:
        return False


async def check_proxy(proxy_url: str | None) -> bool:
    if not proxy_url:
        return False
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=10) as client:
            resp = await client.get("https://api.telegram.org")
            return resp.status_code in (200, 301, 302)
    except Exception:
        return False


async def main() -> None:
    load_dotenv()
    proxy_url = os.getenv("PROXY_URL", "").strip() or None
    direct_ok = await check_direct()
    proxy_ok = await check_proxy(proxy_url)

    print(f"DIRECT: {'OK' if direct_ok else 'FAIL'}")
    print(f"PROXY: {'OK' if proxy_ok else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
