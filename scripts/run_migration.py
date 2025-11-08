#!/usr/bin/env python3
"""
Database Migration Runner for P(Doom)1 Production Database

This script runs SQL migration files against the PostgreSQL database.
It's designed to work with Railway and other hosted PostgreSQL providers.

Usage:
    python scripts/run_migration.py                          # Run all pending migrations
    python scripts/run_migration.py --file 001_initial_schema.sql  # Run specific migration
    python scripts/run_migration.py --check                  # Check which migrations need to run
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("ERROR: psycopg2 is required. Install with: pip install psycopg2-binary")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("WARNING: python-dotenv not installed. Using system environment variables.")


# Migration tracking table
MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT
);
"""


class MigrationRunner:
    """Manages database schema migrations."""

    def __init__(self, database_url: str):
        """Initialize migration runner."""
        self.database_url = database_url
        self.conn = None
        self.migrations_dir = Path(__file__).parent / "db_migrations"

    def connect(self):
        """Connect to the database."""
        try:
            self.conn = psycopg2.connect(self.database_url)
            self.conn.autocommit = False
            print(f"✅ Connected to database")
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            sys.exit(1)

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            print("✅ Disconnected from database")

    def ensure_migrations_table(self):
        """Create migrations tracking table if it doesn't exist."""
        try:
            cur = self.conn.cursor()
            cur.execute(MIGRATIONS_TABLE)
            self.conn.commit()
            print("✅ Migrations table ready")
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Failed to create migrations table: {e}")
            sys.exit(1)

    def get_applied_migrations(self):
        """Get list of already-applied migrations."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT migration_name FROM schema_migrations WHERE success = TRUE")
            applied = [row[0] for row in cur.fetchall()]
            return set(applied)
        except Exception as e:
            print(f"⚠️  Could not read applied migrations: {e}")
            return set()

    def get_pending_migrations(self):
        """Get list of migrations that haven't been applied yet."""
        if not self.migrations_dir.exists():
            print(f"❌ Migrations directory not found: {self.migrations_dir}")
            return []

        all_migrations = sorted([
            f.name for f in self.migrations_dir.glob("*.sql")
        ])

        applied = self.get_applied_migrations()
        pending = [m for m in all_migrations if m not in applied]

        return pending

    def record_migration(self, migration_name: str, success: bool, error_message: str = None):
        """Record a migration attempt in the database."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO schema_migrations (migration_name, success, error_message)
                VALUES (%s, %s, %s)
                ON CONFLICT (migration_name) DO UPDATE
                SET applied_at = NOW(), success = %s, error_message = %s
                """,
                (migration_name, success, error_message, success, error_message)
            )
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"⚠️  Failed to record migration: {e}")

    def run_migration(self, migration_file: str):
        """Run a single migration file."""
        migration_path = self.migrations_dir / migration_file

        if not migration_path.exists():
            print(f"❌ Migration file not found: {migration_path}")
            return False

        print(f"\n{'='*60}")
        print(f"Running migration: {migration_file}")
        print(f"{'='*60}")

        try:
            # Read migration SQL
            with open(migration_path, 'r', encoding='utf-8') as f:
                migration_sql = f.read()

            # Execute migration
            cur = self.conn.cursor()
            cur.execute(migration_sql)
            self.conn.commit()

            # Record success
            self.record_migration(migration_file, True)

            print(f"✅ Migration completed successfully: {migration_file}")
            return True

        except Exception as e:
            self.conn.rollback()
            error_msg = str(e)

            print(f"❌ Migration failed: {migration_file}")
            print(f"   Error: {error_msg}")

            # Record failure
            self.record_migration(migration_file, False, error_msg)

            return False

    def run_all_pending(self):
        """Run all pending migrations in order."""
        pending = self.get_pending_migrations()

        if not pending:
            print("✅ No pending migrations. Database is up to date.")
            return True

        print(f"\n📋 Found {len(pending)} pending migration(s):")
        for migration in pending:
            print(f"   - {migration}")

        print("\n🚀 Starting migrations...")

        all_success = True
        for migration in pending:
            success = self.run_migration(migration)
            if not success:
                all_success = False
                print(f"\n⚠️  Stopping due to failed migration: {migration}")
                break

        if all_success:
            print(f"\n✅ All migrations completed successfully!")
        else:
            print(f"\n❌ Migration process failed. Some migrations may not have been applied.")

        return all_success

    def check_status(self):
        """Check and display migration status."""
        applied = self.get_applied_migrations()
        pending = self.get_pending_migrations()
        all_migrations = sorted([
            f.name for f in self.migrations_dir.glob("*.sql")
        ])

        print(f"\n{'='*60}")
        print("DATABASE MIGRATION STATUS")
        print(f"{'='*60}")
        print(f"Database: {self.database_url.split('@')[1] if '@' in self.database_url else 'localhost'}")
        print(f"Total migrations: {len(all_migrations)}")
        print(f"Applied: {len(applied)}")
        print(f"Pending: {len(pending)}")
        print(f"{'='*60}")

        if applied:
            print("\n✅ Applied Migrations:")
            for migration in sorted(applied):
                print(f"   ✓ {migration}")

        if pending:
            print("\n⏳ Pending Migrations:")
            for migration in pending:
                print(f"   ○ {migration}")
        else:
            print("\n✅ No pending migrations. Database is up to date.")

        print()

    def verify_database(self):
        """Verify database schema after migrations."""
        print(f"\n{'='*60}")
        print("VERIFYING DATABASE SCHEMA")
        print(f"{'='*60}")

        try:
            cur = self.conn.cursor()

            # Check tables
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)

            tables = [row[0] for row in cur.fetchall()]

            print(f"\n✅ Found {len(tables)} tables:")
            for table in tables:
                # Count rows
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"   - {table} ({count} rows)")

            # Check indexes
            cur.execute("""
                SELECT COUNT(*)
                FROM pg_indexes
                WHERE schemaname = 'public'
            """)

            index_count = cur.fetchone()[0]
            print(f"\n✅ Found {index_count} indexes")

            print(f"\n{'='*60}")
            print("✅ Database verification complete")
            print(f"{'='*60}\n")

        except Exception as e:
            print(f"\n❌ Database verification failed: {e}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument("--file", type=str, help="Run specific migration file")
    parser.add_argument("--check", action="store_true", help="Check migration status without running")
    parser.add_argument("--verify", action="store_true", help="Verify database schema")
    parser.add_argument("--database-url", type=str, help="Database URL (overrides DATABASE_URL env var)")

    args = parser.parse_args()

    # Get database URL
    database_url = args.database_url or os.getenv('DATABASE_URL')

    if not database_url:
        print("❌ DATABASE_URL not set")
        print("   Set it in .env file or pass --database-url argument")
        print("   Example: postgresql://user:pass@localhost:5432/pdoom1")
        sys.exit(1)

    # Create runner
    runner = MigrationRunner(database_url)

    try:
        # Connect to database
        runner.connect()

        # Ensure migrations table exists
        runner.ensure_migrations_table()

        if args.check:
            # Just check status
            runner.check_status()

        elif args.verify:
            # Verify database
            runner.verify_database()

        elif args.file:
            # Run specific migration
            runner.run_migration(args.file)

        else:
            # Run all pending migrations
            runner.run_all_pending()

            # Verify after migration
            if input("\nVerify database schema? (y/N): ").lower() == 'y':
                runner.verify_database()

    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

    finally:
        # Always disconnect
        runner.disconnect()


if __name__ == "__main__":
    main()
