from flask import Flask, render_template, request, jsonify, Response
from detector import TrafficSignDetector
import cv2
import numpy as np
import base64
import threading
import time
import json
import os
from werkzeug.utils import secure_filename

# 可以使用这个网络摄像头
# rtsp://admin:admin@10.32.89.127:8554/live

app = Flask(__name__)
detector = TrafficSignDetector()

camera = None
camera_lock = threading.Lock()
is_streaming = False

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


class Camera:
    def __init__(self, source="local", url=None, video_path=None):
        self.source = source
        self.url = url
        self.video_path = video_path
        self.cap = None
        self.frame = None
        self.frame_lock = threading.Lock()

    def start(self):
        if self.source == "local":
            self.cap = cv2.VideoCapture(0)
        elif self.source == "ip":
            self.cap = cv2.VideoCapture(self.url)
        elif self.source == "file":
            self.cap = cv2.VideoCapture(self.video_path)

        if not self.cap.isOpened():
            raise RuntimeError("无法打开视频源")

        threading.Thread(target=self._capture_loop, daemon=True).start()

    def _capture_loop(self):
        global is_streaming
        while is_streaming:
            ret, frame = self.cap.read()
            if ret:
                with self.frame_lock:
                    self.frame = frame
                if self.source == "file" and self.cap.get(cv2.CAP_PROP_POS_FRAMES) == self.cap.get(
                    cv2.CAP_PROP_FRAME_COUNT
                ):
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            time.sleep(1 / 30)

    def get_frame(self):
        with self.frame_lock:
            return self.frame.copy() if self.frame is not None else None

    def release(self):
        if self.cap:
            self.cap.release()


def process_frame(frame):
    detections = detector.detect(frame)
    print(detections)
    filtered_detections = sorted(
        [det for det in detections if det["confidence"] >= 0.5],
        key=lambda x: x["distance"],
    )[:3]

    results = []
    for det in filtered_detections:
        
        x1, y1, x2, y2 = det["bbox"]
        print(frame.shape[0], frame.shape[1])
        x1 = max(0, int(x1.item()))
        y1 = max(0, int(y1.item()))
        x2 = min(frame.shape[1], int(x2.item()))
        y2 = min(frame.shape[0], int(y2.item()))
        print(y1, y2, x1, x2)
        sign_image = frame[y1:y2, x1:x2]

        if sign_image.size == 0:
            continue

        _, buffer = cv2.imencode(".jpg", sign_image)
        image_base64 = base64.b64encode(buffer).decode("utf-8")

        results.append(
            {
                "image": image_base64,
                "type": det["type"],
                "distance": det["distance"],
                "confidence": round(float(det["confidence"].item()) * 100, 2),
            }
        )

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        label = f"{det['type']} {det['distance']:.1f}m {det['confidence']*100:.0f}%"
        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return frame, results


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/start_stream", methods=["POST"])
def start_stream():
    global camera, is_streaming

    try:
        stream_type = request.form.get("type")

        with camera_lock:
            if camera:
                camera.release()

            if stream_type == "camera":
                source = request.form.get("source")
                url = request.form.get("url")
                camera = Camera(source=source, url=url)
            else:
                if "video" not in request.files:
                    return jsonify({"status": "error", "message": "No video file"}), 400

                file = request.files["video"]
                if file.filename == "" or not allowed_file(file.filename):
                    return jsonify({"status": "error", "message": "Invalid file"}), 400

                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)

                camera = Camera(source="file", video_path=filepath)

            is_streaming = True
            camera.start()
            return jsonify({"status": "success"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/stop_stream", methods=["POST"])
def stop_stream():
    global camera, is_streaming
    with camera_lock:
        is_streaming = False
        if camera:
            camera.release()
            camera = None
    return jsonify({"status": "success"})


@app.route("/video_feed")
def video_feed():
    def generate():
        global camera, is_streaming
        while True:
            if not is_streaming:
                break

            with camera_lock:
                if camera is None:
                    break

                frame = camera.get_frame()
                if frame is None:
                    continue

                processed_frame, detections = process_frame(frame)

                _, buffer = cv2.imencode(".jpg", processed_frame)
                frame_base64 = base64.b64encode(buffer).decode("utf-8")

                data = {"frame": frame_base64, "detections": detections}

                yield f"data: {json.dumps(data)}\n\n"

            time.sleep(1 / 30)

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=False, host="10.32.25.161", port=5000, threaded=True)
