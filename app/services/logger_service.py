import logging
import sys

def setup_logger(name: str = "TicketMaster") -> logging.Logger:
    """Konfiguruje domyślny logger dla aplikacji."""
    logger = logging.getLogger(name)
    
    # Uniknij podwójnego dodawania handlerów, jeśli logger jest inicjowany ponownie
    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)
        
        # Konfiguracja formatu logowania
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-7s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Handler do konsoli (w trybie okienkowym PyInstallera sys.stdout może być None)
        if sys.stdout is not None:
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        else:
            logger.addHandler(logging.NullHandler())

        # Handler do pliku logów w data/logs/ticketmaster.log
        try:
            import os
            from logging.handlers import RotatingFileHandler
            log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "logs"))
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "ticketmaster.log")
            file_handler = RotatingFileHandler(log_file, maxBytes=3 * 1024 * 1024, backupCount=3, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            pass
            
    return logger

# Domyślny logger używany w usługach
logger = setup_logger()

def add_gui_handler(log_queue) -> None:
    """Dodaje handler przesyłający logi do kolejki dla GUI."""
    class QueueHandler(logging.Handler):
        def emit(self, record):
            log_queue.put(self.format(record))
            
    queue_handler = QueueHandler()
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-7s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    queue_handler.setFormatter(formatter)
    logger.addHandler(queue_handler)
