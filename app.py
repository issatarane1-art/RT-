import os
import time
import asyncio
import numpy as np
import librosa
import soundfile as sf
import speech_recognition as sr

from flask import Flask, render_template, request, send_from_directory, Response
import edge_tts


app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
SEPARATED_FOLDER = "separated"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SEPARATED_FOLDER, exist_ok=True)


# ==========================================
# صفحه اصلی
# ==========================================
@app.route("/")
def home():
    return render_template("index.html")


# ==========================================
# درباره ما
# ==========================================
@app.route("/about")
def about():
    return """
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>درباره ما</title>
    </head>
    <body>
        <h1>درباره ما</h1>
        <p>ابزار آنلاین تبدیل متن به صدا، پردازش صوت و تبدیل صوت به متن.</p>
    </body>
    </html>
    """


# ==========================================
# تماس با ما
# ==========================================
@app.route("/contact")
def contact():
    return """
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>تماس با ما</title>
    </head>
    <body>
        <h1>تماس با ما</h1>
        <p>برای ارتباط با ما می‌توانید از این صفحه استفاده کنید.</p>
    </body>
    </html>
    """


# ==========================================
# تبدیل متن به صدای فارسی
# ==========================================
async def generate_persian_speech(text, filepath):

    voice = "fa-IR-DilaraNeural"

    communicate = edge_tts.Communicate(
        text,
        voice
    )

    await communicate.save(filepath)


@app.route("/process-text", methods=["POST"])
def process_text():

    text = request.form.get("text_input", "").strip()

    if not text:
        return "متنی وارد نشده است."

    filename = f"speech_{int(time.time())}.mp3"

    filepath = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    try:

        asyncio.run(
            generate_persian_speech(
                text,
                filepath
            )
        )

        return render_template(
            "index.html",
            success_text="صدای فارسی با موفقیت ساخته شد.",
            speech_file=filename
        )

    except Exception as e:

        return f"خطا در تبدیل متن به صدا: {str(e)}"


# ==========================================
# پردازش و جداسازی صوت
# ==========================================
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

        y, sr_rate = librosa.load(
            filepath,
            sr=None,
            mono=False
        )

        if y.ndim == 2 and y.shape[0] >= 2:

            left = y[0]
            right = y[1]

            vocals = (left + right) / 2
            instrumental = (left - right) / 2

            vocals_file = (
                f"vocals_{int(time.time())}.wav"
            )

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
                sr_rate
            )

            sf.write(
                instrumental_path,
                instrumental,
                sr_rate
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


# ==========================================
# تبدیل صوت به متن فارسی
# ==========================================
@app.route("/speech-to-text", methods=["POST"])
def speech_to_text():

    if "speech_file" not in request.files:
        return "فایل صوتی انتخاب نشده است."

    file = request.files["speech_file"]

    if file.filename == "":
        return "فایل صوتی انتخاب نشده است."

    original_filename = file.filename

    input_filename = (
        f"stt_{int(time.time())}_{original_filename}"
    )

    input_path = os.path.join(
        UPLOAD_FOLDER,
        input_filename
    )

    file.save(input_path)

    wav_path = os.path.join(
        UPLOAD_FOLDER,
        f"stt_{int(time.time())}.wav"
    )

    try:

        # تبدیل فایل صوتی به WAV استاندارد
        audio_data, sample_rate = librosa.load(
            input_path,
            sr=16000,
            mono=True
        )

        sf.write(
            wav_path,
            audio_data,
            sample_rate,
            subtype="PCM_16"
        )

        recognizer = sr.Recognizer()

        with sr.AudioFile(wav_path) as source:

            audio = recognizer.record(source)

        # تشخیص گفتار فارسی
        text = recognizer.recognize_google(
            audio,
            language="fa-IR"
        )

        return render_template(
            "index.html",
            transcribed_text=text,
            success_text="صوت با موفقیت به متن تبدیل شد."
        )

    except sr.UnknownValueError:

        return render_template(
            "index.html",
            error_text="صدای واضحی برای تبدیل به متن پیدا نشد."
        )

    except sr.RequestError as e:

        return render_template(
            "index.html",
            error_text=f"خطا در ارتباط با سرویس تشخیص گفتار: {str(e)}"
        )

    except Exception as e:

        return render_template(
            "index.html",
            error_text=f"خطا در تبدیل صوت به متن: {str(e)}"
        )

    finally:

        # حذف فایل موقت WAV
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except:
                pass


# ==========================================
# دانلود فایل
# ==========================================
@app.route("/download/<path:filename>")
def download(filename):

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


# ==========================================
# Sitemap
# ==========================================
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


# ==========================================
# Robots
# ==========================================
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


# ==========================================
# اجرای برنامه
# ==========================================
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
