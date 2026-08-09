import logging
import os

def setup_logger():
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'agent.log')
    
    # Configure the logger
    logger = logging.getLogger('reel_agent')
    logger.setLevel(logging.INFO)
    
    # Create formatters
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    # Avoid duplicate handlers if setup_logger is called multiple times
    if not logger.handlers:
        # File handler
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
    return logger

# Get the logger instance for importing directly
logger = setup_logger()
