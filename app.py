import os
import uuid
import threading
import subprocess

from flask import (
    Flask,
    request,
    render_template,
    send_from_directory,
    jsonify,
    Response,
)

from werkzeug.utils import secure_filename

import numpy as np
import librosa
import soundfile as sf

import edge_tts

import pytesseract
from PIL import Image

from faster_whisper import WhisperModel


# =========================================================
# Flask App
# =========================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
SEPARATED_FOLDER = os.path.join(BASE_DIR, "separated")
WHISPER_CACHE = os.path.join(BASE_DIR, "whisper_cache")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SEPARATED_FOLDER, exist_ok=True)
os.makedirs(WHISPER_CACHE, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SEPARATED_FOLDER"] = SEPARATED_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


# =========================================================
# Allowed Extensions
# =========================================================

ALLOWED_AUDIO = {
    "mp3",
    "wav",
    "m4a",
    "ogg",
    "flac",
    "aac",
}

ALLOWED_IMAGE = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "bmp",
    "tiff",
}


def allowed_file(filename, allowed_extensions):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in allowed_extensions
    )


# =========================================================
# Whisper - Lazy Loading
# =========================================================

whisper_model = None
whisper_lock = threading.Lock()


def get_whisper_model():
    global whisper_model

    if whisper_model is None:
        with whisper_lock:
            if whisper_model is None:
                whisper_model = WhisperModel(
                    "tiny",
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=1,
                    num_workers=1,
                    download_root=WHISPER_CACHE,
                )

    return whisper_model


# =========================================================
# Home
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


# =========================================================
# Text To Speech Page
# =========================================================

@app.route("/text-to-speech")
def text_to_speech():
    return render_template("text-to-speech.html")


# =========================================================
# About
# =========================================================

@app.route("/about")
def about():
    return render_template("about.html")


# =========================================================
# Contact
# =========================================================

@app.route("/contact")
def contact():
    return render_template("contact.html")


# =========================================================
# Text To Persian Speech
# =========================================================

@app.route("/process-text", methods=["POST"])
def process_text():

    text = request.form.get("text", "").strip()

    if not text:
        return jsonify({
            "success": False,
            "error": "لطفاً متن را وارد کنید."
        }), 400

    try:

        filename = f"{uuid.uuid4().hex}.mp3"
        output_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        async def generate_speech():

            communicate = edge_tts.Communicate(
                text,
                "fa-IR-DilaraNeural"
            )

            await communicate.save(output_path)

        import asyncio

        asyncio.run(generate_speech())

        return jsonify({
            "success": True,
            "filename": filename,
            "download_url": f"/download/{filename}"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": f"خطا در تبدیل متن به صدا: {str(e)}"
        }), 500


# =========================================================
# Audio Processing
# =========================================================

@app.route("/process-audio", methods=["POST"])
def process_audio():

    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "فایل صوتی ارسال نشده است."
        }), 400

    file = request.files["audio"]

    if file.filename == "":
        return jsonify({
            "success": False,
            "error": "لطفاً یک فایل صوتی انتخاب کنید."
        }), 400

    if not allowed_file(file.filename, ALLOWED_AUDIO):
        return jsonify({
            "success": False,
            "error": "فرمت فایل صوتی پشتیبانی نمی‌شود."
        }), 400

    original_name = secure_filename(file.filename)

    unique_name = f"{uuid.uuid4().hex}_{original_name}"

    input_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_name
    )

    file.save(input_path)

    try:

        # Load audio as stereo
        y, sr = librosa.load(
            input_path,
            sr=None,
            mono=False
        )

        # Make sure audio has two channels
        if y.ndim == 1:

            y = np.vstack([y, y])

        left = y[0]
        right = y[1]

        # Approximate vocal extraction
        vocals = (left + right) / 2

        # Approximate instrumental extraction
        instrumental = (left - right) / 2

        vocals_filename = f"{uuid.uuid4().hex}_vocals.wav"
        instrumental_filename = (
            f"{uuid.uuid4().hex}_instrumental.wav"
        )

        vocals_path = os.path.join(
            app.config["SEPARATED_FOLDER"],
            vocals_filename
        )

        instrumental_path = os.path.join(
            app.config["SEPARATED_FOLDER"],
            instrumental_filename
        )

        sf.write(
            vocals_path,
            vocals,
            sr
        )

        sf.write(
            instrumental_path,
            instrumental,
            sr
        )

        return jsonify({
            "success": True,
            "vocals": vocals_filename,
            "instrumental": instrumental_filename,
            "vocals_url": f"/download/{vocals_filename}",
            "instrumental_url": f"/download/{instrumental_filename}"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": f"خطا در پردازش فایل صوتی: {str(e)}"
        }), 500


# =========================================================
# Speech To Text
# =========================================================

