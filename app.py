import os
import time
import numpy as np
import librosa
import soundfile as sf

from flask import Flask, render_template, request, send_from_directory, Response
from gtts import gTTS


app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
SEPARATED_FOLDER = "separated"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SEPARATED_FOLDER, exist_ok=True)


# =========================
# صفحه اصلی
# =========================
@app.route("/")
def home():
    return render_template("index.html")


# =========================
# درباره ما
# =========================
@app.route("/about")
def about():
    return """
    <h1>درباره ما</h1>
    <p>ابزار آنلاین تبدیل متن به صدا و پردازش فایل صوتی.</p>
    """


# =========================
# تماس با ما
# =========================
@app.route("/contact")
def contact():
    return """
    <h1>تماس با ما</h1>
    <p>برای ارتباط با ما می‌توانید از این صفحه استفاده کنید.</p>
    """


# =========================
# تبدیل متن فارسی به صدای واقعی
# =========================
@app.route("/process-text", methods=["POST"])
def process_text():

    text = request.form.get("text_input", "").strip()

    if not text:
        return "متنی وارد نشده است."

    filename = f"speech_{int(time.time())}.mp3"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    try:

        # تبدیل متن فارسی به صدای واقعی
        tts = gTTS(
            text=text,
            lang="fa",
            slow=False
        )

        # ذخیره فایل صوتی
        tts.save(filepath)

        return render_template(
            "index.html",
            success_text="صدای فارسی با موفقیت ساخته شد.",
            speech_file=filename
        )

    except Exception as e:

        return f"خطا در تبدیل متن به صدا: {str(e)}"


# =========================
# پردازش فایل صوتی
# =========================
@app.route("/process-audio", methods=["POST"])
def process_audio():

    if "audio_file" not in request.files:
        return "فایلی انتخاب نشده است."

    file = request.files["audio_file"]

    if file.filename == "":
        return "فایلی انتخاب نشده است."

    filename = f"{int(time.time())}_{file.filename}"

    filepath = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    file.save(filepath)

    try:

        y, sr = librosa.load(
            filepath,
            sr=None,
            mono=False
        )

        # اگر فایل استریو باشد
        if y.ndim == 2 and y.shape[0] >= 2:

            left = y[0]
            right = y[1]

            # استخراج تقریبی وکال
            vocals = (left + right) / 2

            # استخراج تقریبی موسیقی
            instrumental = (left - right) / 2

            vocals_file = f"vocals_{int(time.time())}.wav"

            instrumental_file = (
                f"instrumental_{int(time.time())}.wav"
            )

            vocals_path = os.path.join(
                SEPARATED_FOLDER,
                vocals_file
            )

            instrumental_path = os.path.join(
                SEPARATED_FOLDER,
                instrumental_file
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

            return render_template(
                "index.html",
                success_text="پردازش فایل با موفقیت انجام شد.",
                vocals_file=vocals_file,
                instrumental_file=instrumental_file
            )

        else:

            return "برای جداسازی صدا، فایل استریو لازم است."

    except Exception as e:

        return f"خطا در پردازش فایل: {str(e)}"


# =========================
# دانلود فایل
# =========================
@app.route("/download/<path:filename>")
def download(filename):

    # بررسی پوشه uploads
    upload_path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    if os.path.exists(upload_path):

        return send_from_directory(
            UPLOAD_FOLDER,
            filename,
            as_attachment=True
        )

    # بررسی پوشه separated
    separated_path = os.path.join(
        SEPARATED_FOLDER,
        filename
    )

    if os.path.exists(separated_path):

        return send_from_directory(
            SEPARATED_FOLDER,
            filename,
            as_attachment=True
        )

    return "فایل پیدا نشد.", 404


# =========================
# Sitemap
# =========================
@app.route("/sitemap.xml")
def sitemap():

    base_url = "https://rt-k9g5.onrender.com"

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


# =========================
# Robots.txt
# =========================
@app.route("/robots.txt")
def robots():

    base_url = "https://rt-k9g5.onrender.com"

    robots_txt = f"""User-agent: *
Allow: /

Sitemap: {base_url}/sitemap.xml
"""

    return Response(
        robots_txt,
        mimetype="text/plain"
    )


# =========================
# اجرای برنامه
# =========================
if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
