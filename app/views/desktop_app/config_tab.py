import customtkinter as ctk
from services.config_service import config, save_config, AppConfig, SectorPreference
from tkinter import messagebox

class ConfigTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        
        self.grid_columnconfigure(1, weight=1)
        
        # URL
        ctk.CTkLabel(self, text="Target URL (DOMYŚLNY):").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.url_entry = ctk.CTkEntry(self, width=400)
        self.url_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.url_entry.insert(0, config.BASE_URL)
        
        # Tickets Count
        ctk.CTkLabel(self, text="Liczba Biletów:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.tickets_entry = ctk.CTkEntry(self, width=100)
        self.tickets_entry.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        self.tickets_entry.insert(0, str(config.TICKETS_COUNT))
        
        # Preference
        ctk.CTkLabel(self, text="Strefa Cenowa:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.pref_var = ctk.StringVar(value=config.SECTOR_PREFERENCE.value)
        self.pref_combo = ctk.CTkComboBox(self, values=["cheapest", "expensive", "any"], variable=self.pref_var)
        self.pref_combo.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        
        # Headless
        self.headless_var = ctk.BooleanVar(value=config.HEADLESS)
        self.headless_check = ctk.CTkCheckBox(self, text="Tryb Headless (Ukryta przeglądarka)", variable=self.headless_var)
        self.headless_check.grid(row=3, column=0, columnspan=2, padx=10, pady=10)
        
        # Account Configuration Button
        self.auth_btn = ctk.CTkButton(self, text="Skonfiguruj Konto (Logowanie)", fg_color="orange", hover_color="#cc6600", command=self.run_auth_script)
        self.auth_btn.grid(row=4, column=0, columnspan=2, pady=(10, 0))
        
        # Save button
        self.save_btn = ctk.CTkButton(self, text="Zapisz Konfigurację", command=self.save_settings)
        self.save_btn.grid(row=5, column=0, columnspan=2, pady=20)

    def run_auth_script(self):
        import threading
        from utils.save_auth import run_save_auth
        self.auth_btn.configure(state="disabled", text="Przeglądarka otwarta...")
        
        def worker():
            run_save_auth()
            self.auth_btn.configure(state="normal", text="Skonfiguruj Konto (Logowanie)")
            
        threading.Thread(target=worker, daemon=True).start()

    def save_settings(self):
        try:
            new_config = AppConfig(
                BASE_URL=self.url_entry.get(),
                CHECK_INTERVAL=config.CHECK_INTERVAL,
                TICKETS_COUNT=int(self.tickets_entry.get()),
                HEADLESS=self.headless_var.get(),
                COOKIES_FILE=config.COOKIES_FILE,
                SECTOR_PREFERENCE=SectorPreference(self.pref_var.get()),
                HEADERS=config.HEADERS
            )
            save_config(new_config)
            messagebox.showinfo("Zapisano", "Konfiguracja zapisana pomyślnie!")
        except Exception as e:
            messagebox.showerror("Błąd Walidacji", str(e))
