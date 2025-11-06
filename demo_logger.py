#!/usr/bin/env python3
"""
Demo script for Indexao logging system.

Run with:
    python demo_logger.py
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from indexao.logger import get_logger, init_logging, set_level

def main():
    """Demonstrate logging features."""
    
    print("=" * 70)
    print("Indexao Logger Demo")
    print("=" * 70)
    print()
    
    # Initialize logging with INFO level
    print("1. Initializing logger (INFO level)...")
    init_logging(
        level='INFO',
        log_dir='../index/logs',
        console=True,
        file=True
    )
    
    logger = get_logger(__name__)
    logger.info("Logger initialized successfully")
    
    # Basic logging
    print("\n2. Basic logging at different levels:")
    logger.trace("This is a TRACE message (won't appear at INFO level)")
    logger.debug("This is a DEBUG message (won't appear at INFO level)")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    logger.critical("This is a CRITICAL message")
    
    # Context enrichment
    print("\n3. Context enrichment:")
    with logger.context(operation="demo", user="phil"):
        logger.info("Inside context block - check JSON logs for context data")
        
        with logger.context(step="nested"):
            logger.info("Nested context - both 'operation' and 'step' in context")
    
    # Performance timing
    print("\n4. Performance timing (fast operation):")
    with logger.timer("fast_operation", slow_threshold_ms=100):
        time.sleep(0.05)  # 50ms - below threshold
        logger.info("Completed fast task")
    
    print("\n5. Performance timing (slow operation):")
    with logger.timer("slow_operation", slow_threshold_ms=50):
        time.sleep(0.1)  # 100ms - exceeds threshold, will trigger WARNING
        logger.info("Completed slow task")
    
    # Change log level
    print("\n6. Changing log level to DEBUG:")
    set_level('DEBUG')
    logger.debug("This DEBUG message now appears!")
    
    # Module-specific logging
    print("\n7. Module-specific logger:")
    scanner_logger = get_logger('indexao.scanner')
    scanner_logger.info("Scanner module logging")
    scanner_logger.debug("Scanner debug info")
    
    # Exception logging
    print("\n8. Exception logging:")
    try:
        raise ValueError("Simulated error for demo")
    except Exception:
        logger.exception("Caught an exception - traceback will be in logs")
    
    # JSON logging demo
    print("\n9. JSON logging demo:")
    logger.info(
        "This message has structured data",
        extra={'custom_field': 'value', 'count': 42}
    )
    
    print("\n" + "=" * 70)
    print("Demo complete!")
    print(f"Check logs in: ../index/logs/")
    print("Files created:")
    print(f"  - indexao_{time.strftime('%Y%m%d')}.log (INFO+)")
    print(f"  - indexao_debug_{time.strftime('%Y%m%d')}.log (TRACE+)")
    print(f"  - indexao_{time.strftime('%Y%m%d')}.json (structured)")
    print("=" * 70)


if __name__ == '__main__':
    main()
