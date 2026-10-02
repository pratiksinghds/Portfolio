"""Open each Streamlit live demo in a headless browser so it never shows the sleep page.

Clicks "Yes, get this app back up!" when an app is asleep, then waits until the app
has actually rendered. Exits non-zero if any app fails to load, so the GitHub Action
fails and GitHub emails the repo owner.

Run locally:  pip install playwright && playwright install chromium && python scripts/keep_awake.py
"""
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

APPS = [
    "https://pratik-medical-rag.streamlit.app/",
    "https://pratik-travel-planner.streamlit.app/",
    "https://pratik-book-recommender.streamlit.app/",
    "https://pratik-mistvale-tea.streamlit.app/",
]
WAKE_BUTTON = re.compile(r"get this app back up", re.I)
LOAD_TIMEOUT_S = 300          # a cold start can take a few minutes


def app_rendered(page) -> bool:
    """True once the Streamlit app (top page or its iframe) shows real content."""
    try:
        if page.get_by_text(re.compile(r"gone to sleep|in the oven", re.I)).count():
            return False                       # sleep page or still booting
    except Exception:
        pass
    for frame in page.frames:
        try:
            if frame.locator('[data-testid="stAppViewContainer"]').count() and \
               frame.locator('[data-testid="stMainBlockContainer"], [data-testid="stAppViewBlockContainer"]').count():
                return True
        except Exception:
            continue
    return False


def visit(page, url: str) -> tuple[bool, str]:
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    woke = False
    deadline = time.time() + LOAD_TIMEOUT_S
    while time.time() < deadline:
        button = page.get_by_role("button", name=WAKE_BUTTON)
        if not woke and button.count():
            button.first.click()
            woke = True
        if app_rendered(page):
            page.wait_for_timeout(5_000)      # keep the session open briefly so it counts as a visit
            return True, "woken up" if woke else "already awake"
        page.wait_for_timeout(3_000)
    return False, f"did not load within {LOAD_TIMEOUT_S}s" + (" after wake-up" if woke else "")


def main() -> int:
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get("PW_CHANNEL") or None)  # PW_CHANNEL=chrome uses an installed Chrome
        for url in APPS:
            page = browser.new_page()
            try:
                ok, note = visit(page, url)
            except Exception as exc:              # network error, timeout, etc.
                ok, note = False, f"error: {exc.__class__.__name__}"
            print(f"{'OK  ' if ok else 'FAIL'} {url} - {note}", flush=True)
            failures += not ok
            page.close()
        browser.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
