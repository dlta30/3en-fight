```python
import os
import json
import secrets
import hashlib
import csv
import io
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, session,
    render_template, flash, send_file, abort, jsonify
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET", "change-this-secret")
PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")
SCANNER_API_KEY = os.getenv("SCANNER_API_KEY", "")

DATA = "data"
UP = os.path.join(DATA, "uploads")
DB = os.path.join(DATA, "sessions.json")
SCANS_DB = os.path.join(DATA, "scans.json")

os.makedirs(UP, exist_ok=True)

TERMS = [
    "EULEN", "Menyo", "Tiago", "FalloutMenu", "CobraMenu",
    "DOPAMINE MENU", "Phantom", "ZENTRIX", "vMenu", "KekHack",
    "RedEngine", "Mod Menu", "hack_fivem", "fivem esp",
    "wallhack", "injector", "Lua Executor", "GH Injector",
    "Extreme Injector", "Winject", "CheatEngine",
    "UnknownCheats", "DUMPER", "DECRYPTER", "BYPASS",
    "RESOURCE BLOCKER", "RXEXV3", "No_Recoil.rpf",
    "aML.lua", "pedaccuracy.meta", "weaponcomponents.meta",
    "weaponanimation.meta", "bsk_skills.rpf", "quickEnter.rpf"
]


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp, path)


def dbread():
    return read_json(DB, {"sessions": []})


def dbwrite(data):
    write_json(DB, data)


def scans_read():
    return read_json(SCANS_DB, {"scans": []})


def scans_write(data):
    write_json(SCANS_DB, data)


def admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


@app.route("/")
@admin
def home():
    ss = sorted(
        dbread()["sessions"],
        key=lambda x: x.get("created", ""),
        reverse=True
    )
    scans = sorted(
        scans_read()["scans"],
        key=lambda x: x.get("created", ""),
        reverse=True
    )
    return render_template("dashboard.html", ss=ss, scans=scans)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if secrets.compare_digest(
            request.form.get("password", ""),
            PASSWORD
        ):
            session["admin"] = True
            return redirect("/")
        flash("كلمة المرور غير صحيحة")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/create", methods=["POST"])
@admin
def create():
    player = request.form.get("player", "").strip()[:100]
    if not player:
        flash("اكتب اسم اللاعب")
        return redirect("/")

    try:
        mins = max(5, min(int(request.form.get("minutes", 10)), 1440))
    except (ValueError, TypeError):
        mins = 10

    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(24)

    item = {
        "id": secrets.token_hex(5),
        "token": token,
        "player": player,
        "created": now.isoformat(),
        "expires": (now + timedelta(minutes=mins)).isoformat(),
        "status": "بانتظار الملفات",
        "results": []
    }

    data = dbread()
    data["sessions"].append(item)
    dbwrite(data)

    return redirect(url_for("detail", sid=item["id"]))


@app.route("/session/<sid>")
@admin
def detail(sid):
    item = next(
        (x for x in dbread()["sessions"] if x["id"] == sid),
        None
    )
    if not item:
        abort(404)

    return render_template(
        "session.html",
        x=item,
        up=url_for("upload", token=item["token"], _external=True)
    )


@app.route("/upload/<token>", methods=["GET", "POST"])
def upload(token):
    data = dbread()
    item = next(
        (
            x for x in data["sessions"]
            if secrets.compare_digest(x["token"], token)
        ),
        None
    )

    if not item:
        abort(404)

    if datetime.fromisoformat(item["expires"]) < datetime.now(timezone.utc):
        return "انتهت صلاحية الرابط", 410

    if request.method == "POST":
        files = [
            f for f in request.files.getlist("files")
            if f and f.filename
        ]

        if not files:
            flash("اختر ملفات")
            return redirect(request.url)

        folder = os.path.join(UP, item["id"])
        os.makedirs(folder, exist_ok=True)

        for f in files[:200]:
            name = secure_filename(f.filename) or "upload.bin"
            path = os.path.join(
                folder, secrets.token_hex(4) + "_" + name
            )
            h = hashlib.sha256()
            size = 0

            with open(path, "wb") as output:
                while True:
                    chunk = f.stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    h.update(chunk)
                    output.write(chunk)

            hits = [
                term for term in TERMS
                if term.lower() in name.lower()
            ]

            item["results"].append({
                "file": name,
                "size": size,
                "sha256": h.hexdigest(),
                "hits": hits
            })

        item["status"] = "اكتمل الرفع"
        dbwrite(data)
        flash("تم تحليل أسماء الملفات")
        return redirect(request.url)

    return render_template("upload.html", x=item)


@app.route("/report/<sid>.csv")
@admin
def report(sid):
    item = next(
        (x for x in dbread()["sessions"] if x["id"] == sid),
        None
    )
    if not item:
        abort(404)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Player", "Filename", "SizeBytes",
        "SHA256", "Indicators", "Disclaimer"
    ])

    for result in item["results"]:
        writer.writerow([
            item["player"],
            result["file"],
            result["size"],
            result["sha256"],
            "; ".join(result["hits"]),
            "Filename indicator only; not proof"
        ])

    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="3eN_report.csv"
    )


# يستقبل نتائج برنامج Scanner ويحفظها في سجل الموقع المركزي.
@app.route("/api/scan-results", methods=["POST"])
def receive_scan_results():
    if not SCANNER_API_KEY:
        return jsonify({
            "ok": False,
            "error": "SCANNER_API_KEY is not configured"
        }), 503

    supplied_key = request.headers.get("X-Scanner-Key", "")
    if not secrets.compare_digest(supplied_key, SCANNER_API_KEY):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    if not request.is_json:
        return jsonify({"ok": False, "error": "JSON required"}), 400

    payload = request.get_json(silent=True) or {}
    player = str(payload.get("player", "")).strip()[:100]
    results = payload.get("results", [])

    if not player:
        return jsonify({"ok": False, "error": "Player name required"}), 400

    if not isinstance(results, list) or len(results) > 5000:
        return jsonify({"ok": False, "error": "Invalid results"}), 400

    safe_results = []
    for result in results:
        if not isinstance(result, dict):
            continue

        filename = str(result.get("file", result.get("filename", "")))[:255]
        raw_hits = result.get("hits", result.get("indicators", []))

        if not isinstance(raw_hits, list):
            raw_hits = []

        safe_results.append({
            "file": filename,
            "hits": [str(hit)[:100] for hit in raw_hits[:50]],
            "size": max(0, int(result.get("size", 0) or 0))
                    if str(result.get("size", 0) or 0).isdigit()
                    else 0
        })

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": secrets.token_hex(8),
        "player": player,
        "created": now,
        "status": "اكتمل الفحص",
        "total_files": len(safe_results),
        "flagged_files": sum(1 for r in safe_results if r["hits"]),
        "results": safe_results,
        "note": "تطابق اسم الملف مؤشر يحتاج مراجعة وليس دليلاً قاطعاً على الغش."
    }

    data = scans_read()
    data["scans"].append(record)
    scans_write(data)

    return jsonify({
        "ok": True,
        "scan_id": record["id"],
        "message": "Scan results saved"
    }), 201


@app.route("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    app.run()
```
