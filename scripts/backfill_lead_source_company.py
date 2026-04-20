#!/usr/bin/env python3
"""
Backfill script: assign company_id to lead_sources rows that have NULL company_id.

Run this AFTER applying migration k5l6m7n8o9p0 and BEFORE applying the
next migration (PR 2) that enforces NOT NULL on lead_sources.company_id.

Usage
-----
  # Assign all unowned rows to company 1:
  python scripts/backfill_lead_source_company.py --company-id 1

  # Assign only specific sender addresses to company 2:
  python scripts/backfill_lead_source_company.py --company-id 2 \\
      --sender-emails leads@zillow.com notifications@realtor.com

  # Dry-run — show what would be updated without writing:
  python scripts/backfill_lead_source_company.py --company-id 1 --dry-run

  # Production environments require an explicit acknowledgement flag:
  python scripts/backfill_lead_source_company.py --company-id 1 \\
      --confirm-production

Safety guarantees
-----------------
  - Only rows where company_id IS NULL are touched (idempotent).
  - Refuses to run in ENVIRONMENT=production without --confirm-production.
  - Prints a summary of what was (or would be) changed before committing.
  - Exits non-zero on any error; the transaction is rolled back.
"""

import argparse
import os
import sys

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(
        description='Backfill company_id on lead_sources rows that have NULL company_id.'
    )
    parser.add_argument(
        '--company-id',
        type=int,
        required=True,
        help='The company.id to assign to matching rows.',
    )
    parser.add_argument(
        '--sender-emails',
        nargs='*',
        default=None,
        metavar='EMAIL',
        help=(
            'Optional list of sender_email values to restrict the update. '
            'If omitted, all NULL rows are updated.'
        ),
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be updated without writing to the database.',
    )
    parser.add_argument(
        '--confirm-production',
        action='store_true',
        help='Required when ENVIRONMENT=production to prevent accidental runs.',
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Production guard.
    environment = os.getenv('ENVIRONMENT', '')
    if environment == 'production' and not args.confirm_production:
        print(
            '\n✗ Error: ENVIRONMENT=production detected.\n'
            '  Pass --confirm-production to run this script against production.\n'
            '  Make sure you have a database backup before proceeding.',
            file=sys.stderr,
        )
        sys.exit(1)

    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print(
            '\n✗ Error: DATABASE_URL is not set.\n'
            '  Set DATABASE_URL in your .env file before running this script.',
            file=sys.stderr,
        )
        sys.exit(1)

    engine = create_engine(
        database_url,
        connect_args={'check_same_thread': False} if 'sqlite' in database_url else {},
    )
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Verify the target company exists.
        row = db.execute(
            text('SELECT id, name FROM companies WHERE id = :cid'),
            {'cid': args.company_id},
        ).fetchone()
        if row is None:
            print(
                f'\n✗ Error: No company found with id={args.company_id}.',
                file=sys.stderr,
            )
            sys.exit(1)
        company_name = row[1]

        # Build the SELECT to preview affected rows.
        if args.sender_emails:
            placeholders = ', '.join(f':e{i}' for i in range(len(args.sender_emails)))
            params = {f'e{i}': e for i, e in enumerate(args.sender_emails)}
            params['cid'] = args.company_id
            select_sql = text(
                f'SELECT id, sender_email FROM lead_sources '
                f'WHERE company_id IS NULL AND sender_email IN ({placeholders})'
            )
            update_sql = text(
                f'UPDATE lead_sources SET company_id = :cid '
                f'WHERE company_id IS NULL AND sender_email IN ({placeholders})'
            )
        else:
            params = {'cid': args.company_id}
            select_sql = text(
                'SELECT id, sender_email FROM lead_sources WHERE company_id IS NULL'
            )
            update_sql = text(
                'UPDATE lead_sources SET company_id = :cid WHERE company_id IS NULL'
            )

        affected_rows = db.execute(select_sql, params).fetchall()

        if not affected_rows:
            print('✓ No rows with NULL company_id found. Nothing to do.')
            return

        print(f'\nTarget company: {company_name} (id={args.company_id})')
        print(f'Rows to update: {len(affected_rows)}')
        print()
        for r in affected_rows:
            print(f'  lead_source id={r[0]}  sender_email={r[1]}')
        print()

        if args.dry_run:
            print('Dry-run mode — no changes written.')
            return

        # Execute the update.
        result = db.execute(update_sql, params)
        db.commit()

        print(f'✓ Updated {result.rowcount} row(s) → company_id={args.company_id}.')

    except Exception as exc:
        db.rollback()
        print(f'\n✗ Error: {exc}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    main()
