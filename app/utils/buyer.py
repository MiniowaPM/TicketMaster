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
    page.goto(url, wait_until="networkidle")

    # 1. Odblokowanie ukrytego trybu AutoReservation (Ekspres)
    print("[BUYER] Aktywacja trybu automatycznego wyboru biletów...")
    page.evaluate("index.autoReservation.visible(true)")
    page.evaluate("index.autoReservation.step(2)") # Przeskok do wyboru ilości biletów

    # 2. Wybór ilości biletów
    # Selektor id^ dopasowuje początek id, bo końcówka (id kategorii) może być zmienna
    quantity_selector = "select[id^='leftMenu-ticketTypeTicketsQuantity-select-']"
    page.wait_for_selector(quantity_selector, timeout=15000)
    
    print(f"[BUYER] Ustawianie liczby biletów: {config.TICKETS_COUNT}")
    page.select_option(quantity_selector, str(config.TICKETS_COUNT))

    # 3. Dodanie do koszyka
    add_to_cart_btn = "#autoReservation-addToBasket-btn"
    page.wait_for_selector(add_to_cart_btn)
    
    # Usuwamy klasę 'disabled', jeśli JS jej nie zdjął
    page.evaluate(f"document.querySelector('{add_to_cart_btn}').classList.remove('disabled')")
    
    print("[BUYER] Klikam: DODAJ DO KOSZYKA")
    page.click(add_to_cart_btn)

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