import sys
import os

os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'

# Ensure the app folder is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from views.desktop_app.main_window import TicketBotGUI

def main():
    app = TicketBotGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
