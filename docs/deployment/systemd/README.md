# Systemd Deployment (Alternative to Docker Compose)

The `gmail-lead-sync.service` file in this directory is a systemd unit file for deploying the Gmail Lead Sync API directly on a Linux host **without Docker**.

> **Recommended deployment method**: Use Docker Compose (`make up`) as described in the root [README](../../../README.md). The systemd unit is provided for environments where Docker is not available or not desired.

## When to use this

- Bare-metal or VM deployments where Docker is not installed
- Environments managed by a configuration management tool (Ansible, Puppet, Chef) that prefers native systemd units
- Situations where container overhead is unacceptable

## Setup

1. Copy the application to `/opt/gmail-lead-sync/`:
   ```bash
   sudo cp -r . /opt/gmail-lead-sync
   ```

2. Create a dedicated system user:
   ```bash
   sudo useradd --system --no-create-home gmail-lead-sync
   sudo chown -R gmail-lead-sync:gmail-lead-sync /opt/gmail-lead-sync
   ```

3. Create a Python virtual environment and install dependencies:
   ```bash
   sudo -u gmail-lead-sync python3 -m venv /opt/gmail-lead-sync/venv
   sudo -u gmail-lead-sync /opt/gmail-lead-sync/venv/bin/pip install -r requirements-api.txt
   ```

4. Copy `.env.example` to `.env` and fill in real values:
   ```bash
   sudo cp /opt/gmail-lead-sync/.env.example /opt/gmail-lead-sync/.env
   sudo nano /opt/gmail-lead-sync/.env
   ```

5. Install and enable the service:
   ```bash
   sudo cp docs/deployment/systemd/gmail-lead-sync.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable gmail-lead-sync
   sudo systemctl start gmail-lead-sync
   ```

6. Check status:
   ```bash
   sudo systemctl status gmail-lead-sync
   sudo journalctl -u gmail-lead-sync -f
   ```
