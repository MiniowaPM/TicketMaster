import os
import sys

# Ensure app directory is on sys.path
app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from services.config_service import config
from services.logger_service import logger

BUTTON_JS = """
(() => {
    function injectSaveBtn() {
        if (document.getElementById('tm-save-btn')) return;
        const btn = document.createElement('button');
        btn.id = 'tm-save-btn';
        btn.innerHTML = '💾 ZAPISZ SESJĘ I ZAMKNIJ';
        btn.style.position = 'fixed';
        btn.style.top = '10px';
        btn.style.right = '10px';
        btn.style.zIndex = '2147483647';
        btn.style.padding = '12px 20px';
        btn.style.backgroundColor = '#E50914';
        btn.style.color = 'white';
        btn.style.fontWeight = 'bold';
        btn.style.fontFamily = 'sans-serif';
        btn.style.fontSize = '14px';
        btn.style.border = '2px solid white';
        btn.style.borderRadius = '8px';
        btn.style.cursor = 'pointer';
        btn.style.boxShadow = '0 4px 12px rgba(0,0,0,0.5)';
        btn.onclick = () => { window.save_session_clicked = true; };
        if (document.body) {
            document.body.appendChild(btn);
        } else if (document.documentElement) {
            document.documentElement.appendChild(btn);
        }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectSaveBtn);
    } else {
        injectSaveBtn();
    }
})();
"""

def run_save_auth():
    logger.info("Otwieranie przeglądarki do logowania...")
    try:
        os.makedirs(os.path.dirname(config.COOKIES_FILE), exist_ok=True)
        with sync_playwright() as p:
            # Flagi pozwalające na swobodne otwieranie okienek pop-up (OAuth)
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--disable-popup-blocking"]
            )
            context = browser.new_context()
            
            # Wstrzyknięcie skryptu inicjalizacyjnego, aby przycisk istniał na każdej podstronie
            context.add_init_script(BUTTON_JS)
            
            page = context.new_page()
            
            # Włączamy tryb Stealth, żeby Google OAuth nie blokowało logowania jako "automatu"
            stealth = Stealth()
            stealth.apply_stealth_sync(page)
            
            logger.info("Nawigacja do strony logowania eBilet...")
            page.goto("https://sklep.ebilet.pl/LoginRegister?returnUrl=https://www.ebilet.pl")
            
            logger.info("Zaloguj się na swoje konto. Możesz kliknąć czerwony przycisk 'ZAPISZ SESJĘ I ZAMKNIJ' lub po prostu zamknąć przeglądarkę – sesja zapisuje się na bieżąco w tle!")
            
            while True:
                if page.is_closed():
                    logger.info("Wykryto zamknięcie przeglądarki.")
                    break
                    
                try:
                    # Sprawdzamy czy użytkownik kliknął przycisk
                    clicked = page.evaluate("window.save_session_clicked")
                    if clicked:
                        logger.info("Kliknięto przycisk zapisu sesji!")
                        break
                except Exception:
                    pass
                    
                # Upewniamy się, że przycisk jest na stronie (jeśli dynamiczny framework usunął elementy)
                try:
                    page.evaluate(BUTTON_JS)
                except Exception:
                    pass
                    
                try:
                    # Zapisujemy stan sesji co 1 sekundę
                    context.storage_state(path=config.COOKIES_FILE)
                except Exception:
                    pass
                    
                try:
                    page.wait_for_timeout(1000)
                except Exception:
                    if page.is_closed():
                        break
                    
            # Ostateczny zapis przed zamknięciem
            try:
                context.storage_state(path=config.COOKIES_FILE)
            except Exception:
                pass
                
            try:
                browser.close()
            except Exception:
                pass
                
            logger.info(f"Proces zakończony. Sesja pomyślnie utrwalona w {config.COOKIES_FILE}.")
    except Exception as e:
        logger.error(f"Błąd podczas autoryzacji: {e}", exc_info=True)

if __name__ == "__main__":
    run_save_auth()