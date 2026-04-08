import sys
import os
import time
import utils.config as config
from datetime import datetime
from utils.monitor import run_target_monitor, get_all_events
from utils.buyer import start_purchase


def main():
    print("--- EBILET SELECTOR ---")
    print(f"Target URL: {config.BASE_URL}")

    # 1. Pobierz listę dostępnych biletów
    print("Skanowanie biletów...")
    events = get_all_events()
    
    if not events:
        print("Nie znaleziono żadnych meczów na stronie.")
        return

    # 2. Wyświetl menu wyboru
    print("\nLista wszystkich meczów:")
    for index, ev in enumerate(events):
        status_icon = "🟢" if ev['is_buyable'] else "🔴"
        print(f"[{index}] {status_icon} {ev['date']} | {ev['title']}")

    # 3. Użytkownik wybiera cel
    while True:
        try:
            choice = int(input("\nPodaj numer wybranego meczu: "))
            if 0 <= choice < len(events):
                target_event = events[choice]
                break
            print("Nieprawidłowy numer.")
        except ValueError:
            print("Wpisz cyfrę!")

    print(f"\nUstawiono cel: {target_event['title']}")
    print(f"Bot będzie sprawdzał dostępność co {config.CHECK_INTERVAL} sekund...")

    # 4. Uruchomienie pętli monitorującej tylko ten jeden cel
    success = run_target_monitor(target_event)

    # 5. Jeżeli dostępny do zakupu rozpczynamy sekwencję rezerwacji miejsc i zakupu
    if success:
        print(f"\n[MAIN] Przekazuję cel do modułu BUYER: {target_event['url']}")
        start_purchase(target_event['url'])
    else:
        print("\n[MAIN] Monitorowanie zakończone bez zakupu.")

if __name__ == "__main__":
    main()