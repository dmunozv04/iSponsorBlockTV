#!/bin/bash
# Build script for iSponsorBlockTV Web Interface

set -e

echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "Installing Python package..."
pip install -e .

echo "Build complete!"
echo ""
echo "To run the web interface:"
echo "  isponsorblocktv-web"
echo ""
echo "Or with Docker:"
echo "  docker-compose up -d"
