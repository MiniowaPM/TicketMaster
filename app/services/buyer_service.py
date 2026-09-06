import time
import json
from services.config_service import config
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
            success = execute_buy_sequence(page, target_url)
            
            if success and config.HEADLESS:
                print("[BUYER] Przełączanie z trybu ukrytego (Headless) na widoczny, aby dokończyć zakup...")
                context.storage_state(path=config.COOKIES_FILE)
                browser.close()
                
                # Uruchamiamy nową widoczną przeglądarkę
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(storage_state=config.COOKIES_FILE)
                page = context.new_page()
                page.goto(target_url, wait_until="domcontentloaded")
                print("[BUYER] Przeglądarka otwarta. Dokończ płatność!")
                
            # Utrzymanie sesji po sukcesie
            if success:
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

    # 1. Włączanie trybu rezerwacji (EKSPRES) poprzez aktywację w obiekcie strony (Knockout.js)
    print("[BUYER] Wymuszam otwarcie panelu AutoReservation...")
    try:
        # Próbujemy użyć przycisku EKSPRES lub manualnie kliknąć pierwszą dostępną strefę
        page.evaluate("""
            () => {
                if(window.index) {
                    if (window.index.startWindow && typeof window.index.startWindow.expressModeClick === 'function') {
                        window.index.startWindow.expressModeClick();
                    } else if (window.index.autoReservation) {
                        window.index.autoReservation.visible(true);
                        window.index.autoReservation.step(2);
                    }
                }
            }
        """)
        # Jeśli strona korzysta z Manual Map Mode, musimy kliknąć strefę na liście
        is_auto_reservation_ready = page.evaluate("window.index && window.index.autoReservation && typeof window.index.autoReservation.filtredPriceZones === 'function' && window.index.autoReservation.filtredPriceZones().length > 0")
        
        if not is_auto_reservation_ready:
            print("[BUYER] Brak aktywnych stref w Auto-Rezerwacji (Tryb Manualny).")
            
            # W tym trybie trzeba fizycznie kliknąć w kolorowy prostokąt (sektor) na mapie Canvas!
            # Mapa to Leaflet, który renderuje sektory na elemencie <canvas>.
            map_canvas = page.locator("canvas.leaflet-zoom-animated").first
            try:
                map_canvas.wait_for(state="visible", timeout=3000)
                box = map_canvas.bounding_box()
                if box:
                    # Celujemy w środek poziomo i 3/4 wysokości pionowo (tam gdzie są kolorowe sektory na rysunku)
                    target_x = box["width"] / 2
                    target_y = box["height"] * 0.75
                    print(f"[BUYER] Klikam w mapę (sektor) na współrzędnych: {target_x}, {target_y}...")
                    map_canvas.click(position={"x": target_x, "y": target_y}, force=True)
                    time.sleep(1)
            except:
                print("[BUYER] UWAGA: Nie znaleziono mapy (canvas) do kliknięcia!")
                
            # Fallback (na wypadek, gdyby to nie była mapa Canvas, a starsza lista)
            available_zones = page.locator(".items-container .item.row:not(.disabled):not(.noactive)")
            if available_zones.count() > 0 and not page.locator("text='Liczba biletów'").first.is_visible():
                print("[BUYER] Zabezpieczenie: Próbuję jeszcze raz kliknąć strefę na liście bocznej...")
                available_zones.first.click(force=True)
                time.sleep(1)
        else:
            print("[BUYER] Panel Auto-Rezerwacji załadowany.")
    except Exception as e:
        print(f"[BUYER] Nie udało się otworzyć panelu rezerwacji/strefy: {e}")
        page.screenshot(path=f"debug/debug_panel_{int(time.time())}.png")
        return

    try:
        # 2. Wybór ilości biletów i dodanie do koszyka
        print(f"[BUYER] Próba ustawienia {config.TICKETS_COUNT} biletów...")
        
        # Czekamy aż pojawi się przycisk "Dodaj do koszyka", co oznacza że modal jest gotowy
        add_btn = page.locator("button:has-text('Dodaj do koszyka'):visible")
        add_btn.first.wait_for(state="visible", timeout=5000)
        print("[BUYER] Modal wyboru biletów jest widoczny.")
        
        # 1. Próbujemy natywny <select> - najbardziej niezawodny
        ticket_selects = page.locator("select:visible")
        if ticket_selects.count() > 0:
            print("[BUYER] Znaleziono klasyczny <select> wyboru biletów.")
            current_val = ticket_selects.first.input_value()
            if current_val != str(config.TICKETS_COUNT):
                ticket_selects.first.select_option(str(config.TICKETS_COUNT))
                print(f"[BUYER] Zmieniono ilość biletów na {config.TICKETS_COUNT} (natywny select).")
                time.sleep(0.5)
        else:
            # 2. Próbujemy customowy dropdown po etykiecie "Liczba biletów"
            print("[BUYER] Brak natywnego <select>, szukam customowego dropdownu...")
            # Pobieramy kontener z "Liczba biletów" i szukamy w nim klikalnego elementu pokazującego "1"
            container = page.locator("div:has-text('Liczba biletów')").last
            if container.is_visible():
                print("[BUYER] Otwieram customowy dropdown...")
                # Szukamy miejsca, gdzie wyświetla się wybrana liczba (zazwyczaj tekst "1") i klikamy
                # Bezpieczniej jest kliknąć po prostu pod napisem "Liczba biletów" wykorzystując bounding_box
                box = page.locator("text='Liczba biletów'").first.bounding_box()
                if box:
                    # Klikamy trochę poniżej etykiety (tam, gdzie jest pole wyboru)
                    page.mouse.click(box["x"] + 10, box["y"] + box["height"] + 15)
                    time.sleep(0.5)
                    # Teraz szukamy i klikamy pożądaną liczbę na liście (musi być dokładnie ta liczba jako cały tekst, np. opcja w liście)
                    target_option = page.locator(f"text='{config.TICKETS_COUNT}'").locator("visible=true").last
                    target_option.click(force=True)
                    print(f"[BUYER] Zmieniono ilość biletów na {config.TICKETS_COUNT} (custom dropdown).")
                    time.sleep(0.5)
        
        # Ostatecznie klikamy przycisk 'Dodaj do koszyka'
        if add_btn.count() > 0:
            print("[BUYER] Klikam przycisk 'Dodaj do koszyka'...")
            add_btn.first.click(force=True)
            success = True
        else:
            print("[BUYER] UWAGA: Przycisk 'Dodaj do koszyka' zniknął?!")
            success = False
            
    except Exception as e:
        print(f"[BUYER] UWAGA: Błąd wizualnego wyboru ilości biletów: {e}")

        # 4. Opcjonalne okno wyboru strefy (po kliknięciu Dodaj do koszyka)
        try:
            print("[BUYER] Oczekuję na ewentualne okno wyboru strefy...")
            # Szukamy jakiegokolwiek przycisku potwierdzającego, który pojawia się po 1-2 sekundach
            # Możliwe teksty: Rezerwuj, Potwierdź, OK, Zmień, Wybierz
            time.sleep(1.5)
            
            # Pobieramy wszystkie widoczne selecty, które NIE SĄ od wyboru biletów
            zone_selects = page.locator("select:visible").exclude(page.locator("select[id^='leftMenu-ticketTypeTicketsQuantity-select-']"))
            if zone_selects.count() > 0:
                print("[BUYER] Wykryto okno wyboru strefy (select)! Wybieram pierwszą opcję...")
                options = zone_selects.first.locator("option").all()
                for opt in options:
                    val = opt.get_attribute("value")
                    if val and val != "":
                        zone_selects.first.select_option(value=val)
                        print(f"[BUYER] Wybrano strefę o wartości: {val}")
                        break
                        
            # Alternatywnie szukamy przycisków radio
            radios = page.locator("input[type='radio']:visible")
            if radios.count() > 0:
                print("[BUYER] Znaleziono opcje strefy jako radio. Wybieram pierwszą...")
                radios.first.click(force=True)

            # Klikamy dowolny przycisk z popularnymi nazwami potwierdzenia, jeśli jest widoczny
            for btn_text in ["Rezerwuj", "Potwierdź", "OK", "Zatwierdź", "Wybierz"]:
                confirm_btn = page.locator(f"button:has-text('{btn_text}'):visible")
                if confirm_btn.count() > 0:
                    print(f"[BUYER] Klikam przycisk '{btn_text}' w modalu...")
                    confirm_btn.first.click(force=True)
                    break
        except Exception as e:
            print("[BUYER] Brak dodatkowego okna wyboru strefy (lub zniknęło).")
    
    except Exception as e:
        print(f"[BUYER] Błąd interakcji: {e}")
        page.screenshot(path=f"debug/debug_final_{int(time.time())}.png")

    # 4. Weryfikacja rezerwacji
    return verify_reservation(page)

