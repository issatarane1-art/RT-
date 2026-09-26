import os
import re
import uuid
import asyncio
import shutil
import subprocess
import secrets
import string
import difflib
from pathlib import Path

from flask import Flask, render_template, request, send_from_directory, jsonify
from werkzeug.utils import secure_filename


app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# حداکثر حجم فایل ورودی: 100MB
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024


# =========================================================
# فرمت‌های مجاز
# =========================================================

AUDIO_EXTENSIONS = {
    "mp3",
    "wav",
    "m4a",
    "aac",
    "ogg",
    "flac",
    "webm",
    "mp4"
}

IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "bmp",
    "gif",
    "tiff"
}

VIDEO_EXTENSIONS = {
    "mp4",
    "mov",
    "mkv",
    "webm",
    "avi",
    "m4v",
    "mpeg",
    "mpg",
    "3gp"
}


WHISPER_MODEL = None


# =========================================================
# ابزارهای کمکی
# =========================================================

def get_extension(filename):
    filename = secure_filename(filename or "")
    return Path(filename).suffix.lower().replace(".", "")


def save_uploaded_file(file, allowed_extensions):
    if not file or not file.filename:
        raise ValueError("لطفاً یک فایل انتخاب کنید.")

    extension = get_extension(file.filename)

    if extension not in allowed_extensions:
        raise ValueError(
            f"فرمت فایل پشتیبانی نمی‌شود: "
            f"{extension or 'نامشخص'}"
        )

    path = UPLOAD_DIR / (
        f"{uuid.uuid4().hex}.{extension}"
    )

    file.save(path)

    return path


def create_output(extension):
    return OUTPUT_DIR / (
        f"{uuid.uuid4().hex}.{extension}"
    )


def run_command(*command, timeout=900):
    command = [str(x) for x in command]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout
    )

    if result.returncode != 0:
        error = result.stderr.strip()

        if len(error) > 3000:
            error = error[-3000:]

        raise RuntimeError(
            error or "اجرای عملیات با خطا مواجه شد."
        )

    return result


def ensure_output_exists(path):
    path = Path(path)

    if not path.exists():
        raise RuntimeError(
            "فایل خروجی ساخته نشد."
        )

    if path.stat().st_size <= 0:
        raise RuntimeError(
            "فایل خروجی خالی است."
        )

    return path


def render_success(message, **kwargs):
    kwargs["success_text"] = message
    return render_template(
        "index.html",
        **kwargs
    )


def render_failure(error):
    return render_template(
        "index.html",
        error_text=str(error)
    )


# =========================================================
# صفحات اصلی
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    template = BASE_DIR / "templates" / "about.html"

    if template.exists():
        return render_template("about.html")

    return """
    <!doctype html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="utf-8">
        <title>درباره سامانه</title>
    </head>
    <body>
        <h1>سامانه ابزار آنلاین</h1>
        <p>
            مجموعه‌ای از ابزارهای آنلاین پردازش متن،
            تصویر، صوت، ویدیو و PDF.
        </p>
    </body>
    </html>
    """


@app.route("/contact")
def contact():
    template = BASE_DIR / "templates" / "contact.html"

    if template.exists():
        return render_template("contact.html")

    return """
    <!doctype html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="utf-8">
        <title>تماس با ما</title>
    </head>
    <body>
        <h1>تماس با ما</h1>
        <p>
            برای ارتباط با ما از راه‌های ارتباطی سایت استفاده کنید.
        </p>
    </body>
    </html>
    """


@app.route("/text-to-speech")
def text_to_speech():
    return render_template("index.html")


# =========================================================
# 1 - تبدیل متن به صدا
# =========================================================

@app.route("/process-text", methods=["POST"])
def process_text():
    try:
        text = (
            request.form.get("text_input")
            or request.form.get("text")
            or ""
        ).strip()

        if not text:
            raise ValueError(
                "لطفاً متن را وارد کنید."
            )

        import edge_tts

        output = create_output("mp3")

        async def generate_audio():
            communicator = edge_tts.Communicate(
                text,
                "fa-IR-DilaraNeural"
            )

            await communicator.save(
                str(output)
            )

        asyncio.run(generate_audio())

        ensure_output_exists(output)

        return render_success(
            "تبدیل متن به صدا با موفقیت انجام شد.",
            speech_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"تبدیل متن به صدا انجام نشد: {e}"
        )


# =========================================================
# 2 - جداسازی تقریبی صدای خواننده
# =========================================================

@app.route("/process-audio", methods=["POST"])
def process_audio():
    try:
        file = (
            request.files.get("audio_file")
            or request.files.get("audio")
        )

        source = save_uploaded_file(
            file,
            AUDIO_EXTENSIONS
        )

        vocals = create_output("wav")
        instrumental = create_output("wav")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-af",
            "pan=mono|c0=0.5*c0+0.5*c1",
            vocals
        )

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-af",
            "pan=mono|c0=0.5*c0-0.5*c1",
            instrumental
        )

        ensure_output_exists(vocals)
        ensure_output_exists(instrumental)

        return render_success(
            "پردازش صوت انجام شد.",
            vocals_file=vocals.name,
            instrumental_file=instrumental.name
        )

    except Exception as e:
        return render_failure(
            f"پردازش صوت انجام نشد: {e}"
        )


# =========================================================
# 3 - تبدیل صوت به متن
# =========================================================

def get_whisper_model():
    global WHISPER_MODEL

    if WHISPER_MODEL is None:
        from faster_whisper import WhisperModel

        WHISPER_MODEL = WhisperModel(
            "tiny",
            device="cpu",
            compute_type="int8"
        )

    return WHISPER_MODEL


