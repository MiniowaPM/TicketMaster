import time
import json
import re
import os
from services.config_service import config
from playwright.sync_api import sync_playwright, Page
from services.logger_service import logger
from playwright_stealth import Stealth

def start_purchase(target_url: str):
    """Główna funkcja inicjalizująca przeglądarkę i proces zakupu."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.HEADLESS)
        
        context_args = {}
        if os.path.exists(config.COOKIES_FILE):
            context_args["storage_state"] = config.COOKIES_FILE
            logger.info(f"Wczytano sesję z {config.COOKIES_FILE}")

        context = browser.new_context(**context_args)
        page = context.new_page()

        stealth_obj = Stealth()
        stealth_obj.apply_stealth_sync(page)

        try:
            success = execute_buy_sequence(page, target_url)
            
            if success and config.HEADLESS:
                logger.info("Przełączanie z trybu ukrytego (Headless) na widoczny, aby dokończyć zakup...")
                current_url = page.url
                os.makedirs(os.path.dirname(config.COOKIES_FILE), exist_ok=True)
                context.storage_state(path=config.COOKIES_FILE)
                browser.close()
                
                # Uruchamiamy nową widoczną przeglądarkę
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(storage_state=config.COOKIES_FILE)
                page = context.new_page()
                stealth_obj = Stealth()
                stealth_obj.apply_stealth_sync(page)
                page.goto(current_url, wait_until="domcontentloaded")
                logger.info("Przeglądarka otwarta. Dokończ płatność!")
                
            if success:
                keep_browser_open(page)

        except Exception as e:
            logger.error(f"Błąd krytyczny podczas zakupu: {e}", exc_info=True)
        finally:
            try:
                browser.close()
            except Exception:
                pass

def execute_buy_sequence(page: Page, url: str) -> bool:
    """Sekwencja automatyzująca wybór miejsc i dodanie do koszyka."""
    logger.info(f"Nawigacja do: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    # Czyszczenie nakładek blokujących UI i automatyczna akceptacja Cookiebot
    _clean_overlays(page)

    max_engine_attempts = 3
    for attempt in range(1, max_engine_attempts + 1):
        logger.info(f"Próba wyboru miejsc przez silnik eBilet (próba {attempt}/{max_engine_attempts})...")
        engine_result = _reserve_via_ebilet_engine(page, config.TICKETS_COUNT, config.SECTOR_PREFERENCE.value)

        if engine_result.get("ok"):
            logger.info(f"Silnik zainicjował rezerwację w strefie '{engine_result.get('zoneName')}' "
                        f"({engine_result.get('ticketTypeName')}) na {config.TICKETS_COUNT} biletów.")
            
            # Weryfikujemy potwierdzenie z serwera
            is_verified = verify_reservation(page, config.TICKETS_COUNT)
            if is_verified:
                try:
                    page.evaluate("() => { if (window.index && window.index.bottomButton && window.index.bottomButton.click) window.index.bottomButton.click(); }")
                except Exception:
                    pass
                return True
            else:
                logger.warning(f"Próba {attempt} nie powiodła się. Ponawiam próbę z innym sektorem/miejscami...")
                try:
                    page.evaluate("""() => {
                        if (window.index && window.index.eventMap && window.index.eventMap.mapControl) {
                            window.index.eventMap.mapControl.setAllSeatsFree();
                        }
                    }""")
                except Exception:
                    pass
                time.sleep(1.0)
        else:
            logger.warning(f"Silnik JS nie mógł wybrać strefy: {engine_result.get('reason')}.")
            time.sleep(1.0)

    logger.warning("Silnik JS nie sfinalizował rezerwacji. Uruchamiam procedurę awaryjną DOM...")
    _fallback_dom_reservation(page)
    is_verified = verify_reservation(page, config.TICKETS_COUNT)
    if is_verified:
        try:
            page.evaluate("() => { if (window.index && window.index.bottomButton && window.index.bottomButton.click) window.index.bottomButton.click(); }")
        except Exception:
            pass
        return True
    return False

def _clean_overlays(page: Page):
    """Usuwa bannery cookies, nakładki i okna startowe."""
    try:
        page.evaluate("""
            () => {
                const ids = ['loading-view', 'overlay', 'cookies-overlay', 'CybotCookiebotDialog', 'CybotCookiebotDialogBodyUnderlay'];
                ids.forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.remove(); 
                });
                if (window.index && window.index.cookiesPolicy && typeof window.index.cookiesPolicy.acceptCookiesPolicy === 'function') {
                    try { window.index.cookiesPolicy.acceptCookiesPolicy(); } catch(e) {}
                }
                if (window.index && window.index.startWindow && typeof window.index.startWindow.visible === 'function') {
                    try { window.index.startWindow.visible(false); } catch(e) {}
                }
                document.documentElement.style.scrollBehavior = 'auto';
            }
        """)
    except Exception:
        pass

def _reserve_via_ebilet_engine(page: Page, tickets_count: int, preference: str) -> dict:
    """Automatycznie dobiera strefę, miejsca obok siebie i rezerwuje je przez wewnętrzne API Knockout.js."""
    try:
        # Czekamy na załadowanie modelu mapy i sektorów (do 20s)
        page.wait_for_function("""
            () => window.index &&
                  window.index.eventMap &&
                  window.index.eventMap.mapControl &&
                  window.index.eventMap.mapControl.utilities &&
                  window.index.eventMap.mapControl.utilities.sectorsLayerHash &&
                  window.index.eventMap.mapControl.utilities.sectorsLayerHash.sectorsLayerHash &&
                  window.index.eventMap.mapControl.utilities.sectorsLayerHash.sectorsLayerHash.length > 0 &&
                  window.index.autoReservation &&
                  typeof window.index.autoReservation.initAutoReservation === 'function'
        """, timeout=20000)

        result = page.evaluate("""
            (args) => {
                const { ticketsCount, preference } = args;
                try {
                    const idx = window.index;
                    const ar = idx.autoReservation;
                    const mc = idx.eventMap.mapControl;
                    const res = mc.reservation;

                    // 1. Hook eBilet showQuestion - automatycznie akceptuj pytania (np. rozdzielenie miejsc w rzędzie)
                    if (window.eBilet && window.eBilet.Common && window.eBilet.Common.Utilities) {
                        window.eBilet.Common.Utilities.showQuestion = function(title, msg, yesCb, noCb) {
                            if (typeof yesCb === 'function') yesCb();
                        };
                    }

                    // 2. Przechwytuj błędy z showMessage (np. "Ups! Te bilety zniknęły")
                    window._lastReservationError = null;
                    if (window.eBilet && window.eBilet.Common && window.eBilet.Common.Utilities) {
                        window.eBilet.Common.Utilities.showMessage = function(msg, title) {
                            window._lastReservationError = { title: title || '', message: msg || '' };
                            setTimeout(() => {
                                const closeBtn = document.getElementById('alert-question-window-close');
                                if (closeBtn) closeBtn.click();
                            }, 50);
                        };
                    }

                    // 3. Sortuj sektory wg liczby wolnych miejsc (malejąco), aby wybierać sektory o najwyższej szansie na sukces
                    const hashes = mc.utilities && mc.utilities.sectorsLayerHash ? mc.utilities.sectorsLayerHash.sectorsLayerHash : [];
                    const origGetSectors = res.getSectorsForAutoReservation.bind(res);
                    res.getSectorsForAutoReservation = function(t) {
                        const def = origGetSectors(t);
                        return def.then(function(oList) {
                            if (!oList) return oList;
                            oList.forEach(item => {
                                if (item.sectorsIds && item.sectorsIds.length > 1) {
                                    item.sectorsIds.sort((a, b) => {
                                        const hashA = hashes.find(h => h.sectorId === a);
                                        const hashB = hashes.find(h => h.sectorId === b);
                                        const freeA = hashA && hashA.sectorModel ? (hashA.sectorModel.freeSeatsCount || 0) : 0;
                                        const freeB = hashB && hashB.sectorModel ? (hashB.sectorModel.freeSeatsCount || 0) : 0;
                                        return freeB - freeA;
                                    });
                                }
                            });
                            return oList;
                        });
                    };

                    // 4. Hook autoReservation - pomiń wymóg manualnego klikania sektora na mapie
                    res.autoReservation = function(t) {
                        const self = this;
                        _.each(t, function(e) {
                            _.each(e.ticketTypes, function(e) {
                                const matchTT = _.find(idx.eventView.ticketTypes, function(tt) {
                                    return tt.id === e.ticketTypeId;
                                });
                                if (matchTT) {
                                    e.ticketCounter = matchTT.seatCount;
                                }
                            });
                        });
                        const oProm = this.getSectorsForAutoReservation(t);
                        idx.pageLoadingOverlay(true);
                        $.when(oProm).done(function(o) {
                            idx.pageLoadingOverlay(false);
                            if (!o || o.length === 0) return;
                            self.automaticReservation(o, t);
                        });
                    };

                    // 5. Inicjalizacja auto-rezerwacji
                    ar.step(2);
                    ar.initAutoReservation();

                    let zones = ar.filtredPriceZones();
                    if (!zones || zones.length === 0) {
                        return { ok: false, reason: "Brak aktywnych stref w filtredPriceZones" };
                    }

                    // 4. Odrzucenie stref specjalnych (OzN / niepełnosprawni / opiekun)
                    let regularZones = zones.filter(z => {
                        const name = (z.name || "").toLowerCase();
                        return !name.includes("niepełnosprawn") && !name.includes("ozn") && !name.includes("opiekun");
                    });
                    if (regularZones.length === 0) {
                        regularZones = zones;
                    }

                    // 5. Sortowanie stref wg preferencji cenowych
                    const getZonePrice = (z) => {
                        if (z.ticketTypes && z.ticketTypes.length > 0) return z.ticketTypes[0].price || 0;
                        return z.price || 0;
                    };

                    if (preference === "cheapest") {
                        regularZones.sort((a, b) => getZonePrice(a) - getZonePrice(b));
                    } else if (preference === "expensive") {
                        regularZones.sort((a, b) => getZonePrice(b) - getZonePrice(a));
                    }

                    // 6. Wybór pierwszej pasującej strefy i typu biletu (preferowany bilet 'normalny')
                    for (const zone of regularZones) {
                        if (!zone.ticketTypes || zone.ticketTypes.length === 0) continue;
                        let chosenTT = zone.ticketTypes.find(tt => (tt.name || "").toLowerCase().includes("normalny")) || zone.ticketTypes[0];
                        if (!chosenTT) continue;

                        chosenTT.ticketsQuantity(ticketsCount);
                        ar.optionsChanged();
                        ar.next();

                        return {
                            ok: true,
                            zoneName: zone.name,
                            ticketTypeName: chosenTT.name,
                            price: getZonePrice(zone),
                            ticketsCount: ticketsCount
                        };
                    }

                    return { ok: false, reason: "Brak stref z dostępnymi biletami" };
                } catch (err) {
                    return { ok: false, reason: err.toString() };
                }
            }
        """, {"ticketsCount": tickets_count, "preference": preference})

        return result
    except Exception as e:
        return {"ok": False, "reason": str(e)}

def _fallback_dom_reservation(page: Page):
    """Awaryjny wybór oparty o elementy wizualne DOM/Canvas."""
    try:
        # Sprawdzamy czy mamy do czynienia z mapą Canvas
        map_canvas = page.locator("canvas.leaflet-zoom-animated").first
        is_canvas_map = False
        try:
            map_canvas.wait_for(state="visible", timeout=3000)
            is_canvas_map = True
        except Exception:
            pass
            
        if is_canvas_map:
            box = map_canvas.bounding_box()
            if box:
                target_x = box["width"] / 2
                target_y = box["height"] * 0.75
                logger.info(f"Fallback Canvas: klikam w mapę ({target_x}, {target_y})...")
                map_canvas.click(position={"x": target_x, "y": target_y}, force=True)
                time.sleep(1)
        else:
            pref = config.SECTOR_PREFERENCE.value
            available_zones = page.locator(".items-container .item.row:not(.disabled):not(.noactive)")
            zones_count = available_zones.count()
            
            if zones_count > 0:
                zone_data = []
                for i in range(zones_count):
                    loc = available_zones.nth(i)
                    text = loc.inner_text()
                    match = re.search(r'(\d+)[.,](\d{2})', text)
                    price = float(match.group(1) + '.' + match.group(2)) if match else 0.0
                    zone_data.append({"index": i, "price": price, "locator": loc})
                
                if pref == "cheapest":
                    zone_data.sort(key=lambda x: x["price"])
                elif pref == "expensive":
                    zone_data.sort(key=lambda x: x["price"], reverse=True)
                    
                selected_zone = zone_data[0]
                logger.info(f"Fallback DOM: wybrano strefę z ceną {selected_zone['price']} PLN.")
                selected_zone["locator"].click(force=True)
                time.sleep(1)

        # Próba kliknięcia modala liczby biletów
        add_btn = page.locator("button:has-text('Dodaj do koszyka'):visible")
        try:
            add_btn.first.wait_for(state="visible", timeout=4000)
            ticket_selects = page.locator("select:visible")
            if ticket_selects.count() > 0:
                ticket_selects.first.select_option(str(config.TICKETS_COUNT))
            if add_btn.count() > 0:
                add_btn.first.click(force=True)
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"Błąd procedury awaryjnej DOM: {e}")

def verify_reservation(page: Page, expected_tickets: int = 1) -> bool:
    """Sprawdza, czy bilety zostały zablokowane na serwerze i dodane do koszyka."""
    logger.info("Oczekiwanie na potwierdzenie rezerwacji...")
    start_time = time.time()
    
    while time.time() - start_time < 12:
        try:
            status = page.evaluate("""
                () => {
                    const timerVis = window.index && window.index.timer && typeof window.index.timer.isVisible === 'function' 
                        ? window.index.timer.isVisible() 
                        : (window.index && window.index.timer ? !!window.index.timer.isVisible : false);
                    const basketTickets = window.index && window.index.basketTickets && typeof window.index.basketTickets.tickets === 'function'
                        ? window.index.basketTickets.tickets() 
                        : (window.index && window.index.basketTickets ? window.index.basketTickets.tickets || 0 : 0);
                    const seats = window.index && window.index.basketTickets && window.index.basketTickets.seatsReserved 
                        ? window.index.basketTickets.seatsReserved 
                        : [];

                    const alertEl = document.getElementById('alert-question-window');
                    const isAlertVisible = alertEl ? (alertEl.offsetWidth > 0 && alertEl.offsetHeight > 0) : false;
                    let alertTitle = '';
                    let alertMsg = '';
                    if (isAlertVisible) {
                        const titleEl = document.getElementById('alert-question-window-title');
                        const msgEl = document.getElementById('alert-question-window-message');
                        alertTitle = titleEl ? (titleEl.innerText || titleEl.textContent || '') : '';
                        alertMsg = msgEl ? (msgEl.innerText || msgEl.textContent || '') : '';
                    }

                    const lastErr = window._lastReservationError || null;

                    return { timerVis, basketTickets, seats, isAlertVisible, alertTitle, alertMsg, lastErr };
                }
            """)
            
            # Jeśli serwer zwrócił błąd rezerwacji (np. "Ups! Te bilety zniknęły")
            if status.get("isAlertVisible") or status.get("lastErr"):
                err_data = status.get("lastErr") or {}
                title = status.get("alertTitle") or err_data.get("title", "Błąd")
                msg = status.get("alertMsg") or err_data.get("message", "Bilety niedostępne")
                logger.warning(f"Serwer eBilet odrzucił rezerwację: {title} - {msg}")
                try:
                    page.evaluate("""() => {
                        window._lastReservationError = null;
                        const closeBtn = document.getElementById('alert-question-window-close');
                        if (closeBtn) closeBtn.click();
                        const alertEl = document.getElementById('alert-question-window');
                        if (alertEl) alertEl.style.display = 'none';
                    }""")
                except Exception:
                    pass
                return False

            # Prawdziwy sukces rezerwacji (timer widoczny oraz bilety w koszyku)
            if status.get("timerVis") and (status.get("basketTickets", 0) >= expected_tickets or len(status.get("seats", [])) >= expected_tickets):
                seats_str = ", ".join(status["seats"][:6]) if status["seats"] else "standardowe"
                logger.info("=" * 45)
                logger.info("!!! SUKCES: BILETY SĄ ZAREZERWOWANE !!!")
                logger.info(f"Liczba biletów w koszyku: {max(status['basketTickets'], len(status['seats']), expected_tickets)}")
                logger.info(f"Zablokowane ID miejsc: {seats_str}")
                logger.info("Miejsca są zarezerwowane (masz ok. 10 minut na płatność).")
                logger.info("=" * 45)
                try:
                    for _ in range(3):
                        print('\a', end='', flush=True)
                        time.sleep(0.2)
                except Exception:
                    pass
                return True
        except Exception:
            pass
        time.sleep(0.5)

    logger.warning("Nie udało się zweryfikować rezerwacji (timeout). Sprawdź okno przeglądarki!")
    try:
        os.makedirs("debug", exist_ok=True)
        page.screenshot(path=f"debug/debug_verify_{int(time.time())}.png")
    except Exception:
        pass
    return False

def keep_browser_open(page: Page):
    """Zatrzymuje skrypt, dopóki użytkownik nie zamknie przeglądarki."""
    try:
        while not page.is_closed():
            time.sleep(1)
    except Exception:
        pass