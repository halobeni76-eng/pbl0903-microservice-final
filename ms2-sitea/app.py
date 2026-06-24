"""
MS2 — SiteA — Port 5052
Tanggung jawab: CRUD data brand/pabrikan mobil (tabel 'brands') pada DB-A
"""
from flask import Flask, jsonify, request
import sqlite3
import requests
from requests.adapters import HTTPAdapter, Retry

app = Flask(__name__)
DB_PATH = "db-a.db"

# ── Cross-site config (PBL0903) ────────────────────────────────────
MS3_URL = "http://localhost:5053"


def _session_with_retry():
    """HTTP session dengan retry 2x dan backoff 0.5s."""
    session = requests.Session()
    retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503])
    session.mount("http://", HTTPAdapter(max_retries=retries))
    return session


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS brands (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            brandname TEXT NOT NULL,
            country   TEXT NOT NULL,
            founded   INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


@app.route("/")
def index():
    return jsonify({"service": "MS2", "site": "SiteA", "db": "DB-A", "table": "brands"})


@app.route("/brands", methods=["GET"])
def list_brands():
    conn = get_db()
    rows = conn.execute("SELECT * FROM brands ORDER BY id").fetchall()
    conn.close()
    return jsonify({"status": "success", "count": len(rows), "data": [dict(r) for r in rows]}), 200


@app.route("/brands/<int:brand_id>", methods=["GET"])
def get_brand(brand_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"status": "error", "message": "Not found"}), 404
    return jsonify({"status": "success", "data": dict(row)}), 200


@app.route("/brands", methods=["POST"])
def create_brand():
    data = request.get_json(silent=True) or {}
    name    = str(data.get("brandname", "")).strip()
    country = str(data.get("country", "")).strip()
    founded = data.get("founded", 0)
    if not all([name, country, founded]):
        return jsonify({"status": "error", "message": "brandname, country, founded required"}), 400
    try:
        founded = int(founded)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "founded must be a number (year)"}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO brands (brandname, country, founded) VALUES (?,?,?)",
        (name, country, founded),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Brand created", "id": cur.lastrowid}), 201


@app.route("/brands/<int:brand_id>", methods=["PUT"])
def update_brand(brand_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    row = conn.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"status": "error", "message": "Not found"}), 404
    name    = str(data.get("brandname", row["brandname"])).strip()
    country = str(data.get("country",   row["country"])).strip()
    try:
        founded = int(data.get("founded", row["founded"]))
    except (ValueError, TypeError):
        founded = row["founded"]
    conn.execute(
        "UPDATE brands SET brandname=?, country=?, founded=? WHERE id=?",
        (name, country, founded, brand_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Brand updated"}), 200


@app.route("/brands/<int:brand_id>", methods=["DELETE"])
def delete_brand(brand_id):
    conn = get_db()
    cur = conn.execute("DELETE FROM brands WHERE id = ?", (brand_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"status": "error", "message": "Not found"}), 404
    return jsonify({"status": "success", "message": "Brand deleted"}), 200


@app.route("/brands/search", methods=["GET"])
def search_brands():
    keyword = request.args.get("q", "").strip()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM brands WHERE brandname LIKE ? OR country LIKE ?",
        (f"%{keyword}%", f"%{keyword}%"),
    ).fetchall()
    conn.close()
    return jsonify({"status": "success", "count": len(rows), "data": [dict(r) for r in rows]}), 200


# ── CROSS-SITE: Combined Data (PBL0903 — Opsi A: Direct REST Call) ────────────
@app.route("/brands/combined", methods=["GET"])
def combined_brands():
    """
    Menampilkan data gabungan:
      - data_site_a: brands dari DB-A (lokal MS2)
      - data_site_b: dealers dari DB-B (via REST call ke MS3, SiteB)
    Graceful degradation: jika MS3 tidak terjangkau, tetap return data lokal + flag error.
    """
    # Data lokal DB-A
    conn = get_db()
    local_rows = conn.execute("SELECT * FROM brands ORDER BY id").fetchall()
    conn.close()
    local_data = [dict(r) for r in local_rows]

    # Data dari SiteB via REST call ke MS3
    remote_data = []
    remote_error = None
    try:
        session = _session_with_retry()
        resp = session.get(f"{MS3_URL}/dealers", timeout=5)
        if resp.ok:
            remote_data = resp.json().get("data", [])
        else:
            remote_error = f"MS3 returned HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        remote_error = "MS3 (SiteB) timed out after 5s"
    except requests.exceptions.ConnectionError:
        remote_error = "MS3 (SiteB) is not reachable"

    response = {
        "status": "success",
        "source": {
            "site_a_service": "MS2",
            "site_a_table": "brands",
            "site_a_count": len(local_data),
            "site_b_service": "MS3",
            "site_b_table": "dealers",
            "site_b_count": len(remote_data),
        },
        "data_site_a": local_data,
        "data_site_b": remote_data,
    }
    if remote_error:
        response["site_b_warning"] = remote_error

    return jsonify(response), 200


if __name__ == "__main__":
    init_db()
    app.run(port=5052, debug=True)
