import sys
import os
import time
from datetime import datetime
from utils.monitor import get_available_tickets, run_target_monitor, get_all_events

def main():
    print("--- EBILET SELECTOR ---")
    
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

    # 3. Użytkownik wybiera mecze
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
    print("Bot będzie sprawdzał dostępność co 5 sekund...")

    # 4. Uruchomienie pętli monitorującej tylko ten jeden cel
    run_target_monitor(target_event)

if __name__ == "__main__":
    main()