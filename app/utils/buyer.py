import time
import utils.config as config
from playwright.sync_api import sync_playwright, Page
from playwright_stealth import Stealth

def start_purchase(target_url: str):
    """Główna funkcja inicjalizująca przeglądarkę i proces zakupu."""
    with sync_playwright() as p:
        # Uruchomienie przeglądarki
        browser = p.chromium.launch(headless=config.HEADLESS)
        
        # Opcjonalnie: wczytanie sesji, jeśli plik auth.json istnieje
        context_args = {}
        import os
        if os.path.exists(config.COOKIES_FILE):
            context_args["storage_state"] = config.COOKIES_FILE
            print(f"[BUYER] Wczytano sesję z {config.COOKIES_FILE}")

        context = browser.new_context(**context_args)
        page = context.new_page()

        stealth_obj = Stealth()
        stealth_obj.apply_stealth_sync(page)

        try:
            # Przejście do procesu zakupu
            execute_buy_sequence(page, target_url)
            
            # Utrzymanie sesji po sukcesie
            keep_browser_open(page)

        except Exception as e:
            print(f"[BUYER] Błąd krytyczny: {e}")
            input("Naciśnij Enter, aby zamknąć...")
        finally:
            browser.close()

def execute_buy_sequence(page: Page, url: str):
    """Sekwencja kroków automatyzujących dodanie do koszyka."""
    print(f"[BUYER] Nawigacja do: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    print("[BUYER] Usuwanie blokad interfejsu...")
    page.evaluate("""
        () => {
            const ids = ['loading-view', 'overlay', 'cookies-overlay'];
            ids.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.remove(); 
            });
            document.documentElement.style.scrollBehavior = 'auto';
        }
    """)

    # 1. Forsowne wstrzyknięcie trybu AutoReservation
    activated = False
    for i in range(10):
        try:
            page.wait_for_function("window.index !== undefined", timeout=3000)
            page.evaluate("""
                () => {
                    if(window.index && window.index.autoReservation) {
                        index.autoReservation.visible(true);
                        index.autoReservation.step(2);
                        // Forsujemy widoczność kontenerów biletów
                        const style = document.createElement('style');
                        style.innerHTML = `
                            .auto-reservation-window, .auto-reservation, .ticket-type-box { 
                                display: block !important; 
                                visibility: visible !important; 
                                opacity: 1 !important; 
                                height: auto !important; 
                            }
                            #autoReservation-addToBasket-btn {
                                display: block !important;
                                visibility: visible !important;
                            }
                        `;
                        document.head.appendChild(style);
                    }
                }
            """)
            # Sprawdzamy czy panel faktycznie się pojawił
            page.wait_for_selector("select[id^='leftMenu-ticketTypeTicketsQuantity-select-']", state="attached", timeout=2000)            
            activated = True
            print("[BUYER] Panel rezerwacji aktywowany.")
            break
        except:
            print(f"[BUYER] Próba {i+1}: Stabilizacja widoku...")
            time.sleep(0.5)

    if not activated:
        print("[BUYER] Nie udało się wywołać panelu rezerwacji.")
        return

    try:
        # 2. Wybór ilości biletów

            # quantity_selects = page.locator("select[id^='leftMenu-ticketTypeTicketsQuantity-select-']")
            # print(f"[BUYER] Próba ustawienia {config.TICKETS_COUNT} biletów...")
            # quantity_selects.first.select_option(value=str(config.TICKETS_COUNT), force=True)

        # Wersja siłowa
        print(f"[BUYER] Ustawiam {config.TICKETS_COUNT} biletów (JS Direct)...")
        page.evaluate(f"""
            (count) => {{
                const sel = document.querySelector("select[id^='leftMenu-ticketTypeTicketsQuantity-select-']");
                if (sel) {{
                    sel.value = count;
                    sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}
        """, str(config.TICKETS_COUNT))

        time.sleep(1)

        # 4. Dodanie do koszyka

            # add_btn = "#autoReservation-addToBasket-btn"

            # time.sleep(0.8)

            # page.evaluate(f"document.querySelector('{add_btn}').classList.remove('disabled')")

            # print("[BUYER] Klikam przycisk rezerwacji...")
            # page.locator(add_btn).click(force=True)
    
    except Exception as e:
        print(f"[BUYER] Błąd interakcji: {e}")
        page.screenshot(path=f"debug_final_{int(time.time())}.png")

    # 4. Weryfikacja rezerwacji
    verify_reservation(page)

def verify_reservation(page: Page):
    """Sprawdza, czy serwer potwierdził rezerwację."""
    print("[BUYER] Oczekiwanie na potwierdzenie z serwera...")
    # Czekamy na przejście do kolejnego kroku (np. Dane kontaktowe)
    # Na eBilet krok 4 to zazwyczaj Contact Details
    try:
        page.wait_for_selector("#step-4", timeout=10000)
        print("\n" + "!"*40)
        print("!!! SUKCES: BILETY SĄ W KOSZYKU !!!")
        print("Miejsca zostały zarezerwowane na ok. 10 minut.")
        print("Dokończ płatność ręcznie.")
        print("!"*40 + "\n")
        # Alarm dźwiękowy
        for _ in range(5): print('\a'); time.sleep(0.2)
    except:
        print("[BUYER] UWAGA: Nie wykryto przejścia do kroku 4. Sprawdź okno przeglądarki!")

def keep_browser_open(page: Page):
    """Zatrzymuje skrypt, dopóki użytkownik nie zamknie przeglądarki."""
    while not page.is_closed():
        time.sleep(1)