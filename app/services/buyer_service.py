import time
import json
import re
import os
from services.config_service import config
from playwright.sync_api import sync_playwright, Page
from services.logger_service import logger
from playwright_stealth import Stealth

# Maksymalna liczba prób na jedną strefę cenową, zanim przejdziemy do kolejnej
ATTEMPTS_PER_ZONE = 2
# Czas oczekiwania na odpowiedź serwera po zleceniu rezerwacji (s)
RESERVATION_TIMEOUT = 12.0
# Kody błędów eBilet oznaczające, że miejsca zostały zajęte przez kogoś innego
SEATS_TAKEN_CODES = {79, 62, 21, 17}


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
    target_total = config.TICKETS_COUNT

    # Nasłuch odpowiedzi serwera na rezerwację - najpewniejsze źródło informacji o wyniku
    responses: list = []

    def _on_response(response):
        if "/api/reservation/reserveseats" not in response.url.lower():
            return
        try:
            data = response.json()
        except Exception:
            data = {"t": -1, "err": [{"m": f"HTTP {response.status}", "c": response.status}]}
        if response.status == 429:
            data = {"t": -1, "err": [{"m": "Zbyt wiele zapytań (HTTP 429)", "c": 429}]}
        responses.append(data)

    page.on("response", _on_response)

    logger.info(f"Nawigacja do: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    # Czyszczenie nakładek blokujących UI i automatyczna akceptacja Cookiebot
    _clean_overlays(page)

    try:
        if not _wait_for_engine(page):
            logger.warning("Silnik rezerwacji eBilet nie załadował się. Przechodzę do procedury awaryjnej DOM...")
            return _run_dom_fallback(page, responses, target_total)

        _install_hooks(page)
        _preload_seats(page)

        limits = _get_limits(page)
        if limits["max"] and target_total > limits["max"]:
            logger.warning(f"Wydarzenie pozwala kupić maksymalnie {limits['max']} biletów "
                           f"(ustawiono {target_total}). Ograniczam do {limits['max']}.")
            target_total = limits["max"]

        zones_count = _get_zones_count(page)
        if zones_count == 0:
            logger.warning("Brak dostępnych stref cenowych w silniku. Przechodzę do procedury awaryjnej DOM...")
            return _run_dom_fallback(page, responses, target_total)

        attempt = 0
        basket_full = False
        for zone_index in range(zones_count):
            if basket_full:
                break
            for _ in range(ATTEMPTS_PER_ZONE):
                basket = _get_state(page)["basket"]
                needed = target_total - basket
                if needed <= 0:
                    basket_full = True
                    break

                attempt += 1
                logger.info(f"Próba {attempt}: strefa {zone_index + 1}/{zones_count}, "
                            f"potrzeba {needed} biletów (w koszyku: {basket}/{target_total})...")

                responses.clear()
                engine_result = _reserve_via_ebilet_engine(page, needed, config.SECTOR_PREFERENCE.value, zone_index)
                if not engine_result.get("ok"):
                    logger.warning(f"Silnik nie mógł zlecić rezerwacji: {engine_result.get('reason')}")
                    _reset_after_failure(page)
                    break  # ta strefa nie ma sensu - przejdź do kolejnej

                logger.info(f"Zlecono rezerwację: strefa '{engine_result.get('zoneName')}' "
                            f"({engine_result.get('ticketTypeName')}, {engine_result.get('price')} PLN) x{needed}.")

                result = _wait_for_reservation_result(page, responses, target_total)
                if result["status"] == "ok":
                    _report_success(page, result["basket"], target_total)
                    return True

                if result["status"] == "partial":
                    logger.warning(f"Zarezerwowano częściowo: {result['basket']}/{target_total}. Dobieram resztę...")
                    continue

                logger.warning(f"Próba {attempt} nieudana: {result.get('message')}")
                _reset_after_failure(page)
                page.wait_for_timeout(800)

        final_basket = _get_state(page)["basket"]
        if final_basket >= target_total:
            _report_success(page, final_basket, target_total)
            return True

        if final_basket > 0:
            logger.warning(f"Udało się zarezerwować tylko {final_basket} z {target_total} biletów. "
                           f"Zostawiam je w koszyku - dokończ zakup ręcznie lub dobierz resztę.")
            _report_success(page, final_basket, target_total)
            return True

        logger.warning("Silnik nie zarezerwował biletów. Uruchamiam procedurę awaryjną DOM...")
        return _run_dom_fallback(page, responses, target_total)
    finally:
        # Przywróć oryginalne okna eBilet, żeby użytkownik widział komunikaty przy płatności
        _restore_hooks(page)
        try:
            page.remove_listener("response", _on_response)
        except Exception:
            pass


def _run_dom_fallback(page: Page, responses: list, target_total: int) -> bool:
    """Uruchamia procedurę DOM tylko gdy koszyk jest pusty (żeby nie dublować biletów)."""
    if _get_state(page)["basket"] > 0:
        logger.info("Koszyk nie jest pusty - pomijam procedurę awaryjną DOM.")
        return True
    responses.clear()
    _fallback_dom_reservation(page, target_total)
    result = _wait_for_reservation_result(page, responses, target_total)
    if result["status"] in ("ok", "partial"):
        _report_success(page, result["basket"], target_total)
        return True
    logger.warning(f"Procedura awaryjna nie powiodła się: {result.get('message')}")
    _save_debug_screenshot(page)
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


def _wait_for_engine(page: Page) -> bool:
    """Czeka na załadowanie modelu mapy i sektorów (do 20s)."""
    try:
        page.wait_for_function("""
            () => window.index &&
                  window.index.eventMap &&
                  window.index.eventMap.mapControl &&
                  window.index.eventMap.mapControl.reservation &&
                  window.index.eventMap.mapControl.utilities &&
                  window.index.eventMap.mapControl.utilities.sectorsLayerHash &&
                  window.index.eventMap.mapControl.utilities.sectorsLayerHash.sectorsLayerHash &&
                  window.index.eventMap.mapControl.utilities.sectorsLayerHash.sectorsLayerHash.length > 0 &&
                  window.index.autoReservation &&
                  typeof window.index.autoReservation.initAutoReservation === 'function'
        """, timeout=20000)
        return True
    except Exception:
        return False


def _install_hooks(page: Page):
    """Zakłada hooki na silnik eBilet dokładnie raz i zapamiętuje oryginalne funkcje."""
    page.evaluate("""
        () => {
            if (window.__tmOrig) return;  // hooki już założone
            const idx = window.index;
            const res = idx.eventMap.mapControl.reservation;
            const U = window.eBilet.Common.Utilities;

            window.__tmOrig = {
                showQuestion: U.showQuestion,
                showMessage: U.showMessage,
                getSectors: res.getSectorsForAutoReservation,
                autoReservation: res.autoReservation
            };
            window.__tmLastError = null;

            // Automatycznie akceptuj pytania (np. rozdzielenie miejsc / zmiana sektora)
            U.showQuestion = function(title, msg, yesCb, noCb) {
                if (typeof yesCb === 'function') yesCb();
            };

            // Przechwytuj komunikaty błędów (np. "Ups! Te bilety zniknęły") zamiast pokazywać modal
            U.showMessage = function(msg, title) {
                window.__tmLastError = { title: title || '', message: msg || '' };
            };

            // Sortuj sektory malejąco wg liczby wolnych miejsc
            res.getSectorsForAutoReservation = function(t) {
                return window.__tmOrig.getSectors.call(this, t).then(function(list) {
                    if (!list) return list;
                    const hashes = idx.eventMap.mapControl.utilities.sectorsLayerHash.sectorsLayerHash;
                    const free = (id) => {
                        const h = hashes.find(x => String(x.sectorId) === String(id));
                        return h && h.sectorModel ? (h.sectorModel.freeSeatsCount || 0) : 0;
                    };
                    list.forEach(item => {
                        if (item.sectorsIds && item.sectorsIds.length > 1) {
                            item.sectorsIds.sort((a, b) => free(b) - free(a));
                        }
                    });
                    return list;
                });
            };

            // Pomiń wymóg ręcznego klikania sektora na mapie
            res.autoReservation = function(t) {
                const self = this;
                _.each(t, function(e) {
                    _.each(e.ticketTypes, function(e) {
                        const matchTT = _.find(idx.eventView.ticketTypes, tt => tt.id === e.ticketTypeId);
                        if (matchTT) e.ticketCounter = matchTT.seatCount;
                    });
                });
                idx.pageLoadingOverlay(true);
                $.when(this.getSectorsForAutoReservation(t)).done(function(o) {
                    idx.pageLoadingOverlay(false);
                    if (!o || o.length === 0) {
                        window.__tmLastError = { title: 'Brak miejsc', message: 'Brak sektora z wystarczającą liczbą wolnych miejsc w tej strefie' };
                        return;
                    }
                    self.automaticReservation(o, t);
                }).fail(function() {
                    idx.pageLoadingOverlay(false);
                    window.__tmLastError = { title: 'Błąd', message: 'Nie udało się pobrać sektorów' };
                });
            };
        }
    """)


def _preload_seats(page: Page):
    """Pobiera mapy miejsc sektorów z wolnymi miejscami, żeby pierwsza próba nie trafiała na puste dane."""
    try:
        count = page.evaluate("""
            () => new Promise(resolve => {
                const mc = window.index.eventMap.mapControl;
                const hashes = mc.utilities.sectorsLayerHash.sectorsLayerHash
                    .filter(h => h.sectorModel && h.sectorModel.freeSeatsCount > 0 && !(h.seats && h.seats.downloaded));
                if (hashes.length === 0) return resolve(0);
                const timer = setTimeout(() => resolve(-1), 8000);
                $.when.apply($, hashes.map(h => mc.getSeats(h, false)))
                    .always(() => { clearTimeout(timer); resolve(hashes.length); });
            })
        """)
        if count and count > 0:
            logger.info(f"Pobrano mapy miejsc dla {count} sektorów.")
    except Exception as e:
        logger.warning(f"Nie udało się wstępnie pobrać map miejsc: {e}")


def _restore_hooks(page: Page):
    """Przywraca oryginalne funkcje eBilet (komunikaty i pytania znów widoczne dla użytkownika)."""
    try:
        page.evaluate("""
            () => {
                const o = window.__tmOrig;
                if (!o) return;
                const U = window.eBilet.Common.Utilities;
                const res = window.index.eventMap.mapControl.reservation;
                U.showQuestion = o.showQuestion;
                U.showMessage = o.showMessage;
                res.getSectorsForAutoReservation = o.getSectors;
                res.autoReservation = o.autoReservation;
                delete window.__tmOrig;
                window.__tmLastError = null;
            }
        """)
    except Exception:
        pass


def _get_limits(page: Page) -> dict:
    try:
        return page.evaluate("""
            () => ({ max: (window.index && window.index.eventView && window.index.eventView.maxTicketsOptions) || 0 })
        """)
    except Exception:
        return {"max": 0}


_ZONES_JS = """
    (preference) => {
        const ar = window.index.autoReservation;
        ar.step(2);
        ar.initAutoReservation();
        const zones = ar.filtredPriceZones() || [];
        let regular = zones.filter(z => {
            const n = (z.name || '').toLowerCase();
            return !n.includes('niepełnosprawn') && !n.includes('ozn') && !n.includes('opiekun');
        });
        if (regular.length === 0) regular = zones.slice();
        regular = regular.filter(z => z.ticketTypes && z.ticketTypes.length > 0);

        const pickTT = (z) => z.ticketTypes.find(tt => (tt.name || '').toLowerCase().includes('normalny')) || z.ticketTypes[0];
        const priceOf = (z) => { const tt = pickTT(z); return (tt && tt.price) || z.price || 0; };

        if (preference === 'cheapest') regular.sort((a, b) => priceOf(a) - priceOf(b));
        else if (preference === 'expensive') regular.sort((a, b) => priceOf(b) - priceOf(a));
        return { zones: regular, pickTT, priceOf };
    }
"""


def _get_zones_count(page: Page) -> int:
    try:
        return page.evaluate(f"""
            (preference) => ({_ZONES_JS})(preference).zones.length
        """, config.SECTOR_PREFERENCE.value)
    except Exception:
        return 0


def _reserve_via_ebilet_engine(page: Page, tickets_count: int, preference: str, zone_index: int = 0) -> dict:
    """Zleca rezerwację `tickets_count` miejsc obok siebie w strefie o indeksie `zone_index`."""
    try:
        return page.evaluate(f"""
            (args) => {{
                const {{ ticketsCount, preference, zoneIndex }} = args;
                try {{
                    window.__tmLastError = null;
                    const ar = window.index.autoReservation;
                    const {{ zones, pickTT, priceOf }} = ({_ZONES_JS})(preference);
                    if (zones.length === 0) return {{ ok: false, reason: 'Brak aktywnych stref cenowych' }};
                    if (zoneIndex >= zones.length) return {{ ok: false, reason: 'Brak kolejnych stref' }};

                    // Wyzeruj ilości we wszystkich strefach, żeby nie zamówić biletów z poprzedniej próby
                    zones.forEach(z => z.ticketTypes.forEach(tt => {{
                        if (typeof tt.ticketsQuantity === 'function') tt.ticketsQuantity(0);
                    }}));

                    const zone = zones[zoneIndex];
                    const tt = pickTT(zone);
                    tt.ticketsQuantity(ticketsCount);
                    ar.optionsChanged();
                    ar.next();

                    return {{ ok: true, zoneName: zone.name, ticketTypeName: tt.name, price: priceOf(zone) }};
                }} catch (err) {{
                    return {{ ok: false, reason: err.toString() }};
                }}
            }}
        """, {"ticketsCount": tickets_count, "preference": preference, "zoneIndex": zone_index})
    except Exception as e:
        return {"ok": False, "reason": str(e)}


def _get_state(page: Page) -> dict:
    """Odczytuje stan rezerwacji z obserwabli Knockout eBilet."""
    try:
        return page.evaluate("""
            () => {
                const idx = window.index;
                const bt = idx && idx.basketTickets;
                const timerVis = !!(idx && idx.timer && typeof idx.timer.isVisible === 'function' && idx.timer.isVisible());
                const basket = bt && typeof bt.tickets === 'function' ? (bt.tickets() || 0) : 0;
                const seats = bt && Array.isArray(bt.seatsReserved) ? bt.seatsReserved.map(String) : [];

                const alertEl = document.getElementById('alert-question-window');
                const alertVisible = !!(alertEl && alertEl.offsetWidth > 0 && alertEl.offsetHeight > 0);
                const txt = (id) => { const el = document.getElementById(id); return el ? (el.innerText || el.textContent || '').trim() : ''; };

                return {
                    timerVis,
                    basket: Math.max(basket, seats.length),
                    seats,
                    alertVisible,
                    alertTitle: alertVisible ? txt('alert-question-window-title') : '',
                    alertMsg: alertVisible ? txt('alert-question-window-message') : '',
                    lastErr: window.__tmLastError || null
                };
            }
        """)
    except Exception:
        return {"timerVis": False, "basket": 0, "seats": [], "alertVisible": False,
                "alertTitle": "", "alertMsg": "", "lastErr": None}


def _wait_for_reservation_result(page: Page, responses: list, target_total: int,
                                 timeout: float = RESERVATION_TIMEOUT) -> dict:
    """
    Czeka na wynik rezerwacji. Zwraca dict ze statusem:
    ok / partial / error / timeout oraz aktualną liczbą biletów w koszyku.
    """
    logger.info("Oczekiwanie na potwierdzenie rezerwacji z serwera...")
    start = time.time()
    success_at = None
    state = _get_state(page)

    while time.time() - start < timeout:
        state = _get_state(page)

        # 1. Odpowiedź serwera z błędem
        if responses and responses[-1].get("t") != 0:
            data = responses[-1]
            errs = data.get("err") or []
            code = errs[0].get("c") if errs else None
            msg = errs[0].get("m") if errs else "Nieznany błąd rezerwacji"
            if code in SEATS_TAKEN_CODES:
                msg = f"Miejsca zajęte przez kogoś innego (kod {code}): {msg}"
            elif code is not None:
                msg = f"{msg} (kod {code})"
            _dismiss_alert(page)
            return {"status": "error", "basket": state["basket"], "message": msg}

        # 2. Komunikat błędu z silnika (przed wysłaniem zapytania, np. brak miejsc)
        if state.get("lastErr") or state.get("alertVisible"):
            err = state.get("lastErr") or {}
            title = state.get("alertTitle") or err.get("title") or "Błąd"
            msg = state.get("alertMsg") or err.get("message") or "Bilety niedostępne"
            _dismiss_alert(page)
            return {"status": "error", "basket": state["basket"], "message": f"{title} - {msg}"}

        # 3. Sukces potwierdzony przez timer i koszyk
        if state["timerVis"] and state["basket"] >= target_total:
            return {"status": "ok", "basket": state["basket"]}

        # 4. Serwer potwierdził (t=0), ale koszyk niepełny - daj chwilę na odświeżenie koszyka
        if responses and responses[-1].get("t") == 0:
            success_at = success_at or time.time()
            if time.time() - success_at > 4:
                return {"status": "partial" if state["basket"] > 0 else "error",
                        "basket": state["basket"],
                        "message": "Serwer potwierdził rezerwację, ale koszyk jest pusty"}

        # wait_for_timeout (a nie time.sleep) - pozwala Playwright obsłużyć zdarzenia 'response'
        page.wait_for_timeout(300)

    if state["timerVis"] and state["basket"] > 0:
        return {"status": "partial", "basket": state["basket"]}
    return {"status": "timeout", "basket": state["basket"],
            "message": "Brak odpowiedzi serwera w wyznaczonym czasie"}


def _dismiss_alert(page: Page):
    try:
        page.evaluate("""
            () => {
                window.__tmLastError = null;
                const closeBtn = document.getElementById('alert-question-window-close');
                if (closeBtn && closeBtn.offsetWidth > 0) closeBtn.click();
                const alertEl = document.getElementById('alert-question-window');
                if (alertEl) alertEl.style.display = 'none';
            }
        """)
    except Exception:
        pass


def _reset_after_failure(page: Page):
    """Czyści stan silnika po nieudanej próbie, zachowując już zarezerwowane miejsca."""
    try:
        page.evaluate("""
            () => {
                try {
                    const idx = window.index;
                    const mc = idx.eventMap.mapControl;
                    const bt = idx.basketTickets;
                    const reserved = new Set((bt.seatsReserved || []).map(String));

                    // Usuń z "wybranych" miejsca, których serwer nie zarezerwował
                    if (Array.isArray(bt.seatsChosen)) {
                        for (let i = bt.seatsChosen.length - 1; i >= 0; i--) {
                            if (!reserved.has(String(bt.seatsChosen[i]))) bt.seatsChosen.splice(i, 1);
                        }
                    }
                    if (idx.autoReservation && typeof idx.autoReservation.pending === 'function') idx.autoReservation.pending(false);
                    if (typeof mc.setAutoReserveSelectSectorMode === 'function') mc.setAutoReserveSelectSectorMode(false);
                    if (mc.utilities) mc.utilities.reservationInProgress = false;
                    if (typeof idx.pageLoadingOverlay === 'function') idx.pageLoadingOverlay(false);
                    if (window.NProgress) window.NProgress.done();
                } catch (e) {}
                window.__tmLastError = null;
            }
        """)
    except Exception:
        pass
    _dismiss_alert(page)


def _report_success(page: Page, basket: int, target_total: int):
    seats = _get_state(page).get("seats", [])
    seats_str = ", ".join(seats[:10]) if seats else "standardowe"
    logger.info("=" * 45)
    if basket >= target_total:
        logger.info("!!! SUKCES: BILETY SĄ ZAREZERWOWANE !!!")
    else:
        logger.info(f"!!! CZĘŚCIOWY SUKCES: {basket}/{target_total} BILETÓW !!!")
    logger.info(f"Liczba biletów w koszyku: {basket}")
    logger.info(f"Zablokowane ID miejsc: {seats_str}")
    logger.info("Miejsca są zarezerwowane (masz ok. 10 minut na płatność).")
    logger.info("=" * 45)
    try:
        for _ in range(3):
            print('\a', end='', flush=True)
            time.sleep(0.2)
    except Exception:
        pass
    # Przejście do kolejnego kroku (Kup bilet / Dane kontaktowe)
    try:
        page.evaluate("() => { if (window.index && window.index.bottomButton && window.index.bottomButton.click) window.index.bottomButton.click(); }")
    except Exception:
        pass


def _save_debug_screenshot(page: Page):
    try:
        os.makedirs("debug", exist_ok=True)
        page.screenshot(path=f"debug/debug_verify_{int(time.time())}.png")
    except Exception:
        pass


def _fallback_dom_reservation(page: Page, tickets_count: int):
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
                ticket_selects.first.select_option(str(tickets_count))
            if add_btn.count() > 0:
                add_btn.first.click(force=True)
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"Błąd procedury awaryjnej DOM: {e}")


def verify_reservation(page: Page, expected_tickets: int = 1) -> bool:
    """Sprawdza (bez nasłuchu sieci), czy bilety zostały zablokowane na serwerze i dodane do koszyka."""
    result = _wait_for_reservation_result(page, [], expected_tickets)
    if result["status"] == "ok":
        _report_success(page, result["basket"], expected_tickets)
        return True
    logger.warning(f"Nie udało się zweryfikować rezerwacji: {result.get('message')}")
    _save_debug_screenshot(page)
    return False


def keep_browser_open(page: Page):
    """Zatrzymuje skrypt, dopóki użytkownik nie zamknie przeglądarki."""
    try:
        while not page.is_closed():
            time.sleep(1)
    except Exception:
        pass