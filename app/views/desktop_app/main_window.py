import customtkinter as ctk
from views.desktop_app.dashboard_tab import DashboardTab
from views.desktop_app.config_tab import ConfigTab

class TicketBotGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("eBilet Sniper Bot")
        self.geometry("900x600")
        
        # Konfiguracja kolorów
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # TabView
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Dodanie zakładek
        self.tabview.add("Dashboard")
        self.tabview.add("Konfiguracja")
        
        # Inicjalizacja zawartości zakładek
        self.dashboard = DashboardTab(self.tabview.tab("Dashboard"))
        self.dashboard.pack(fill="both", expand=True)
        
        self.config = ConfigTab(self.tabview.tab("Konfiguracja"))
        self.config.pack(fill="both", expand=True)
