import sys
from playwright.sync_api import sync_playwright

SHOT_DIR = r"C:\Users\bbuny\AppData\Local\Temp\claude\c--new\7e763b8e-60b7-4dbf-b332-b8513c094a74\scratchpad"

errors = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto("http://127.0.0.1:8010/")
    page.wait_for_selector("text=최근 제·개정 규정", timeout=10000)
    page.screenshot(path=f"{SHOT_DIR}/1_landing.png", full_page=True)

    # click a category in the tree
    page.click("text=관리사무")
    page.wait_for_selector("table.reg-list", timeout=10000)
    page.screenshot(path=f"{SHOT_DIR}/2_list.png", full_page=True)

    # click first regulation row
    page.click("table.reg-list tbody tr:first-child")
    page.wait_for_selector(".reg-detail", timeout=10000)
    page.wait_for_selector("text=부칙", timeout=10000)
    page.screenshot(path=f"{SHOT_DIR}/3_detail.png", full_page=True)

    # search test with 2-char term
    page.select_option("#searchScope", "body")
    page.fill("#searchInput", "학생")
    page.click("#searchBtn")
    page.wait_for_selector(".result-count", timeout=10000)
    page.screenshot(path=f"{SHOT_DIR}/4_search.png", full_page=True)

    result_text = page.inner_text(".result-count")

    browser.close()

print("RESULT_COUNT_TEXT:", result_text)
print("CONSOLE_ERRORS:", errors)
