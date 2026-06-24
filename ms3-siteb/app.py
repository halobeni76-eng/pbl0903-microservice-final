"""
MS3 — SiteB — Port 5053
Tanggung jawab: CRUD data dealer (tabel 'dealers') pada DB-B
"""
from flask import Flask, jsonify, request
import sqlite3
import requests
from requests.adapters import HTTPAdapter, Retry

app = Flask(__name__)
DB_PATH = "db-b.db"

# ── Cross-site config (PBL0903) ────────────────────────────────────
MS1_URL = "http://localhost:5051"


def _session_with_retry():
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
        CREATE TABLE IF NOT EXISTS dealers (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            dealername TEXT NOT NULL,
            city       TEXT NOT NULL,
            phone      TEXT NOT NULL,
            carbrand   TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


@app.route("/")
def index():
    return jsonify({"service": "MS3", "site": "SiteB", "db": "DB-B", "table": "dealers"})


@app.route("/dealers", methods=["GET"])
def list_dealers():
    conn = get_db()
    rows = conn.execute("SELECT * FROM dealers ORDER BY id").fetchall()
    conn.close()
    return jsonify({"status": "success", "count": len(rows), "data": [dict(r) for r in rows]}), 200


@app.route("/dealers/<int:dealer_id>", methods=["GET"])
def get_dealer(dealer_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM dealers WHERE id = ?", (dealer_id,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"status": "error", "message": "Not found"}), 404
    return jsonify({"status": "success", "data": dict(row)}), 200


@app.route("/dealers", methods=["POST"])
def create_dealer():
    data = request.get_json(silent=True) or {}
    name     = str(data.get("dealername", "")).strip()
    city     = str(data.get("city", "")).strip()
    phone    = str(data.get("phone", "")).strip()
    carbrand = str(data.get("carbrand", "")).strip()
    if not all([name, city, phone, carbrand]):
        return jsonify({"status": "error", "message": "dealername, city, phone, carbrand required"}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO dealers (dealername, city, phone, carbrand) VALUES (?,?,?,?)",
        (name, city, phone, carbrand),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Dealer created", "id": cur.lastrowid}), 201


@app.route("/dealers/<int:dealer_id>", methods=["PUT"])
def update_dealer(dealer_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    row = conn.execute("SELECT * FROM dealers WHERE id = ?", (dealer_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"status": "error", "message": "Not found"}), 404
    name     = str(data.get("dealername", row["dealername"])).strip()
    city     = str(data.get("city",       row["city"])).strip()
    phone    = str(data.get("phone",      row["phone"])).strip()
    carbrand = str(data.get("carbrand",   row["carbrand"])).strip()
    conn.execute(
        "UPDATE dealers SET dealername=?, city=?, phone=?, carbrand=? WHERE id=?",
        (name, city, phone, carbrand, dealer_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Dealer updated"}), 200


@app.route("/dealers/<int:dealer_id>", methods=["DELETE"])
def delete_dealer(dealer_id):
    conn = get_db()
    cur = conn.execute("DELETE FROM dealers WHERE id = ?", (dealer_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"status": "error", "message": "Not found"}), 404
    return jsonify({"status": "success", "message": "Dealer deleted"}), 200


@app.route("/dealers/search", methods=["GET"])
def search_dealers():
    keyword = request.args.get("q", "").strip()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM dealers WHERE dealername LIKE ? OR city LIKE ? OR carbrand LIKE ?",
        (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
    ).fetchall()
    conn.close()
    return jsonify({"status": "success", "count": len(rows), "data": [dict(r) for r in rows]}), 200


# ── CROSS-SITE: Combined Data (PBL0903 — Opsi A: Direct REST Call) ────────────
@app.route("/dealers/combined", methods=["GET"])
def combined_dealers():
    """
    Menampilkan data gabungan:
      - data_site_b: dealers dari DB-B (lokal MS3)
      - data_site_a: cars dari DB-A (via REST call ke MS1, SiteA)
    Graceful degradation: jika MS1 tidak terjangkau, tetap return data lokal + flag error.
    """
    # Data lokal DB-B
    conn = get_db()
    local_rows = conn.execute("SELECT * FROM dealers ORDER BY id").fetchall()
    conn.close()
    local_data = [dict(r) for r in local_rows]

    # Data dari SiteA via REST call ke MS1
    remote_data = []
    remote_error = None
    try:
        session = _session_with_retry()
        resp = session.get(f"{MS1_URL}/cars", timeout=5)
        if resp.ok:
            remote_data = resp.json().get("data", [])
        else:
            remote_error = f"MS1 returned HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        remote_error = "MS1 (SiteA) timed out after 5s"
    except requests.exceptions.ConnectionError:
        remote_error = "MS1 (SiteA) is not reachable"

    response = {
        "status": "success",
        "source": {
            "site_b_service": "MS3",
            "site_b_table": "dealers",
            "site_b_count": len(local_data),
            "site_a_service": "MS1",
            "site_a_table": "cars",
            "site_a_count": len(remote_data),
        },
        "data_site_b": local_data,
        "data_site_a": remote_data,
    }
    if remote_error:
        response["site_a_warning"] = remote_error

    return jsonify(response), 200


if __name__ == "__main__":
    init_db()
    app.run(port=5053, debug=True)
