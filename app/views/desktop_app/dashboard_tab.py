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
        self.selected_event = None
        self.is_running = False
        self.log_queue = queue.Queue()
        
        add_gui_handler(self.log_queue)
        
        # Górny panel (Przyciski)
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.scan_btn = ctk.CTkButton(self.top_frame, text="Skanuj Wydarzenia", command=self.scan_events)
        self.scan_btn.pack(side="left", padx=10, pady=10)
        
        self.event_combo = ctk.CTkComboBox(self.top_frame, width=400, values=["Najpierw kliknij Skanuj..."])
        self.event_combo.pack(side="left", padx=10, pady=10)
        
        self.start_btn = ctk.CTkButton(self.top_frame, text="START BOT", command=self.start_bot, fg_color="green", state="disabled")
        self.start_btn.pack(side="right", padx=10, pady=10)
        
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
        self.event_combo.set("Skanowanie...")
        threading.Thread(target=self._scan_events_worker, daemon=True).start()

    def _scan_events_worker(self):
        try:
            self.events = get_all_events()
            if not self.events:
                self.event_combo.configure(values=["Brak wydarzeń."])
                self.event_combo.set("Brak wydarzeń.")
            else:
                event_titles = [ev.title for ev in self.events]
                self.event_combo.configure(values=event_titles)
                self.event_combo.set(event_titles[0])
                self.start_btn.configure(state="normal")
        except Exception as e:
            self.event_combo.set(f"Błąd skanowania")
        finally:
            self.scan_btn.configure(state="normal")

    def start_bot(self):
        if self.is_running:
            return
            
        selected_title = self.event_combo.get()
        self.selected_event = next((ev for ev in self.events if ev.title == selected_title), None)
        
        if not self.selected_event:
            return
            
        self.is_running = True
        self.start_btn.configure(state="disabled", fg_color="gray", text="BOT DZIAŁA...")
        self.scan_btn.configure(state="disabled")
        
        # Odpalenie w tle
        threading.Thread(target=self._bot_worker, daemon=True).start()

    def _bot_worker(self):
        # Etap monitorowania
        success = run_target_monitor(self.selected_event)
        
        if success:
            # Uruchamiamy klasyczny, pojedynczy zakup
            start_purchase(self.selected_event.url)
                
        # Zakończenie
        self.is_running = False
        self.start_btn.configure(state="normal", fg_color="green", text="START BOT")
        self.scan_btn.configure(state="normal")
