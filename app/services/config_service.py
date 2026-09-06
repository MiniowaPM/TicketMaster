import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "config.json")

class ConfigService:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(CONFIG_PATH):
            return self.get_default_config()
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_config(self, new_config):
        self.config.update(new_config)
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)

    def get_default_config(self):
        return {
            "BASE_URL": "https://www.ebilet.pl/sport/sporty-druzynowe/siatkowka",
            "CHECK_INTERVAL": 5,
            "TICKETS_COUNT": 6,
            "HEADLESS": True,
            "COOKIES_FILE": "app/data/auth.json",
            "HEADERS": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8"
            }
        }

    @property
    def BASE_URL(self): return self.config.get("BASE_URL")
    
    @property
    def CHECK_INTERVAL(self): return self.config.get("CHECK_INTERVAL")
    
    @property
    def TICKETS_COUNT(self): return self.config.get("TICKETS_COUNT")
    
    @property
    def HEADLESS(self): return self.config.get("HEADLESS")
    
    @property
    def COOKIES_FILE(self): 
        path = self.config.get("COOKIES_FILE")
        if path and not os.path.isabs(path):
            return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", path))
        return path
    
    @property
    def HEADERS(self): return self.config.get("HEADERS")

config = ConfigService()
