#!/usr/bin/env bash
# ═══════════════════════════════════════
# Beeba Boys 1001 — Billing Software Setup
# ═══════════════════════════════════════
set -e

echo "🧾 Beeba Boys 1001 — Billing Software Setup"
echo "═══════════════════════════════════════════"

# Check Python
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
    echo "❌ Python 3 not found. Install it first: https://python.org"
    exit 1
fi

echo "✅ Python: $($PYTHON --version)"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    $PYTHON -m venv venv
fi

# Activate
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null || true

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt --quiet

# Check .env
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  No .env file found."
    echo "   Copy .env.example to .env and fill in your values:"
    echo "   cp .env.example .env"
    echo ""
else
    echo "✅ .env found"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "✅ Setup complete!"
echo ""
echo "   Start the software:"
echo "     python -m app.main           # Web UI + Telegram bot"
echo "     python -m app.main web       # Web UI only"
echo "     python -m app.main bot       # Telegram bot only"
echo ""
echo "   Open the dashboard:"
echo "     http://127.0.0.1:5000"
echo ""
echo "   Run tests:"
echo "     pytest tests/ -v"
echo "═══════════════════════════════════════════"
