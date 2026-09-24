import os
import uuid
import threading

from flask import Flask, render_template, request, send_from_directory, Response
from werkzeug.utils import secure_filename

import numpy as np
import soundfile as sf
import librosa
import edge_tts
import pytesseract

from PIL import Image, ImageOps

# Whisper را فقط هنگام نیاز بارگذاری می‌کنیم
from faster_whisper import WhisperModel


# =========================================================
# Flask
# =========================================================

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
SEPARATED_FOLDER = os.path.join(BASE_DIR, "separated")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SEPARATED_FOLDER, exist_ok=True)


# =========================================================
# Whisper
# =========================================================

whisper_model = None
whisper_lock = threading.Lock()


def get_whisper_model():
    """
    مدل Whisper فقط زمانی ساخته می‌شود که واقعاً
    کاربر از قابلیت صدا به متن استفاده کند.
    """

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
                    download_root=os.path.join(BASE_DIR, "whisper_cache")
                )

    return whisper_model


# =========================================================
# Home
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html",
        audio_file=None,
        instrumental_file=None,
        vocal_file=None,
        transcribed_text=None,
        image_text=None,
        error=None
    )


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
# Text To Speech
# =========================================================

@app.route("/process-text", methods=["POST"])
def process_text():

    text = request.form.get("text", "").strip()

    if not text:

        return render_template(
            "index.html",
            error="لطفاً متنی وارد کنید.",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )

    # محدود کردن متن برای جلوگیری از مصرف بیش از حد منابع
    if len(text) > 5000:

        return render_template(
            "index.html",
            error="متن واردشده خیلی طولانی است. لطفاً حداکثر ۵۰۰۰ کاراکتر وارد کنید.",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )

    filename = secure_filename(
        f"tts_{uuid.uuid4().hex}.mp3"
    )

    filepath = os.path.join(UPLOAD_FOLDER, filename)

    try:

        voice = "fa-IR-DilaraNeural"

        communicate = edge_tts.Communicate(
            text,
            voice
        )

        # اجرای async بدون نیاز به تغییر ساختار Flask
        import asyncio

        asyncio.run(
            communicate.save(filepath)
        )

        return render_template(
            "index.html",
            audio_file=filename,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None,
            error=None
        )

    except Exception as e:

        return render_template(
            "index.html",
            error=f"خطا در تبدیل متن به صدا: {str(e)}",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )


# =========================================================
# Audio Processing
# =========================================================

@app.route("/process-audio", methods=["POST"])
def process_audio():

    if "audio" not in request.files:

        return render_template(
            "index.html",
            error="فایل صوتی انتخاب نشده است.",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )

    file = request.files["audio"]

    if not file or file.filename == "":

        return render_template(
            "index.html",
            error="لطفاً یک فایل صوتی انتخاب کنید.",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )

    original_name = secure_filename(file.filename)

    if not original_name:

        return render_template(
            "index.html",
            error="نام فایل معتبر نیست.",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )

    input_filename = f"{uuid.uuid4().hex}_{original_name}"

    input_path = os.path.join(
        UPLOAD_FOLDER,
        input_filename
    )

    file.save(input_path)

    try:

        # خواندن فایل صوتی
        audio, sample_rate = librosa.load(
            input_path,
            sr=None,
            mono=False
        )

        # اگر فایل Mono باشد
        if audio.ndim == 1:

            audio = np.expand_dims(
                audio,
                axis=0
            )

        # روش ساده برای جداسازی تقریبی
        # این روش AI Source Separation واقعی نیست.
        if audio.shape[0] >= 2:

            left = audio[0]
            right = audio[1]

            vocals = (left + right) / 2
            instrumental = (left - right) / 2

        else:

            vocals = audio[0]
            instrumental = np.zeros_like(vocals)

        vocal_filename = f"vocals_{uuid.uuid4().hex}.wav"
        instrumental_filename = f"instrumental_{uuid.uuid4().hex}.wav"

        vocal_path = os.path.join(
            SEPARATED_FOLDER,
            vocal_filename
        )

        instrumental_path = os.path.join(
            SEPARATED_FOLDER,
            instrumental_filename
        )

        sf.write(
            vocal_path,
            vocals,
            sample_rate
        )

        sf.write(
            instrumental_path,
            instrumental,
            sample_rate
        )

        return render_template(
            "index.html",
            audio_file=None,
            vocal_file=vocal_filename,
            instrumental_file=instrumental_filename,
            transcribed_text=None,
            image_text=None,
            error=None
        )

    except Exception as e:

        return render_template(
            "index.html",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None,
            error=f"خطا در پردازش فایل صوتی: {str(e)}"
        )


# =========================================================
# Speech To Text
# =========================================================

