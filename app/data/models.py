from dataclasses import dataclass
from typing import Optional

@dataclass
class Event:
    id: str
    title: str
    date: str
    is_buyable: bool
    status_text: str
    url: str
