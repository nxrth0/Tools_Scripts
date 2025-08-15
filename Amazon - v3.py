import asyncio
import random
import re
from playwright.async_api import async_playwright
import csv

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
]

async def scrape_amazon():
    keywords = input("Enter keywords (comma-separated): ").split(",")
    keywords = [kw.strip() for kw in keywords]
    min_price = float(input("Enter minimum price: "))
    max_price = float(input("Enter maximum price: "))
    min_reviews = int(input("Enter minimum reviews: "))
    max_reviews = int(input("Enter maximum reviews: "))

    output_file = "amazon_products_filtered.csv"

    with open(output_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Product Title", "ASIN", "Price", "Reviews", "Product URL", "Brand Name", "Sold By Business Name", "Seller Address"])

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()

            for keyword in keywords:
                print(f"Scraping keyword: {keyword}")
                page_number = 1

                while True:
                    search_url = f"https://www.amazon.com/s?k={keyword.replace(' ', '+')}&page={page_number}"
                    print(f"Navigating to: {search_url}")
                    await page.goto(search_url)
                    await page.wait_for_timeout(3000)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(2000)

                    products = await page.query_selector_all("div.s-main-slot div[data-asin]")
                    print(f"Found {len(products)} products on page {page_number}")
                    if not products:
                        break

                    for product in products:
                        asin = await product.get_attribute("data-asin")
                        if asin:
                            title_els = await product.query_selector_all("xpath=.//h2/a/span")
                            title_el = title_els[0] if title_els else None
                            title = await title_el.inner_text() if title_el else "N/A"

                            if title == "N/A":
                                print(f"[DEBUG] Fallback triggered for ASIN: {asin}")
                                link_el = await product.query_selector("a.a-link-normal.s-no-outline")
                                product_link = await link_el.get_attribute("href") if link_el else None
                                if product_link and not product_link.startswith("http"):
                                    product_link = "https://www.amazon.com" + product_link

                                try:
                                    detail_page = await context.new_page()
                                    await detail_page.goto(product_link)
                                    await detail_page.wait_for_selector("#productTitle", timeout=5000)
                                    await detail_page.wait_for_timeout(1000)
                                    title_el = await detail_page.query_selector("#productTitle")
                                    title = (await title_el.inner_text()).strip() if title_el else "N/A"
                                except Exception as e:
                                    print(f"[ERROR] Failed to fetch title for ASIN {asin}: {e}")
                                finally:
                                    await detail_page.close()

                            price_whole_el = await product.query_selector("span.a-price-whole")
                            price_fraction_el = await product.query_selector("span.a-price-fraction")
                            price_range_el = await product.query_selector("span.a-price-range")
                            reviews_el = await product.query_selector("span.a-size-base")

                            price = 0.0
                            if price_range_el:
                                price_text = await price_range_el.inner_text()
                                prices = [float(p.replace('$', '').replace(',', '').strip()) for p in price_text.replace('–', '-').split('-')]
                                price = sum(prices) / len(prices)
                            elif price_whole_el and price_fraction_el:
                                price_whole = (await price_whole_el.inner_text()).replace(',', '').replace('\n', '').replace('.', '').strip()
                                price_fraction = (await price_fraction_el.inner_text()).replace(',', '').replace('\n', '').replace('.', '').strip()
                                price_string = f"{price_whole}.{price_fraction}".replace('..', '.').strip()
                                price_string = re.sub(r'[^0-9.]', '', price_string)
                                price = float(price_string)

                            reviews = int((await reviews_el.inner_text()).replace(',', '')) if reviews_el and (await reviews_el.inner_text()).isdigit() else 0

                            product_url = f"https://www.amazon.com/dp/{asin}"

                            brand_name = "N/A"
                            sold_by_name = "N/A"
                            seller_address = "N/A"

                            if min_price <= price <= max_price and min_reviews <= reviews <= max_reviews:
                                link_el = await product.query_selector("a.a-link-normal.s-no-outline")
                                product_link = await link_el.get_attribute("href") if link_el else None
                                if product_link and not product_link.startswith("http"):
                                    product_link = "https://www.amazon.com" + product_link

                                try:
                                    detail_page = await context.new_page()
                                    await detail_page.goto(product_link)
                                    await detail_page.wait_for_timeout(3000)

                                    brand_el = await detail_page.query_selector("#bylineInfo")
                                    sold_by_el = await detail_page.query_selector("#sellerProfileTriggerId")

                                    brand_name_text = await brand_el.inner_text() if brand_el else "N/A"
                                    brand_name = brand_name_text.replace("Visit the ", "").replace("Store", "").strip() if brand_name_text else "N/A"
                                    sold_by_name = await sold_by_el.inner_text() if sold_by_el else "N/A"

                                    if sold_by_el:
                                        seller_profile_url = await sold_by_el.get_attribute("href")
                                        if seller_profile_url and not seller_profile_url.startswith("http"):
                                            seller_profile_url = "https://www.amazon.com" + seller_profile_url
                                        seller_page = await context.new_page()
                                        await seller_page.goto(seller_profile_url)
                                        await seller_page.wait_for_timeout(3000)
                                        seller_address_el = await seller_page.query_selector("div#page-section-detail-seller-info")
                                        seller_address = await seller_address_el.inner_text() if seller_address_el else "N/A"
                                        await seller_page.close()

                                    await detail_page.close()

                                    writer.writerow([title, asin, price, reviews, product_url, brand_name, sold_by_name, seller_address])
                                except Exception as e:
                                    print(f"[ERROR] Detail page failed for ASIN {asin}: {e}")

                    next_button = await page.query_selector("li.a-last a")
                    if next_button:
                        page_number += 1
                    else:
                        break

            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_amazon())
