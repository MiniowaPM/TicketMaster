# USTAWIENIA PORTALU
BASE_URL = "https://www.ebilet.pl/sport/sporty-druzynowe/siatkowka"

# USTAWIENIA SNIPERA
CHECK_INTERVAL = 5       # Czas między zapytaniami (sekundy)
TICKETS_COUNT = 6        # Ile biletów bot ma próbować kupić
HEADLESS = False         # Czy pokazywać okno przeglądarki (False = widoczne)

# IDENTYFIKACJA (User-Agent pomaga omijać podstawowe blokady)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8"
}

# PLIKI DANYCH
COOKIES_FILE = "auth.json" # Plik w którym zapiszemy sesję zalogowanego użytkownika