def verify_reservation(page: Page) -> bool:
    """Sprawdza, czy serwer potwierdził rezerwację."""
    print("[BUYER] Oczekiwanie na potwierdzenie z serwera...")
    # Czekamy na przejście do kolejnego kroku (np. Dane kontaktowe) lub pojawienie się timera rezerwacji
    try:
        # eBilet może przenieść nas do #step-4 (stary design) lub pokazać timer i pasek z przyciskiem "Kup X bilet" (nowy design)
        # page.locator(...).or_(page.locator(...)) pozwala czekać na jedno z dwóch
        success_locator = page.locator("#step-4").or_(page.locator("div#timer:visible"))
        success_locator.first.wait_for(timeout=10000)
        
        print("\n" + "!"*40)
        print("!!! SUKCES: BILETY SĄ ZAREZERWOWANE !!!")
        print("Miejsca zostały zablokowane w systemie (masz ok. 10 minut).")
        print("Kliknij 'Kup bilet' i dokończ płatność ręcznie w oknie przeglądarki.")
        print("!"*40 + "\n")
        # Alarm dźwiękowy
        for _ in range(5): print('\a'); time.sleep(0.2)
        return True
    except:
        print("[BUYER] UWAGA: Nie udało się zweryfikować rezerwacji (brak kroku 4 lub timera). Sprawdź okno przeglądarki!")
        page.screenshot(path=f"debug/debug_verify_{int(time.time())}.png")
        return False

def keep_browser_open(page: Page):
    """Zatrzymuje skrypt, dopóki użytkownik nie zamknie przeglądarki."""
    while not page.is_closed():
        time.sleep(1)