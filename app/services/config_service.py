import json
import os
from enum import Enum
from typing import Dict
from pydantic import BaseModel, field_validator

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "config.json")

class SectorPreference(str, Enum):
    CHEAPEST = "cheapest"
    EXPENSIVE = "expensive"
    ANY = "any"

class AppConfig(BaseModel):
    BASE_URL: str
    CHECK_INTERVAL: int
    TICKETS_COUNT: int
    HEADLESS: bool
    COOKIES_FILE: str
    SECTOR_PREFERENCE: SectorPreference = SectorPreference.CHEAPEST
    HEADERS: Dict[str, str]

    @field_validator("COOKIES_FILE")
    @classmethod
    def make_absolute(cls, v: str) -> str:
        if v and not os.path.isabs(v):
            return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", v))
        return v

def load_config() -> AppConfig:
    if not os.path.exists(CONFIG_PATH):
        # Domyślna konfiguracja jeśli plik nie istnieje
        default_config = AppConfig(
            BASE_URL="https://www.ebilet.pl/sport/sporty-druzynowe/siatkowka",
            CHECK_INTERVAL=5,
            TICKETS_COUNT=6,
            HEADLESS=True,
            COOKIES_FILE="app/data/auth.json",
            SECTOR_PREFERENCE=SectorPreference.CHEAPEST,
            HEADERS={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8"
            }
        )
        save_config(default_config)
        return default_config
        
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        return AppConfig(**data)

def save_config(new_config: AppConfig) -> None:
    global config
    config = new_config
    
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config.model_dump(mode='json'), f, indent=4)

# Zmienna globalna przechowująca załadowaną i zwalidowaną konfigurację
config = load_config()