@app.route("/process-speech", methods=["POST"])
def process_speech():

    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "فایل صوتی ارسال نشده است."
        }), 400

    file = request.files["audio"]

    if file.filename == "":
        return jsonify({
            "success": False,
            "error": "لطفاً فایل صوتی را انتخاب کنید."
        }), 400

    if not allowed_file(file.filename, ALLOWED_AUDIO):
        return jsonify({
            "success": False,
            "error": "فرمت فایل صوتی پشتیبانی نمی‌شود."
        }), 400

    original_name = secure_filename(file.filename)

    unique_name = f"{uuid.uuid4().hex}_{original_name}"

    input_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_name
    )

    file.save(input_path)

    try:

        model = get_whisper_model()

        segments, info = model.transcribe(
            input_path,
            language="fa",
            task="transcribe",
            beam_size=1,
            best_of=1,
            temperature=0,
            vad_filter=True,
            condition_on_previous_text=False,
            without_timestamps=True,
        )

        text_parts = []

        for segment in segments:
            text_parts.append(segment.text)

        extracted_text = " ".join(text_parts).strip()

        return jsonify({
            "success": True,
            "text": extracted_text
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": f"خطا در تبدیل صدا به متن: {str(e)}"
        }), 500


# =========================================================
# Image To Text / OCR
# =========================================================

@app.route("/image-to-text", methods=["POST"])
def image_to_text():

    if "image" not in request.files:
        return jsonify({
            "success": False,
            "error": "تصویر ارسال نشده است."
        }), 400

    file = request.files["image"]

    if file.filename == "":
        return jsonify({
            "success": False,
            "error": "لطفاً یک تصویر انتخاب کنید."
        }), 400

    if not allowed_file(file.filename, ALLOWED_IMAGE):
        return jsonify({
            "success": False,
            "error": "فرمت تصویر پشتیبانی نمی‌شود."
        }), 400

    original_name = secure_filename(file.filename)

    unique_name = f"{uuid.uuid4().hex}_{original_name}"

    input_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_name
    )

    file.save(input_path)

    try:

        image = Image.open(input_path)

        image = image.convert("RGB")

        # Limit image size to reduce memory usage
        max_dimension = 1800

        width, height = image.size

        if max(width, height) > max_dimension:

            scale = max_dimension / max(width, height)

            new_width = int(width * scale)
            new_height = int(height * scale)

            image = image.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )

        # Convert to grayscale
        image = image.convert("L")

        extracted_text = pytesseract.image_to_string(
            image,
            lang="fas+eng",
            config="--psm 6",
            timeout=30
        )

        extracted_text = extracted_text.strip()

        return jsonify({
            "success": True,
            "text": extracted_text
        })

    except RuntimeError as e:

        return jsonify({
            "success": False,
            "error": "پردازش تصویر بیش از زمان مجاز طول کشید."
        }), 500

    except Exception as e:

        return jsonify({
            "success": False,
            "error": f"خطا در استخراج متن از تصویر: {str(e)}"
        }), 500


# =========================================================
# Download Files
# =========================================================

@app.route("/download/<path:filename>")
def download_file(filename):

    # First check uploads
    upload_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    if os.path.isfile(upload_path):

        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            filename,
            as_attachment=True
        )

    # Then check separated files
    separated_path = os.path.join(
        app.config["SEPARATED_FOLDER"],
        filename
    )

    if os.path.isfile(separated_path):

        return send_from_directory(
            app.config["SEPARATED_FOLDER"],
            filename,
            as_attachment=True
        )

    return "File not found", 404


# =========================================================
# Sitemap
# =========================================================

@app.route("/sitemap.xml")
def sitemap():

    pages = [
        "/",
        "/text-to-speech",
        "/about",
        "/contact",
    ]

    base_url = "https://rt-k9g5.onrender.com"

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]

    for page in pages:

        xml.append(
            f"""
            <url>
                <loc>{base_url}{page}</loc>
            </url>
            """
        )

    xml.append("</urlset>")

    return Response(
        "\n".join(xml),
        mimetype="application/xml"
    )


# =========================================================
# Robots.txt
# =========================================================

@app.route("/robots.txt")
def robots():

    content = """User-agent: *
Allow: /

Sitemap: https://rt-k9g5.onrender.com/sitemap.xml
"""

    return Response(
        content,
        mimetype="text/plain"
    )


# =========================================================
# Error Handlers
# =========================================================

@app.errorhandler(413)
def too_large(error):

    return jsonify({
        "success": False,
        "error": "حجم فایل بیش از حد مجاز است. حداکثر حجم فایل 50 مگابایت است."
    }), 413


@app.errorhandler(404)
def not_found(error):

    return jsonify({
        "success": False,
        "error": "صفحه موردنظر پیدا نشد."
    }), 404


@app.errorhandler(500)
def internal_error(error):

    return jsonify({
        "success": False,
        "error": "خطای داخلی سرور."
    }), 500


# =========================================================
# Run
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
