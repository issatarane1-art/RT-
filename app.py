import os
import time
import numpy as np
import librosa
import soundfile as sf

from flask import Flask, render_template, request, send_from_directory, Response
from gtts import gTTS


app = Flask(__name__)

# پوشه‌های فایل
UPLOAD_FOLDER = "uploads"
SEPARATED_FOLDER = "separated"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SEPARATED_FOLDER, exist_ok=True)


# =========================
# صفحه اصلی
# =========================

@app.route("/")
def index():
    return render_template("index.html")


# =========================
# درباره ما
# =========================

@app.route("/about")
def about():
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>درباره ما</title>
    </head>
    <body>
        <h1>درباره سامانه پردازش صوت</h1>
        <p>
            این سامانه برای تبدیل متن به صوت و پردازش فایل‌های صوتی طراحی شده است.
        </p>
        <a href="/">بازگشت به صفحه اصلی</a>
    </body>
    </html>
    """


# =========================
# تماس با ما
# =========================

@app.route("/contact")
def contact():
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>تماس با ما</title>
    </head>
    <body>
        <h1>تماس با ما</h1>
        <p>
            برای ارتباط با ما می‌توانید از اطلاعات تماس موجود در سایت استفاده کنید.
        </p>
        <a href="/">بازگشت به صفحه اصلی</a>
    </body>
    </html>
    """


# =========================
# تبدیل متن به صوت
# =========================

@app.route("/process-text", methods=["POST"])
def process_text():

    text = request.form.get("text_input", "").strip()

    if not text:
        return render_template(
            "index.html",
            error_text="لطفاً متن خود را وارد کنید."
        )

    try:

        # نام فایل
        filename = f"speech_{int(time.time())}.mp3"

        filepath = os.path.join(UPLOAD_FOLDER, filename)

        # تبدیل متن فارسی به صدای واقعی
        tts = gTTS(
            text=text,
            lang="fa",
            slow=False
        )

        tts.save(filepath)

        return render_template(
            "index.html",
            speech_file=filename,
            success_text="متن با موفقیت به صوت تبدیل شد."
        )

    except Exception as e:

        print("TTS ERROR:", e)

        return render_template(
            "index.html",
            error_text="در تبدیل متن به صوت خطایی رخ داد. لطفاً دوباره تلاش کنید."
        )


# =========================
# پردازش فایل صوتی
# =========================

@app.route("/process-audio", methods=["POST"])
def process_audio():

    if "file" not in request.files:

        return render_template(
            "index.html",
            error_audio="فایلی انتخاب نشده است."
        )

    file = request.files["file"]

    if file.filename == "":

        return render_template(
            "index.html",
            error_audio="لطفاً یک فایل صوتی انتخاب کنید."
        )

    try:

        filename = file.filename

        input_path = os.path.join(
            UPLOAD_FOLDER,
            filename
        )

        file.save(input_path)

        # خواندن فایل صوتی
        y, sr = librosa.load(
            input_path,
            sr=None,
            mono=False
        )

        # اگر صدا استریو باشد
        if y.ndim == 2:

            # کانال‌ها
            left = y[0]
            right = y[1]

            # روش ساده برای پردازش کانال‌ها
            instrumental = (left - right) / 2
            vocals = (left + right) / 2

        else:

            instrumental = y
            vocals = y

        base_name = os.path.splitext(filename)[0]

        instrumental_filename = (
            base_name + "_instrumental.wav"
        )

        vocals_filename = (
            base_name + "_vocals.wav"
        )

        instrumental_path = os.path.join(
            SEPARATED_FOLDER,
            instrumental_filename
        )

        vocals_path = os.path.join(
            SEPARATED_FOLDER,
            vocals_filename
        )

        # ذخیره فایل‌ها
        sf.write(
            instrumental_path,
            instrumental,
            sr
        )

        sf.write(
            vocals_path,
            vocals,
            sr
        )

        return render_template(
            "index.html",
            success_audio="پردازش فایل صوتی انجام شد.",
            instrumental=instrumental_filename,
            vocals=vocals_filename
        )

    except Exception as e:

        print("AUDIO ERROR:", e)

        return render_template(
            "index.html",
            error_audio="پردازش فایل صوتی با خطا مواجه شد."
        )


# =========================
# دانلود فایل
# =========================

@app.route("/download/<path:filename>")
def download(filename):

    # اول در uploads جستجو می‌کنیم
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

    # سپس در separated
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

    return "File not found", 404


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

    content = """User-agent: *
Allow: /

Sitemap: https://rt-k9g5.onrender.com/sitemap.xml
"""

    return Response(
        content,
        mimetype="text/plain"
    )


# =========================
# اجرای برنامه
# =========================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 5000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
