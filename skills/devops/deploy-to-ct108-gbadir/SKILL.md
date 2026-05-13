---
name: deploy-to-ct108-gbadir
description: Deploy dashboard atau project ke LXC Container 108 (Webserver) di Proxmox pvegbadir. Include stop host services, deploy di CT, verify LAN access.
trigger: deploy dashboard ke CT 108, deploy project roti stnk, deploy ke LXC 108
---

# Deploy ke CT 108 (gbadir-pve / LXC Webserver)

## Akses

| Item | Value |
|------|-------|
| Proxmox Host | `100.68.172.35` |
| User | `root` |
| Password | `6201919` |
| CT ID | `108` |
| CT Name | `Webserver` |
| CT IP LAN | `192.168.1.14` |
| CT SSH via Proxmox | `pct exec 108 -- ...` |

## ⚠️ PERATURAN PENTING - READ ONLY di Proxmox Host

**DILARANG keras utak-atik services di Proxmox Host tanpa izin explicit dari user.**

Akses ke Proxmox (100.68.172.35):
- ✅ BOLEH: Cek status, monitoring, read logs
- ✅ BOLEH: Push files, start/stop services di LXC 108 (CT) via `pct exec`
- ❌ TIDAK BOLEH: Matikan/mulai services di Proxmox Host langsung
- ❌ TIDAK BOLEH: Ubah konfigurasi apapun di Proxmox Host
- ❌ TIDAK BOLEH: git push/pull/install di Proxmox Host atau CT tanpa izin

**Semua operasi deployment dan modifikasi dilakukan di Mac Mini lokal, bukan di Proxmox/CT.**

---

## ⚠️ NAMING CONFLICT - server.py

**MASALAH:** STNK dan ROTI Monitor KEDUA-DUANYA pakai nama file `server.py` di CT 108.

Saat deploy/kill dengan `pkill -f 'server.py'`, KEDUA-DUANYA ikut mati!

**SOLUSI:**
- Untuk kill hanya SATU service, gunakan PID spesifik — JANGAN pakai `pkill -f 'server.py'`
- Cek PID dulu: `ps aux | grep server.py | grep -v grep`
- Kill by PID: `kill <PID>`
- Atau rename service file di masa depan (misal: `roti_server.py` vs `stnk_server.py`)

**Contoh aman untuk restart ROTI saja (tanpa matikan STNK):**
```bash
# Get ROTI PID
ps aux | grep roti-monitor/server.py | grep -v grep
# Kill spesifik ROTI
kill <ROTI_PID>
# Start ROTI
pct exec 108 -- bash -c 'cd /opt/roti-monitor && ./venv/bin/python server.py > /tmp/roti.log 2>&1 &'
```

---

## Services yang jalan di CT 108

### 1. Transfer files to CT 108
```bash
# Use pct push - DO NOT use scp to Proxmox /tmp (CT has separate filesystem)
cat /local/server.py | sshpass -p '6201919' ssh root@100.68.172.35 "pct exec 108 -- bash -c 'cat > /opt/roti-monitor/server.py'"
# OR
pct push 108 /local/server.py /opt/roti-monitor/server.py
```

### 2. Stop service in CT 108
```bash
pct exec 108 -- pkill -f 'server.py'
# ⚠️ CAUTION: This kills ALL server.py processes (both ROTI and STNK if both running)
# Better approach - kill by specific PID if known
```

### 3. Start service in CT 108
```bash
pct exec 108 -- bash -c 'cd /opt/roti-monitor && /opt/roti-monitor/venv/bin/python server.py > /tmp/roti.log 2>&1 &'
```

### 4. Database schema migration (if needed)
```python
# If "no such table: standard_history" error on CSV export
python_script = """
import sqlite3
db = sqlite3.connect('roti_monitor.db')
db.execute('''
    CREATE TABLE IF NOT EXISTS standard_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        old_standard REAL NOT NULL,
        new_standard REAL NOT NULL,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
db.commit()
"""
# Pipe to CT 108 and run
```

### 5. Verify service
```bash
pct exec 108 -- ss -tlnp | grep 8787
curl http://192.168.1.14:8787/
```

---

## ⚠️ KNOWN ISSUES & GOTCHAS

