import os
import shutil
import logging
import datetime
import gzip
import json
import tarfile
import lz4.frame
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enhanced backup configuration
BACKUP_RETENTION_CONFIG = {
    'incremental': {
        'retention_days': 7,
        'max_backups': 10,
        'compression_level': 6
    },
    'full': {
        'retention_days': 30,
        'max_backups': 2,
        'compression_level': 9
    }
}

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects"""
    def default(self, o):
        if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
            return o.isoformat()
        return super().default(o)

def _serialize_data(data):
    """Helper function to serialize data with datetime handling"""
    if isinstance(data, dict):
        return {key: _serialize_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_serialize_data(item) for item in data]
    elif isinstance(data, (datetime.datetime, datetime.date, datetime.time)):
        return data.isoformat()
    return data

class BackupManager:
    def __init__(self, backup_dir="backup_system/backups"):
        self.backup_dir = Path(backup_dir)
        self.app_dir = Path(os.getcwd())
        self.full_backup_dir = self.backup_dir / 'full_backups'
        self.incremental_dir = self.backup_dir / 'incremental'
        self.last_backup_time = None
        self.db_url = os.environ.get('DATABASE_URL')
        self.engine = None

        # Enhanced compression settings
        self.GZIP_COMPRESSION_LEVEL = 9  # Maximum compression
        self.BATCH_SIZE = 1000  # Number of records to process at once
        self.COMPRESS_EXTENSIONS = {
            '.txt', '.py', '.js', '.css', '.html', '.json', '.md',
            '.yml', '.yaml', '.xml', '.csv', '.log', '.conf', '.ini',
            '.sql', '.env', '.properties', '.toml'
        }
        self.LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB

        # Content-based compression settings
        self.CONTENT_COMPRESSION_LEVELS = {
            'text': 9,
            'code': 9,
            'data': 6,
            'binary': 1
        }

        self.EXCLUDE_PATTERNS = {
            '__pycache__',
            '*.pyc',
            'backups',
            '.git',
            'node_modules',
            'venv',
            '*.tar.gz',
            '*.sql',
            '.local',
            '.cache',
            '.pythonlibs',
            '*.dat',
            '*.mo',
            '*.so',
            '*.msgpack',
            '*.zip',
            '*.rar',
            '*.7z',
            '*.bak',
            '*.swp',
            '*.swo',
            '*.tmp',
            '*.temp',
            '*.log.*',
            '__MACOSX',
            'Thumbs.db',
            '.DS_Store'
        }

        self._setup_database()
        self._setup_backup_directory()

    def _determine_compression_level(self, file_path):
        """Determine optimal compression level based on file type and size"""
        file_size = file_path.stat().st_size
        if file_size > self.LARGE_FILE_THRESHOLD:
            return self.CONTENT_COMPRESSION_LEVELS['binary']

        suffix = file_path.suffix.lower()
        if suffix in {'.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.rb', '.php', '.java', '.cs'}:
            return self.CONTENT_COMPRESSION_LEVELS['code']
        elif suffix in {'.txt', '.md', '.csv', '.json', '.xml', '.yaml', '.yml', '.ini', '.conf'}:
            return self.CONTENT_COMPRESSION_LEVELS['text']
        elif suffix in {'.dat', '.db', '.sqlite', '.sql'}:
            return self.CONTENT_COMPRESSION_LEVELS['data']
        else:
            return self.CONTENT_COMPRESSION_LEVELS['binary']

    def _compress_with_lz4(self, source_path, dest_path):
        """Compress a file using LZ4 compression"""
        try:
            with open(source_path, 'rb') as src:
                with lz4.frame.open(dest_path, 'wb', compression_level=6) as dst:
                    while True:
                        chunk = src.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        dst.write(chunk)
            return True
        except Exception as e:
            logger.error(f"LZ4 compression failed for {source_path}: {e}")
            return False

    def _compress_file(self, source_path, dest_path, temp_path=None):
        """Compress a file with proper error handling and atomic operations"""
        try:
            if temp_path is None:
                temp_path = dest_path.parent / f"temp_{dest_path.name}"

            # Ensure parent directories exist
            os.makedirs(dest_path.parent, exist_ok=True)
            os.makedirs(temp_path.parent, exist_ok=True)

            # Use LZ4 for large files
            if source_path.stat().st_size > self.LARGE_FILE_THRESHOLD:
                success = self._compress_with_lz4(source_path, temp_path)
                if not success:
                    raise ValueError(f"Failed to compress {source_path} with LZ4")
            else:
                # Use gzip for smaller files
                compression_level = self._determine_compression_level(source_path)
                with open(source_path, 'rb') as src, \
                     gzip.open(temp_path, 'wb', compresslevel=compression_level) as dst:
                    while True:
                        chunk = src.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        dst.write(chunk)

            # Verify the compressed file
            if not temp_path.exists() or temp_path.stat().st_size == 0:
                raise ValueError(f"Failed to compress {source_path}")

            # Atomic move to final location
            shutil.move(temp_path, dest_path)

            # Log compression metrics
            file_size = source_path.stat().st_size
            compressed_size = dest_path.stat().st_size
            compression_ratio = ((file_size - compressed_size) / file_size) * 100
            logger.info(f"Compressed {source_path.name}: {compression_ratio:.1f}% reduction")

            return True

        except Exception as e:
            logger.error(f"Compression failed for {source_path}: {e}")
            if temp_path and temp_path.exists():
                temp_path.unlink()
            return False

    def _should_compress(self, file_path):
        """Determine if a file should be compressed based on extension and content"""
        if file_path.suffix.lower() in self.COMPRESS_EXTENSIONS:
            return True

        # Check first few bytes for text content
        try:
            with open(file_path, 'rb') as f:
                is_text = True
                for chunk in [f.read(1024) for _ in range(2)]:
                    if b'\x00' in chunk:
                        is_text = False
                        break
                return is_text
        except Exception:
            return False

    def _copy_with_compression(self, source_path, dest_dir, relative_path=None):
        """Copy a file with optional compression and atomic operations"""
        if relative_path is None:
            relative_path = source_path.relative_to(self.app_dir)

        dest_path = dest_dir / relative_path
        temp_path = dest_dir / f"temp_{relative_path}"

        try:
            # Ensure parent directories exist
            os.makedirs(dest_path.parent, exist_ok=True)

            if self._should_compress(source_path):
                success = self._compress_file(source_path, dest_path.with_suffix(dest_path.suffix + '.gz'), temp_path)
                if not success:
                    raise ValueError(f"Failed to compress {source_path}")
            else:
                # Copy binary files directly with atomic operation
                shutil.copy2(source_path, temp_path)
                shutil.move(temp_path, dest_path)

            return True

        except Exception as e:
            logger.error(f"Failed to copy {source_path}: {e}")
            if temp_path.exists():
                temp_path.unlink()
            return False

    def _setup_backup_directory(self):
        """Create backup directory structure with proper permissions"""
        try:
            # Create main backup directories
            os.makedirs(self.backup_dir, exist_ok=True)
            os.makedirs(self.full_backup_dir, exist_ok=True)
            os.makedirs(self.incremental_dir, exist_ok=True)

            # Ensure proper permissions
            for directory in [self.backup_dir, self.full_backup_dir, self.incremental_dir]:
                os.chmod(directory, 0o755)

            logger.info(f"Backup directories created and secured: {self.backup_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to create backup directories: {e}")
            return False

    def _test_database_connection(self):
        """Test database connection"""
        if not self.engine:
            logger.error("No database engine configured")
            return False

        try:
            with self._get_connection() as connection:
                connection.execute(text('SELECT 1'))
                connection.commit()
                logger.info("Database connection test successful")
                return True
        except SQLAlchemyError as e:
            logger.error(f"Database connection test failed: {str(e)}")
            return False

    def create_code_backup(self, backup_dir: Path, timestamp: str) -> Optional[Path]:
        """Create compressed backup of code files with improved error handling"""
        code_backup = backup_dir / 'code_backup.tar.gz'
        temp_code_backup = backup_dir / f'temp_code_backup_{timestamp}.tar.gz'

        logger.info("Creating code backup...")
        try:
            # Ensure backup directory exists
            backup_dir.mkdir(parents=True, exist_ok=True)

            logger.debug(f"Creating temporary backup at: {temp_code_backup}")

            # Create tar archive with compression
            with tarfile.open(str(temp_code_backup), 'w:gz', compresslevel=6) as tar:
                for root, dirs, files in os.walk(str(self.app_dir)):
                    # Filter directories
                    dirs[:] = [d for d in dirs if not any(pattern in d for pattern in self.EXCLUDE_PATTERNS)]

                    for file in files:
                        # Skip excluded files
                        if any(pattern.endswith(file) if '*' in pattern else pattern == file
                               for pattern in self.EXCLUDE_PATTERNS):
                            continue

                        try:
                            file_path = Path(root) / file
                            relative_path = file_path.relative_to(self.app_dir)

                            if file_path.exists() and os.access(file_path, os.R_OK):
                                tar.add(str(file_path), arcname=str(relative_path))
                                logger.debug(f"Added to backup: {relative_path}")
                        except Exception as e:
                            logger.warning(f"Failed to backup file {file}: {e}")
                            continue

            # Verify the archive was created and is not empty
            if not temp_code_backup.exists():
                raise ValueError(f"Failed to create temporary backup at {temp_code_backup}")

            if temp_code_backup.stat().st_size == 0:
                raise ValueError("Created backup file is empty")

            # Verify the archive can be read
            try:
                with tarfile.open(str(temp_code_backup), 'r:gz') as tar:
                    names = tar.getnames()
                    if not names:
                        raise ValueError("No files in backup archive")
            except Exception as e:
                raise ValueError(f"Invalid backup archive: {e}")

            # Atomic move to final location
            if code_backup.exists():
                code_backup.unlink()
            shutil.move(str(temp_code_backup), str(code_backup))

            # Log backup metrics
            backup_size = code_backup.stat().st_size
            logger.info(f"Code backup created successfully: {backup_size / (1024*1024):.2f} MB")
            return code_backup

        except Exception as e:
            logger.error(f"Failed to create code backup: {e}")
            if temp_code_backup and temp_code_backup.exists():
                temp_code_backup.unlink()
            return None

    def _backup_database(self, backup_dir: Path, timestamp: str) -> Optional[Path]:
        """Create a compressed backup of the database with proper datetime handling"""
        if not self.db_url or not self._test_database_connection():
            return None

        temp_backup_file = None
        try:
            # Create database backup directory
            db_backup_dir = backup_dir / 'database'
            db_backup_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created database backup directory: {db_backup_dir}")

            db_backup_file = db_backup_dir / 'database_backup.json.gz'
            temp_backup_file = db_backup_dir / f'temp_backup_{timestamp}.json.gz'

            backup_data = {}
            inspector = inspect(self.engine)
            total_tables = len(inspector.get_table_names())
            tables_processed = 0

            with self._get_connection() as connection:
                for table_name in inspector.get_table_names():
                    tables_processed += 1
                    logger.info(f"Backing up table: {table_name} ({tables_processed}/{total_tables})")

                    columns = inspector.get_columns(table_name)
                    result = connection.execute(text(f'SELECT COUNT(*) FROM {table_name}'))
                    total_rows = result.scalar()

                    backup_data[table_name] = {
                        'schema': {col['name']: str(col['type']) for col in columns},
                        'data': []
                    }

                    # Process data in batches with proper serialization
                    offset = 0
                    while offset < total_rows:
                        batch_query = text(f'SELECT * FROM {table_name} LIMIT :limit OFFSET :offset')
                        result = connection.execute(batch_query, {'limit': self.BATCH_SIZE, 'offset': offset})

                        # Serialize each row with datetime handling
                        batch_data = []
                        for row in result:
                            row_dict = dict(row._mapping)
                            serialized_row = _serialize_data(row_dict)
                            batch_data.append(serialized_row)

                        backup_data[table_name]['data'].extend(batch_data)
                        offset += self.BATCH_SIZE
                        if total_rows > 0:
                            progress = min(offset, total_rows) / total_rows * 100
                            logger.info(f"Table {table_name}: {progress:.1f}% complete ({min(offset, total_rows)}/{total_rows} rows)")

            # Write to temporary file with compression
            logger.info("Compressing database backup...")
            try:
                temp_backup_file.parent.mkdir(parents=True, exist_ok=True)

                with gzip.open(temp_backup_file, 'wt', encoding='utf-8', compresslevel=self.GZIP_COMPRESSION_LEVEL) as f:
                    json.dump(backup_data, f, cls=DateTimeEncoder, indent=2)

                # Verify temp backup file
                if not temp_backup_file.exists() or temp_backup_file.stat().st_size == 0:
                    raise ValueError("Failed to create database backup file")

                # Verify backup data can be read
                with gzip.open(temp_backup_file, 'rt', encoding='utf-8') as f:
                    verify_data = json.load(f)
                    if not isinstance(verify_data, dict) or not verify_data:
                        raise ValueError("Invalid backup data format")

                # Atomic move to final location
                if db_backup_file.exists():
                    db_backup_file.unlink()
                temp_backup_file.replace(db_backup_file)

                # Log compression metrics
                original_size = len(json.dumps(backup_data, cls=DateTimeEncoder).encode('utf-8'))
                compressed_size = db_backup_file.stat().st_size
                compression_ratio = (1 - compressed_size / original_size) * 100
                logger.info(f"Database backup compressed: {compression_ratio:.1f}% reduction")
                logger.info(f"Final backup size: {compressed_size / (1024*1024):.2f} MB")
                logger.info(f"Total tables backed up: {total_tables}")

                return db_backup_file

            except Exception as e:
                logger.error(f"Failed to write database backup: {e}")
                if temp_backup_file and temp_backup_file.exists():
                    temp_backup_file.unlink()
                raise

        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            if temp_backup_file and temp_backup_file.exists():
                temp_backup_file.unlink()
            return None

    def create_full_backup(self):
        """Create a complete backup with improved error handling and verification"""
        backup_dir = None
        temp_dir = None
        try:
            # Setup checks
            if not self._setup_backup_directory():
                raise ValueError("Failed to setup backup directories")

            if not self._setup_database():
                raise ValueError("Failed to setup database connection")

            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = self.full_backup_dir / timestamp

            # Create temporary directory with proper cleanup
            temp_dir = self._setup_temp_directory(self.full_backup_dir, timestamp)

            # Create database backup
            db_backup = self._backup_database(temp_dir, timestamp)
            if not db_backup:
                raise ValueError("Database backup failed")

            # Create code backup
            code_backup = self.create_code_backup(temp_dir, timestamp)
            if not code_backup:
                raise ValueError("Code backup failed")

            # Verify backup integrity in temporary directory
            if not self._verify_backup_integrity(temp_dir):
                raise ValueError("Backup verification failed")

            # If verification passed, move temp directory to final location atomically
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            temp_dir.replace(backup_dir)

            # Cleanup and update timestamp
            self._cleanup_old_backups()
            self.last_backup_time = datetime.datetime.now()

            # Log backup completion
            total_size = sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file())
            logger.info(f"Full backup completed successfully at: {backup_dir}")
            logger.info(f"Total backup size: {total_size / (1024*1024):.2f} MB")

            return backup_dir

        except Exception as e:
            logger.error(f"Full backup failed: {str(e)}")
            # Cleanup temporary directory if it exists
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup temporary directory: {cleanup_error}")
            # Cleanup failed backup directory if it exists
            if backup_dir and backup_dir.exists():
                try:
                    shutil.rmtree(backup_dir)
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup backup directory: {cleanup_error}")
            return None

    def create_incremental_backup(self):
        """Create an incremental backup with improved error handling"""
        backup_dir = None
        try:
            if not self.last_backup_time:
                logger.warning("No previous backup found, creating full backup instead")
                return self.create_full_backup()

            if not self._setup_backup_directory():
                raise ValueError("Failed to setup backup directories")

            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = self.incremental_dir / timestamp
            temp_dir = self.incremental_dir / f"temp_{timestamp}"

            # Create temporary directory first
            temp_dir.mkdir(parents=True, exist_ok=True)

            changes = {'modified': [], 'added': [], 'deleted': []}

            # Track changed files since last backup
            for root, _, files in os.walk(self.app_dir):
                rel_path = Path(root).relative_to(self.app_dir)

                # Skip excluded directories
                if any(part in self.EXCLUDE_PATTERNS for part in rel_path.parts):
                    continue

                for file in files:
                    if any(file.endswith(ext) for ext in ['.pyc', '.tar.gz', '.sql']):
                        continue

                    file_path = Path(root) / file
                    if file_path.stat().st_mtime > self.last_backup_time.timestamp():
                        rel_file_path = file_path.relative_to(self.app_dir)
                        changes['modified'].append(str(rel_file_path))

                        backup_file_dir = temp_dir / rel_file_path.parent
                        backup_file_dir.mkdir(parents=True, exist_ok=True)

                        if not self._copy_with_compression(file_path, temp_dir, rel_file_path):
                            raise ValueError(f"Failed to backup file {rel_file_path}")

            if not any(changes.values()):
                logger.info("No changes detected")
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                return None

            # Create manifest with improved error handling
            manifest = {
                'timestamp': timestamp,
                'base_backup': str(self.last_backup_time),
                'changes': changes
            }

            manifest_file = temp_dir / 'backup_manifest.json.gz'

            try:
                with gzip.open(manifest_file, 'wt', encoding='utf-8', compresslevel=self.GZIP_COMPRESSION_LEVEL) as f:
                    json.dump(manifest, f, indent=2)

                # Verify manifest before finalizing
                with gzip.open(manifest_file, 'rt', encoding='utf-8') as f:
                    test_manifest = json.load(f)
                    if not all(key in test_manifest for key in ['timestamp', 'base_backup', 'changes']):
                        raise ValueError("Invalid manifest format")

                # Move entire temporary directory atomically
                shutil.move(str(temp_dir), str(backup_dir))

                logger.info(f"Incremental backup completed at: {backup_dir}")
                return backup_dir

            except Exception as e:
                logger.error(f"Failed to create manifest: {e}")
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                raise

        except Exception as e:
            logger.error(f"Incremental backup failed: {str(e)}")
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir)
            if backup_dir and backup_dir.exists():
                shutil.rmtree(backup_dir)
            return None

    def _verify_backup_integrity(self, backup_dir):
        """Verify the integrity of a backup with improved error handling"""
        try:
            if not isinstance(backup_dir, Path):
                backup_dir = Path(backup_dir)

            if not backup_dir.exists():
                logger.error(f"Backup directory does not exist: {backup_dir}")
                return False

            # First verify database backup
            db_backup = backup_dir / 'database' / 'database_backup.json.gz'
            if not db_backup.exists() or db_backup.stat().st_size == 0:
                logger.error(f"Invalid database backup file: {db_backup}")
                return False

            try:
                with gzip.open(db_backup, 'rt', encoding='utf-8') as f:
                    backup_data = json.load(f)
                    if not isinstance(backup_data, dict) or not backup_data:
                        logger.error("Invalid database backup format")
                        return False
                    logger.info(f"Database backup verified: {len(backup_data)} tables")
            except Exception as e:
                logger.error(f"Failed to verify database backup: {e}")
                return False

            # Then verify code backup
            code_backup = backup_dir / 'code_backup.tar.gz'
            if not code_backup.exists() or code_backup.stat().st_size == 0:
                logger.error(f"Invalid code backup file: {code_backup}")
                return False

            try:
                with tarfile.open(code_backup, 'r:gz') as tar:
                    member_names = tar.getnames()
                    if not member_names:
                        logger.error("Empty code backup archive")
                        return False

                    # Calculate compression metrics
                    total_size = sum(m.size for m in tar.getmembers())
                    compressed_size = code_backup.stat().st_size
                    compression_ratio = ((total_size - compressed_size) / total_size) * 100
                    logger.info(f"Code backup compression ratio: {compression_ratio:.1f}%")
                    logger.info(f"Files in backup: {len(member_names)}")

            except Exception as e:
                logger.error(f"Failed to verify code backup: {e}")
                return False

            # Calculate total backup size
            total_backup_size = sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file())
            logger.info(f"Total backup size: {total_backup_size / (1024*1024):.2f} MB")
            logger.info("Backup integrity verification completed successfully")
            return True

        except Exception as e:
            logger.error(f"Backup verification failed: {str(e)}")
            return False

    def _cleanup_old_backups(self):
        """Enhanced cleanup with retention policy"""
        try:
            # Clean full backups
            full_config = BACKUP_RETENTION_CONFIG['full']
            self._cleanup_backup_type(self.full_backup_dir, full_config)

            # Clean incremental backups
            incr_config = BACKUP_RETENTION_CONFIG['incremental']
            self._cleanup_backup_type(self.incremental_dir, incr_config)

            logger.info("Backup cleanup completed successfully")

        except Exception as e:
            logger.error(f"Backup cleanup failed: {str(e)}")

    def _cleanup_backup_type(self, backup_dir: Path, config: dict):
        """Clean up specific backup type according to retention policy"""
        try:
            if not backup_dir.exists():
                return

            # Get all backup directories sorted by creation time (newest first)
            backups = sorted(
                [d for d in backup_dir.iterdir() if d.is_dir()],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            # First, enforce max_backups limit
            if len(backups) > config['max_backups']:
                excess_backups = backups[config['max_backups']:]
                for backup in excess_backups:
                    try:
                        if backup.exists():
                            shutil.rmtree(backup)
                            logger.info(f"Removed excess backup to meet max_backups limit: {backup}")
                    except Exception as e:
                        logger.error(f"Failed to remove excess backup {backup}: {e}")

            # Then, apply retention days policy to remaining backups
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=config['retention_days'])

            # Get updated list after removing excess backups
            remaining_backups = sorted(
                [d for d in backup_dir.iterdir() if d.is_dir()],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            for backup in remaining_backups:
                if datetime.datetime.fromtimestamp(backup.stat().st_mtime) < cutoff_date:
                    try:
                        if backup.exists():
                            shutil.rmtree(backup)
                            logger.info(f"Removed old backup exceeding retention period: {backup}")
                    except Exception as e:
                        logger.error(f"Failed to remove old backup {backup}: {e}")

            # Log final backup count
            final_backups = [d for d in backup_dir.iterdir() if d.is_dir()]
            logger.info(f"Backup cleanup completed. Remaining backups: {len(final_backups)}")

        except Exception as e:
            logger.error(f"Failed to clean up {backup_dir}: {e}")


    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        if not self.engine:
            raise ValueError("Database engine not configured")

        connection = None
        try:
            connection = self.engine.connect()
            yield connection
        finally:
            if connection:
                connection.close()
    def _setup_database(self):
        """Initialize database connection with proper error handling"""
        if not self.db_url:
            logger.error("No DATABASE_URL found in environment variables")
            return False

        try:
            self.engine = create_engine(
                self.db_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=300,
                pool_pre_ping=True
            )
            # Test connection
            if self._test_database_connection():
                logger.info("Database engine initialized successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            self.engine = None
            return False

    def _setup_temp_directory(self, base_dir: Path, timestamp: str) -> Path:
        """Create and setup a temporary directory with proper error handling"""
        attempt = 0
        max_attempts = 3

        while attempt < max_attempts:
            temp_dir = base_dir / f"temp_{timestamp}_{attempt}"
            try:
                # Clean up any existing temp directory
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)

                # Create fresh temporary directory
                temp_dir.mkdir(parents=True)
                logger.info(f"Created temporary directory: {temp_dir}")
                return temp_dir

            except Exception as e:
                logger.error(f"Failed to setup temporary directory (attempt {attempt + 1}/{max_attempts}): {e}")
                attempt += 1
                if attempt == max_attempts:
                    logger.error("Maximum attempts reached for creating temporary directory")
                    raise

        raise ValueError("Failed to create temporary directory after multiple attempts")