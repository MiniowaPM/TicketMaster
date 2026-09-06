import json
import time
from services.config_service import config
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from services.logger_service import logger
from data.models import Event

def run_target_monitor(target: Event):
    target_id = target.id
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        stealth = Stealth()
        stealth.apply_stealth_sync(page)
        
        try:
            while True:
                current_events = get_all_events(page)
                target_status = next((ev for ev in current_events if ev.id == target_id), None)            
                
                if not target_status:
                    logger.error(f"Błąd: Mecz {target_id} zniknął z systemu!")
                    return False
                
                if target_status.is_buyable:
                    logger.info("!!! BILETY SĄ DOSTĘPNE !!!")
                    logger.info(f"Bilety na {target.title} są dostępne!")
                    logger.info(f"Link: {target.url}")
                    
                    logger.info("Kończę monitorowanie. Przechodzę do zakupu...")
                    return True 
                else:
                    # Zostawiamy jeden print dla efektu "odświeżania w tej samej linii", 
                    # logger zazwyczaj drukuje to w nowych liniach, co zaśmieciłoby konsolę.
                    # W idealnym świecie ten print trafi do CLI View, ale tymczasowo go tu zostawimy z logowaniem na poziomie DEBUG.
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Cel: {target.title[:30]}... | Status: Czekam", end='\r')
                
                time.sleep(config.CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.warning("Monitorowanie przerwane przez użytkownika.")
            return False
        finally:
            browser.close()


def get_all_events(page=None):
    """Pobiera wszystkie mecze, niezależnie od dostępności biletów."""
    
    if page is None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            temp_page = browser.new_page()
            stealth = Stealth()
            stealth.apply_stealth_sync(temp_page)
            events = _fetch_events_from_page(temp_page)
            browser.close()
            return events
    else:
        return _fetch_events_from_page(page)

def _fetch_events_from_page(page):
    all_events = []
    try:
        page.goto(config.BASE_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(1)
        html_content = page.content()

        start_marker = '<script id="serverApp-state" type="application/json">'
        if start_marker in html_content:
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
                                    id=event.get('id'),
                                    title=event.get('title'),
                                    date=event.get('date'),
                                    is_buyable=is_buyable,
                                    status_text="DOSTĘPNE" if is_buyable else "NIEDOSTĘPNE/WYPRZEDANE",
                                    url=shop_url
                                )
                                all_events.append(event_obj)
        return all_events
    except Exception as e:
        logger.error(f"Błąd monitora: {e}")
        return []