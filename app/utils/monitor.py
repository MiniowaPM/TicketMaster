import requests
import json
import time
import config
from datetime import datetime

def get_available_tickets():
    available_events = []
    try:
        response = requests.get(config.BASE_URL, headers=config.HEADERS, timeout=10)
        if response.status_code != 200: return []

        start_marker = '<script id="serverApp-state" type="application/json">'
        content = response.text
        if start_marker in content:
            raw_json = content.split(start_marker)[1].split('</script>')[0]
            data = json.loads(raw_json)
            
            for key in data:
                if isinstance(data[key], dict) and 'b' in data[key]:
                    body = data[key]['b']
                    if isinstance(body, dict) and 'groups' in body:
                        for group in body['groups']:
                            for event in group.get('events', []):
                                is_sold_out = event.get('soldOut', True)
                                free_seats_data = event.get('freeSeats') or event.get('free_seats') or {}
                                has_seats = free_seats_data.get('hasFreeSeats', False)
                                
                                if has_seats and not is_sold_out:
                                    available_events.append({
                                        'id': event.get('id'), # To ID będzie potrzebne do zakupu
                                        'title': event.get('title'),
                                        'date': event.get('date'), # Format ISO np. 2026-06-24T13:00:00
                                        'url': f"https://www.ebilet.pl/bilety/{event.get('id')}" # Dodajemy URL dla wygody                                    
                                        })
        return available_events
    except Exception as e:
        print(f"Błąd monitora: {e}")
        return []
    
def run_target_monitor(target):
    target_id = target['id']
    
    try:
        while True:
            current_status = get_available_tickets()
            
            # Sprawdzamy czy nasz target_id znajduje się na liście dostępnych
            is_available = any(event['id'] == target_id for event in current_status)
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            if is_available:
                print(f"\n[{timestamp}] !!! SUKCES !!!")
                print(f"Bilety na {target['title']} są dostępne!")
                print(f"Link: {target.get('url', 'Przejdź do strony eBilet')}")
                
                # ZAMKNIĘCIE PĘTLI - tutaj w przyszłości wywołamy buyer.py
                print("\nKonczę monitorowanie. Przechodzę do zakupu...")
                break 
            else:
                print(f"[{timestamp}] Cel: {target['title'][:30]}... | Status: Czekam", end='\r')
            
            time.sleep(config.CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n\nMonitorowanie przerwane przez użytkownika.")

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
                                
                                # Flaga czy bilet można kupić TERAZ
                                is_buyable = has_seats and not is_sold_out and not is_unavailable
                                
                                all_events.append({
                                    'id': event.get('id'),
                                    'title': event.get('title'),
                                    'date': event.get('date'),
                                    'is_buyable': is_buyable,
                                    'status_text': "DOSTĘPNE" if is_buyable else "NIEDOSTĘPNE/WYPRZEDANE",
                                    'url': f"https://www.ebilet.pl/bilety/{event.get('id')}"
                                })
        return all_events
    except Exception as e:
        print(f"Błąd monitora: {e}")
        return []