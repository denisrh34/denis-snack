# Denis Snack - Toko Camilan Online Indonesia

Toko camilan online yang menyajikan keripik, kue kering, permen, dan aneka snack pilihan.

## 🚀 Quick Start (Local)

```bash
# 1. Clone repo
git clone https://github.com/denisrh34/denis-snack.git
cd denis-snack

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python3 app.py

# 4. Open browser: http://localhost:5000
```

## ☁️ Deploy to Railway (5 menit)

### Prasyarat:
- GitHub account (sudah login via `gh`)
- Railway account (gratis, $5 credit/bulan)
- Node.js 18+

### Langkah-langkah:

#### 1. Buat Akun Railway
Buka https://railway.app dan login dengan GitHub.

#### 2. Buat Project Baru
- Buka Dashboard: https://railway.app/dashboard
- Klik **"New Project"** → **"Deploy from GitHub Repo"**
- Pilih repo: `denisrh34/denis-snack`
- Klik **"Deploy"**

#### 3. Tambahkan PostgreSQL Database
- Di project dashboard, klik **"+ Add Service"** → **"PostgreSQL"**
- Tunggu database provision (1-2 menit)

#### 4. Setting Environment Variables
Di tab **"Variables"**, tambahkan:
```
FLASK_SECRET_KEY = (random string, misalnya: c2VjcmV0X2tleV9mb3JfZGV2)
DATA_DIR = /app/data
DB_PATH = /app/data/denis_snack.db
RAILWAY_VOLUME_MOUNT_PATH = /app/data
```

#### 5. Install Railway CLI (opsional, untuk deploy lokal)
```bash
# macOS
brew install railwayapp/tap/railway

# Linux (x64)
curl -fsSL https://github.com/railwayapp/railway/releases/download/v3.4.0/railway-v3.4.0-linux-x64.tar.gz | tar xz -C /usr/local/bin/
```

Atau deploy langsung dari dashboard Railway (tanpa CLI).

#### 6. Deploy
- Dashboard Railway akan auto-deploy setelah push ke GitHub
- Atau via CLI: `railway deploy`

#### 7. Hasil
URL deploy: `https://denis-snack.up.railway.app`

## 🛠️ Tech Stack
- **Backend**: Flask 3.1.3 (Python)
- **Database**: SQLite (development) / PostgreSQL (Railway)
- **Frontend**: Tailwind CSS + vanilla JS
- **Deployment**: Railway

## 📋 Fitur
- ✅ Halaman beranda profesional (hero, kategori, produk, promo, about)
- ✅ Theme Builder (warna, font, background, logo, hero)
- ✅ WhatsApp Notifikasi (Fonnte, Wablas, Custom Webhook)
- ✅ Keranjang belanja (localStorage)
- ✅ Checkout dan order flow
- ✅ Admin panel (produk, kategori, stok, pesanan, pelanggan, promo, tema)
- ✅ Edit Customer
- ✅ Security headers, password hashing, SQL injection protection
- ✅ Responsive design (mobile, tablet, desktop)

## 📝 Env Variables (Production)
| Variable | Description | Required |
|----------|-------------|----------|
| `FLASK_SECRET_KEY` | Secret key untuk sessions | Yes |
| `DATA_DIR` | Directory untuk database file | Yes |
| `DB_PATH` | Path ke SQLite database file | Yes |
| `DATABASE_URL` | (Opsional) URL PostgreSQL | No |
| `WA_PROVIDER` | WhatsApp provider (fonnte/wablas/custom) | No |
| `WA_API_KEY` | API key provider WhatsApp | No |
| `WA_NOTIFY_ADMIN` | Notifikasi admin (1/0) | No |
| `WA_NOTIFY_CUSTOMER` | Notifikasi customer (1/0) | No |

## 📄 License
MIT