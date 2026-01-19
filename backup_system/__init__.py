"""
AI-BUDDY Backup System
Handles database and file backups with integrity verification
"""

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Version info
__version__ = '1.0.0'
