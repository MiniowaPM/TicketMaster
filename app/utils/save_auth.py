import os
import sys

# Ensure app is in path if script is run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from app.services.config_service import config
from app.services.logger_service import logger

def run_save_auth():
    logger.info("Otwieranie przeglądarki do logowania...")
    try:
        with sync_playwright() as p:
            # Flagi pozwalające na swobodne otwieranie okienek pop-up (OAuth)
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--disable-popup-blocking"]
            )
            context = browser.new_context()
            page = context.new_page()
            
            # Włączamy tryb Stealth, żeby Google OAuth nie blokowało logowania jako "automatu"
            stealth = Stealth()
            stealth.apply_stealth_sync(page)
            
            logger.info("Nawigacja do strony logowania eBilet...")
            page.goto("https://sklep.ebilet.pl/LoginRegister?returnUrl=https://www.ebilet.pl")
            
            # Wstrzyknięcie widocznego przycisku do zapisywania
            page.evaluate("""
                const btn = document.createElement('button');
                btn.innerHTML = 'ZAPISZ SESJĘ I ZAMKNIJ';
                btn.style.position = 'fixed';
                btn.style.top = '10px';
                btn.style.right = '10px';
                btn.style.zIndex = '999999';
                btn.style.padding = '15px 25px';
                btn.style.backgroundColor = '#E50914';
                btn.style.color = 'white';
                btn.style.fontWeight = 'bold';
                btn.style.border = 'none';
                btn.style.borderRadius = '5px';
                btn.style.cursor = 'pointer';
                btn.style.boxShadow = '0 4px 6px rgba(0,0,0,0.3)';
                btn.onclick = () => { window.save_session_clicked = true; };
                document.body.appendChild(btn);
            """)
            
            logger.info("Zaloguj się na swoje konto. Możesz kliknąć czerwony przycisk w prawym górnym rogu lub po prostu zamknąć przeglądarkę – sesja zapisuje się na bieżąco w tle!")
            
            while True:
                if page.is_closed():
                    logger.info("Wykryto zamknięcie przeglądarki (is_closed).")
                    break
                    
                try:
                    # Sprawdzamy czy użytkownik kliknął przycisk (może rzucić błąd podczas przeładowywania strony)
                    clicked = page.evaluate("window.save_session_clicked")
                    if clicked:
                        logger.info("Kliknięto przycisk zapisu!")
                        break
                except Exception as e:
                    pass
                    
                try:
                    # Zapisujemy stan co 1 sekundę
                    context.storage_state(path=config.COOKIES_FILE)
                except Exception as e:
                    pass
                    
                try:
                    page.wait_for_timeout(1000)
                except Exception as e:
                    if page.is_closed():
                        break
                    
            # Ostateczny zapis przed zamknięciem (jeśli zamykamy przyciskiem)
            try:
                context.storage_state(path=config.COOKIES_FILE)
            except:
                pass
                
            browser.close()
            logger.info(f"Proces zakończony. Sesja pomyślnie utrwalona w {config.COOKIES_FILE}.")
    except Exception as e:
        logger.error(f"Błąd podczas autoryzacji: {e}", exc_info=True)

if __name__ == "__main__":
    run_save_auth()