# Scripts Directory

This directory contains utility scripts for the Gmail Lead Sync Web UI & API Layer.

## seed_data.py

Generates demo data for testing and development purposes.

### Features

- **Idempotent**: Safe to run multiple times without creating duplicates
- **Clear flag**: Option to delete existing data before seeding
- **Progress messages**: Shows what's being created
- **Error handling**: Graceful error messages with helpful hints
- **Secure by default**: Requires explicit opt-in and a caller-supplied admin password

### Prerequisites

1. `ENVIRONMENT=development` must be set
2. `DEV_SEED=true` must be set
3. `DEV_ADMIN_PASSWORD` must be set (the admin user's password)
4. Database must be initialized with migrations:
   ```bash
   alembic upgrade head
   ```
5. `ENCRYPTION_KEY` must be set

### Usage

The recommended way is via `make`:

```bash
export DEV_ADMIN_PASSWORD='your-secure-password'
make seed-dev
```

Or manually (both env vars must be set):

```bash
ENVIRONMENT=development DEV_SEED=true DEV_ADMIN_PASSWORD='your-secure-password' \
  python scripts/seed_data.py

# Clear existing data before seeding
ENVIRONMENT=development DEV_SEED=true DEV_ADMIN_PASSWORD='your-secure-password' \
  python scripts/seed_data.py --clear
```

### Generated Data

The script creates:

- **2 demo users**:
  - Admin: `username=admin`, password from `DEV_ADMIN_PASSWORD`
  - Viewer: `username=viewer`, password from `DEV_VIEWER_PASSWORD` (falls back to `DEV_ADMIN_PASSWORD`)

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

- **20 demo leads** with various statuses

- **5 default settings**

### Troubleshooting

**Error: ENVIRONMENT is not 'development'**

Set `ENVIRONMENT=development` in your `.env` file or inline before the command.

**Error: DEV_SEED is not set to 'true'**

Set `DEV_SEED=true` in your `.env` file or use `make seed-dev` which sets it automatically.

**Error: DEV_ADMIN_PASSWORD is not set**

```bash
export DEV_ADMIN_PASSWORD='your-secure-password'
```

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
ENVIRONMENT=development DEV_SEED=true DEV_ADMIN_PASSWORD='...' python scripts/seed_data.py --clear
```
