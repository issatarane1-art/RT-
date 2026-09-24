import os
import time
import asyncio

import numpy as np
import librosa
import soundfile as sf
import speech_recognition as sr
import pytesseract

from PIL import Image, ImageEnhance, ImageFilter

from flask import Flask, render_template, request, send_from_directory, Response

import edge_tts


app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
SEPARATED_FOLDER = "separated"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SEPARATED_FOLDER, exist_ok=True)


# =========================================================
# صفحه اصلی
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# درباره ما
# =========================================================

@app.route("/about")
def about():
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>درباره ما</title>
    </head>
    <body>
        <h1>درباره ما</h1>

        <p>
            ابزار آنلاین تبدیل متن به صدا،
            پردازش صوت، تبدیل صوت به متن و تبدیل عکس به متن.
        </p>

        <a href="/">بازگشت به صفحه اصلی</a>
    </body>
    </html>
    """


# =========================================================
# تماس با ما
# =========================================================

@app.route("/contact")
def contact():
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>تماس با ما</title>
    </head>
    <body>
        <h1>تماس با ما</h1>

        <p>
            برای ارتباط با ما می‌توانید از این صفحه استفاده کنید.
        </p>

        <a href="/">بازگشت به صفحه اصلی</a>
    </body>
    </html>
    """


# =========================================================
# تبدیل متن به صدا
# =========================================================

async def generate_persian_speech(text, filepath):

    voice = "fa-IR-DilaraNeural"

    communicate = edge_tts.Communicate(
        text,
        voice
    )

    await communicate.save(filepath)


@app.route("/process-text", methods=["POST"])
def process_text():

    text = request.form.get(
        "text_input",
        ""
    ).strip()

    if not text:

        return render_template(
            "index.html",
            error_text="لطفاً ابتدا متن را وارد کنید."
        )

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

        return render_template(
            "index.html",
            error_text=f"خطا در تبدیل متن به صدا: {str(e)}"
        )


# =========================================================
# پردازش فایل صوتی
# =========================================================

@app.route("/process-audio", methods=["POST"])
def process_audio():

    if "audio_file" not in request.files:

        return render_template(
            "index.html",
            error_text="فایل صوتی انتخاب نشده است."
        )

    file = request.files["audio_file"]

    if file.filename == "":

        return render_template(
            "index.html",
            error_text="فایل صوتی انتخاب نشده است."
        )

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

        if y.ndim != 2 or y.shape[0] < 2:

            return render_template(
                "index.html",
                error_text="برای این نوع جداسازی، فایل صوتی استریو لازم است."
            )

        left = y[0]
        right = y[1]

        vocals = (left + right) / 2

        instrumental = (left - right) / 2

        vocals_file = f"vocals_{int(time.time())}.wav"

        instrumental_file = f"instrumental_{int(time.time())}.wav"

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

    except Exception as e:

        return render_template(
            "index.html",
            error_text=f"خطا در پردازش فایل صوتی: {str(e)}"
        )

    finally:

        if os.path.exists(filepath):

            try:
                os.remove(filepath)

            except:
                pass


# =========================================================
# تبدیل صوت به متن
# =========================================================

