"""
Logging configuration for the microservice
"""
import logging
import sys
from typing import Optional
from contextlib import contextmanager

# Configure logging format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def setup_logging(level: str = "INFO"):
    """Setup application logging"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)

@contextmanager
def RequestLogger(logger, request_id: str, operation: str):
    """Context manager for request logging"""
    logger.info(f"[{request_id}] Starting {operation}")
    try:
        yield
        logger.info(f"[{request_id}] Completed {operation}")
    except Exception as e:
        logger.error(f"[{request_id}] Failed {operation}: {e}")
        raise
