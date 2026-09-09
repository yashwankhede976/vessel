#!/usr/bin/env bash
# Run the Django development server locally.
# Usage: ./scripts/dev-backend.sh
set -euo pipefail

cd "$(dirname "$0")/../backend"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip >/dev/null
pip install -r requirements.txt

python manage.py migrate
python manage.py runserver 0.0.0.0:8000
