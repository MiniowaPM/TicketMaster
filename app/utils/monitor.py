import json
import time
import utils.config as config
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

def run_target_monitor(target):
    target_id = target['id']
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        stealth = Stealth()
        stealth.apply_stealth_sync(page)
        
        try:
            while True:
                current_events = get_all_events(page)
                target_status = next((ev for ev in current_events if ev['id'] == target_id), None)            
                
                if not target_status:
                    print(f"\nBłąd: Mecz {target_id} zniknął z systemu!")
                    return False
                
                timestamp = datetime.now().strftime('%H:%M:%S')
                
                if target_status['is_buyable']:
                    print(f"\n[{timestamp}] !!! BILETY SĄ DOSTĘPNE !!!")
                    print(f"Bilety na {target['title']} są dostępne!")
                    print(f"Link: {target.get('url', 'Przejdź do strony eBilet')}")
                    
                    print("\nKonczę monitorowanie. Przechodzę do zakupu...")
                    return True 
                else:
                    print(f"[{timestamp}] Cel: {target['title'][:30]}... | Status: Czekam", end='\r')
                
                time.sleep(config.CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\n\nMonitorowanie przerwane przez użytkownika.")
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
        # Give it a tiny bit of time to settle just in case
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
                                # Pobieramy statusy
                                is_sold_out = event.get('soldOut', False)
                                is_unavailable = event.get('currentlyUnavailable', False)
                                free_seats_data = event.get('freeSeats') or event.get('free_seats') or {}
                                has_seats = free_seats_data.get('hasFreeSeats', False)
                                tech_id = free_seats_data.get('decryptedEventId')

                                if not tech_id:
                                    tech_id = event.get('id')

                                shop_url = f"https://sklep.ebilet.pl/{tech_id}"

                                # Flaga czy bilet można kupić TERAZ
                                is_buyable = has_seats and not is_sold_out and not is_unavailable
                                
                                all_events.append({
                                    'id': event.get('id'),
                                    'title': event.get('title'),
                                    'date': event.get('date'),
                                    'is_buyable': is_buyable,
                                    'status_text': "DOSTĘPNE" if is_buyable else "NIEDOSTĘPNE/WYPRZEDANE",
                                    'url': shop_url
                                })
        return all_events
    except Exception as e:
        print(f"Błąd monitora: {e}")
        return []