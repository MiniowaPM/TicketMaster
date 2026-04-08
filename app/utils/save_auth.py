from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://sklep.ebilet.pl/LoginRegister?returnUrl=https://www.ebilet.pl") # Przejdź do logowania
    
    print("Zaloguj się ręcznie w oknie przeglądarki...")
    page.wait_for_timeout(60000)
    
    context.storage_state(path="auth.json")
    print("Sesja zapisana do auth.json!")
    browser.close()