@app.route("/speech-to-text", methods=["POST"])
def speech_to_text():
    try:
        file = (
            request.files.get("speech_file")
            or request.files.get("speech")
            or request.files.get("audio")
        )

        source = save_uploaded_file(
            file,
            AUDIO_EXTENSIONS
        )

        wav_file = create_output("wav")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-ac",
            "1",
            "-ar",
            "16000",
            wav_file
        )

        model = get_whisper_model()

        segments, info = model.transcribe(
            str(wav_file),
            language="fa",
            vad_filter=True
        )

        text_parts = []

        for segment in segments:
            value = segment.text.strip()

            if value:
                text_parts.append(value)

        text = " ".join(
            text_parts
        ).strip()

        if not text:
            text = (
                "متنی از فایل صوتی شناسایی نشد."
            )

        return render_success(
            "تبدیل صوت به متن انجام شد.",
            transcribed_text=text
        )

    except Exception as e:
        return render_failure(
            f"تبدیل صوت به متن انجام نشد: {e}"
        )


# =========================================================
# 4 - عکس به متن
# =========================================================

@app.route("/image-to-text", methods=["POST"])
def image_to_text():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import Image
        import pytesseract

        image = Image.open(source)

        text = pytesseract.image_to_string(
            image,
            lang="fas+eng"
        ).strip()

        if not text:
            text = (
                "متنی در تصویر پیدا نشد."
            )

        return render_success(
            "متن تصویر استخراج شد.",
            image_text=text
        )

    except Exception as e:
        return render_failure(
            f"استخراج متن انجام نشد: {e}"
        )


# =========================================================
# 5 - فشرده سازی تصویر
# =========================================================