@app.route("/speech-to-text", methods=["POST"])
def speech_to_text():

    if "speech_file" not in request.files:

        return render_template(
            "index.html",
            error_text="فایل صوتی انتخاب نشده است."
        )

    file = request.files["speech_file"]

    if file.filename == "":

        return render_template(
            "index.html",
            error_text="فایل صوتی انتخاب نشده است."
        )

    input_filename = (
        f"stt_{int(time.time())}_{file.filename}"
    )

    input_path = os.path.join(
        UPLOAD_FOLDER,
        input_filename
    )

    file.save(input_path)

    try:

        # تبدیل فایل به WAV با کیفیت مناسب
        audio_data, sample_rate = librosa.load(
            input_path,
            sr=16000,
            mono=True
        )

        recognizer = sr.Recognizer()

        # فایل را به قطعات 30 ثانیه‌ای تقسیم می‌کنیم
        chunk_seconds = 30

        chunk_size = 16000 * chunk_seconds

        total_samples = len(audio_data)

        all_text = []

        # برای جلوگیری از خطای timeout
        recognizer.operation_timeout = 30

        for start in range(
            0,
            total_samples,
            chunk_size
        ):

            end = min(
                start + chunk_size,
                total_samples
            )

            chunk = audio_data[start:end]

            chunk_filename = (
                f"chunk_{int(time.time())}_{start}.wav"
            )

            chunk_path = os.path.join(
                UPLOAD_FOLDER,
                chunk_filename
            )

            try:

                # ذخیره قطعه
                sf.write(
                    chunk_path,
                    chunk,
                    16000,
                    subtype="PCM_16"
                )

                # خواندن فایل
                with sr.AudioFile(chunk_path) as source:

                    audio = recognizer.record(
                        source
                    )

                try:

                    text = recognizer.recognize_google(
                        audio,
                        language="fa-IR"
                    )

                    if text:

                        all_text.append(
                            text.strip()
                        )

                except sr.UnknownValueError:

                    # اگر این قطعه قابل تشخیص نبود
                    # قطعات دیگر ادامه پیدا می‌کنند
                    pass

                except sr.RequestError:

                    # اگر سرویس موقتاً پاسخ نداد
                    pass

            finally:

                if os.path.exists(chunk_path):

                    try:
                        os.remove(chunk_path)

                    except:
                        pass


        final_text = " ".join(
            all_text
        ).strip()


        if not final_text:

            return render_template(
                "index.html",
                error_text=(
                    "متن قابل تشخیصی پیدا نشد. "
                    "لطفاً فایل صوتی واضح‌تر و با صدای گوینده مشخص‌تر "
                    "امتحان کنید."
                )
            )


        return render_template(
            "index.html",
            transcribed_text=final_text,
            success_text="صوت با موفقیت به متن تبدیل شد."
        )


    except sr.RequestError as e:

        return render_template(
            "index.html",
            error_text=(
                "ارتباط با سرویس تشخیص گفتار برقرار نشد. "
                f"جزئیات: {str(e)}"
            )
        )


    except Exception as e:

        return render_template(
            "index.html",
            error_text=f"خطا در تبدیل صوت به متن: {str(e)}"
        )


    finally:

        if os.path.exists(input_path):

            try:
                os.remove(input_path)

            except:
                pass


# =========================================================
# تبدیل عکس به متن
# =========================================================

@app.route("/image-to-text", methods=["POST"])
def image_to_text():

    if "image_file" not in request.files:

        return render_template(
            "index.html",
            error_text="عکسی انتخاب نشده است."
        )

    file = request.files["image_file"]

    if file.filename == "":

        return render_template(
            "index.html",
            error_text="عکسی انتخاب نشده است."
        )


    filename = (
        f"ocr_{int(time.time())}_{file.filename}"
    )

    image_path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    file.save(image_path)


    try:

        # باز کردن عکس
        image = Image.open(
            image_path
        )

        # تبدیل به RGB
        image = image.convert("RGB")

        # ==========================================
        # بزرگ کردن عکس برای OCR بهتر
        # ==========================================

        width, height = image.size

        if width < 1600:

            ratio = 1600 / width

            image = image.resize(
                (
                    1600,
                    int(height * ratio)
                )
            )


        # ==========================================
        # بهبود تصویر
        # ==========================================

        image = image.convert("L")

        image = ImageEnhance.Contrast(
            image
        ).enhance(2)

        image = image.filter(
            ImageFilter.SHARPEN
        )


        # ==========================================
        # استخراج متن فارسی و انگلیسی
        # ==========================================

        extracted_text = pytesseract.image_to_string(
            image,
            lang="fas+eng",
            config="--psm 6"
        )


        extracted_text = extracted_text.strip()


        if not extracted_text:

            return render_template(
                "index.html",
                error_text=(
                    "متنی در تصویر پیدا نشد. "
                    "لطفاً عکس واضح‌تر و با کیفیت‌تری انتخاب کنید."
                )
            )


        return render_template(
            "index.html",
            image_text=extracted_text,
            success_text="متن تصویر با موفقیت استخراج شد."
        )


    except Exception as e:

        return render_template(
            "index.html",
            error_text=(
                f"خطا در استخراج متن از عکس: {str(e)}"
            )
        )


    finally:

        if os.path.exists(image_path):

            try:
                os.remove(image_path)

            except:
                pass


# =========================================================
# دانلود فایل‌ها
# =========================================================

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


# =========================================================
# Sitemap
# =========================================================

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


# =========================================================
# Robots.txt
# =========================================================

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


# =========================================================
# اجرای برنامه
# =========================================================

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
