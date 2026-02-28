# Deployment Guide: Gmail Lead Sync & Response Engine

This guide provides comprehensive instructions for deploying the Gmail Lead Sync & Response Engine to production Linux servers as a long-running background service.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Server Setup](#server-setup)
- [Installation](#installation)
- [Configuration](#configuration)
- [Systemd Service Setup](#systemd-service-setup)
- [Database Management](#database-management)
- [Security Best Practices](#security-best-practices)
- [Monitoring and Alerting](#monitoring-and-alerting)
- [Backup and Recovery](#backup-and-recovery)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+, or RHEL 8+)
- **Python**: 3.10 or higher
- **Memory**: Minimum 512MB RAM, recommended 1GB+
- **Disk Space**: Minimum 1GB free space (more for logs and database growth)
- **Network**: Outbound access to Gmail servers (imap.gmail.com:993, smtp.gmail.com:587)

### Required Accounts and Credentials

- Gmail account with 2FA enabled
- Gmail App Password generated
- Encryption key for credential storage

## Server Setup

### 1. Create Dedicated User

Create a dedicated system user for running the service:

```bash
# Create user without home directory login
sudo useradd -r -s /bin/bash -m -d /opt/gmail-lead-sync gmail-sync

# Set password (optional, for sudo access)
sudo passwd gmail-sync
```

### 2. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip git sqlite3
```

**CentOS/RHEL:**
```bash
sudo dnf install -y python3.10 python3-pip git sqlite
```

### 3. Configure Firewall

Allow outbound connections to Gmail servers:

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow out 993/tcp comment 'Gmail IMAP'
sudo ufw allow out 587/tcp comment 'Gmail SMTP'

# Firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=993/tcp
sudo firewall-cmd --permanent --add-port=587/tcp
sudo firewall-cmd --reload
```

If running the health check endpoint:

```bash
# Allow inbound on port 5000 (adjust as needed)
sudo ufw allow 5000/tcp comment 'Health check endpoint'
```

## Installation

### 1. Clone Repository

```bash
# Switch to service user
sudo su - gmail-sync

# Clone repository
cd /opt/gmail-lead-sync
git clone <repository-url> .

# Or download release tarball
wget https://github.com/your-org/gmail-lead-sync/archive/v1.0.0.tar.gz
tar -xzf v1.0.0.tar.gz --strip-components=1
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3.10 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 3. Install Application

```bash
# Install dependencies
pip install -r requirements.txt

# Install application
pip install -e .

# Verify installation
gmail-lead-sync --version
```

### 4. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Verify database created
ls -lh gmail_lead_sync.db
```

## Configuration

### 1. Environment Variables

Create environment file for the service:

```bash
sudo nano /opt/gmail-lead-sync/.env
```

Add the following configuration:

```bash
# Required: Encryption key for credential storage
ENCRYPTION_KEY="your-generated-encryption-key-here"

# Required: Gmail credentials
GMAIL_EMAIL="your-agent@gmail.com"
GMAIL_APP_PASSWORD="your-app-password-here"

# Optional: Database location
DATABASE_URL="sqlite:////opt/gmail-lead-sync/gmail_lead_sync.db"

# Optional: Logging configuration
LOG_LEVEL="INFO"
LOG_FILE="/var/log/gmail-lead-sync/app.log"

# Optional: Agent information for templates
AGENT_NAME="Your Name"
AGENT_PHONE="+1-555-123-4567"
AGENT_EMAIL="your-agent@gmail.com"

# Optional: Health check endpoint
HEALTH_CHECK_PORT="5000"
HEALTH_CHECK_HOST="0.0.0.0"
```

**Generate encryption key:**

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Secure Environment File

```bash
# Set restrictive permissions
sudo chmod 600 /opt/gmail-lead-sync/.env
sudo chown gmail-sync:gmail-sync /opt/gmail-lead-sync/.env
```

### 3. Configure Lead Sources

Add lead source configurations:

```bash
# Activate virtual environment
source /opt/gmail-lead-sync/venv/bin/activate

# Add lead source
gmail-lead-sync add-source \
    --sender "leads@zillow.com" \
    --identifier "New Lead Notification" \
    --name-regex "Name:\s*(.+)" \
    --phone-regex "Phone:\s*([\d\-\(\)\s]+)"
```

### 4. Configure Templates (Optional)

Create response template:

```bash
# Create template file
cat > /opt/gmail-lead-sync/template.txt << 'EOF'
Hello {lead_name},

Thank you for your interest in our real estate services. I received your inquiry and will get back to you shortly.

Best regards,
{agent_name}
{agent_phone}
{agent_email}
EOF

# Add template
gmail-lead-sync add-template \
    --name "Default Acknowledgment" \
    --subject "Thank you for your inquiry" \
    --body-file /opt/gmail-lead-sync/template.txt

# Link template to lead source
gmail-lead-sync update-source --id 1 --auto-respond --template-id 1
```

## Systemd Service Setup

### 1. Create Service File

Create systemd service unit file:

```bash
sudo nano /etc/systemd/system/gmail-lead-sync.service
```

Add the following configuration:

```ini
[Unit]
Description=Gmail Lead Sync & Response Engine
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=gmail-sync
Group=gmail-sync
WorkingDirectory=/opt/gmail-lead-sync
EnvironmentFile=/opt/gmail-lead-sync/.env

# Use virtual environment Python
ExecStart=/opt/gmail-lead-sync/venv/bin/python -m gmail_lead_sync start

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5

# Resource limits
MemoryLimit=1G
CPUQuota=50%

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/gmail-lead-sync /var/log/gmail-lead-sync

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=gmail-lead-sync

[Install]
WantedBy=multi-user.target
```

### 2. Create Log Directory

```bash
# Create log directory
sudo mkdir -p /var/log/gmail-lead-sync

# Set ownership
sudo chown gmail-sync:gmail-sync /var/log/gmail-lead-sync

# Set permissions
sudo chmod 750 /var/log/gmail-lead-sync
```

### 3. Enable and Start Service

```bash
# Reload systemd daemon
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable gmail-lead-sync

# Start service
sudo systemctl start gmail-lead-sync

# Check status
sudo systemctl status gmail-lead-sync
```

### 4. Service Management Commands

```bash
# Start service
sudo systemctl start gmail-lead-sync

# Stop service
sudo systemctl stop gmail-lead-sync

# Restart service
sudo systemctl restart gmail-lead-sync

# Reload configuration (without restart)
sudo systemctl reload gmail-lead-sync

# View service status
sudo systemctl status gmail-lead-sync

# View logs
sudo journalctl -u gmail-lead-sync -f

# View logs since boot
sudo journalctl -u gmail-lead-sync -b

# View logs for last hour
sudo journalctl -u gmail-lead-sync --since "1 hour ago"
```

### 5. Automatic Restart Configuration

The service is configured to automatically restart on failure. Adjust restart behavior if needed:

```ini
# In /etc/systemd/system/gmail-lead-sync.service

# Always restart (default)
Restart=always

# Restart only on failure
Restart=on-failure

# Restart on abnormal exit
Restart=on-abnormal

# Wait time before restart (seconds)
RestartSec=10

# Maximum restart attempts in time window
StartLimitInterval=300
StartLimitBurst=5
```

After changes:

```bash
sudo systemctl daemon-reload
sudo systemctl restart gmail-lead-sync
```

## Database Management

### Database Location

Default location: `/opt/gmail-lead-sync/gmail_lead_sync.db`

### Database Permissions

```bash
# Set restrictive permissions
chmod 600 /opt/gmail-lead-sync/gmail_lead_sync.db
chown gmail-sync:gmail-sync /opt/gmail-lead-sync/gmail_lead_sync.db
```

### Database Maintenance

**Vacuum database (reclaim space):**

```bash
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "VACUUM;"
```

**Analyze database (optimize queries):**

```bash
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "ANALYZE;"
```

**Check database integrity:**

```bash
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "PRAGMA integrity_check;"
```

**Clean old processing logs:**

```bash
# Delete logs older than 90 days
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db \
  "DELETE FROM processing_logs WHERE timestamp < datetime('now', '-90 days');"

# Vacuum after deletion
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "VACUUM;"
```

### Database Monitoring

**Check database size:**

```bash
du -h /opt/gmail-lead-sync/gmail_lead_sync.db
```

**View table sizes:**

```bash
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db << 'EOF'
SELECT 
    name,
    (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=m.name) as row_count
FROM sqlite_master m
WHERE type='table'
ORDER BY name;
EOF
```

**View recent activity:**

```bash
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db << 'EOF'
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as total_processed,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) as failed
FROM processing_logs
WHERE timestamp > datetime('now', '-7 days')
GROUP BY DATE(timestamp)
ORDER BY date DESC;
EOF
```

## Security Best Practices

### 1. File Permissions

Set restrictive permissions on sensitive files:

```bash
# Application directory
sudo chown -R gmail-sync:gmail-sync /opt/gmail-lead-sync
sudo chmod 750 /opt/gmail-lead-sync

# Environment file (contains secrets)
sudo chmod 600 /opt/gmail-lead-sync/.env
sudo chown gmail-sync:gmail-sync /opt/gmail-lead-sync/.env

# Database file
sudo chmod 600 /opt/gmail-lead-sync/gmail_lead_sync.db
sudo chown gmail-sync:gmail-sync /opt/gmail-lead-sync/gmail_lead_sync.db

# Log directory
sudo chmod 750 /var/log/gmail-lead-sync
sudo chown gmail-sync:gmail-sync /var/log/gmail-lead-sync

# Log files
sudo chmod 640 /var/log/gmail-lead-sync/*.log
sudo chown gmail-sync:gmail-sync /var/log/gmail-lead-sync/*.log
```

### 2. Encryption Key Management

**Key Storage Best Practices:**

- Store encryption key in environment file with 600 permissions
- Never commit encryption key to version control
- Use different keys for dev, staging, and production
- Store backup of key in secure password manager or secrets vault
- Rotate keys periodically (every 6-12 months)

**Key Rotation Process:**

```bash
# 1. Generate new encryption key
NEW_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. Backup current database
cp /opt/gmail-lead-sync/gmail_lead_sync.db /opt/gmail-lead-sync/gmail_lead_sync.db.backup

# 3. Export credentials with old key
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db \
  "SELECT agent_id, email_encrypted, app_password_encrypted FROM credentials;" > creds_backup.txt

# 4. Stop service
sudo systemctl stop gmail-lead-sync

# 5. Update encryption key in .env file
sudo nano /opt/gmail-lead-sync/.env
# Replace ENCRYPTION_KEY with new key

# 6. Re-encrypt credentials using Python script
python3 << 'EOF'
from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
from gmail_lead_sync.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Setup database
engine = create_engine('sqlite:////opt/gmail-lead-sync/gmail_lead_sync.db')
Session = sessionmaker(bind=engine)
session = Session()

# Re-store credentials with new key
store = EncryptedDBCredentialsStore(session)
store.store_credentials("agent1", "your-email@gmail.com", "your-app-password")
session.commit()
EOF

# 7. Start service
sudo systemctl start gmail-lead-sync

# 8. Verify service is working
sudo systemctl status gmail-lead-sync

# 9. Securely delete backup if successful
shred -u creds_backup.txt
```

### 3. Gmail App Password Security

**Best Practices:**

- Use unique app password for this application only
- Never share app password or commit to version control
- Revoke and regenerate if compromised
- Store in encrypted environment file only
- Monitor Gmail account for suspicious activity

**Revoke Compromised Password:**

1. Visit https://myaccount.google.com/apppasswords
2. Find "Gmail Lead Sync" app password
3. Click "Remove" to revoke
4. Generate new app password
5. Update `.env` file with new password
6. Restart service: `sudo systemctl restart gmail-lead-sync`

### 4. Network Security

**Firewall Configuration:**

```bash
# Allow only necessary outbound connections
sudo ufw default deny outgoing
sudo ufw allow out 993/tcp  # Gmail IMAP
sudo ufw allow out 587/tcp  # Gmail SMTP
sudo ufw allow out 53       # DNS
sudo ufw allow out 80/tcp   # HTTP (for updates)
sudo ufw allow out 443/tcp  # HTTPS (for updates)

# Allow inbound SSH (adjust port as needed)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

**TLS/SSL Verification:**

The application enforces TLS for both IMAP and SMTP connections. Never disable certificate verification in production.

### 5. System Hardening

**Disable Unnecessary Services:**

```bash
# List running services
sudo systemctl list-units --type=service --state=running

# Disable unnecessary services
sudo systemctl disable <service-name>
sudo systemctl stop <service-name>
```

**Keep System Updated:**

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo dnf update -y

# Enable automatic security updates (Ubuntu/Debian)
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

**Configure SELinux (CentOS/RHEL):**

```bash
# Check SELinux status
sestatus

# Set SELinux context for application directory
sudo semanage fcontext -a -t bin_t "/opt/gmail-lead-sync/venv/bin/python"
sudo restorecon -Rv /opt/gmail-lead-sync

# Allow network connections
sudo setsebool -P httpd_can_network_connect 1
```

### 6. Audit Logging

Enable audit logging for security events:

```bash
# Install auditd
sudo apt install auditd  # Ubuntu/Debian
sudo dnf install audit   # CentOS/RHEL

# Add audit rules for sensitive files
sudo auditctl -w /opt/gmail-lead-sync/.env -p wa -k gmail-sync-config
sudo auditctl -w /opt/gmail-lead-sync/gmail_lead_sync.db -p wa -k gmail-sync-db

# Make rules persistent
sudo sh -c 'auditctl -l >> /etc/audit/rules.d/gmail-sync.rules'

# View audit logs
sudo ausearch -k gmail-sync-config
sudo ausearch -k gmail-sync-db
```

### 7. Secrets Management (Advanced)

For enterprise deployments, consider using a secrets management system:

**HashiCorp Vault:**

```bash
# Store encryption key in Vault
vault kv put secret/gmail-lead-sync encryption_key="your-key"

# Retrieve in service startup script
export ENCRYPTION_KEY=$(vault kv get -field=encryption_key secret/gmail-lead-sync)
```

**AWS Secrets Manager:**

```bash
# Store secret
aws secretsmanager create-secret \
    --name gmail-lead-sync/encryption-key \
    --secret-string "your-key"

# Retrieve in service startup script
export ENCRYPTION_KEY=$(aws secretsmanager get-secret-value \
    --secret-id gmail-lead-sync/encryption-key \
    --query SecretString --output text)
```

### 8. Security Checklist

- [ ] Dedicated system user created with minimal privileges
- [ ] File permissions set to 600 for sensitive files (`.env`, database)
- [ ] Directory permissions set to 750 for application directory
- [ ] Encryption key generated and stored securely
- [ ] Gmail App Password generated (not main account password)
- [ ] Firewall configured to allow only necessary connections
- [ ] System packages updated to latest versions
- [ ] Automatic security updates enabled
- [ ] Audit logging configured for sensitive files
- [ ] Service runs with `NoNewPrivileges=true`
- [ ] Service uses `ProtectSystem=strict` and `ProtectHome=true`
- [ ] Backup encryption key stored in secure location
- [ ] Regular security audits scheduled

## Monitoring and Alerting

### 1. Health Check Endpoint

The application exposes a health check endpoint for monitoring:

**Endpoint:** `http://localhost:5000/health`

**Response (Healthy):**
```json
{
  "status": "healthy",
  "database": "connected",
  "imap": "connected",
  "last_successful_sync": "2024-01-15T10:30:00",
  "timestamp": "2024-01-15T10:35:00"
}
```

**Response (Degraded):**
```json
{
  "status": "degraded",
  "database": "connected",
  "imap": "disconnected",
  "last_successful_sync": "2024-01-15T09:00:00",
  "timestamp": "2024-01-15T10:35:00"
}
```

**HTTP Status Codes:**
- `200 OK`: System is healthy
- `503 Service Unavailable`: System is degraded

### 2. Monitoring with Systemd

**Check service status:**

```bash
# Basic status
sudo systemctl status gmail-lead-sync

# Detailed status with recent logs
sudo systemctl status gmail-lead-sync -l

# Check if service is active
sudo systemctl is-active gmail-lead-sync

# Check if service is enabled
sudo systemctl is-enabled gmail-lead-sync
```

**Monitor service restarts:**

```bash
# View restart count
sudo systemctl show gmail-lead-sync -p NRestarts

# View service start time
sudo systemctl show gmail-lead-sync -p ActiveEnterTimestamp
```

### 3. Log Monitoring

**View real-time logs:**

```bash
# Follow systemd journal
sudo journalctl -u gmail-lead-sync -f

# Follow application log file
tail -f /var/log/gmail-lead-sync/app.log
```

**Search logs for errors:**

```bash
# Search for errors in last 24 hours
sudo journalctl -u gmail-lead-sync --since "24 hours ago" | grep ERROR

# Search for specific error patterns
sudo journalctl -u gmail-lead-sync | grep -i "authentication\|connection\|failed"

# Count errors by type
sudo journalctl -u gmail-lead-sync --since "24 hours ago" | \
  grep ERROR | awk '{print $NF}' | sort | uniq -c | sort -rn
```

**Log rotation configuration:**

```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/gmail-lead-sync
```

Add the following:

```
/var/log/gmail-lead-sync/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 gmail-sync gmail-sync
    sharedscripts
    postrotate
        systemctl reload gmail-lead-sync > /dev/null 2>&1 || true
    endscript
}
```

### 4. Monitoring with Prometheus

**Install Prometheus Node Exporter:**

```bash
# Download and install
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.1/node_exporter-1.6.1.linux-amd64.tar.gz
tar xvfz node_exporter-1.6.1.linux-amd64.tar.gz
sudo cp node_exporter-1.6.1.linux-amd64/node_exporter /usr/local/bin/

# Create systemd service
sudo nano /etc/systemd/system/node_exporter.service
```

Add:

```ini
[Unit]
Description=Node Exporter
After=network.target

[Service]
Type=simple
User=gmail-sync
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter
```

**Custom Metrics Script:**

Create a script to export custom metrics:

```bash
sudo nano /opt/gmail-lead-sync/metrics.sh
```

```bash
#!/bin/bash
# Export custom metrics for Prometheus

DB_PATH="/opt/gmail-lead-sync/gmail_lead_sync.db"
METRICS_FILE="/var/lib/node_exporter/textfile_collector/gmail_lead_sync.prom"

# Ensure directory exists
mkdir -p /var/lib/node_exporter/textfile_collector

# Total leads
TOTAL_LEADS=$(sqlite3 $DB_PATH "SELECT COUNT(*) FROM leads;")
echo "gmail_lead_sync_total_leads $TOTAL_LEADS" > $METRICS_FILE

# Leads today
LEADS_TODAY=$(sqlite3 $DB_PATH "SELECT COUNT(*) FROM leads WHERE DATE(created_at) = DATE('now');")
echo "gmail_lead_sync_leads_today $LEADS_TODAY" >> $METRICS_FILE

# Processing success rate (last 24h)
SUCCESS_RATE=$(sqlite3 $DB_PATH "SELECT ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) FROM processing_logs WHERE timestamp > datetime('now', '-24 hours');")
echo "gmail_lead_sync_success_rate_24h $SUCCESS_RATE" >> $METRICS_FILE

# Database size
DB_SIZE=$(stat -f%z "$DB_PATH" 2>/dev/null || stat -c%s "$DB_PATH")
echo "gmail_lead_sync_database_size_bytes $DB_SIZE" >> $METRICS_FILE

# Service uptime
UPTIME=$(systemctl show gmail-lead-sync -p ActiveEnterTimestampMonotonic --value)
echo "gmail_lead_sync_uptime_seconds $UPTIME" >> $METRICS_FILE
```

Make executable and schedule:

```bash
sudo chmod +x /opt/gmail-lead-sync/metrics.sh
sudo chown gmail-sync:gmail-sync /opt/gmail-lead-sync/metrics.sh

# Add to crontab (run every 5 minutes)
sudo crontab -u gmail-sync -e
```

Add:

```
*/5 * * * * /opt/gmail-lead-sync/metrics.sh
```

### 5. Alerting with Systemd

**Email alerts on service failure:**

Install mail utilities:

```bash
sudo apt install mailutils  # Ubuntu/Debian
sudo dnf install mailx      # CentOS/RHEL
```

Create alert script:

```bash
sudo nano /opt/gmail-lead-sync/alert.sh
```

```bash
#!/bin/bash
# Send email alert on service failure

SERVICE="gmail-lead-sync"
EMAIL="admin@example.com"
HOSTNAME=$(hostname)

# Get service status
STATUS=$(systemctl is-active $SERVICE)

if [ "$STATUS" != "active" ]; then
    SUBJECT="ALERT: $SERVICE failed on $HOSTNAME"
    BODY="Service $SERVICE is $STATUS on $HOSTNAME at $(date)"
    
    # Get recent logs
    LOGS=$(journalctl -u $SERVICE --since "10 minutes ago" --no-pager)
    
    echo -e "$BODY\n\nRecent logs:\n$LOGS" | mail -s "$SUBJECT" $EMAIL
fi
```

Make executable:

```bash
sudo chmod +x /opt/gmail-lead-sync/alert.sh
```

Configure systemd to run on failure:

```bash
sudo nano /etc/systemd/system/gmail-lead-sync.service
```

Add to `[Service]` section:

```ini
OnFailure=gmail-lead-sync-alert.service
```

Create alert service:

```bash
sudo nano /etc/systemd/system/gmail-lead-sync-alert.service
```

```ini
[Unit]
Description=Gmail Lead Sync Alert Service

[Service]
Type=oneshot
ExecStart=/opt/gmail-lead-sync/alert.sh
```

Reload and test:

```bash
sudo systemctl daemon-reload
```

### 6. Monitoring Checklist

**Daily Checks:**
- [ ] Service is running: `systemctl status gmail-lead-sync`
- [ ] No errors in logs: `journalctl -u gmail-lead-sync --since today | grep ERROR`
- [ ] Health endpoint returns 200: `curl http://localhost:5000/health`
- [ ] Recent leads processed: Check database or logs

**Weekly Checks:**
- [ ] Database size is reasonable: `du -h gmail_lead_sync.db`
- [ ] Log files are rotating properly: `ls -lh /var/log/gmail-lead-sync/`
- [ ] No authentication failures: `journalctl -u gmail-lead-sync --since "7 days ago" | grep -i auth`
- [ ] Processing success rate > 90%: Query processing_logs table

**Monthly Checks:**
- [ ] System updates applied: `apt list --upgradable`
- [ ] Disk space sufficient: `df -h`
- [ ] Review and clean old processing logs
- [ ] Backup database and encryption key
- [ ] Review security audit logs

### 7. Recommended Monitoring Tools

**Open Source:**
- **Prometheus + Grafana**: Metrics collection and visualization
- **Nagios**: Service monitoring and alerting
- **Zabbix**: Comprehensive monitoring solution
- **ELK Stack**: Log aggregation and analysis (Elasticsearch, Logstash, Kibana)

**Commercial:**
- **Datadog**: Full-stack monitoring and alerting
- **New Relic**: Application performance monitoring
- **PagerDuty**: Incident management and alerting
- **Splunk**: Log analysis and monitoring

## Backup and Recovery

### 1. Database Backup Strategy

**Automated Daily Backups:**

Create backup script:

```bash
sudo nano /opt/gmail-lead-sync/backup.sh
```

```bash
#!/bin/bash
# Automated database backup script

# Configuration
DB_PATH="/opt/gmail-lead-sync/gmail_lead_sync.db"
BACKUP_DIR="/opt/gmail-lead-sync/backups"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/gmail_lead_sync_$DATE.db"

# Create backup directory if not exists
mkdir -p $BACKUP_DIR

# Create backup using SQLite backup command (hot backup)
sqlite3 $DB_PATH ".backup '$BACKUP_FILE'"

# Compress backup
gzip $BACKUP_FILE

# Verify backup integrity
if [ $? -eq 0 ]; then
    echo "Backup successful: $BACKUP_FILE.gz"
    
    # Delete backups older than retention period
    find $BACKUP_DIR -name "*.db.gz" -mtime +$RETENTION_DAYS -delete
    
    # Log backup
    logger -t gmail-lead-sync-backup "Database backup completed: $BACKUP_FILE.gz"
else
    echo "Backup failed!"
    logger -t gmail-lead-sync-backup "Database backup FAILED"
    exit 1
fi

# Optional: Upload to remote storage
# aws s3 cp $BACKUP_FILE.gz s3://your-bucket/backups/
# rsync -avz $BACKUP_FILE.gz user@backup-server:/backups/
```

Make executable:

```bash
sudo chmod +x /opt/gmail-lead-sync/backup.sh
sudo chown gmail-sync:gmail-sync /opt/gmail-lead-sync/backup.sh
```

Schedule daily backups:

```bash
sudo crontab -u gmail-sync -e
```

Add:

```
# Daily backup at 2 AM
0 2 * * * /opt/gmail-lead-sync/backup.sh >> /var/log/gmail-lead-sync/backup.log 2>&1
```

**Manual Backup:**

```bash
# Stop service for consistent backup
sudo systemctl stop gmail-lead-sync

# Create backup
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db ".backup '/opt/gmail-lead-sync/backups/manual_backup.db'"

# Compress
gzip /opt/gmail-lead-sync/backups/manual_backup.db

# Start service
sudo systemctl start gmail-lead-sync
```

**Hot Backup (without stopping service):**

```bash
# SQLite supports hot backups
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db ".backup '/opt/gmail-lead-sync/backups/hot_backup.db'"
```

### 2. Configuration Backup

**Backup critical configuration files:**

```bash
# Create configuration backup
sudo tar -czf /opt/gmail-lead-sync/backups/config_$(date +%Y%m%d).tar.gz \
    /opt/gmail-lead-sync/.env \
    /opt/gmail-lead-sync/template*.txt \
    /etc/systemd/system/gmail-lead-sync.service

# Set permissions
sudo chmod 600 /opt/gmail-lead-sync/backups/config_*.tar.gz
```

**Backup encryption key separately:**

```bash
# Extract encryption key
grep ENCRYPTION_KEY /opt/gmail-lead-sync/.env > /opt/gmail-lead-sync/backups/encryption_key.txt

# Secure the file
sudo chmod 400 /opt/gmail-lead-sync/backups/encryption_key.txt

# Store in password manager or secure vault
# NEVER commit to version control
```

### 3. Remote Backup Storage

**AWS S3:**

```bash
# Install AWS CLI
sudo apt install awscli

# Configure credentials
aws configure

# Upload backup
aws s3 cp /opt/gmail-lead-sync/backups/gmail_lead_sync_20240115.db.gz \
    s3://your-bucket/gmail-lead-sync/backups/

# Sync entire backup directory
aws s3 sync /opt/gmail-lead-sync/backups/ \
    s3://your-bucket/gmail-lead-sync/backups/ \
    --exclude "*" --include "*.db.gz"
```

**Rsync to Remote Server:**

```bash
# Setup SSH key authentication first
ssh-keygen -t rsa -b 4096
ssh-copy-id backup-user@backup-server

# Sync backups
rsync -avz --delete \
    /opt/gmail-lead-sync/backups/ \
    backup-user@backup-server:/backups/gmail-lead-sync/
```

**Automated Remote Backup Script:**

```bash
sudo nano /opt/gmail-lead-sync/remote_backup.sh
```

```bash
#!/bin/bash
# Upload backups to remote storage

BACKUP_DIR="/opt/gmail-lead-sync/backups"
REMOTE_BUCKET="s3://your-bucket/gmail-lead-sync/backups"

# Find today's backup
TODAY_BACKUP=$(find $BACKUP_DIR -name "gmail_lead_sync_$(date +%Y%m%d)*.db.gz" -type f | head -n 1)

if [ -n "$TODAY_BACKUP" ]; then
    # Upload to S3
    aws s3 cp "$TODAY_BACKUP" "$REMOTE_BUCKET/"
    
    if [ $? -eq 0 ]; then
        logger -t gmail-lead-sync-backup "Remote backup successful: $TODAY_BACKUP"
    else
        logger -t gmail-lead-sync-backup "Remote backup FAILED: $TODAY_BACKUP"
        exit 1
    fi
else
    logger -t gmail-lead-sync-backup "No backup found for today"
    exit 1
fi
```

Schedule:

```bash
# Run 30 minutes after local backup
30 2 * * * /opt/gmail-lead-sync/remote_backup.sh
```

### 4. Database Recovery

**Restore from Backup:**

```bash
# Stop service
sudo systemctl stop gmail-lead-sync

# Backup current database (just in case)
cp /opt/gmail-lead-sync/gmail_lead_sync.db /opt/gmail-lead-sync/gmail_lead_sync.db.before_restore

# Decompress backup
gunzip -c /opt/gmail-lead-sync/backups/gmail_lead_sync_20240115.db.gz > /tmp/restore.db

# Verify backup integrity
sqlite3 /tmp/restore.db "PRAGMA integrity_check;"

# If integrity check passes, restore
cp /tmp/restore.db /opt/gmail-lead-sync/gmail_lead_sync.db

# Set permissions
chmod 600 /opt/gmail-lead-sync/gmail_lead_sync.db
chown gmail-sync:gmail-sync /opt/gmail-lead-sync/gmail_lead_sync.db

# Start service
sudo systemctl start gmail-lead-sync

# Verify service is working
sudo systemctl status gmail-lead-sync
curl http://localhost:5000/health
```

**Restore from Remote Backup:**

```bash
# Download from S3
aws s3 cp s3://your-bucket/gmail-lead-sync/backups/gmail_lead_sync_20240115.db.gz \
    /opt/gmail-lead-sync/backups/

# Or download from remote server
rsync -avz backup-user@backup-server:/backups/gmail-lead-sync/gmail_lead_sync_20240115.db.gz \
    /opt/gmail-lead-sync/backups/

# Then follow restore steps above
```

### 5. Disaster Recovery Plan

**Complete System Recovery:**

1. **Provision new server** with same OS and specifications
2. **Install dependencies** (Python, SQLite, etc.)
3. **Clone repository** or download release
4. **Restore configuration files** from backup
5. **Restore database** from backup
6. **Restore encryption key** from secure storage
7. **Set file permissions** as documented
8. **Install and enable systemd service**
9. **Start service and verify** functionality
10. **Update DNS/load balancer** if applicable

**Recovery Time Objective (RTO):** Target 1 hour

**Recovery Point Objective (RPO):** Maximum 24 hours (daily backups)

**Disaster Recovery Checklist:**

- [ ] Database backup exists and is recent
- [ ] Configuration backup exists
- [ ] Encryption key is stored securely and accessible
- [ ] Remote backups are up to date
- [ ] Recovery procedure is documented
- [ ] Recovery procedure has been tested
- [ ] Contact information for Gmail account owner is available
- [ ] Backup server credentials are accessible

### 6. Backup Verification

**Test Backup Integrity:**

```bash
# Decompress and check
gunzip -c /opt/gmail-lead-sync/backups/gmail_lead_sync_20240115.db.gz > /tmp/test_restore.db

# Run integrity check
sqlite3 /tmp/test_restore.db "PRAGMA integrity_check;"

# Verify table structure
sqlite3 /tmp/test_restore.db ".schema" | grep "CREATE TABLE"

# Verify data exists
sqlite3 /tmp/test_restore.db "SELECT COUNT(*) FROM leads;"

# Clean up
rm /tmp/test_restore.db
```

**Automated Backup Verification:**

Add to backup script:

```bash
# After creating backup
BACKUP_FILE="$BACKUP_DIR/gmail_lead_sync_$DATE.db"

# Verify backup
sqlite3 $BACKUP_FILE "PRAGMA integrity_check;" | grep -q "ok"

if [ $? -eq 0 ]; then
    echo "Backup verification passed"
else
    echo "Backup verification FAILED"
    logger -t gmail-lead-sync-backup "Backup verification FAILED: $BACKUP_FILE"
    exit 1
fi
```

### 7. Backup Recommendations

**Backup Frequency:**
- **Database**: Daily (automated)
- **Configuration**: After each change
- **Encryption key**: Once, stored securely
- **Remote sync**: Daily (after local backup)

**Retention Policy:**
- **Local backups**: 30 days
- **Remote backups**: 90 days
- **Monthly snapshots**: 1 year

**Backup Storage Requirements:**
- Estimate: ~10MB per day (varies with lead volume)
- Monthly: ~300MB
- Annual: ~3.6GB

**Backup Security:**
- Encrypt backups before uploading to remote storage
- Use separate encryption key for backup encryption
- Restrict access to backup storage
- Audit backup access logs regularly

## Maintenance

### 1. Regular Maintenance Tasks

**Daily:**
- Monitor service status and logs
- Check health endpoint
- Verify recent leads are being processed

**Weekly:**
- Review error logs and processing failures
- Check database size and growth rate
- Verify backups are completing successfully
- Review processing success rate

**Monthly:**
- Apply system security updates
- Clean old processing logs (>90 days)
- Vacuum and analyze database
- Review and rotate logs
- Test backup restoration
- Review disk space usage

**Quarterly:**
- Review and update lead source configurations
- Review and update response templates
- Audit security settings and permissions
- Review and update monitoring alerts
- Test disaster recovery procedure

**Annually:**
- Rotate encryption keys
- Review and update documentation
- Conduct security audit
- Review system capacity and performance

### 2. System Updates

**Update Application:**

```bash
# Switch to service user
sudo su - gmail-sync

# Navigate to application directory
cd /opt/gmail-lead-sync

# Stop service
sudo systemctl stop gmail-lead-sync

# Backup current version
tar -czf /opt/gmail-lead-sync/backups/app_backup_$(date +%Y%m%d).tar.gz \
    /opt/gmail-lead-sync --exclude=backups --exclude=venv

# Pull latest changes
git fetch origin
git checkout v1.1.0  # or specific version tag

# Update dependencies
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Run database migrations
alembic upgrade head

# Start service
sudo systemctl start gmail-lead-sync

# Verify service is working
sudo systemctl status gmail-lead-sync
curl http://localhost:5000/health
```

**Update Python:**

```bash
# Install new Python version
sudo apt install python3.11

# Create new virtual environment
python3.11 -m venv /opt/gmail-lead-sync/venv-new

# Activate and install dependencies
source /opt/gmail-lead-sync/venv-new/bin/activate
pip install -r /opt/gmail-lead-sync/requirements.txt
pip install -e /opt/gmail-lead-sync

# Test with new environment
/opt/gmail-lead-sync/venv-new/bin/python -m gmail_lead_sync --version

# If successful, update systemd service
sudo nano /etc/systemd/system/gmail-lead-sync.service
# Update ExecStart path to use venv-new

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart gmail-lead-sync

# Remove old virtual environment after verification
rm -rf /opt/gmail-lead-sync/venv
mv /opt/gmail-lead-sync/venv-new /opt/gmail-lead-sync/venv
```

**Update System Packages:**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt upgrade -y
sudo apt autoremove -y

# CentOS/RHEL
sudo dnf update -y
sudo dnf autoremove -y

# Reboot if kernel updated
sudo reboot
```

### 3. Database Maintenance

**Optimize Database:**

```bash
# Vacuum to reclaim space
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "VACUUM;"

# Analyze to update statistics
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "ANALYZE;"

# Rebuild indexes
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "REINDEX;"
```

**Clean Old Data:**

```bash
# Delete processing logs older than 90 days
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db << 'EOF'
DELETE FROM processing_logs 
WHERE timestamp < datetime('now', '-90 days');
EOF

# Vacuum after deletion
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "VACUUM;"
```

**Database Health Check:**

```bash
# Check integrity
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "PRAGMA integrity_check;"

# Check foreign key constraints
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "PRAGMA foreign_key_check;"

# View database statistics
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db << 'EOF'
SELECT 
    name,
    (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=m.name) as tables,
    (SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name=m.name) as indexes
FROM sqlite_master m
WHERE type='table'
ORDER BY name;
EOF
```

### 4. Log Management

**Rotate Logs Manually:**

```bash
# Force log rotation
sudo logrotate -f /etc/logrotate.d/gmail-lead-sync
```

**Archive Old Logs:**

```bash
# Compress logs older than 30 days
find /var/log/gmail-lead-sync -name "*.log" -mtime +30 -exec gzip {} \;

# Move compressed logs to archive
mkdir -p /opt/gmail-lead-sync/log-archive
find /var/log/gmail-lead-sync -name "*.log.gz" -mtime +60 \
    -exec mv {} /opt/gmail-lead-sync/log-archive/ \;
```

**Clean Old Logs:**

```bash
# Delete archived logs older than 1 year
find /opt/gmail-lead-sync/log-archive -name "*.log.gz" -mtime +365 -delete
```

### 5. Performance Tuning

**Monitor Resource Usage:**

```bash
# CPU and memory usage
top -b -n 1 | grep gmail-lead-sync

# Detailed process information
ps aux | grep gmail-lead-sync

# Memory usage over time
pidstat -r -p $(pgrep -f gmail-lead-sync) 1 10
```

**Optimize SQLite Performance:**

```bash
# Enable WAL mode (Write-Ahead Logging)
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "PRAGMA journal_mode=WAL;"

# Set cache size (in KB)
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "PRAGMA cache_size=-10000;"  # 10MB

# Set synchronous mode
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db "PRAGMA synchronous=NORMAL;"
```

**Adjust Service Resource Limits:**

Edit systemd service file:

```bash
sudo nano /etc/systemd/system/gmail-lead-sync.service
```

Adjust limits:

```ini
[Service]
# Increase memory limit if needed
MemoryLimit=2G

# Adjust CPU quota
CPUQuota=75%

# Set nice level (lower priority)
Nice=10

# Set I/O scheduling class
IOSchedulingClass=best-effort
IOSchedulingPriority=4
```

Reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart gmail-lead-sync
```

### 6. Troubleshooting Common Issues

**Service Won't Start:**

```bash
# Check service status
sudo systemctl status gmail-lead-sync -l

# Check logs
sudo journalctl -u gmail-lead-sync -n 50 --no-pager

# Verify configuration
source /opt/gmail-lead-sync/.env
echo $ENCRYPTION_KEY  # Should not be empty

# Test manually
sudo su - gmail-sync
cd /opt/gmail-lead-sync
source venv/bin/activate
python -m gmail_lead_sync start
```

**High CPU Usage:**

```bash
# Identify process
top -b -n 1 | grep gmail-lead-sync

# Check for regex catastrophic backtracking
sudo journalctl -u gmail-lead-sync | grep -i "timeout\|regex"

# Review lead source patterns
gmail-lead-sync list-sources

# Test patterns for performance
gmail-lead-sync test-parser --email-file sample.txt --name-regex "pattern"
```

**Database Locked:**

```bash
# Check for other processes accessing database
lsof /opt/gmail-lead-sync/gmail_lead_sync.db

# Kill stale connections if needed
kill -9 <PID>

# Restart service
sudo systemctl restart gmail-lead-sync
```

**Memory Leaks:**

```bash
# Monitor memory over time
watch -n 5 'ps aux | grep gmail-lead-sync'

# Check for large email bodies
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db \
  "SELECT gmail_uid, LENGTH(error_details) FROM processing_logs ORDER BY LENGTH(error_details) DESC LIMIT 10;"

# Restart service daily as workaround
sudo crontab -e
# Add: 0 3 * * * systemctl restart gmail-lead-sync
```

### 7. Capacity Planning

**Monitor Growth Trends:**

```bash
# Database size over time
du -h /opt/gmail-lead-sync/gmail_lead_sync.db

# Lead creation rate
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db << 'EOF'
SELECT 
    DATE(created_at) as date,
    COUNT(*) as leads_created
FROM leads
WHERE created_at > datetime('now', '-30 days')
GROUP BY DATE(created_at)
ORDER BY date;
EOF

# Processing log growth
sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db \
  "SELECT COUNT(*) FROM processing_logs;"
```

**Estimate Storage Requirements:**

```bash
# Current database size
DB_SIZE=$(du -b /opt/gmail-lead-sync/gmail_lead_sync.db | cut -f1)

# Leads per day
LEADS_PER_DAY=$(sqlite3 /opt/gmail-lead-sync/gmail_lead_sync.db \
  "SELECT AVG(daily_count) FROM (SELECT COUNT(*) as daily_count FROM leads WHERE created_at > datetime('now', '-30 days') GROUP BY DATE(created_at));")

# Estimate growth per month (rough)
echo "Current DB size: $(($DB_SIZE / 1024 / 1024)) MB"
echo "Leads per day: $LEADS_PER_DAY"
echo "Estimated growth: ~$((LEADS_PER_DAY * 30 * 1024 / 1024)) MB/month"
```

**Scale Up Recommendations:**

- **< 100 leads/day**: Current setup sufficient
- **100-500 leads/day**: Increase memory to 2GB, monitor disk space
- **500-1000 leads/day**: Consider PostgreSQL migration, dedicated server
- **> 1000 leads/day**: Implement horizontal scaling, load balancing

### 8. Maintenance Checklist

**Pre-Maintenance:**
- [ ] Notify stakeholders of maintenance window
- [ ] Backup database and configuration
- [ ] Verify backup integrity
- [ ] Document current system state
- [ ] Prepare rollback plan

**During Maintenance:**
- [ ] Stop service gracefully
- [ ] Perform maintenance tasks
- [ ] Test changes in isolation
- [ ] Verify database integrity
- [ ] Start service

**Post-Maintenance:**
- [ ] Verify service is running
- [ ] Check health endpoint
- [ ] Monitor logs for errors
- [ ] Verify leads are being processed
- [ ] Update documentation
- [ ] Notify stakeholders of completion

## Troubleshooting

### Common Deployment Issues

**Issue: Permission Denied Errors**

```bash
# Fix file ownership
sudo chown -R gmail-sync:gmail-sync /opt/gmail-lead-sync

# Fix file permissions
sudo chmod 750 /opt/gmail-lead-sync
sudo chmod 600 /opt/gmail-lead-sync/.env
sudo chmod 600 /opt/gmail-lead-sync/gmail_lead_sync.db
```

**Issue: Module Not Found**

```bash
# Verify virtual environment
source /opt/gmail-lead-sync/venv/bin/activate
python -c "import gmail_lead_sync; print(gmail_lead_sync.__file__)"

# Reinstall if needed
pip install -e /opt/gmail-lead-sync
```

**Issue: Database Migration Fails**

```bash
# Check current version
alembic current

# View migration history
alembic history

# Downgrade and retry
alembic downgrade -1
alembic upgrade head
```

**Issue: Service Fails to Start After Reboot**

```bash
# Check service is enabled
sudo systemctl is-enabled gmail-lead-sync

# Enable if not
sudo systemctl enable gmail-lead-sync

# Check dependencies
sudo systemctl list-dependencies gmail-lead-sync
```

For additional troubleshooting, refer to the main [README.md](README.md#troubleshooting) troubleshooting section.

## Additional Resources

- [README.md](README.md) - Installation and usage guide
- [Design Document](.kiro/specs/gmail-lead-sync-engine/design.md) - Architecture and design details
- [Requirements Document](.kiro/specs/gmail-lead-sync-engine/requirements.md) - Functional requirements
- [Gmail IMAP Documentation](https://developers.google.com/gmail/imap/imap-smtp)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Systemd Service Documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)

## Support

For deployment issues or questions:

1. Check the troubleshooting sections in this guide and README.md
2. Review service logs: `sudo journalctl -u gmail-lead-sync -f`
3. Check health endpoint: `curl http://localhost:5000/health`
4. Open an issue on the project repository with:
   - Deployment environment details (OS, Python version)
   - Error messages and logs (redact sensitive information)
   - Steps to reproduce the issue
   - Configuration details (redact credentials)

---

**Document Version:** 1.0  
**Last Updated:** 2024-01-15  
**Maintained By:** Gmail Lead Sync Development Team
