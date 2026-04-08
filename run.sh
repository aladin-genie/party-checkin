#!/bin/bash

# Party Check-In System Runner
cd ~/.openclaw/workspace/pocs/2026-04-08/party-checkin

# Activate virtual environment
source venv/bin/activate

# Initialize database
python3 -c "from app import app, db; app.app_context().push(); db.create_all(); print('Database initialized')"

# Run the Flask app with gunicorn for production-like environment
echo "🎉 Starting Party Check-In System..."
echo ""
echo "Access the app at:"
echo "  • Home: http://localhost:5000"
echo "  • Register: http://localhost:5000/register"
echo "  • Scanner: http://localhost:5000/scanner"
echo "  • Admin: http://localhost:5000/admin"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Use gunicorn if available, fallback to Flask dev server
if command -v gunicorn &> /dev/null; then
    gunicorn app:app --config gunicorn.conf.py
else
    echo "⚠️  Gunicorn not found, using Flask dev server (not for production)"
    python3 app.py
fi
