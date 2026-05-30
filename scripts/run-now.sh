#!/bin/bash
# Manually trigger a single news post with email notifications
# Usage: ./scripts/run-now.sh

echo "=== Facebook News Bot — Manual Trigger ==="
echo ""
echo "Triggering single post..."
echo ""

RESPONSE=$(curl -s http://localhost:5678/webhook/trigger-post)

echo "Response: $RESPONSE"
echo ""
echo "What happens next:"
echo "  1. Production gate checks APIs"
echo "  2. Fetches US politics + celebrity news"
echo "  3. Claude generates caption + compliance review"
echo "  4. Publishes to Facebook"
echo "  5. Emails sent to talhazahoor786@gmail.com"
echo ""
echo "Done. Check your email for updates."
