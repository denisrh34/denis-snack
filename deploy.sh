#!/bin/bash
# Denis Snack - Railway Deployment Script
# Jalankan script ini setelah mengikuti langkah-langkah di bawah.

set -e

echo "🚀 Deploying Denis Snack to Railway..."

# 1. Install Railway CLI
echo "📦 Installing Railway CLI..."
if command -v railway &> /dev/null; then
    echo "Railway CLI already installed"
else
    echo "Railway CLI not found. Install manually:"
    echo "  macOS: brew install railwayapp/tap/railway"
    echo "  Linux: curl -fsSL https://github.com/railwayapp/railway/releases | tar xz"
    echo "  Or download from: https://railway.app/download"
    exit 1
fi

# 2. Login to Railway
echo "🔐 Logging in to Railway..."
railway login

# 3. Initialize project
echo "📁 Initializing Railway project..."
railway init

# 4. Add PostgreSQL database
echo "🐘 Adding PostgreSQL database..."
railway plugin:install postgresql
railway services:create postgresql

# 5. Set environment variables
echo "⚙️ Setting environment variables..."
railway variable set FLASK_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
railway variable set DATA_DIR=/app/data
railway variable set DB_PATH=/app/data/denis_snack.db
railway variable set RAILWAY_VOLUME_MOUNT_PATH=/app/data

# 6. Deploy
echo "🚀 Deploying..."
railway deploy

# 7. Get URL
echo "✅ Deployment complete!"
railway domain

echo ""
echo "🎉 Site URL:"
railway domain
echo ""
echo "📝 Next steps:"
echo "  1. Open Railway dashboard: https://railway.app/dashboard"
echo "  2. Check deployment logs"
echo "  3. Add custom domain if needed"
echo "  4. Seed database by visiting the URL once"