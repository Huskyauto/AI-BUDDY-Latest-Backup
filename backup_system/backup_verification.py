"""
AI-BUDDY Backup Verification System
Handles verification of backup integrity and structure with enhanced error handling
"""

import logging
import tarfile
from pathlib import Path
from typing import Set, Dict, Any, Optional
from datetime import datetime
import json
import gzip
import os
import shutil

logger = logging.getLogger(__name__)

class BackupVerification:
    """Handles verification of backup integrity with improved error handling"""

    @staticmethod
    def verify_backup_structure(backup_dir: Path) -> bool:
        """Verify the basic structure of a backup directory with enhanced checks"""
        try:
            if not isinstance(backup_dir, Path):
                backup_dir = Path(backup_dir)

            if not backup_dir.exists():
                logger.error(f"Backup directory does not exist: {backup_dir}")
                return False

            # Check required directories and files
            required_dirs = {'database'}
            actual_dirs = {d.name for d in backup_dir.iterdir() if d.is_dir()}
            missing_dirs = required_dirs - actual_dirs

            if missing_dirs:
                logger.error(f"Missing required directories: {missing_dirs}")
                return False

            # Verify database directory is not empty
            db_dir = backup_dir / 'database'
            if not any(db_dir.iterdir()):
                logger.error("Database backup directory is empty")
                return False

            # Verify code backup exists and is readable
            code_backup = backup_dir / 'code_backup.tar.gz'
            if not code_backup.exists():
                logger.error("Code backup file missing")
                return False

            # Verify tar file integrity
            try:
                with tarfile.open(code_backup, 'r:gz') as tar:
                    # Verify tar file is readable
                    tar.getmembers()
            except Exception as e:
                logger.error(f"Code backup file is corrupted: {e}")
                return False

            logger.info(f"Backup structure verified: {backup_dir}")
            return True

        except Exception as e:
            logger.error(f"Backup structure verification failed: {e}")
            return False

    @staticmethod
    def verify_database_backup(backup_dir: Path, required_tables: Optional[Set[str]] = None) -> bool:
        """Verify database backup integrity with enhanced checks"""
        try:
            db_dir = backup_dir / 'database'
            if not db_dir.exists():
                logger.error("Database backup directory missing")
                return False

            # Find latest database backup file
            backup_files = list(db_dir.glob('*.json.gz'))
            if not backup_files:
                logger.error("No database backup files found")
                return False

            latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
            temp_file = None

            try:
                # Create temporary file for verification
                temp_file = latest_backup.parent / f"temp_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

                # Decompress and verify backup data
                with gzip.open(latest_backup, 'rt', encoding='utf-8') as f_in:
                    backup_data = json.load(f_in)

                    # Write to temp file for integrity check
                    with open(temp_file, 'w', encoding='utf-8') as f_out:
                        json.dump(backup_data, f_out)

                if not isinstance(backup_data, dict):
                    logger.error("Database backup is not in correct format")
                    return False

                # Verify essential tables if specified
                if required_tables:
                    missing_tables = required_tables - set(backup_data.keys())
                    if missing_tables:
                        logger.error(f"Missing required tables: {missing_tables}")
                        return False

                # Verify each table's structure and data
                for table_name, table_data in backup_data.items():
                    if not isinstance(table_data, dict):
                        logger.error(f"Invalid structure for table {table_name}")
                        return False

                    if 'schema' not in table_data or 'data' not in table_data:
                        logger.error(f"Missing schema or data for table {table_name}")
                        return False

                    # Verify data structure matches schema
                    for row in table_data['data']:
                        if not all(field in row for field in table_data['schema']):
                            logger.error(f"Data-schema mismatch in table {table_name}")
                            return False

                logger.info(f"Database backup verified: {latest_backup}")
                return True

            finally:
                # Cleanup temporary file
                if temp_file and temp_file.exists():
                    temp_file.unlink()

        except Exception as e:
            logger.error(f"Database backup verification failed: {e}")
            return False

    @staticmethod
    def calculate_backup_metrics(backup_dir: Path) -> Dict[str, Any]:
        """Calculate and return backup metrics"""
        try:
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'total_size': 0,
                'database_size': 0,
                'code_size': 0,
                'compression_ratio': 0,
                'file_count': 0
            }

            # Calculate total backup size
            total_size = sum(f.stat().st_size for f in Path(backup_dir).rglob('*') if f.is_file())
            metrics['total_size'] = round(total_size / (1024 * 1024), 2)  # MB

            # Calculate database backup size
            db_backup = next((backup_dir / 'database').glob('*.json.gz'), None)
            if db_backup:
                metrics['database_size'] = round(db_backup.stat().st_size / (1024 * 1024), 2)  # MB

            # Calculate code backup metrics
            code_backup = backup_dir / 'code_backup.tar.gz'
            if code_backup.exists():
                code_size = code_backup.stat().st_size
                metrics['code_size'] = round(code_size / (1024 * 1024), 2)  # MB

                with tarfile.open(code_backup, 'r:gz') as tar:
                    metrics['file_count'] = len(tar.getmembers())
                    uncompressed_size = sum(m.size for m in tar.getmembers())
                    if uncompressed_size > 0:
                        metrics['compression_ratio'] = round(
                            ((uncompressed_size - code_size) / uncompressed_size) * 100, 2
                        )

            return metrics

        except Exception as e:
            logger.error(f"Failed to calculate backup metrics: {e}")
            return {}

    @classmethod
    def verify_full_backup(cls, backup_dir: Path, required_files: Optional[Set[str]] = None,
                          required_tables: Optional[Set[str]] = None) -> bool:
        """Perform complete backup verification with enhanced checks"""
        try:
            logger.info(f"Starting full backup verification for: {backup_dir}")

            # Create temporary directory for verification
            temp_verify_dir = backup_dir / f"temp_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            temp_verify_dir.mkdir(exist_ok=True)

            try:
                # Verify basic structure
                if not cls.verify_backup_structure(backup_dir):
                    return False

                # Verify database backup
                if not cls.verify_database_backup(backup_dir, required_tables):
                    return False

                # Verify code backup integrity
                code_backup = backup_dir / 'code_backup.tar.gz'
                if code_backup.exists():
                    try:
                        with tarfile.open(code_backup, 'r:gz') as tar:
                            # Extract a sample of files for verification
                            members = tar.getmembers()
                            if not members:
                                logger.error("Empty code backup archive")
                                return False

                            # Verify required files if specified
                            if required_files:
                                found_files = {Path(m.name).name for m in members}
                                missing_files = required_files - found_files
                                if missing_files:
                                    logger.error(f"Missing required files: {missing_files}")
                                    return False

                            # Verify archive contents are readable
                            for member in members:
                                if member.isfile():
                                    try:
                                        tar.extractfile(member)
                                    except Exception as e:
                                        logger.error(f"Failed to read file {member.name}: {e}")
                                        return False

                    except Exception as e:
                        logger.error(f"Failed to verify code backup: {e}")
                        return False

                # Calculate and log metrics
                metrics = cls.calculate_backup_metrics(backup_dir)
                if metrics:
                    logger.info("Backup metrics:")
                    for key, value in metrics.items():
                        logger.info(f"{key}: {value}")

                logger.info("Full backup verification completed successfully")
                return True

            finally:
                # Cleanup temporary verification directory
                if temp_verify_dir.exists():
                    shutil.rmtree(temp_verify_dir)

        except Exception as e:
            logger.error(f"Full backup verification failed: {e}")
            return False

    @classmethod
    def verify_incremental_backup(cls, backup_dir: Path) -> bool:
        """Verify incremental backup integrity with enhanced error handling"""
        try:
            backup_dir = Path(backup_dir)
            if not backup_dir.exists():
                logger.error(f"Incremental backup directory not found: {backup_dir}")
                return False

            # Create temporary directory for verification
            temp_verify_dir = backup_dir / f"temp_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            temp_verify_dir.mkdir(exist_ok=True)

            try:
                # Verify manifest exists and is valid
                manifest_file = backup_dir / 'backup_manifest.json.gz'
                if not manifest_file.exists():
                    logger.error("Backup manifest missing")
                    return False

                try:
                    with gzip.open(manifest_file, 'rt', encoding='utf-8') as f:
                        manifest = json.load(f)
                        required_keys = {'timestamp', 'base_backup', 'changes'}
                        if not all(key in manifest for key in required_keys):
                            logger.error("Invalid manifest structure")
                            return False

                        # Verify each changed file exists and is readable
                        for change_type in ['added', 'modified']:
                            for file_path in manifest['changes'].get(change_type, []):
                                backup_file = backup_dir / file_path
                                if not backup_file.exists():
                                    logger.error(f"Missing backup file: {file_path}")
                                    return False

                                # Verify file is readable
                                try:
                                    with open(backup_file, 'rb') as f:
                                        f.read(1)  # Read first byte to verify readability
                                except Exception as e:
                                    logger.error(f"Failed to read backup file {file_path}: {e}")
                                    return False

                        logger.info("Backup manifest verified successfully")
                        return True

                except Exception as e:
                    logger.error(f"Failed to verify manifest: {e}")
                    return False

            finally:
                # Cleanup temporary verification directory
                if temp_verify_dir.exists():
                    shutil.rmtree(temp_verify_dir)

        except Exception as e:
            logger.error(f"Incremental backup verification failed: {e}")
            return False