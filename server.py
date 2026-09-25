import io
import os
import tempfile
import zipfile
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from androguard.misc import AnalyzeAPK

app = Flask(__name__)
CORS(app)

# Render Free has limited memory. Keep uploads deliberately small.
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "35"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# Indicators are intentionally transparent and simple.
INDICATORS = {
    "billing": [
        "billingclient", "com.android.vending.billing", "iap",
        "purchase", "purchases", "inapp"
    ],
    "ads": [
        "admob", "adsense", "rewardedad", "interstitialad",
        "bannerad", "google_mobile_ads"
    ],
    "tracking": [
        "appsflyer", "adjust", "firebase.analytics", "analytics",
        "amplitude", "branch.io"
    ],
    "network": [
        "okhttp", "retrofit", "volley", "httpurlconnection",
        "webview", "javax.net"
    ],
}

CATEGORY_AR = {
    "billing": "شراء وفوترة",
    "ads": "إعلانات",
    "tracking": "تحليلات/تتبع",
    "network": "شبكة",
}


def safe_text(value):
    return str(value or "").lower()


def classify(text):
    t = safe_text(text)
    hits = []
    for category, terms in INDICATORS.items():
        matched = [term for term in terms if term in t]
        if matched:
            hits.append((category, matched))
    return hits


def make_result(category, name, code, class_name="", source="DEX",
                return_type="—", percent=0):
    return {
        "name": name,
        "category": CATEGORY_AR.get(category, category),
        "percent": int(max(1, min(99, percent))),
        "code": code,
        "class_name": class_name,
        "source": source,
        "return_type": return_type,
    }


def analyze_one_apk(apk_bytes, filename):
    # AnalyzeAPK accepts a file path more reliably across Androguard versions.
    with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as tmp:
        tmp.write(apk_bytes)
        path = tmp.name

    results = []
    try:
        a, d, dx = AnalyzeAPK(path)

        # Scan strings from every DEX.
        strings = []
        for dex in d if isinstance(d, list) else [d]:
            try:
                strings.extend([s.getValue() for s in dex.getStrings()])
            except Exception:
                pass

        # String indicators.
        for value in strings:
            text = safe_text(value)
            for category, terms in INDICATORS.items():
                for term in terms:
                    if term in text:
                        results.append(make_result(
                            category=category,
                            name=term,
                            code=value[:500],
                            class_name="—",
                            source=filename,
                            percent=72 if category == "billing" else 58,
                        ))
                        break

        # Method/class indicators. Keep this bounded for the free tier.
        seen = set()
        for dex in d if isinstance(d, list) else [d]:
            try:
                classes = dex.getClasses()
            except Exception:
                classes = []
            for cls in classes:
                try:
                    class_name = cls.getName()
                    methods = cls.getMethods()
                except Exception:
                    continue
                for method in methods:
                    try:
                        name = method.getName()
                        sig = f"{class_name}->{name}"
                        hit = classify(sig)
                    except Exception:
                        continue
                    for category, terms in hit:
                        key = (category, sig)
                        if key in seen:
                            continue
                        seen.add(key)
                        results.append(make_result(
                            category=category,
                            name=name,
                            code=sig,
                            class_name=class_name,
                            source=filename,
                            percent=82 if category == "billing" else 63,
                        ))
                        if len(results) >= 300:
                            break
                    if len(results) >= 300:
                        break
                if len(results) >= 300:
                    break
            if len(results) >= 300:
                break

        # De-duplicate exact entries and cap output.
        unique = {}
        for item in results:
            key = (item["category"], item["code"], item["class_name"])
            unique[key] = item
        return list(unique.values())[:300]
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def extract_apks(data):
    """Return (filename, bytes) pairs for APK or APKS/ZIP uploads."""
    if data[:2] != b"PK":
        return [("upload.apk", data)]

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [
            n for n in z.namelist()
            if n.lower().endswith(".apk") and not n.endswith("/")
        ]
        if not names:
            raise ValueError("ملف ZIP/APKS لا يحتوي على APK")
        return [(Path(n).name, z.read(n)) for n in names[:10]]


@app.get("/")
def home():
    return jsonify({
        "success": True,
        "app": "PRECISION ENGINE",
        "message": "APK analyzer is running"
    })


@app.get("/api/health")
def health():
    return jsonify({"success": True, "status": "online"})


@app.post("/api/analyze")
def analyze():
    uploaded = request.files.get("file")
    mode = request.form.get("mode", "game")

    if not uploaded or not uploaded.filename:
        return jsonify({"success": False, "error": "لم يتم رفع ملف"}), 400

    data = uploaded.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return jsonify({
            "success": False,
            "error": f"حجم الملف أكبر من الحد المسموح ({MAX_UPLOAD_MB} MB)"
        }), 413

    try:
        apk_items = extract_apks(data)
        all_results = []
        for filename, apk_bytes in apk_items:
            all_results.extend(analyze_one_apk(apk_bytes, filename))

        # Game/app mode currently changes the UI only; keep one analyzer.
        all_results.sort(key=lambda x: x["percent"], reverse=True)

        return jsonify({
            "success": True,
            "mode": mode,
            "file": uploaded.filename,
            "apk_count": len(apk_items),
            "results": all_results[:300]
        })
    except zipfile.BadZipFile:
        return jsonify({"success": False, "error": "ملف APKS/ZIP غير صالح"}), 400
    except Exception as exc:
        app.logger.exception("Analysis failed")
        return jsonify({
            "success": False,
            "error": "فشل تحليل الملف: " + str(exc)[:300]
        }), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