1. **`pkill -f server.py` kills BOTH ROTI and STNK** — they share the same filename `server.py`. Always restart BOTH after any change.
2. **CT 108 has separate /tmp** — scp to Proxmox /tmp won't work for CT. Use `pct push` instead.
3. **Database tables must be created manually** — `standard_history` table not auto-created on git pull. Must be added via Python script.
4. **git pull doesn't work in CT** — CT 108 doesn't have git repo. Push files via `pct push` or `cat | ssh` method.
5. **Port stuck di CT 108 — `kill -9` tidak bisa digunakan di LXC container.** Jika port lama masih绑定 (address already in use) dan proses tidak bisa di-kill, SOLUSI: **ganti port** (misal 8787 → 8788) daripada mencoba memaksa membunuh proses.

## ⚠️ Port Stuck di CT 108 — Ganti Port Sebagai Solusi

Jika `ss -tlnp | grep <port>` menunjukkan port masih digunakan tapi proses tidak bisa di-kill:

```
# Gejala: port masih listen padahal sudah coba kill
pct exec 108 -- ss -tlnp | grep 8787
# Output: python3 127.0.0.1:8787 ... (tidak bisa di-kill dengan kill -9)

# SOLUSI: Ganti port di server.py dari 8787 ke 8788
# Edit server.py:
#   PORT = 8788  # ganti dari 8787
#   app.run(host='0.0.0.0', port=PORT, debug=False)
```

Lalu push ulang file dan start ulang service. Ini lebih cepat daripada menghabiskan waktu mencoba kill proses yang stuck.

---

## Full Deploy Workflow (when updating)

```bash
# 1. Kill both services (they share server.py filename)
sshpass -p '6201919' ssh root@100.68.172.35 "pct exec 108 -- pkill -f 'server.py'"

# 2. Push updated files to CT 108
pct push 108 /local/server.py /opt/roti-monitor/server.py
pct push 108 /local/index.html /opt/roti-monitor/index.html

# 3. Start BOTH services
sshpass -p '6201919' ssh root@100.68.172.35 "pct exec 108 -- bash -c 'cd /opt/roti-monitor && /opt/roti-monitor/venv/bin/python server.py > /tmp/roti.log 2>&1 &'"
sshpass -p '6201919' ssh root@100.68.172.35 "pct exec 108 -- bash -c 'cd /opt/stnk-modern && /usr/bin/python3 server.py > /tmp/stnk.log 2>&1 &'"

# 4. Verify
pct exec 108 -- ss -tlnp | grep -E '8087|8787'
```

---

## Services yang jalan di CT 108

| Service | Port | Project Path | Start Command |
|---------|------|--------------|---------------|
| STNK | 8087 | `/opt/stnk-modern/` | `cd /opt/stnk-modern && python3 server.py > /tmp/stnk.log 2>&1 &` |
| ROTI | 8788 | `/opt/roti-monitor/` | `cd /opt/roti-monitor && ./venv/bin/python server.py > /tmp/roti.log 2>&1 &` |

## Services yang jalan di Proxmox Host (sebelum dipindahkan)

| Service | Port | PID | Path |
|---------|------|-----|------|
| STNK | 8087 | (varies) | `/opt/stnk-modern/` |
| ROTI | 8787 | (varies) | `/opt/roti-monitor/` |

## Topologi Network

```
Kantor (192.168.1.0/24)
├── Router: 192.168.1.253
├── Proxmox Host (pvegbadir): 192.168.1.20 (vmbr0)
│   └── LXC 108 (Webserver): 192.168.1.14 (eth0)
└── Tailscale: 100.68.172.35 (tailnet only)
```

## Problem yang pernah terjadi

1. **STNK/ROTI jalan di Proxmox Host** — tidak bisa diakses dari LAN karyawan (connection refused)
2. **Tailscale Serve intercept port 8087** — jadi "tailnet only", karyawan LAN tidak bisa akses
3. **Solusi**: Pindahkan services dari Host ke LXC 108 — biar accessible langsung via LAN

## Deployment Steps

### 1. Check Current State
```bash
sshpass -p '6201919' ssh -o User=root 100.68.172.35 "ss -tlnp | grep -E '8087|8787'"
```

### 2. Check services di Proxmox Host
```bash
sshpass -p '6201919' ssh -o User=root 100.68.172.35 "ps aux | grep server.py | grep -v grep"
```

### 3. Stop services di Host (cek PIDs dulu)
```bash
# Get PIDs first
sshpass -p '6201919' ssh -o User=root 100.68.172.35 "ps aux | grep server.py | grep -v grep"
# Kill dengan PID yang benar
sshpass -p '6201919' ssh -o User=root 100.68.172.35 "kill <PID_STNK> <PID_ROTI>"
```

