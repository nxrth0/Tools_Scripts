
from playwright.sync_api import sync_playwright
import json
import time

def extract_pinned_and_center_rows():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("🔓 Go to Seller Database and apply your filters. Then press ENTER here to start scraping...")
        page.goto("https://app.smartscout.com/seller-database")
        input("✅ Ready? Press ENTER to begin scrolling + extraction...")

        collected_rows = []
        seen = set()

        for i in range(100):
            # Horizontal scroll unlock (to be safe)
            try:
                first_row = page.locator(".ag-center-cols-container .ag-row").first
                first_row.hover()
                for _ in range(6):
                    page.keyboard.press("ArrowRight")
                    time.sleep(0.05)
            except:
                pass

            # Extract pinned and center data together
            data = page.evaluate("""
                () => {
                    const pinned = document.querySelectorAll('.ag-pinned-left-cols-container .ag-row');
                    const center = document.querySelectorAll('.ag-center-cols-container .ag-row');
                    const combined = [];

                    for (let i = 0; i < Math.min(pinned.length, center.length); i++) {
                        const rowData = [];
                        pinned[i].querySelectorAll('.ag-cell').forEach(cell => rowData.push(cell.innerText));
                        center[i].querySelectorAll('.ag-cell').forEach(cell => rowData.push(cell.innerText));
                        if (rowData.length > 0) combined.push(rowData);
                    }
                    return combined;
                }
            """)

            new_rows = 0
            for row in data:
                key = tuple(row)
                if key not in seen:
                    seen.add(key)
                    collected_rows.append(row)
                    new_rows += 1

            print(f"🔁 Scroll {i+1}: +{new_rows} new rows (total so far: {len(collected_rows)})")

            page.evaluate("""
                () => {
                    const viewport = document.querySelector('.ag-body-viewport');
                    if (viewport) viewport.scrollTop += 1000;
                }
            """)

            time.sleep(0.8)

        with open("smartscout_combined_rows.json", "w", encoding="utf-8") as f:
            json.dump(collected_rows, f, indent=2, ensure_ascii=False)

        print(f"✅ Done! Exported {len(collected_rows)} rows to smartscout_combined_rows.json")
        browser.close()

extract_pinned_and_center_rows()
