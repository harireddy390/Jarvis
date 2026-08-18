from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    try:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        print(f"Connected. Contexts: {len(browser.contexts)}")
        for i, context in enumerate(browser.contexts):
            print(f"Context {i}: {len(context.pages)} pages")
            for page in context.pages:
                print(f"  - URL: {page.url}")
    except Exception as e:
        print(f"Connection failed: {e}")