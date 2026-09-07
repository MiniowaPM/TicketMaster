# 🎫 TicketMaster (eBilet Sniper)

**Automating the ticket purchasing process. Built to secure your spots at the hottest events.**

![Python](https://img.shields.io/badge/Backend-Python_3.10+-blue)
![Playwright](https://img.shields.io/badge/Automation-Playwright-green)
![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-orange)
![Pydantic](https://img.shields.io/badge/Data-Pydantic-yellow)

## 🚀 About The Project

**TicketMaster** was born out of pure frustration. After months of waiting for the Volleyball World Championship tickets to drop, I found myself staring at a "sold out" screen within seconds, unable to secure a single seat. It became clear that getting tickets to the most anticipated events shouldn't require superhuman reflexes—or competing against swarms of scalper bots manually.

This project levels the playing field. Using advanced web automation (Playwright) combined with anti-bot evasion techniques (Stealth Mode), the application continuously monitors target events and autonomously navigates the reservation and checkout processes the exact millisecond tickets become available.

## ✨ Key Features

### 🖥️ Desktop GUI (MVC Architecture)
* **Modern Interface:** A dark-mode, responsive desktop application built with `customtkinter`.
* **Real-time Console:** Live streaming of application logs directly into the UI.
* **Separation of Concerns:** Strict MVC pattern isolating logic (`services`) from presentation (`views`).

### 🛡️ Smart Authentication
* **Continuous Snapshotting:** Dedicated login script that injects a custom JS interface and automatically snapshots session cookies every second to prevent data loss.
* **Stealth Mode:** Bypasses basic bot detection during OAuth (Google/Facebook) and checkout phases using `playwright-stealth`.

### 🎯 Dynamic Targeting
* **Price Zone Preference:** Tell the bot exactly what to aim for – the cheapest seats, VIP/expensive seats, or an unconditional 'grab anything' approach.
* **Canvas Fallback:** Automatically detects and interacts with modern, complex HTML5 Canvas seat maps when traditional DOM elements are unavailable.

## 🏗️ Architecture & Tech Stack

The project consists of a fully-featured Python desktop application utilizing modern design patterns.

### UI/UX (Frontend)
* **Framework:** CustomTkinter (Python)
* **Threading:** Asynchronous background workers to prevent UI freezing during automation tasks.

### Automation Engine (Backend)
* **Framework:** Playwright (Sync API)
* **Data Validation:** Pydantic models ensure strict typing and validation for application configurations (`config.json`).
* **Logging:** Global, thread-safe logger queueing output to the UI.

## 📥 Installation

### Prerequisites
* Python 3.10+
* Git

### Setup
```bash
# Clone the repository
git clone https://github.com/twoj-profil/TicketMaster.git
cd TicketMaster

# Create and activate virtual environment (recommended)
python -m venv app/venv
app\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

### Run the App
```bash
# Launch the Graphical Interface (Recommended)
python app/desktop_main.py

# Alternatively, run the classic CLI version
python app/main.py
```

## 📸 Gallery
<img width="902" height="632" alt="image" src="https://github.com/user-attachments/assets/95518243-efa6-49a9-b946-cfba4296b212" />
<img width="902" height="632" alt="image" src="https://github.com/user-attachments/assets/e962a833-8fb6-4bdb-b123-ca26098f8a62" />


## ⚠️ Disclaimer
**For educational purposes only.** This tool was created as a personal programming challenge to learn web automation, stealth techniques, and GUI development in Python. Using automated bots on ticketing platforms may violate their Terms of Service (ToS). The author does not endorse scalping and assumes no liability for blocked accounts, financial losses, or other damages arising from the use of this software.