### 3b. Upload files to CT (⚠️ CRITICAL: pct push, NOT scp+cp)

Proxmox Host `/tmp` ≠ CT `/tmp` — they are **separate filesystems**.

❌ WRONG (will fail):
```bash
scp file root@100.68.172.35:/tmp/
pct exec 108 -- cp /tmp/file /dest/  # CT /tmp doesn't have it!
```

✅ CORRECT — Use `pct push`:
```bash
# Push files directly into CT filesystem
pct push 108 /path/to/local/file /path/in/ct/file
```

### 4. Start services di LXC 108
```bash
sshpass -p '6201919' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@100.68.172.35 "pct exec 108 -- bash -c 'cd /opt/roti-monitor && /opt/roti-monitor/venv/bin/python server.py > /tmp/roti.log 2>&1 &'"
```

### 5. Verify services running di CT 108
```bash
sshpass -p '6201919' ssh -o User=root 100.68.172.35 "pct exec 108 -- ss -tlnp | grep -E '8087|8787'"
```

### 6. Test LAN access (dari Proxmox ke CT 108)
```bash
sshpass -p '6201919' ssh -o User=root 100.68.172.35 "curl -s --connect-timeout 5 http://192.168.1.14:8087/ | head -3"
sshpass -p '6201919' ssh -o User=root 100.68.172.35 "curl -s --connect-timeout 5 http://192.168.1.14:8787/ | head -3"
```

## Database Schema Migration Gotcha

When deploying updated code to CT 108 with an **existing database**, `init_db()` uses `CREATE TABLE IF NOT EXISTS` — which only creates tables that DON'T exist. It does NOT add new tables that were added to `init_db()` after the database was first created.

**Symptom:** API returns `sqlite3.OperationalError: no such table: <table_name>`

**Fix:** Manually create the missing table:
```bash
# On CT 108, run via Python script:
python -c "
import sqlite3
db = sqlite3.connect('/opt/roti-monitor/roti_monitor.db')
db.execute('''CREATE TABLE IF NOT EXISTS standard_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    old_standard REAL NOT NULL,
    new_standard REAL NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
db.commit()
"
```

Alternatively, delete the old DB and let `init_db()` recreate it fresh (loses data).

---

## Verifikasi Setelah Deploy

Services di CT 108 bisa stop sendiri (crash, reboot, dll). Setelah deploy, selalu verify:

```bash
# Cek port listening
pct exec 108 -- ss -tlnp | grep -E '8087|8788'

# Cek process running
pct exec 108 -- ps aux | grep server.py | grep -v grep

# Test LAN HTTP
curl -s --connect-timeout 3 http://192.168.1.14:8087/ | head -3
curl -s --connect-timeout 3 http://192.168.1.14:8788/ | head -3
```

**Jika service tidak running → start ulang manual:**
```bash
pct exec 108 -- bash -c 'cd /opt/stnk-modern && /usr/bin/python3 server.py > /tmp/stnk.log 2>&1 &'
pct exec 108 -- bash -c 'cd /opt/roti-monitor && /opt/roti-monitor/venv/bin/python server.py > /tmp/roti.log 2>&1 &'
```

---

## Notes Penting

- **LXC 108 sudah ada files** di `/opt/stnk-modern/` dan `/opt/roti-monitor/` — mungkin sudah deployed
- **Tailscale Serve di Host** intercept port 8087 → "tailnet only" — ini yang bikin LAN tidak bisa akses
- **VM dan CT lain tidak terganggu** — hanya STNK dan ROTI yang affected saat switching
- **Downtime sementara** 1-2 menit saat switch

## Jika perlu restart services di CT 108

```bash
# Find and kill existing
sshpass -p '6201919' ssh -o User=root 100.68.172.35 "pct exec 108 -- pkill -f 'server.py'"
sleep 2
# Start ulang
sshpass -p '6201919' ssh -o User=root 100.68.172.35 "pct exec 108 -- bash -c 'cd /opt/stnk-modern && /usr/bin/python3 server.py > /tmp/stnk.log 2>&1 &'"
sshpass -p '6201919' ssh -o User=root 100.68.172.35 "pct exec 108 -- bash -c 'cd /opt/roti-monitor && /opt/roti-monitor/venv/bin/python server.py > /tmp/roti.log 2>&1 &'"
```