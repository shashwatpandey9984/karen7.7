import base64
import binascii
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta

import cv2
import numpy as np
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from code_debugger.api import code_debugger_bp
from news_service import fetch_current_affairs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
CORS(app)

app.register_blueprint(code_debugger_bp)

# =====================
# Globals for face presence alarm
# =====================
last_seen = datetime.now()
alert_triggered = False

# Load Haar cascade (bundled with OpenCV) with fallback
def load_cascade():
    # primary location from cv2 package
    try:
        cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        if os.path.exists(cascade_path):
            clf = cv2.CascadeClassifier(cascade_path)
            if not clf.empty():
                logger.info("Loaded Haar cascade from cv2.data.haarcascades")
                return clf
    except (AttributeError, OSError, cv2.error):
        logger.exception("Could not load cascade from cv2.data")

    # fallback: check local file in project (static or project root)
    local_paths = [
        os.path.join(os.path.dirname(__file__), "haarcascade_frontalface_default.xml"),
        os.path.join(os.path.dirname(__file__), "static", "haarcascade_frontalface_default.xml"),
    ]
    for p in local_paths:
        if os.path.exists(p):
            clf = cv2.CascadeClassifier(p)
            if not clf.empty():
                logger.info("Loaded Haar cascade from %s", p)
                return clf

    logger.error("Haar cascade not found or failed to load.")
    return None

face_cascade = load_cascade()

# helper: decode base64 image to cv2 image
def b64_to_cv2(b64_string):
    if not isinstance(b64_string, str):
        return None
    b64_data = re.sub(r"^data:image/.+;base64,", "", b64_string)
    try:
        img_data = base64.b64decode(b64_data)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except (binascii.Error, cv2.error, TypeError, ValueError):
        logger.exception("Failed to decode base64 image")
        return None

@app.route("/api/detect_faces", methods=["POST"])
def detect_faces():
    global last_seen, alert_triggered
    if face_cascade is None:
        return jsonify({"error": "face_cascade_not_loaded", "message": "Face detection not available"}), 503

    data = request.get_json(force=True, silent=True)
    if not data or "image" not in data:
        return jsonify({"error": "missing_image"}), 400

    img = b64_to_cv2(data["image"])
    if img is None:
        return jsonify({"error": "decode_failed"}), 400

    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        faces_list = [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)} for (x, y, w, h) in faces]

        # update last_seen if face(s) detected
        if len(faces_list) > 0:
            last_seen = datetime.now()
            alert_triggered = False

        return jsonify({
            "faces": faces_list,
            "width": int(img.shape[1]),
            "height": int(img.shape[0])
        })
    except cv2.error as error:
        logger.exception("detect_faces error")
        return jsonify({"error": "exception", "message": str(error)}), 500

@app.route("/api/news", methods=["POST"])
def get_news():
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"error": True, "message": "Enter a topic or ask for current affairs."}), 400

    result, status = fetch_current_affairs(query, data.get("date"))
    return jsonify(result), status

# Serve frontend: try templates first, fallback to static/index.html
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route("/")
def home():
    return send_from_directory(PROJECT_DIR, "index.html")

@app.route("/index.js")
def javascript():
    return send_from_directory(PROJECT_DIR, "index.js")

@app.route("/style.css")
def stylesheet():
    return send_from_directory(PROJECT_DIR, "style.css")

@app.route("/config.js")
def frontend_config():
    api_base_url = os.environ.get("KAREN_API_BASE_URL", "").rstrip("/")
    config = (
        f"window.KAREN_API_BASE_URL = {json.dumps(api_base_url)};\n"
        "window.KAREN_API_ENABLED = true;\n"
    )
    return Response(config, mimetype="application/javascript")

@app.route("/alarm.mp3")
def alarm_audio():
    return send_from_directory(PROJECT_DIR, "alarm.mp3")

@app.route("/check")
def check_alert():
    return jsonify({"alert": alert_triggered})

# Test route to set/clear alert flag (for development/testing)
@app.route("/set_alert", methods=["POST"])
def set_alert():
    global alert_triggered, last_seen
    data = request.get_json(force=True, silent=True) or {}
    val = data.get("alert")
    if isinstance(val, bool):
        alert_triggered = val
        if val:
            # if alert set from client, don't update last_seen
            logger.info("Alert set via /set_alert -> %s", alert_triggered)
        else:
            last_seen = datetime.now()
        return jsonify({"ok": True, "alert": alert_triggered})
    return jsonify({"ok": False, "message": "send JSON {\"alert\": true/false}"}), 400

def alert_monitor():
    global alert_triggered
    while True:
        if datetime.now() - last_seen > timedelta(seconds=30):
            if not alert_triggered:
                alert_triggered = True
                logger.info("No face detected for 30 seconds; alert set")
        else:
            if alert_triggered:
                alert_triggered = False
        time.sleep(2)

# start background monitor (daemon so it stops with app)
threading.Thread(target=alert_monitor, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)