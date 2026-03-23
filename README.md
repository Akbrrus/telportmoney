# 💰 Telegram Finance Tracker Bot

Bot Telegram pribadi untuk mencatat pengeluaran harian, dengan penyimpanan otomatis ke Google Sheets.

## Fitur

- **Catat pengeluaran** — kirim nominal langsung ke chat (`50k makan siang`)
- **Format fleksibel** — mendukung `50000`, `50.000`, `50k`, `50rb`, `1.5jt`
- **Summary harian** — `/summary` untuk melihat pengeluaran hari ini
- **Laporan bulanan** — `/monthly` untuk ringkasan bulan berjalan
- **Laporan otomatis** — setiap tanggal 1, bot kirim rekap bulan lalu
- **Budget tracker** — set budget bulanan dan dapat warning saat mendekati limit
- **Undo** — `/undo` untuk menghapus catatan terakhir
- **Google Sheets** — semua data tersimpan rapi per bulan, bisa dilihat kapan saja

## Struktur Google Sheets

Bot akan otomatis membuat worksheet per bulan (`2026-03`, `2026-04`, dst.) dengan kolom:

| Tanggal    | Waktu | Nominal   | Keterangan  | Running Total |
|------------|-------|-----------|-------------|---------------|
| 2026-03-21 | 14:30 | 50000     | makan siang | 50000         |
| 2026-03-21 | 18:00 | 25000     | grab        | 75000         |

---

## Setup

### 1. Buat Telegram Bot

1. Buka Telegram, cari **@BotFather**
2. Kirim `/newbot`, ikuti instruksi
3. Simpan **token** yang diberikan

### 2. Setup Google Sheets API

1. Buka [Google Cloud Console](https://console.cloud.google.com/)
2. Buat project baru (atau pakai yang sudah ada)
3. Aktifkan **Google Sheets API** dan **Google Drive API**
4. Buat **Service Account**:
   - Pergi ke **IAM & Admin → Service Accounts**
   - Klik **Create Service Account**
   - Beri nama, klik **Done**
   - Klik service account yang baru dibuat → **Keys** → **Add Key** → **JSON**
   - Download file JSON, rename jadi `credentials.json`
5. Buat Google Spreadsheet baru
6. **Share** spreadsheet ke email service account (yang ada di `credentials.json`, field `client_email`) dengan akses **Editor**
7. Ambil **Sheet ID** dari URL:
   ```
   https://docs.google.com/spreadsheets/d/SHEET_ID_DISINI/edit
   ```

### 3. Konfigurasi

```bash
# Clone / copy project
cd finance_bot

# Copy dan isi .env
cp .env.example .env
nano .env  # isi semua value

# Taruh credentials.json di folder yang sama
cp ~/Downloads/credentials.json .
```

### 4. Install & Jalankan

```bash
# Buat virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Jalankan
python bot.py
```

### 5. Cari Tahu Telegram User ID

Kirim pesan ke **@userinfobot** di Telegram untuk mengetahui User ID kamu.
Masukkan ke `ALLOWED_USER_IDS` di `.env`.

---

## Cara Pakai

### Mencatat Pengeluaran

Cukup kirim pesan ke bot:

| Input | Tercatat sebagai |
|-------|-----------------|
| `50000` | Rp 50.000 |
| `50.000 makan` | Rp 50.000 (makan) |
| `50k makan siang` | Rp 50.000 (makan siang) |
| `50rb transport` | Rp 50.000 (transport) |
| `1.5jt sewa kos` | Rp 1.500.000 (sewa kos) |

### Commands

| Command | Fungsi |
|---------|--------|
| `/start` | Mulai bot & lihat panduan |
| `/summary` | Ringkasan pengeluaran hari ini |
| `/monthly` | Laporan bulan ini (total per hari) |
| `/setbudget 5000000` | Set budget bulanan |
| `/budget` | Cek sisa budget + progress bar |
| `/undo` | Hapus catatan terakhir |
| `/help` | Bantuan |

---

## Deploy (Opsional)

Untuk menjalankan bot 24/7, bisa deploy ke:

### VPS (Recommended)
```bash
# Pakai systemd service
sudo nano /etc/systemd/system/finance-bot.service
```

```ini
[Unit]
Description=Telegram Finance Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/finance_bot
ExecStart=/home/youruser/finance_bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable finance-bot
sudo systemctl start finance-bot
```

### Railway / Render / Fly.io
Tambahkan `Procfile`:
```
worker: python bot.py
```

Set environment variables di dashboard platform masing-masing.

---

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Bot tidak merespon | Cek token & pastikan bot sudah di-start |
| Google Sheets error | Pastikan service account sudah di-share ke spreadsheet |
| `gspread.exceptions.APIError` | Cek quota Google Sheets API (100 requests/100 detik) |
| Budget tidak tersimpan setelah restart | Budget disimpan di memory; set ulang setelah restart |

---

## Lisensi

Proyek pribadi — bebas digunakan dan dimodifikasi.

