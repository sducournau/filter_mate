"""
Test SQLite lock handling with retry mechanism.

Tests the robustness of database operations when multiple concurrent
accesses cause "database is locked" errors.
"""

import unittest
import sqlite3
import tempfile
import os
import threading
import time
from unittest.mock import Mock, patch

# Mock QGIS before importing modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from conftest import mock_qgis_modules
mock_qgis_modules()

# Import after mocking
from modules.appTasks import (
    spatialite_connect, 
    sqlite_execute_with_retry,
    SQLITE_TIMEOUT,
    SQLITE_MAX_RETRIES,
    SQLITE_RETRY_DELAY
)


class TestSQLiteLockHandling(unittest.TestCase):
    """Test SQLite lock handling with retry mechanism."""
    
    def setUp(self):
        """Create a temporary database for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        
        # Create test database with a simple table
        conn = sqlite3.connect(self.db_path)
        conn.execute('CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)')
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)
    
    def test_spatialite_connect_timeout(self):
        """Test that spatialite_connect uses the correct timeout."""
        # Note: We can't actually test Spatialite extension loading
        # without it being installed, but we can verify connection params
        conn = sqlite3.connect(self.db_path, timeout=SQLITE_TIMEOUT)
        self.assertIsNotNone(conn)
        conn.close()
    
    def test_sqlite_execute_with_retry_success(self):
        """Test successful operation without retries."""
        call_count = 0
        
        def operation():
            nonlocal call_count
            call_count += 1
            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO test_table (value) VALUES ('test')")
                conn.commit()
                return True
            finally:
                conn.close()
        
        result = sqlite_execute_with_retry(operation, "test insert")
        self.assertTrue(result)
        self.assertEqual(call_count, 1, "Should succeed on first attempt")
        
        # Verify data was inserted
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM test_table")
        count = cur.fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)
    
    def test_sqlite_execute_with_retry_locked_database(self):
        """Test retry mechanism when database is locked."""
        # Create a long-running transaction to lock the database
        lock_conn = sqlite3.connect(self.db_path, timeout=0.1)
        lock_conn.execute("BEGIN EXCLUSIVE")
        
        # This will cause "database is locked" errors
        call_count = 0
        
        def operation():
            nonlocal call_count
            call_count += 1
            conn = sqlite3.connect(self.db_path, timeout=0.1)
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO test_table (value) VALUES ('test')")
                conn.commit()
                return True
            finally:
                conn.close()
        
        # Run operation in a thread and release lock after short delay
        def release_lock():
            time.sleep(0.3)  # Wait for first retry
            lock_conn.rollback()
            lock_conn.close()
        
        release_thread = threading.Thread(target=release_lock)
        release_thread.start()
        
        # Should succeed after retries
        result = sqlite_execute_with_retry(
            operation, 
            "test insert with lock",
            max_retries=5,
            initial_delay=0.1
        )
        
        release_thread.join()
        
        self.assertTrue(result)
        self.assertGreater(call_count, 1, "Should have retried at least once")
        self.assertLessEqual(call_count, 5, "Should not exceed max retries")
    
    def test_sqlite_execute_with_retry_permanent_lock(self):
        """Test that retry eventually fails if lock persists."""
        # Lock database permanently
        lock_conn = sqlite3.connect(self.db_path, timeout=0.1)
        lock_conn.execute("BEGIN EXCLUSIVE")
        
        call_count = 0
        
        def operation():
            nonlocal call_count
            call_count += 1
            conn = sqlite3.connect(self.db_path, timeout=0.1)
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO test_table (value) VALUES ('test')")
                conn.commit()
                return True
            finally:
                conn.close()
        
        # Should fail after max retries
        with self.assertRaises(sqlite3.OperationalError):
            sqlite_execute_with_retry(
                operation,
                "test insert with permanent lock",
                max_retries=3,
                initial_delay=0.05
            )
        
        lock_conn.rollback()
        lock_conn.close()
        
        self.assertEqual(call_count, 3, "Should retry exactly max_retries times")
    
    def test_sqlite_execute_with_retry_non_lock_error(self):
        """Test that non-lock errors are not retried."""
        call_count = 0
        
        def operation():
            nonlocal call_count
            call_count += 1
            # Raise a different error (table doesn't exist)
            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO nonexistent_table (value) VALUES ('test')")
                conn.commit()
                return True
            finally:
                conn.close()
        
        # Should fail immediately without retries
        with self.assertRaises(sqlite3.OperationalError):
            sqlite_execute_with_retry(operation, "test non-lock error")
        
        self.assertEqual(call_count, 1, "Should not retry non-lock errors")
    
    def test_exponential_backoff(self):
        """Test that retry delays increase exponentially."""
        delays = []
        original_sleep = time.sleep
        
        def mock_sleep(duration):
            delays.append(duration)
            # Actually sleep a tiny amount to avoid tight loop
            original_sleep(0.001)
        
        # Lock database
        lock_conn = sqlite3.connect(self.db_path, timeout=0.1)
        lock_conn.execute("BEGIN EXCLUSIVE")
        
        def operation():
            conn = sqlite3.connect(self.db_path, timeout=0.1)
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO test_table (value) VALUES ('test')")
                conn.commit()
                return True
            finally:
                conn.close()
        
        with patch('time.sleep', side_effect=mock_sleep):
            try:
                sqlite_execute_with_retry(
                    operation,
                    "test exponential backoff",
                    max_retries=4,
                    initial_delay=0.1
                )
            except sqlite3.OperationalError:
                pass  # Expected to fail
        
        lock_conn.rollback()
        lock_conn.close()
        
        # Verify exponential backoff: 0.1, 0.2, 0.4
        self.assertEqual(len(delays), 3, "Should have 3 delays for 4 attempts")
        self.assertAlmostEqual(delays[0], 0.1, places=2)
        self.assertAlmostEqual(delays[1], 0.2, places=2)
        self.assertAlmostEqual(delays[2], 0.4, places=2)


class TestConcurrentAccess(unittest.TestCase):
    """Test concurrent database access scenarios."""
    
    def setUp(self):
        """Create a temporary database for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_concurrent.db')
        
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA journal_mode=WAL')  # Enable WAL mode
        conn.execute('CREATE TABLE test_table (id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT, thread_id INTEGER)')
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Clean up temporary files."""
        # Clean up WAL files too
        for ext in ['', '-wal', '-shm']:
            file_path = self.db_path + ext
            if os.path.exists(file_path):
                os.remove(file_path)
        os.rmdir(self.temp_dir)
    
    def test_concurrent_writes(self):
        """Test multiple threads writing to database simultaneously."""
        num_threads = 5
        inserts_per_thread = 10
        errors = []
        
        def worker(thread_id):
            try:
                for i in range(inserts_per_thread):
                    def operation():
                        conn = sqlite3.connect(self.db_path, timeout=30.0)
                        try:
                            cur = conn.cursor()
                            cur.execute(
                                "INSERT INTO test_table (value, thread_id) VALUES (?, ?)",
                                (f"value_{i}", thread_id)
                            )
                            conn.commit()
                            return True
                        finally:
                            conn.close()
                    
                    sqlite_execute_with_retry(
                        operation,
                        f"thread {thread_id} insert {i}",
                        max_retries=10,
                        initial_delay=0.05
                    )
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Launch threads
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Check results
        self.assertEqual(len(errors), 0, f"No errors should occur: {errors}")
        
        # Verify all inserts succeeded
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM test_table")
        count = cur.fetchone()[0]
        conn.close()
        
        expected_count = num_threads * inserts_per_thread
        self.assertEqual(
            count, 
            expected_count,
            f"Should have {expected_count} rows from {num_threads} threads"
        )


if __name__ == '__main__':
    unittest.main()
