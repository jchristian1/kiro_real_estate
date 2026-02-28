#!/bin/bash
# Gmail Lead Sync - Environment Setup Script

echo "=== Gmail Lead Sync Environment Setup ==="
echo ""
echo "Please enter your Gmail credentials:"
echo ""

# Get Gmail email
read -p "Gmail Email Address: " GMAIL_EMAIL
export GMAIL_EMAIL

# Get App Password
echo ""
echo "Enter your 16-character App Password (no spaces):"
read -s GMAIL_APP_PASSWORD
export GMAIL_APP_PASSWORD

# Set encryption key
export ENCRYPTION_KEY="381SQe-HnEQJ1IOwI29L5U4NSJu6em_GyHuW5izVoz4="

echo ""
echo "✅ Environment variables set!"
echo ""
echo "To verify, run:"
echo "  echo \$GMAIL_EMAIL"
echo "  echo \$ENCRYPTION_KEY"
echo ""
echo "Now you can run the watcher with:"
echo "  python -m gmail_lead_sync start --use-env --log-level DEBUG"
