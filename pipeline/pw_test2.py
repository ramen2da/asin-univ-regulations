from playwright.sync_api import sync_playwright

SHOT = r"C:\Users\bbuny\AppData\Local\Temp\claude\c--new\7e763b8e-60b7-4dbf-b332-b8513c094a74\scratchpad"
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto("http://127.0.0.1:8010/")
    page.wait_for_selector(".tree .category", timeout=10000)
    page.screenshot(path=f"{SHOT}/6_tree_collapsed.png")

    # expand "일반행정" via its arrow, then click "복무 및 인사" subcategory label to load list
    page.click("text=일반행정 >> xpath=preceding-sibling::span[1]")
    page.wait_for_timeout(200)
    page.click(".tree .category .label:text-is('복무 및 인사')")
    page.wait_for_selector("table.reg-list", timeout=10000)
    page.screenshot(path=f"{SHOT}/7_list_page1.png", full_page=True)

    result_count = page.inner_text(".result-count")
    pager_text = page.inner_text(".pager span") if page.query_selector(".pager") else "NO PAGER"

    # go to next page
    if page.query_selector("#nextPage"):
        page.click("#nextPage")
        page.wait_for_timeout(300)
        pager_text2 = page.inner_text(".pager span")
        first_row_seq_p2 = page.inner_text("table.reg-list tbody tr:first-child td:first-child")
    else:
        pager_text2 = "NO NEXT BTN"
        first_row_seq_p2 = None

    page.screenshot(path=f"{SHOT}/8_list_page2.png", full_page=True)

    browser.close()

print("RESULT_COUNT:", result_count)
print("PAGER_P1:", pager_text)
print("PAGER_P2:", pager_text2)
print("FIRST_ROW_SEQ_P2:", first_row_seq_p2)
print("CONSOLE_ERRORS:", errors)
