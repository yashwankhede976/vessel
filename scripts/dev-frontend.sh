#!/usr/bin/env bash
# Run the React (Vite) development server locally.
# Usage: ./scripts/dev-frontend.sh
set -euo pipefail

cd "$(dirname "$0")/../frontend"

if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install
fi

npm run dev
