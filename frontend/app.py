from flask import Flask, request, Response
import requests as req

app = Flask(__name__)

ROUTES = {
    "ms1": "http://localhost:5051",
    "ms2": "http://localhost:5052",
    "ms3": "http://localhost:5053",
}


@app.route("/<service>", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE"])
@app.route("/<service>/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy(service, path):
    if service not in ROUTES:
        return {"status": "error", "message": f"Unknown service '{service}'. Available: ms1, ms2, ms3"}, 404
    target_url = f"{ROUTES[service]}/{path}"
    try:
        resp = req.request(
            method=request.method,
            url=target_url,
            headers={k: v for k, v in request.headers if k.lower() != "host"},
            params=request.args,
            json=request.get_json(silent=True),
            timeout=10,
        )
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "application/json"))
    except req.exceptions.ConnectionError:
        return {"status": "error", "message": f"Service '{service}' is not reachable"}, 503
    except req.exceptions.Timeout:
        return {"status": "error", "message": f"Service '{service}' timed out"}, 504


@app.route("/")
def index():
    return {
        "status": "ok",
        "message": "PBL0902 Front End (APPX) — Microservice Car",
        "services": {
            "ms1": "http://localhost:5051 — CRUD cars (DB-A, SiteA)",
            "ms2": "http://localhost:5052 — CRUD brands (DB-A, SiteA)",
            "ms3": "http://localhost:5053 — CRUD dealers (DB-B, SiteB)",
        },
        "usage": {
            "list_cars":    "GET /ms1/cars",
            "create_car":   "POST /ms1/cars  {carname, carbrand, carmodel, carprice}",
            "update_car":   "PUT /ms1/cars/<id>",
            "delete_car":   "DELETE /ms1/cars/<id>",
            "search_cars":  "GET /ms1/cars/search?q=<keyword>",
        }
    }


if __name__ == "__main__":
    app.run(port=5000, debug=True)
