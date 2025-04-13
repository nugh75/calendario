"""
Questo file contiene una classe LoggerDebugContainer corretta
da sostituire in file_utils.py
"""

class LoggerDebugContainer:
    def text(self, message): 
        try:
            from log_utils import logger
            logger.debug(message)
        except ImportError:
            pass
            
    def info(self, message): 
        try:
            from log_utils import logger
            logger.info(message)
        except ImportError:
            pass
            
    def success(self, message): 
        try:
            from log_utils import logger
            logger.info(f"SUCCESS: {message}")
        except ImportError:
            pass
            
    def warning(self, message): 
        try:
            from log_utils import logger
            logger.warning(message)
        except ImportError:
            pass
            
    def error(self, message): 
        try:
            from log_utils import logger
            logger.error(message)
        except ImportError:
            pass
            
    def expander(self, title): 
        return self
        
    def __enter__(self): 
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb): 
        pass
