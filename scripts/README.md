# Scripts Directory

This directory contains utility scripts for the Gmail Lead Sync Web UI & API Layer.

## seed_data.py

Generates demo data for testing and development purposes.

### Features

- **Idempotent**: Safe to run multiple times without creating duplicates
- **Clear flag**: Option to delete existing data before seeding
- **Progress messages**: Shows what's being created
- **Error handling**: Graceful error messages with helpful hints

### Usage

```bash
# Add seed data (idempotent - won't create duplicates)
python scripts/seed_data.py

# Clear existing data before seeding
python scripts/seed_data.py --clear

# Show help
python scripts/seed_data.py --help
```

### Prerequisites

1. Database must be initialized with migrations:
   ```bash
   alembic upgrade head
   ```

2. Environment variables must be set:
   - `DATABASE_URL` - SQLite database path (default: sqlite:///./gmail_lead_sync.db)
   - `ENCRYPTION_KEY` - Key for credential encryption (required)

   Generate encryption key:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

### Generated Data

The script creates:

- **2 demo users**:
  - Admin: `username=admin, password=admin123`
  - Viewer: `username=viewer, password=viewer123`

- **3 demo agents** with encrypted Gmail credentials:
  - demo_agent_1 (demo.agent1@example.com)
  - demo_agent_2 (demo.agent2@example.com)
  - demo_agent_3 (demo.agent3@example.com)

- **5 demo lead sources** with various regex patterns:
  - leads@zillow.com
  - notifications@realtor.com
  - leads@redfin.com
  - system@trulia.com
  - alerts@homes.com

- **3 demo templates** with different content:
  - Welcome Template
  - Quick Response
  - Detailed Follow-up

- **20 demo leads** with various statuses:
  - Mix of responded and pending leads
  - Various timestamps (from 5 days ago to now)
  - Different response statuses (success, failed, pending)

- **5 default settings**:
  - sync_interval_seconds = 300
  - regex_timeout_ms = 1000
  - session_timeout_hours = 24
  - max_leads_per_page = 50
  - enable_auto_restart = true

### Example Output

```
============================================================
Gmail Lead Sync - Seed Data Script
============================================================

✓ Connected to database

Creating demo users...
  ✓ Created admin user (username: admin, password: admin123)
  ✓ Created viewer user (username: viewer, password: viewer123)

Creating demo templates...
  ✓ Created template: Welcome Template
  ✓ Created template: Quick Response
  ✓ Created template: Detailed Follow-up

...

============================================================
Seed data complete!
============================================================

Summary:
  Users: 2
  Templates: 3
  Agents: 3
  Lead Sources: 5
  Leads: 20

Login credentials:
  Admin: username=admin, password=admin123
  Viewer: username=viewer, password=viewer123
```

### Troubleshooting

**Error: ENCRYPTION_KEY environment variable not set**

Generate and set an encryption key:
```bash
export ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

**Error: Database connection failed**

Ensure the database exists and migrations are applied:
```bash
alembic upgrade head
```

**Error: Foreign key constraint failed**

Run with `--clear` flag to reset the database:
```bash
python scripts/seed_data.py --clear
```
