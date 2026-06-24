# PBL0903 — Microservice Final: Cross-Site Connectivity

## Framework
**Python[1]** — Flask

## Deskripsi
Lanjutan dari PBL0902. Menambahkan kemampuan akses data **lintas site** antara SiteA dan SiteB menggunakan **Opsi A: Direct REST Call antar Service**.

## Solusi Cross-Site: Opsi A — Direct REST Call

**Alasan memilih Opsi A:**
- Paling sederhana dan konsisten dengan stack yang sudah ada (semua service sudah REST API Flask)
- Tidak butuh infrastruktur tambahan (message broker, API gateway kompleks)
- Mudah diuji dan di-debug langsung dengan curl
- Trade-off: tight coupling antar service — jika salah satu down, endpoint combined akan terdampak. Dimitigasi dengan graceful degradation (timeout + return data lokal tetap 200).

## Arsitektur Final (Cross-Site)

```
        SiteA ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
       │                                           │
       │   ┌─────┐  5051  ┌──────┐                │
       │   │ MS1 │────────▶│ DB-A │                │
       │   └─────┘        └──────┘                │
       │                                           │
       │   ┌─────┐  5052  ┌──────┐                │
       │   │ MS2 │────────▶│ DB-A │                │
       │   └──┬──┘        └──────┘                │
       │      │ REST GET /dealers (cross-site)     │
       └──────┼─────────────────────────────────── ┘
              │
       ┌──────▼───────────┐  ← Direct REST Call (Opsi A)
       │  http://MS3:5053  │
       └──────┬────────────┘
              │ REST GET /cars (cross-site)
       ┌──────┼─────────────────────────────────── ┐
       │      │                                     │
       │   ┌──┴──┐  5053  ┌──────┐                 │
       │   │ MS3 │────────▶│ DB-B │                 │
       │   └─────┘        └──────┘                  │
        SiteB ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

## Aturan Cross-Site

| Service | Akses DB Lokal | Akses Cross-Site |
|---|---|---|
| **MS1** | DB-A (cars) | — tidak berubah — |
| **MS2** | DB-A (brands) | Memanggil MS3 untuk data dealers (DB-B) |
| **MS3** | DB-B (dealers) | Memanggil MS1 untuk data cars (DB-A) |

## Cara Menjalankan (4 terminal terpisah)

```bash
cd ms1-sitea && python app.py   # port 5051
cd ms2-sitea && python app.py   # port 5052
cd ms3-siteb && python app.py   # port 5053
cd frontend   && python app.py  # port 5000
```

## Endpoint Cross-Site

```bash
# MS2: gabungan brands (DB-A) + dealers dari MS3 (DB-B)
curl http://localhost:5000/ms2/brands/combined

# MS3: gabungan dealers (DB-B) + cars dari MS1 (DB-A)
curl http://localhost:5000/ms3/dealers/combined

# Uji graceful degradation: matikan MS3, panggil ms2/brands/combined
# → Harus tetap return 200 dengan data_site_b: [] + site_b_warning: "MS3 (SiteB) is not reachable"
```

## Fitur Graceful Degradation

- Setiap cross-site call diberi **timeout 5 detik**
- Menggunakan **Retry(total=2, backoff_factor=0.5)** sebelum dianggap gagal
- Jika site lain tidak terjangkau, response tetap `{"status": "success"}` dengan `data_site_x: []` dan `site_x_warning: "<pesan error>"`
- **Tidak ada hard crash / HTTP 500** karena koneksi cross-site gagal
