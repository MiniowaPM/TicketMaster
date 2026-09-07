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
        
        # Handler do konsoli
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        
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
