"""Browser checks against the real local frontend, catalog, and model services.

Run normally, then stop only the model and run with --fallback. The script never
creates an application account or writes to Supabase.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx
import pyarrow.dataset as ds
from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fallback", action="store_true")
    parser.add_argument("--check-covers", action="store_true")
    parser.add_argument("--browser", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = root / "logs" / "demo"
    output.mkdir(parents=True, exist_ok=True)
    browser_path = args.browser
    if browser_path is None and os.name == "nt":
        cached = sorted(
            (Path(os.environ["LOCALAPPDATA"]) / "ms-playwright").glob(
                "chromium-*/chrome-win64/chrome.exe"
            )
        )
        if cached:
            browser_path = cached[-1]
    aliases = {
        row["source_book_id"]: row["item_idx"]
        for row in ds.dataset(root / "artifacts/remote-demo/serving/aliases", format="parquet")
        .to_table()
        .to_pylist()
    }
    client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=15)
    catalog = client.get("/api/books?limit=100&sort=ratings_count").json()["data"]
    by_id = {str(row["id"]): row for row in catalog}
    seed = catalog[0]
    results = []
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, executable_path=str(browser_path) if browser_path else None
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        response = page.goto("http://127.0.0.1:3000/demo", wait_until="domcontentloaded")
        assert response is not None and response.ok
        expect(page.get_by_role("button", name="Lấy gợi ý", exact=True)).to_be_enabled(
            timeout=60000
        )
        for scenario in ["history"] if args.fallback else ["genre", "favorite", "history"]:
            page.get_by_label("Tình huống", exact=True).select_option(scenario)
            if scenario == "genre":
                page.get_by_label("Thể loại", exact=True).select_option("Fantasy & Paranormal")
            else:
                page.get_by_label("Chọn sách", exact=True).select_option(str(seed["id"]))
            page.get_by_role("button", name="Lấy gợi ý", exact=True).click()
            status = page.get_by_test_id("demo-status")
            expect(status).to_contain_text(
                "Đang dùng fallback" if args.fallback else "Đang dùng model", timeout=60000
            )
            if not args.fallback:
                expect(status).to_contain_text("remote-demo")
            cards = page.get_by_test_id("demo-results").locator("[data-book-id]")
            expect(cards.first).to_be_visible()
            ids = cards.evaluate_all("nodes => nodes.map(node => node.dataset.bookId)")
            assert ids and len(ids) == len(set(ids))
            assert set(ids) <= set(by_id)
            works = [aliases[str(by_id[value]["goodreads_id"])] for value in ids]
            if not args.fallback:
                assert len(works) == len(set(works)), "Duplicate work in model recommendations"
            excluded = []
            if scenario in {"favorite", "history"}:
                excluded.append(seed)
            if scenario == "history":
                excluded.extend(row for row in catalog[1:3])
            assert not ({str(row["id"]) for row in excluded} & set(ids))
            if not args.fallback:
                excluded_works = {aliases[str(row["goodreads_id"])] for row in excluded}
                assert not (excluded_works & set(works))
            covers = []
            if args.check_covers:
                cards.last.scroll_into_view_if_needed()
                page.evaluate("""async () => {
                    const images = document.querySelectorAll('[data-book-id] img');
                    await Promise.all([...images].map(image => Promise.race([
                        image.decode().catch(() => {}),
                        new Promise(resolve => setTimeout(resolve, 10000))
                    ])));
                }""")
                covers = cards.evaluate_all("""nodes => nodes.map(node => {
                    const image = node.querySelector('img');
                    return {
                        id: node.dataset.bookId,
                        url: image?.currentSrc ?? null,
                        loaded: Boolean(image?.complete && image.naturalWidth > 0),
                        sourcePlaceholder: Boolean(image?.currentSrc.includes('nophoto'))
                    };
                })""")
                assert any(row["loaded"] and not row["sourcePlaceholder"] for row in covers), (
                    "No real book cover loaded in the browser"
                )
            filename = f"{'fallback-' if args.fallback else ''}{scenario}.png"
            page.screenshot(path=str(output / filename), full_page=True)
            results.append(
                {
                    "scenario": scenario,
                    "status": status.inner_text(),
                    "book_ids": ids,
                    "works": works,
                    "screenshot": filename,
                    "covers": covers,
                }
            )
        assert not errors, errors
        # Narrow viewport: verify the same demo controls remain usable.
        page.set_viewport_size({"width": 390, "height": 844})
        expect(page.get_by_role("button", name="Lấy gợi ý", exact=True)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        browser.close()
    client.close()
    report = {"passed": True, "fallback": args.fallback, "results": results, "page_errors": errors}
    destination = output / ("fallback-check.json" if args.fallback else "browser-check.json")
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
