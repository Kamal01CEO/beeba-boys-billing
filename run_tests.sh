#!/usr/bin/env bash
# ═══════════════════════════════════════
# Run all tests with coverage
# ═══════════════════════════════════════
set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "❌ Run setup.sh first"
    exit 1
fi

source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

echo "🧪 Running tests..."
python -m pytest tests/ -v --tb=short "$@"
echo ""
echo "✅ All tests passed!"
