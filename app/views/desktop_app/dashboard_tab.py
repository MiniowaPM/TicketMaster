import customtkinter as ctk
import threading
import queue
import time
from services.config_service import config, SectorPreference
from services.monitor_service import get_all_events, run_target_monitor
from services.buyer_service import start_purchase
from services.logger_service import add_gui_handler

class DashboardTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Opcje i Eventy
        self.events = []
        self.event_map = {}
        self.is_running = False
        self.stop_event = threading.Event()
        self.log_queue = queue.Queue()
        
        add_gui_handler(self.log_queue)
        
        # Górny panel (Przyciski)
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.top_frame.grid_columnconfigure(1, weight=1)
        
        self.scan_btn = ctk.CTkButton(self.top_frame, text="Skanuj Wydarzenia", command=self.scan_events)
        self.scan_btn.grid(row=0, column=0, padx=10, pady=10)
        
        self.event_combo = ctk.CTkComboBox(self.top_frame, width=420, values=["Najpierw kliknij Skanuj..."])
        self.event_combo.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        self.start_btn = ctk.CTkButton(self.top_frame, text="START BOT", command=self.toggle_bot, fg_color="green", hover_color="#107c41", state="disabled")
        self.start_btn.grid(row=0, column=2, padx=10, pady=10)
        
        # Konsola logów
        self.log_console = ctk.CTkTextbox(self, state="disabled", fg_color="black", text_color="#00FF00", font=("Consolas", 12))
        self.log_console.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        
        # Pętla czytająca logi z kolejki
        self.update_logs()

    def update_logs(self):
        """Czyta logi z kolejki i dopisuje do okienka."""
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_console.configure(state="normal")
            self.log_console.insert("end", msg + "\n")
            self.log_console.see("end")
            self.log_console.configure(state="disabled")
        # Wywołaj ponownie za 100ms
        self.after(100, self.update_logs)

    def scan_events(self):
        self.scan_btn.configure(state="disabled")
        self.event_combo.set("Skanowanie wydarzeń...")
        threading.Thread(target=self._scan_events_worker, daemon=True).start()

    def _scan_events_worker(self):
        try:
            events = get_all_events()
            self.after(0, lambda: self._on_scan_completed(events, None))
        except Exception as e:
            self.after(0, lambda: self._on_scan_completed([], str(e)))

    def _on_scan_completed(self, events, error_msg):
        self.scan_btn.configure(state="normal")
        if error_msg:
            self.event_combo.configure(values=[f"Błąd: {error_msg}"])
            self.event_combo.set(f"Błąd skanowania")
            return

        if not events:
            self.event_combo.configure(values=["Brak wydarzeń na podanej stronie."])
            self.event_combo.set("Brak wydarzeń.")
            self.start_btn.configure(state="disabled")
            return

        self.events = events
        self.event_map = {}
        labels = []
        for ev in events:
            status_tag = "[DOSTĘPNE]" if ev.is_buyable else "[BRAK]"
            label = f"{status_tag} {ev.date} | {ev.title} (ID: {ev.id})"
            labels.append(label)
            self.event_map[label] = ev

        self.event_combo.configure(values=labels)
        self.event_combo.set(labels[0])
        self.start_btn.configure(state="normal")

    def toggle_bot(self):
        if self.is_running:
            self.stop_bot()
        else:
            self.start_bot()

    def stop_bot(self):
        if self.is_running:
            self.stop_event.set()
            self.start_btn.configure(state="disabled", text="ZATRZYMYWANIE...")

    def start_bot(self):
        if self.is_running:
            return
            
        selected_label = self.event_combo.get()
        selected_event = self.event_map.get(selected_label)
        
        # Fallback jeśli label nie został w mapie (np. ręcznie wpisany lub początkowy)
        if not selected_event and self.events:
            selected_event = self.events[0]
            
        if not selected_event:
            return
            
        self.is_running = True
        self.stop_event.clear()
        
        self.start_btn.configure(state="normal", fg_color="#C0392B", hover_color="#962D22", text="STOP BOT")
        self.scan_btn.configure(state="disabled")
        self.event_combo.configure(state="disabled")
        
        threading.Thread(target=self._bot_worker, args=(selected_event,), daemon=True).start()

    def _bot_worker(self, target_event):
        try:
            success = run_target_monitor(target_event, stop_event=self.stop_event)
            if success and not self.stop_event.is_set():
                start_purchase(target_event.url)
        finally:
            self.after(0, self._on_bot_finished)

    def _on_bot_finished(self):
        self.is_running = False
        self.start_btn.configure(state="normal", fg_color="green", hover_color="#107c41", text="START BOT")
        self.scan_btn.configure(state="normal")
        self.event_combo.configure(state="normal")