@app.route("/image-compress", methods=["POST"])
def image_compress():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import Image

        image = Image.open(source)

        max_width = request.form.get(
            "max_width",
            "1600"
        )

        quality = request.form.get(
            "quality",
            "80"
        )

        max_width = (
            int(max_width)
            if max_width
            else 1600
        )

        quality = (
            int(quality)
            if quality
            else 80
        )

        max_width = max(
            100,
            min(max_width, 5000)
        )

        quality = max(
            10,
            min(quality, 95)
        )

        if image.width > max_width:
            ratio = (
                max_width /
                image.width
            )

            image = image.resize(
                (
                    max_width,
                    max(
                        1,
                        int(
                            image.height *
                            ratio
                        )
                    )
                ),
                Image.Resampling.LANCZOS
            )

        if image.mode not in (
            "RGB",
            "L"
        ):
            image = image.convert("RGB")

        output = create_output("jpg")

        image.save(
            output,
            "JPEG",
            quality=quality,
            optimize=True
        )

        ensure_output_exists(output)

        return render_success(
            "تصویر با موفقیت فشرده شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 6 - تصویر به PDF
# =========================================================

@app.route("/image-to-pdf", methods=["POST"])
def image_to_pdf():
    try:
        files = request.files.getlist(
            "images"
        )

        if not files:
            single = (
                request.files.get("image_file")
                or request.files.get("image")
            )

            if single:
                files = [single]

        from PIL import Image

        images = []

        for file in files:
            if not file or not file.filename:
                continue

            source = save_uploaded_file(
                file,
                IMAGE_EXTENSIONS
            )

            image = Image.open(
                source
            ).convert("RGB")

            images.append(image)

        if not images:
            raise ValueError(
                "حداقل یک تصویر انتخاب کنید."
            )

        output = create_output("pdf")

        images[0].save(
            output,
            "PDF",
            save_all=True,
            append_images=images[1:]
        )

        ensure_output_exists(output)

        return render_success(
            "تصویر به PDF تبدیل شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 7 - متن به PDF
# =========================================================

@app.route("/text-to-pdf", methods=["POST"])
def text_to_pdf():
    try:
        text = (
            request.form.get("text_content")
            or request.form.get("text")
            or ""
        )

        if not text.strip():
            raise ValueError(
                "متنی برای ساخت PDF وارد کنید."
            )

        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4

        output = create_output("pdf")

        pdf = canvas.Canvas(
            str(output),
            pagesize=A4
        )

        width, height = A4
        y = height - 50

        for line in text.splitlines():
            if not line:
                y -= 18
                continue

            pdf.drawString(
                40,
                y,
                line[:120]
            )

            y -= 18

            if y < 40:
                pdf.showPage()
                y = height - 50

        pdf.save()

        ensure_output_exists(output)

        return render_success(
            "PDF ساخته شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"ساخت PDF انجام نشد: {e}"
        )


# =========================================================
# 8 - QR Code
# =========================================================

@app.route("/qr-code", methods=["POST"])
def qr_code():
    try:
        data = request.form.get(
            "qr_data",
            ""
        ).strip()

        if not data:
            raise ValueError(
                "متن یا لینک QR را وارد کنید."
            )

        import qrcode

        output = create_output("png")

        qr = qrcode.QRCode(
            version=None,
            error_correction=(
                qrcode.constants.ERROR_CORRECT_M
            ),
            box_size=10,
            border=4
        )

        qr.add_data(data)
        qr.make(fit=True)

        image = qr.make_image()

        image.save(output)

        ensure_output_exists(output)

        return render_success(
            "QR Code ساخته شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 9 - فشرده سازی PDF
# =========================================================

@app.route("/pdf-compress", methods=["POST"])
def pdf_compress():
    try:
        file = (
            request.files.get("pdf_file")
            or request.files.get("file")
        )

        source = save_uploaded_file(
            file,
            {"pdf"}
        )

        ghostscript = shutil.which("gs")

        if not ghostscript:
            raise RuntimeError(
                "Ghostscript روی سرور نصب نیست."
            )

        output = create_output("pdf")

        run_command(
            ghostscript,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/ebook",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={output}",
            source
        )

        ensure_output_exists(output)

        return render_success(
            "PDF فشرده شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 10 - PDF به متن
# =========================================================

@app.route("/pdf-to-text", methods=["POST"])
def pdf_to_text():
    try:
        file = (
            request.files.get("pdf_file")
            or request.files.get("file")
        )

        source = save_uploaded_file(
            file,
            {"pdf"}
        )

        from pypdf import PdfReader

        reader = PdfReader(
            str(source)
        )

        parts = []

        for page in reader.pages:
            parts.append(
                page.extract_text() or ""
            )

        text = "\n\n".join(
            parts
        ).strip()

        if not text:
            text = (
                "متنی از PDF استخراج نشد."
            )

        return render_success(
            "متن PDF استخراج شد.",
            transcribed_text=text
        )

    except Exception as e:
        return render_failure(
            f"استخراج PDF انجام نشد: {e}"
        )


# =========================================================
# 11 - تصویر به JPG
# =========================================================

@app.route("/image-to-jpg", methods=["POST"])
def image_to_jpg():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import Image

        image = Image.open(
            source
        ).convert("RGB")

        output = create_output("jpg")

        image.save(
            output,
            "JPEG",
            quality=92
        )

        ensure_output_exists(output)

        return render_success(
            "تصویر به JPG تبدیل شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 12 - تصویر به PNG
# =========================================================

@app.route("/image-to-png", methods=["POST"])
def image_to_png():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import Image

        image = Image.open(source)

        output = create_output("png")

        image.save(
            output,
            "PNG",
            optimize=True
        )

        ensure_output_exists(output)

        return render_success(
            "تصویر به PNG تبدیل شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 13 - برش تصویر
# =========================================================

@app.route("/image-crop", methods=["POST"])
def image_crop():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import Image

        image = Image.open(source)

        x = request.form.get("x", "0")
        y = request.form.get("y", "0")

        width = request.form.get(
            "width",
            str(image.width)
        )

        height = request.form.get(
            "height",
            str(image.height)
        )

        x = int(x) if x else 0
        y = int(y) if y else 0

        width = (
            int(width)
            if width
            else image.width
        )

        height = (
            int(height)
            if height
            else image.height
        )

        x = max(0, x)
        y = max(0, y)

        width = max(1, width)
        height = max(1, height)

        x2 = min(
            image.width,
            x + width
        )

        y2 = min(
            image.height,
            y + height
        )

        if x >= x2 or y >= y2:
            raise ValueError(
                "محدوده برش معتبر نیست."
            )

        result = image.crop(
            (x, y, x2, y2)
        )

        output = create_output("png")

        result.save(
            output,
            "PNG"
        )

        ensure_output_exists(output)

        return render_success(
            "تصویر برش خورد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 14 - چرخش تصویر
# =========================================================

@app.route("/image-rotate", methods=["POST"])
def image_rotate():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import Image

        image = Image.open(source)

        angle = request.form.get(
            "angle",
            "90"
        )

        angle = (
            float(angle)
            if angle
            else 90
        )

        result = image.rotate(
            -angle,
            expand=True
        )

        output = create_output("png")

        result.save(
            output,
            "PNG"
        )

        ensure_output_exists(output)

        return render_success(
            "تصویر چرخانده شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 15 - آینه‌ای کردن تصویر
# =========================================================

@app.route("/image-mirror", methods=["POST"])
def image_mirror():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import ImageOps, Image

        image = Image.open(source)

        result = ImageOps.mirror(image)

        output = create_output("png")

        result.save(
            output,
            "PNG"
        )

        ensure_output_exists(output)

        return render_success(
            "تصویر آینه‌ای شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 16 - سیاه و سفید
# =========================================================

@app.route("/image-grayscale", methods=["POST"])
def image_grayscale():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import ImageOps, Image

        image = Image.open(source)

        result = ImageOps.grayscale(image)

        output = create_output("png")

        result.save(
            output,
            "PNG"
        )

        ensure_output_exists(output)

        return render_success(
            "تصویر سیاه و سفید شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 17 - روشنایی
# =========================================================

@app.route("/image-brightness", methods=["POST"])
def image_brightness():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import Image, ImageEnhance

        image = Image.open(source)

        factor = request.form.get(
            "factor",
            "1.2"
        )

        factor = (
            float(factor)
            if factor
            else 1.2
        )

        factor = max(
            0,
            min(factor, 3)
        )

        result = ImageEnhance.Brightness(
            image
        ).enhance(factor)

        output = create_output("png")

        result.save(
            output,
            "PNG"
        )

        ensure_output_exists(output)

        return render_success(
            "روشنایی تصویر تغییر کرد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 18 - کنتراست
# =========================================================

@app.route("/image-contrast", methods=["POST"])
def image_contrast():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import Image, ImageEnhance

        image = Image.open(source)

        factor = request.form.get(
            "factor",
            "1.2"
        )

        factor = (
            float(factor)
            if factor
            else 1.2
        )

        factor = max(
            0,
            min(factor, 3)
        )

        result = ImageEnhance.Contrast(
            image
        ).enhance(factor)

        output = create_output("png")

        result.save(
            output,
            "PNG"
        )

        ensure_output_exists(output)

        return render_success(
            "کنتراست تصویر تغییر کرد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 19 - ویرایشگر تصویر
# =========================================================

@app.route("/image-editor", methods=["POST"])
def image_editor():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import (
            Image,
            ImageEnhance,
            ImageOps,
            ImageFilter,
            ImageDraw
        )

        image = Image.open(
            source
        ).convert("RGBA")

        if request.form.get(
            "mirror"
        ) == "1":
            image = ImageOps.mirror(
                image
            )

        angle = request.form.get(
            "angle",
            "0"
        )

        angle = (
            float(angle)
            if angle
            else 0
        )

        if angle:
            image = image.rotate(
                -angle,
                expand=True
            )

        brightness = request.form.get(
            "brightness",
            "1"
        )

        brightness = (
            float(brightness)
            if brightness
            else 1
        )

        brightness = max(
            0,
            min(brightness, 3)
        )

        image = ImageEnhance.Brightness(
            image
        ).enhance(brightness)

        contrast = request.form.get(
            "contrast",
            "1"
        )

        contrast = (
            float(contrast)
            if contrast
            else 1
        )

        contrast = max(
            0,
            min(contrast, 3)
        )

        image = ImageEnhance.Contrast(
            image
        ).enhance(contrast)

        blur = request.form.get(
            "blur",
            "0"
        )

        blur = (
            float(blur)
            if blur
            else 0
        )

        blur = max(
            0,
            min(blur, 20)
        )

        if blur:
            image = image.filter(
                ImageFilter.GaussianBlur(
                    blur
                )
            )

        overlay_text = request.form.get(
            "overlay_text",
            ""
        ).strip()

        if overlay_text:
            draw = ImageDraw.Draw(
                image
            )

            draw.text(
                (30, 30),
                overlay_text[:500],
                fill=(
                    255,
                    255,
                    255,
                    255
                )
            )

        output = create_output("png")

        image.save(
            output,
            "PNG"
        )

        ensure_output_exists(output)

        return render_success(
            "ویرایش تصویر انجام شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 20 - تبدیل فرمت صوت
# =========================================================

@app.route("/audio-convert", methods=["POST"])
def audio_convert():
    try:
        file = (
            request.files.get("audio_file")
            or request.files.get("file")
        )

        fmt = request.form.get(
            "format",
            "mp3"
        ).lower()

        allowed_formats = {
            "mp3",
            "wav",
            "ogg",
            "flac",
            "m4a"
        }

        if fmt not in allowed_formats:
            raise ValueError(
                "فرمت خروجی معتبر نیست."
            )

        source = save_uploaded_file(
            file,
            AUDIO_EXTENSIONS
        )

        output = create_output(fmt)

        if fmt == "mp3":
            command = [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-vn",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "2",
                output
            ]

        elif fmt == "wav":
            command = [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-vn",
                "-c:a",
                "pcm_s16le",
                output
            ]

        elif fmt == "ogg":
            command = [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-vn",
                "-c:a",
                "libvorbis",
                "-q:a",
                "5",
                output
            ]

        elif fmt == "flac":
            command = [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-vn",
                "-c:a",
                "flac",
                output
            ]

        else:
            command = [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-vn",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                output
            ]

        run_command(*command)

        ensure_output_exists(output)

        return render_success(
            "فرمت صوت تبدیل شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 21 - برش صوت
# =========================================================

@app.route("/audio-cut", methods=["POST"])
def audio_cut():
    try:
        file = (
            request.files.get("audio_file")
            or request.files.get("file")
        )

        source = save_uploaded_file(
            file,
            AUDIO_EXTENSIONS
        )

        start = request.form.get(
            "start",
            "0"
        )

        duration = request.form.get(
            "duration",
            "10"
        )

        start = (
            float(start)
            if start
            else 0
        )

        duration = (
            float(duration)
            if duration
            else 10
        )

        start = max(0, start)
        duration = max(
            0.1,
            duration
        )

        output = create_output("mp3")

        run_command(
            "ffmpeg",
            "-y",
            "-ss",
            start,
            "-i",
            source,
            "-t",
            duration,
            "-vn",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            output
        )

        ensure_output_exists(output)

        return render_success(
            "قسمت انتخاب‌شده از صدا جدا شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 22 - تغییر حجم صدا
# =========================================================

@app.route("/audio-volume", methods=["POST"])
def audio_volume():
    try:
        file = (
            request.files.get("audio_file")
            or request.files.get("file")
        )

        source = save_uploaded_file(
            file,
            AUDIO_EXTENSIONS
        )

        volume = request.form.get(
            "volume",
            "1.2"
        )

        volume = (
            float(volume)
            if volume
            else 1.2
        )

        volume = max(
            0,
            min(volume, 5)
        )

        output = create_output("mp3")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-af",
            f"volume={volume}",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            output
        )

        ensure_output_exists(output)

        return render_success(
            "بلندی صدا تغییر کرد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 23 - کاهش نویز
# =========================================================

@app.route("/audio-clean", methods=["POST"])
def audio_clean():
    try:
        file = (
            request.files.get("audio_file")
            or request.files.get("file")
        )

        source = save_uploaded_file(
            file,
            AUDIO_EXTENSIONS
        )

        output = create_output("mp3")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-af",
            "afftdn",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            output
        )

        ensure_output_exists(output)

        return render_success(
            "کاهش نویز انجام شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 24 - حذف سکوت
# =========================================================

@app.route("/audio-silence", methods=["POST"])
def audio_silence():
    try:
        file = (
            request.files.get("audio_file")
            or request.files.get("file")
        )

        source = save_uploaded_file(
            file,
            AUDIO_EXTENSIONS
        )

        output = create_output("mp3")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-af",
            (
                "silenceremove="
                "stop_periods=-1:"
                "stop_duration=1:"
                "stop_threshold=-45dB"
            ),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            output
        )

        ensure_output_exists(output)

        return render_success(
            "سکوت‌های طولانی حذف شدند.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 25 - ادغام صوت
# =========================================================

@app.route("/audio-merge", methods=["POST"])
def audio_merge():
    try:
        files = request.files.getlist(
            "audio_files"
        )

        valid_files = [
            file
            for file in files
            if (
                file
                and file.filename
                and get_extension(
                    file.filename
                ) in AUDIO_EXTENSIONS
            )
        ]

        if len(valid_files) < 2:
            raise ValueError(
                "حداقل دو فایل صوتی انتخاب کنید."
            )

        normalized = []

        for file in valid_files:
            source = save_uploaded_file(
                file,
                AUDIO_EXTENSIONS
            )

            normalized_file = create_output(
                "wav"
            )

            run_command(
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-ar",
                "44100",
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                normalized_file
            )

            normalized.append(
                normalized_file
            )

        list_file = (
            UPLOAD_DIR /
            f"{uuid.uuid4().hex}.txt"
        )

        with open(
            list_file,
            "w",
            encoding="utf-8"
        ) as f:

            for source in normalized:
                safe_path = str(
                    source
                ).replace(
                    "'",
                    "'\\''"
                )

                f.write(
                    f"file '{safe_path}'\n"
                )

        output = create_output("mp3")

        run_command(
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            output
        )

        ensure_output_exists(output)

        return render_success(
            "فایل‌های صوتی ادغام شدند.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 26 - ادغام PDF
# =========================================================

@app.route("/pdf-merge", methods=["POST"])
def pdf_merge():
    try:
        files = request.files.getlist(
            "pdf_files"
        )

        if len(files) < 2:
            raise ValueError(
                "حداقل دو فایل PDF انتخاب کنید."
            )

        from pypdf import (
            PdfReader,
            PdfWriter
        )

        writer = PdfWriter()

        for file in files:
            if not file or not file.filename:
                continue

            source = save_uploaded_file(
                file,
                {"pdf"}
            )

            reader = PdfReader(
                str(source)
            )

            for page in reader.pages:
                writer.add_page(page)

        if len(writer.pages) == 0:
            raise ValueError(
                "PDF معتبر پیدا نشد."
            )

        output = create_output("pdf")

        with open(
            output,
            "wb"
        ) as file:
            writer.write(file)

        ensure_output_exists(output)

        return render_success(
            "PDFها با موفقیت ادغام شدند.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 27 - استخراج صفحات PDF
# =========================================================

@app.route("/pdf-extract-pages", methods=["POST"])
def pdf_extract_pages():
    try:
        file = (
            request.files.get("pdf_file")
            or request.files.get("file")
        )

        source = save_uploaded_file(
            file,
            {"pdf"}
        )

        from pypdf import (
            PdfReader,
            PdfWriter
        )

        reader = PdfReader(
            str(source)
        )

        pages_text = request.form.get(
            "pages",
            "1"
        )

        selected_pages = []

        for item in pages_text.split(","):
            item = item.strip()

            if not item:
                continue

            if "-" in item:
                start, end = map(
                    int,
                    item.split("-", 1)
                )

                if start > end:
                    start, end = end, start

                selected_pages.extend(
                    range(
                        start,
                        end + 1
                    )
                )

            else:
                selected_pages.append(
                    int(item)
                )

        writer = PdfWriter()

        for number in selected_pages:
            if (
                1 <= number
                <= len(reader.pages)
            ):
                writer.add_page(
                    reader.pages[
                        number - 1
                    ]
                )

        if len(writer.pages) == 0:
            raise ValueError(
                "شماره صفحه معتبر نیست."
            )

        output = create_output("pdf")

        with open(
            output,
            "wb"
        ) as file:
            writer.write(file)

        ensure_output_exists(output)

        return render_success(
            "صفحات انتخاب‌شده جدا شدند.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 28 - PDF به JPG
# =========================================================

@app.route("/pdf-to-jpg", methods=["POST"])
def pdf_to_jpg():
    try:
        file = (
            request.files.get("pdf_file")
            or request.files.get("file")
        )

        source = save_uploaded_file(
            file,
            {"pdf"}
        )

        pdftoppm = shutil.which(
            "pdftoppm"
        )

        if not pdftoppm:
            raise RuntimeError(
                "pdftoppm روی سرور نصب نیست."
            )

        prefix = (
            OUTPUT_DIR /
            uuid.uuid4().hex
        )

        run_command(
            pdftoppm,
            "-f",
            "1",
            "-singlefile",
            "-jpeg",
            "-r",
            "150",
            source,
            prefix
        )

        result = OUTPUT_DIR / (
            prefix.name + ".jpg"
        )

        ensure_output_exists(result)

        return render_success(
            "صفحه اول PDF به JPG تبدیل شد.",
            result_file=result.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 29 - آمار متن
# =========================================================

@app.route("/text-stats", methods=["POST"])
def text_stats():
    try:
        text = (
            request.form.get("text_content")
            or request.form.get("text")
            or ""
        )

        characters = len(text)

        characters_without_spaces = len(
            re.sub(r"\s+", "", text)
        )

        words = len(
            re.findall(
                r"\S+",
                text
            )
        )

        lines = (
            len(text.splitlines())
            if text
            else 0
        )

        result = (
            f"تعداد حروف: {characters}\n"
            f"حروف بدون فاصله: "
            f"{characters_without_spaces}\n"
            f"تعداد کلمات: {words}\n"
            f"تعداد خطوط: {lines}"
        )

        return render_success(
            "آمار متن محاسبه شد.",
            transcribed_text=result
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 30 - تغییر حروف
# =========================================================

@app.route("/text-case", methods=["POST"])
def text_case():
    try:
        text = (
            request.form.get("text_content")
            or request.form.get("text")
            or ""
        )

        mode = request.form.get(
            "mode",
            "upper"
        )

        if mode == "lower":
            result = text.lower()

        elif mode == "title":
            result = text.title()

        else:
            result = text.upper()

        return render_success(
            "حروف متن تبدیل شدند.",
            transcribed_text=result
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 31 - پاکسازی متن
# =========================================================

@app.route("/text-clean", methods=["POST"])
def text_clean():
    try:
        text = (
            request.form.get("text_content")
            or request.form.get("text")
            or ""
        )

        text = re.sub(
            r"[ \t]+",
            " ",
            text
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text
        )

        text = text.strip()

        return render_success(
            "متن پاکسازی شد.",
            transcribed_text=text
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 32 - مرتب سازی متن
# =========================================================

@app.route("/text-sort", methods=["POST"])
def text_sort():
    try:
        text = (
            request.form.get("text_content")
            or request.form.get("text")
            or ""
        )

        lines = [
            line
            for line in text.splitlines()
            if line.strip()
        ]

        mode = request.form.get(
            "mode",
            "asc"
        )

        lines.sort(
            reverse=(
                mode == "desc"
            )
        )

        result = "\n".join(lines)

        return render_success(
            "متن مرتب شد.",
            transcribed_text=result
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 33 - شماره گذاری متن
# =========================================================

@app.route("/text-number", methods=["POST"])
def text_number():
    try:
        text = (
            request.form.get("text_content")
            or request.form.get("text")
            or ""
        )

        result = "\n".join(
            f"{index}. {line}"
            for index, line
            in enumerate(
                text.splitlines(),
                start=1
            )
        )

        return render_success(
            "متن شماره‌گذاری شد.",
            transcribed_text=result
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 34 - جایگزینی متن
# =========================================================

@app.route("/text-replace", methods=["POST"])
def text_replace():
    try:
        text = request.form.get(
            "text_content",
            ""
        )

        find_text = request.form.get(
            "find_text",
            ""
        )

        replace_text = request.form.get(
            "replace_text",
            ""
        )

        if not find_text:
            raise ValueError(
                "عبارت مورد جستجو را وارد کنید."
            )

        result = text.replace(
            find_text,
            replace_text
        )

        return render_success(
            "جایگزینی انجام شد.",
            transcribed_text=result
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 35 - مقایسه متن
# =========================================================

@app.route("/text-compare", methods=["POST"])
def text_compare():
    try:
        first = request.form.get(
            "text_a",
            ""
        )

        second = request.form.get(
            "text_b",
            ""
        )

        if first == second:
            result = (
                "دو متن کاملاً یکسان هستند."
            )

        else:
            result = "\n".join(
                difflib.unified_diff(
                    first.splitlines(),
                    second.splitlines(),
                    fromfile="متن اول",
                    tofile="متن دوم",
                    lineterm=""
                )
            )

        return render_success(
            "مقایسه متن انجام شد.",
            transcribed_text=result
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 36 - ساخت رمز عبور
# =========================================================

@app.route("/password", methods=["POST"])
def password():
    try:
        length = request.form.get(
            "length",
            "16"
        )

        length = (
            int(length)
            if length
            else 16
        )

        length = max(
            4,
            min(length, 128)
        )

        characters = (
            string.ascii_letters
            + string.digits
            + "!@#$%^&*_-+="
        )

        result = "".join(
            secrets.choice(
                characters
            )
            for _ in range(length)
        )

        return render_success(
            "رمز عبور ساخته شد.",
            transcribed_text=result
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 37 - عدد تصادفی
# =========================================================

@app.route("/random-number", methods=["POST"])
def random_number():
    try:
        minimum = request.form.get(
            "minimum",
            "1"
        )

        maximum = request.form.get(
            "maximum",
            "100"
        )

        minimum = (
            int(minimum)
            if minimum
            else 1
        )

        maximum = (
            int(maximum)
            if maximum
            else 100
        )

        if minimum > maximum:
            minimum, maximum = (
                maximum,
                minimum
            )

        number = (
            secrets.randbelow(
                maximum -
                minimum +
                1
            )
            + minimum
        )

        return render_success(
            "عدد تصادفی ساخته شد.",
            transcribed_text=str(
                number
            )
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 38 - تبدیل واحد
# =========================================================

@app.route("/unit-convert", methods=["POST"])
def unit_convert():
    try:
        value = request.form.get(
            "value",
            "0"
        )

        value = (
            float(value)
            if value
            else 0
        )

        conversion = request.form.get(
            "kind",
            "km-m"
        )

        conversions = {
            "km-m": value * 1000,
            "m-km": value / 1000,
            "kg-g": value * 1000,
            "g-kg": value / 1000,
            "l-ml": value * 1000,
            "ml-l": value / 1000,
            "c-f": (
                value * 9 / 5
                + 32
            ),
            "f-c": (
                value - 32
            ) * 5 / 9
        }

        if conversion not in conversions:
            raise ValueError(
                "نوع تبدیل واحد نامعتبر است."
            )

        return render_success(
            "تبدیل واحد انجام شد.",
            transcribed_text=str(
                conversions[conversion]
            )
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 39 - حذف اطلاعات اضافی عکس
# =========================================================

@app.route(
    "/image-remove-metadata",
    methods=["POST"]
)
def image_remove_metadata():
    try:
        file = (
            request.files.get("image_file")
            or request.files.get("image")
        )

        source = save_uploaded_file(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import Image

        image = Image.open(source)

        clean = Image.new(
            image.mode,
            image.size
        )

        if image.mode == "RGBA":
            clean.paste(
                image,
                (0, 0),
                image
            )
        else:
            clean.paste(
                image,
                (0, 0)
            )

        output = create_output("png")

        clean.save(
            output,
            "PNG"
        )

        ensure_output_exists(output)

        return render_success(
            "اطلاعات اضافی تصویر حذف شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 40 - نرمال سازی صدا
# =========================================================

@app.route("/audio-normalize", methods=["POST"])
def audio_normalize():
    try:
        file = (
            request.files.get("audio_file")
            or request.files.get("file")
        )

        source = save_uploaded_file(
            file,
            AUDIO_EXTENSIONS
        )

        output = create_output("mp3")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-af",
            (
                "loudnorm="
                "I=-16:"
                "TP=-1.5:"
                "LRA=11"
            ),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            output
        )

        ensure_output_exists(output)

        return render_success(
            "بلندی صدا نرمال شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(e)


# =========================================================
# 41 - تبدیل فرمت ویدیو
# =========================================================

@app.route(
    "/video-convert",
    methods=["POST"]
)
def video_convert():
    try:
        file = (
            request.files.get("video_file")
            or request.files.get("file")
            or request.files.get("video")
        )

        source = save_uploaded_file(
            file,
            VIDEO_EXTENSIONS
        )

        fmt = request.form.get(
            "format",
            "mp4"
        ).lower().strip()

        allowed_formats = {
            "mp4",
            "webm",
            "mov",
            "mkv"
        }

        if fmt not in allowed_formats:
            raise ValueError(
                "فرمت خروجی ویدیو معتبر نیست."
            )

        output = create_output(fmt)

        if fmt == "mp4":
            command = [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                output
            ]

        elif fmt == "webm":
            command = [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c:v",
                "libvpx-vp9",
                "-crf",
                "32",
                "-b:v",
                "0",
                "-c:a",
                "libopus",
                "-b:a",
                "128k",
                output
            ]

        else:
            command = [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                output
            ]

        run_command(
            *command,
            timeout=900
        )

        ensure_output_exists(output)

        return render_success(
            "فرمت ویدیو با موفقیت تبدیل شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"تبدیل ویدیو انجام نشد: {e}"
        )


# =========================================================
# 42 - استخراج صدا از ویدیو
# =========================================================

@app.route(
    "/video-extract-audio",
    methods=["POST"]
)
def video_extract_audio():
    try:
        file = (
            request.files.get("video_file")
            or request.files.get("file")
            or request.files.get("video")
        )

        source = save_uploaded_file(
            file,
            VIDEO_EXTENSIONS
        )

        fmt = request.form.get(
            "format",
            "mp3"
        ).lower().strip()

        allowed_formats = {
            "mp3",
            "wav",
            "aac",
            "m4a"
        }

        if fmt not in allowed_formats:
            raise ValueError(
                "فرمت صوتی خروجی معتبر نیست."
            )

        output = create_output(fmt)

        if fmt == "mp3":
            command = [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-vn",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "2",
                output
            ]

        elif fmt == "wav":
            command = [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-vn",
                "-c:a",
                "pcm_s16le",
                output
            ]

        else:
            command = [
                "ffmpeg",
                "-y",
                "-i",
                source,
                "-vn",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                output
            ]

        run_command(
            *command,
            timeout=900
        )

        ensure_output_exists(output)

        return render_success(
            "صدا از ویدیو استخراج شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"استخراج صدا انجام نشد: {e}"
        )


# =========================================================
# 43 - برش ویدیو
# =========================================================

@app.route(
    "/video-cut",
    methods=["POST"]
)
def video_cut():
    try:
        file = (
            request.files.get("video_file")
            or request.files.get("file")
            or request.files.get("video")
        )

        source = save_uploaded_file(
            file,
            VIDEO_EXTENSIONS
        )

        start = request.form.get(
            "start",
            "0"
        )

        duration = request.form.get(
            "duration",
            "10"
        )

        try:
            start = float(start)
            duration = float(duration)
        except ValueError:
            raise ValueError(
                "زمان شروع و مدت باید عدد باشند."
            )

        start = max(0, start)
        duration = max(
            0.1,
            duration
        )

        output = create_output("mp4")

        run_command(
            "ffmpeg",
            "-y",
            "-ss",
            start,
            "-i",
            source,
            "-t",
            duration,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            output,
            timeout=900
        )

        ensure_output_exists(output)

        return render_success(
            "ویدیو با موفقیت برش خورد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"برش ویدیو انجام نشد: {e}"
        )


# =========================================================
# 44 - حذف صدای ویدیو
# =========================================================

@app.route(
    "/video-mute",
    methods=["POST"]
)
def video_mute():
    try:
        file = (
            request.files.get("video_file")
            or request.files.get("file")
            or request.files.get("video")
        )

        source = save_uploaded_file(
            file,
            VIDEO_EXTENSIONS
        )

        output = create_output("mp4")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-an",
            "-movflags",
            "+faststart",
            output,
            timeout=900
        )

        ensure_output_exists(output)

        return render_success(
            "صدای ویدیو حذف شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"حذف صدای ویدیو انجام نشد: {e}"
        )


# =========================================================
# 45 - تغییر صدای ویدیو
# =========================================================

@app.route(
    "/video-volume",
    methods=["POST"]
)
def video_volume():
    try:
        file = (
            request.files.get("video_file")
            or request.files.get("file")
            or request.files.get("video")
        )

        source = save_uploaded_file(
            file,
            VIDEO_EXTENSIONS
        )

        volume = request.form.get(
            "volume",
            "1"
        )

        try:
            volume = float(volume)
        except ValueError:
            raise ValueError(
                "مقدار صدا باید عدد باشد."
            )

        volume = max(
            0,
            min(volume, 5)
        )

        output = create_output("mp4")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-af",
            f"volume={volume}",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            output,
            timeout=900
        )

        ensure_output_exists(output)

        return render_success(
            "صدای ویدیو تغییر کرد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"تغییر صدای ویدیو انجام نشد: {e}"
        )


# =========================================================
# 46 - فشرده سازی ویدیو
# =========================================================

@app.route(
    "/video-compress",
    methods=["POST"]
)
def video_compress():
    try:
        file = (
            request.files.get("video_file")
            or request.files.get("file")
            or request.files.get("video")
        )

        source = save_uploaded_file(
            file,
            VIDEO_EXTENSIONS
        )

        quality = request.form.get(
            "quality",
            "medium"
        ).lower()

        crf_map = {
            "high": "20",
            "medium": "26",
            "low": "31"
        }

        crf = crf_map.get(
            quality,
            "26"
        )

        output = create_output("mp4")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            crf,
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            output,
            timeout=900
        )

        ensure_output_exists(output)

        return render_success(
            "ویدیو با موفقیت فشرده شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"فشرده‌سازی ویدیو انجام نشد: {e}"
        )


# =========================================================
# 47 - استخراج فریم
# =========================================================

@app.route(
    "/video-frame",
    methods=["POST"]
)
def video_frame():
    try:
        file = (
            request.files.get("video_file")
            or request.files.get("file")
            or request.files.get("video")
        )

        source = save_uploaded_file(
            file,
            VIDEO_EXTENSIONS
        )

        timestamp = request.form.get(
            "timestamp",
            "0"
        )

        try:
            timestamp = float(timestamp)
        except ValueError:
            raise ValueError(
                "زمان فریم باید عدد باشد."
            )

        timestamp = max(
            0,
            timestamp
        )

        output = create_output("jpg")

        run_command(
            "ffmpeg",
            "-y",
            "-ss",
            timestamp,
            "-i",
            source,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            output,
            timeout=300
        )

        ensure_output_exists(output)

        return render_success(
            "فریم ویدیو استخراج شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"استخراج فریم انجام نشد: {e}"
        )


# =========================================================
# 48 - چرخاندن ویدیو
# =========================================================

@app.route(
    "/video-rotate",
    methods=["POST"]
)
def video_rotate():
    try:
        file = (
            request.files.get("video_file")
            or request.files.get("file")
            or request.files.get("video")
        )

        source = save_uploaded_file(
            file,
            VIDEO_EXTENSIONS
        )

        angle = str(
            request.form.get(
                "angle",
                "90"
            )
        )

        allowed_angles = {
            "90",
            "180",
            "270"
        }

        if angle not in allowed_angles:
            raise ValueError(
                "زاویه باید 90، 180 یا 270 درجه باشد."
            )

        filters = {
            "90": "transpose=1",
            "180": (
                "transpose=1,"
                "transpose=1"
            ),
            "270": "transpose=2"
        }

        output = create_output("mp4")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            filters[angle],
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            output,
            timeout=900
        )

        ensure_output_exists(output)

        return render_success(
            "ویدیو چرخانده شد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"چرخاندن ویدیو انجام نشد: {e}"
        )


# =========================================================
# 49 - تغییر اندازه ویدیو
# =========================================================

@app.route(
    "/video-resize",
    methods=["POST"]
)
def video_resize():
    try:
        file = (
            request.files.get("video_file")
            or request.files.get("file")
            or request.files.get("video")
        )

        source = save_uploaded_file(
            file,
            VIDEO_EXTENSIONS
        )

        width = request.form.get(
            "width",
            "1280"
        )

        height = request.form.get(
            "height",
            "-2"
        )

        try:
            width = int(width)
            height = int(height)
        except ValueError:
            raise ValueError(
                "عرض و ارتفاع باید عدد باشند."
            )

        width = max(
            160,
            min(width, 3840)
        )

        if height != -2:
            height = max(
                90,
                min(height, 2160)
            )

        output = create_output("mp4")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            f"scale={width}:{height}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            output,
            timeout=900
        )

        ensure_output_exists(output)

        return render_success(
            "اندازه ویدیو تغییر کرد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"تغییر اندازه ویدیو انجام نشد: {e}"
        )


# =========================================================
# 50 - تغییر FPS
# =========================================================

@app.route(
    "/video-fps",
    methods=["POST"]
)
def video_fps():
    try:
        file = (
            request.files.get("video_file")
            or request.files.get("file")
            or request.files.get("video")
        )

        source = save_uploaded_file(
            file,
            VIDEO_EXTENSIONS
        )

        fps = request.form.get(
            "fps",
            "30"
        )

        try:
            fps = float(fps)
        except ValueError:
            raise ValueError(
                "FPS باید عدد باشد."
            )

        fps = max(
            1,
            min(fps, 120)
        )

        output = create_output("mp4")

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-r",
            fps,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            output,
            timeout=900
        )

        ensure_output_exists(output)

        return render_success(
            "FPS ویدیو تغییر کرد.",
            result_file=output.name
        )

    except Exception as e:
        return render_failure(
            f"تغییر FPS ویدیو انجام نشد: {e}"
        )


# =========================================================
# دانلود فایل
# =========================================================

@app.route(
    "/download/<path:filename>"
)
def download(filename):
    return send_from_directory(
        OUTPUT_DIR,
        filename,
        as_attachment=True
    )


# =========================================================
# Health Check
# =========================================================

@app.route("/health")
def health():
    return jsonify(
        status="ok",
        service="online",
        ffmpeg=bool(
            shutil.which("ffmpeg")
        )
    )


# =========================================================
# API
# =========================================================

@app.route("/api/tools")
def api_tools():
    return jsonify(
        status="active",
        tools=50,
        audio_tools=10,
        image_tools=15,
        pdf_tools=7,
        text_tools=7,
        utility_tools=2,
        video_tools=10
    )


# =========================================================
# Sitemap
# =========================================================

from flask import Response

@app.route("/sitemap.xml")
def sitemap():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">

<url>
<loc>https://rt-k9g5.onrender.com/</loc>
</url>

<url>
<loc>https://rt-k9g5.onrender.com/about</loc>
</url>

<url>
<loc>https://rt-k9g5.onrender.com/contact</loc>
</url>

<url>
<loc>https://rt-k9g5.onrender.com/text-to-speech</loc>
</url>

</urlset>"""

    return Response(xml, mimetype="application/xml")

# =========================================================
# خطای حجم فایل
# =========================================================

@app.errorhandler(413)
def file_too_large(error):
    return (
        render_failure(
            "حجم فایل بیشتر از 100 مگابایت است."
        ),
        413
    )


# =========================================================
# خطای داخلی
# =========================================================

@app.errorhandler(500)
def server_error(error):
    return (
        render_failure(
            "خطای داخلی سرور رخ داد. دوباره تلاش کنید."
        ),
        500
    )


# =========================================================
# اجرای محلی
# =========================================================

if __name__ == "__main__":
    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
