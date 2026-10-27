import json
import time
import random
from services.config_service import config
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from services.logger_service import logger
from data.models import Event

def run_target_monitor(target: Event, stop_event=None) -> bool:
    target_id = target.id
    logger.info(f"Rozpoczynam monitorowanie celu: {target.title} (ID: {target_id})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        stealth = Stealth()
        stealth.apply_stealth_sync(page)
        
        try:
            iteration = 0
            failures = 0
            while True:
                if stop_event and stop_event.is_set():
                    logger.info("Monitorowanie przerwane przez użytkownika.")
                    return False

                iteration += 1
                current_events = _fetch_events_from_page(page)

                if current_events is None:
                    # Błąd sieci / blokada (np. HTTP 429) - nie przerywamy, tylko zwalniamy
                    failures += 1
                    wait_s = min(120, max(1, config.CHECK_INTERVAL) * (2 ** failures))
                    logger.warning(f"[{iteration}] Nie udało się pobrać listy wydarzeń (próba {failures}). "
                                   f"Ponowię za {wait_s}s...")
                    if not _interruptible_sleep(wait_s, stop_event):
                        logger.info("Monitorowanie przerwane przez użytkownika.")
                        return False
                    continue
                failures = 0

                target_status = next((ev for ev in current_events if ev.id == target_id), None)            
                
                if not target_status:
                    logger.error(f"Błąd: Wydarzenie '{target.title}' (ID: {target_id}) nie zostało znalezione na liście!")
                    return False
                
                if target_status.is_buyable:
                    logger.info("=" * 40)
                    logger.info("!!! BILETY SĄ DOSTĘPNE !!!")
                    logger.info(f"Bilety na: {target.title}")
                    logger.info(f"Link: {target.url}")
                    logger.info("Kończę monitorowanie. Przechodzę do zakupu...")
                    logger.info("=" * 40)
                    return True 
                else:
                    logger.info(f"[{iteration}] Oczekiwanie na bilety: {target.title[:35]}... (sprawdzę za ok. {config.CHECK_INTERVAL}s)")
                
                # Losowy odstęp (jitter), żeby nie odpytywać serwera w idealnie równych odstępach
                sleep_duration = max(1, config.CHECK_INTERVAL) * random.uniform(0.8, 1.3)
                if not _interruptible_sleep(sleep_duration, stop_event):
                    logger.info("Monitorowanie przerwane przez użytkownika.")
                    return False

        except KeyboardInterrupt:
            logger.warning("Monitorowanie przerwane (KeyboardInterrupt).")
            return False
        except Exception as e:
            logger.error(f"Błąd podczas pętli monitorowania: {e}", exc_info=True)
            return False
        finally:
            try:
                browser.close()
            except Exception:
                pass

def get_all_events(page=None):
    """Pobiera wszystkie mecze, niezależnie od dostępności biletów."""
    if page is None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                temp_page = browser.new_page()
                stealth = Stealth()
                stealth.apply_stealth_sync(temp_page)
                return _fetch_events_from_page(temp_page) or []
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
    else:
        return _fetch_events_from_page(page) or []

def _interruptible_sleep(seconds: float, stop_event=None) -> bool:
    """Śpi `seconds` sekund. Zwraca False, jeśli przerwano przez stop_event."""
    end = time.time() + seconds
    while time.time() < end:
        if stop_event and stop_event.is_set():
            return False
        time.sleep(0.1)
    return True

def _fetch_events_from_page(page):
    """Zwraca listę wydarzeń lub None, gdy pobranie się nie powiodło (błąd sieci, HTTP 429 itp.)."""
    all_events = []
    try:
        response = page.goto(config.BASE_URL, wait_until="domcontentloaded", timeout=30000)
        if response is not None and response.status >= 400:
            logger.warning(f"Serwer eBilet zwrócił HTTP {response.status}"
                           f"{' (zbyt wiele zapytań - zwiększ CHECK_INTERVAL)' if response.status == 429 else ''}.")
            return None
        time.sleep(1)
        html_content = page.content()

        start_marker = '<script id="serverApp-state" type="application/json">'
        if start_marker not in html_content:
            logger.warning("Nie znaleziono danych wydarzeń na stronie (możliwa blokada lub zmiana strony).")
            return None

        raw_json = html_content.split(start_marker)[1].split('</script>')[0]
        data = json.loads(raw_json)
        
        for key in data:
            if isinstance(data[key], dict) and 'b' in data[key]:
                body = data[key]['b']
                if isinstance(body, dict) and 'groups' in body:
                    for group in body['groups']:
                        for event in group.get('events', []):
                            is_sold_out = event.get('soldOut', False)
                            is_unavailable = event.get('currentlyUnavailable', False)
                            free_seats_data = event.get('freeSeats') or event.get('free_seats') or {}
                            has_seats = free_seats_data.get('hasFreeSeats', False)
                            tech_id = free_seats_data.get('decryptedEventId')

                            if not tech_id:
                                tech_id = event.get('id')

                            shop_url = f"https://sklep.ebilet.pl/{tech_id}"
                            is_buyable = has_seats and not is_sold_out and not is_unavailable
                            
                            event_obj = Event(
                                id=str(event.get('id')),
                                title=event.get('title') or "Bez tytułu",
                                date=event.get('date') or "Brak daty",
                                is_buyable=is_buyable,
                                status_text="DOSTĘPNE" if is_buyable else "NIEDOSTĘPNE/WYPRZEDANE",
                                url=shop_url
                            )
                            all_events.append(event_obj)
        return all_events
    except Exception as e:
        logger.error(f"Błąd monitora: {e}")
        return None