@app.route("/speech-to-text", methods=["POST"])
def speech_to_text():

    if "audio" not in request.files:

        return render_template(
            "index.html",
            error="فایل صوتی انتخاب نشده است.",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )

    file = request.files["audio"]

    if not file or file.filename == "":

        return render_template(
            "index.html",
            error="لطفاً یک فایل صوتی انتخاب کنید.",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )

    original_name = secure_filename(file.filename)

    if not original_name:

        return render_template(
            "index.html",
            error="نام فایل معتبر نیست.",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )

    filename = f"stt_{uuid.uuid4().hex}_{original_name}"

    input_path = os.path.join(
        UPLOAD_FOLDER,
        filename
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
            without_timestamps=True
        )

        text_parts = []

        for segment in segments:

            text = segment.text.strip()

            if text:

                text_parts.append(text)

        transcribed_text = " ".join(
            text_parts
        ).strip()

        if not transcribed_text:

            transcribed_text = "متنی از فایل صوتی تشخیص داده نشد."

        return render_template(
            "index.html",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=transcribed_text,
            image_text=None,
            error=None
        )

    except Exception as e:

        return render_template(
            "index.html",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None,
            error=f"خطا در تبدیل صدا به متن: {str(e)}"
        )


# =========================================================
# Image To Text / OCR
# =========================================================

@app.route("/image-to-text", methods=["POST"])
def image_to_text():

    if "image" not in request.files:

        return render_template(
            "index.html",
            error="تصویری انتخاب نشده است.",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )

    file = request.files["image"]

    if not file or file.filename == "":

        return render_template(
            "index.html",
            error="لطفاً یک تصویر انتخاب کنید.",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )

    original_name = secure_filename(file.filename)

    if not original_name:

        return render_template(
            "index.html",
            error="نام فایل معتبر نیست.",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None
        )

    filename = f"ocr_{uuid.uuid4().hex}_{original_name}"

    input_path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    file.save(input_path)

    try:

        # -------------------------------------------------
        # باز کردن تصویر
        # -------------------------------------------------

        image = Image.open(
            input_path
        )

        # تبدیل به RGB
        if image.mode != "RGB":

            image = image.convert("RGB")

        # -------------------------------------------------
        # محدود کردن اندازه تصویر
        # برای جلوگیری از مصرف شدید RAM
        # -------------------------------------------------

        max_size = 1800

        width, height = image.size

        if width > max_size or height > max_size:

            scale = min(
                max_size / width,
                max_size / height
            )

            new_width = max(
                1,
                int(width * scale)
            )

            new_height = max(
                1,
                int(height * scale)
            )

            image = image.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )

        # -------------------------------------------------
        # تبدیل تصویر به خاکستری
        # -------------------------------------------------

        image = ImageOps.grayscale(
            image
        )

        # -------------------------------------------------
        # OCR
        # -------------------------------------------------

        extracted_text = pytesseract.image_to_string(
            image,
            lang="fas+eng",
            config="--psm 6",
            timeout=30
        )

        extracted_text = extracted_text.strip()

        if not extracted_text:

            extracted_text = (
                "متنی در تصویر پیدا نشد. "
                "لطفاً تصویر واضح‌تر و با کیفیت بالاتر انتخاب کنید."
            )

        return render_template(
            "index.html",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=extracted_text,
            error=None
        )

    except RuntimeError as e:

        return render_template(
            "index.html",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None,
            error="پردازش OCR بیش از حد طول کشید. لطفاً تصویر کوچک‌تر و واضح‌تری انتخاب کنید."
        )

    except Exception as e:

        return render_template(
            "index.html",
            audio_file=None,
            instrumental_file=None,
            vocal_file=None,
            transcribed_text=None,
            image_text=None,
            error=f"خطا در استخراج متن تصویر: {str(e)}"
        )


# =========================================================
# Download
# =========================================================

@app.route("/download/<path:filename>")
def download(filename):

    # اول پوشه uploads
    uploads_path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    if os.path.isfile(uploads_path):

        return send_from_directory(
            UPLOAD_FOLDER,
            filename,
            as_attachment=True
        )

    # سپس separated
    separated_path = os.path.join(
        SEPARATED_FOLDER,
        filename
    )

    if os.path.isfile(separated_path):

        return send_from_directory(
            SEPARATED_FOLDER,
            filename,
            as_attachment=True
        )

    return "File not found", 404


# =========================================================
# Sitemap
# =========================================================

@app.route("/sitemap.xml")
def sitemap():

    base_url = request.url_root.rstrip("/")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">

    <url>
        <loc>{base_url}/</loc>
    </url>

    <url>
        <loc>{base_url}/about</loc>
    </url>

    <url>
        <loc>{base_url}/contact</loc>
    </url>

</urlset>
"""

    return Response(
        xml,
        mimetype="application/xml"
    )


# =========================================================
# Robots
# =========================================================

@app.route("/robots.txt")
def robots():

    base_url = request.url_root.rstrip("/")

    robots_txt = f"""User-agent: *
Allow: /

Sitemap: {base_url}/sitemap.xml
"""

    return Response(
        robots_txt,
        mimetype="text/plain"
    )


# =========================================================
# Error handlers
# =========================================================

@app.errorhandler(413)
def too_large(error):

    return render_template(
        "index.html",
        error="حجم فایل خیلی زیاد است. حداکثر حجم فایل ۵۰ مگابایت است.",
        audio_file=None,
        instrumental_file=None,
        vocal_file=None,
        transcribed_text=None,
        image_text=None
    ), 413


@app.errorhandler(500)
def internal_error(error):

    return render_template(
        "index.html",
        error="خطای داخلی سرور رخ داد. لطفاً دوباره تلاش کنید.",
        audio_file=None,
        instrumental_file=None,
        vocal_file=None,
        transcribed_text=None,
        image_text=None
    ), 500


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
        port=port,
        debug=False
    )
