import requests
import json
import time
import utils.config as config
from datetime import datetime

def run_target_monitor(target):
    target_id = target['id']
    
    try:
        while True:
            current_events = get_all_events()
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


def get_all_events():
    """Pobiera wszystkie mecze, niezależnie od dostępności biletów."""
    all_events = []
    try:
        response = requests.get(config.BASE_URL, headers=config.HEADERS, timeout=10)
        if response.status_code != 200: return []

        start_marker = '<script id="serverApp-state" type="application/json">'
        if start_marker in response.text:
            raw_json = response.text.split(start_marker)[1].split('</script>')[0]
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