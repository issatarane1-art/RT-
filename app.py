import os
import re
import uuid
import asyncio
import shutil
import subprocess
from pathlib import Path

from flask import Flask, render_template, request, send_from_directory, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

AUDIO_EXTENSIONS = {
    "mp3", "wav", "m4a", "aac",
    "ogg", "flac", "webm", "mp4"
}

IMAGE_EXTENSIONS = {
    "jpg", "jpeg", "png", "webp",
    "bmp", "gif", "tiff"
}


# =========================================================
# ابزارهای کمکی
# =========================================================

def get_extension(filename):
    filename = secure_filename(filename or "")
    return Path(filename).suffix.lower().replace(".", "")


def save_uploaded_file(file, allowed_extensions):
    if not file or not file.filename:
        raise ValueError("فایلی انتخاب نشده است.")

    extension = get_extension(file.filename)

    if extension not in allowed_extensions:
        raise ValueError("نوع فایل انتخاب‌شده پشتیبانی نمی‌شود.")

    path = UPLOAD_DIR / f"{uuid.uuid4().hex}.{extension}"
    file.save(path)

    return path


def create_output(extension):
    return OUTPUT_DIR / f"{uuid.uuid4().hex}.{extension}"


def run_command(*command, timeout=900):
    result = subprocess.run(
        [str(x) for x in command],
        capture_output=True,
        text=True,
        timeout=timeout
    )

    if result.returncode != 0:
        error = result.stderr.strip()

        if len(error) > 3000:
            error = error[-3000:]

        raise RuntimeError(
            error or "پردازش فایل با خطا مواجه شد."
        )

    return result


def success(message, **kwargs):
    kwargs["success_text"] = message
    return render_template(
        "index.html",
        **kwargs
    )


def failure(error):
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

    return "سامانه ابزار آنلاین"


@app.route("/contact")
def contact():
    template = BASE_DIR / "templates" / "contact.html"

    if template.exists():
        return render_template("contact.html")

    return "تماس با ما"


@app.route("/text-to-speech")
def text_to_speech():
    template = BASE_DIR / "templates" / "text-to-speech.html"

    if template.exists():
        return render_template("text-to-speech.html")

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

        asyncio.run(
            generate_audio()
        )

        return success(
            "تبدیل متن به صدا با موفقیت انجام شد.",
            speech_file=output.name
        )

    except Exception as e:

        return failure(
            f"تبدیل متن به صدا انجام نشد: {e}"
        )


# =========================================================
# 2 - پردازش صوت / جداسازی تقریبی
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

        # جداسازی تقریبی کانال‌های استریو
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

        return success(
            "پردازش فایل صوتی انجام شد.",
            vocals_file=vocals.name,
            instrumental_file=instrumental.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 3 - تبدیل صوت به متن
# =========================================================

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

        from faster_whisper import WhisperModel

        model = WhisperModel(
            "tiny",
            device="cpu",
            compute_type="int8"
        )

        segments, info = model.transcribe(
            str(wav_file),
            language="fa",
            vad_filter=True
        )

        text = " ".join(
            segment.text.strip()
            for segment in segments
        ).strip()

        if not text:
            text = "متنی از فایل صوتی شناسایی نشد."

        return success(
            "تبدیل صوت به متن انجام شد.",
            transcribed_text=text
        )

    except Exception as e:

        return failure(
            f"تبدیل صوت به متن انجام نشد: {e}"
        )


# =========================================================
# 4 - تبدیل عکس به متن
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
            text = "متنی در تصویر پیدا نشد."

        return success(
            "متن تصویر استخراج شد.",
            image_text=text
        )

    except Exception as e:

        return failure(
            f"استخراج متن انجام نشد: {e}"
        )


# =========================================================
# 5 - فشرده‌سازی و تغییر اندازه عکس
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

        max_width = int(
            request.form.get(
                "max_width",
                "1600"
            )
        )

        quality = int(
            request.form.get(
                "quality",
                "80"
            )
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

            ratio = max_width / image.width

            new_width = max_width

            new_height = max(
                1,
                int(image.height * ratio)
            )

            image = image.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )

        if image.mode not in ("RGB", "L"):

            image = image.convert("RGB")

        output = create_output("jpg")

        image.save(
            output,
            "JPEG",
            quality=quality,
            optimize=True
        )

        return success(
            "تصویر فشرده و تغییر اندازه داده شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


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

        first = images[0]

        first.save(
            output,
            "PDF",
            save_all=True,
            append_images=images[1:]
        )

        return success(
            "تصویر به PDF تبدیل شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


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

        lines = text.splitlines()

        if not lines:
            lines = [text]

        for line in lines:

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

        return success(
            "PDF ساخته شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 8 - ساخت QR Code
# =========================================================

@app.route("/qr-code", methods=["POST"])
def qr_code():

    try:

        data = (
            request.form.get(
                "qr_data",
                ""
            )
            .strip()
        )

        if not data:
            raise ValueError(
                "متن یا لینک QR را وارد کنید."
            )

        import qrcode

        output = create_output("png")

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4
        )

        qr.add_data(data)

        qr.make(
            fit=True
        )

        image = qr.make_image()

        image.save(
            output
        )

        return success(
            "QR Code ساخته شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 9 - فشرده‌سازی PDF
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

        ghostscript = shutil.which(
            "gs"
        )

        if not ghostscript:

            raise RuntimeError(
                "Ghostscript روی سرور نصب نشده است."
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

        return success(
            "PDF فشرده شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


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

        text_parts = []

        for page in reader.pages:

            text_parts.append(
                page.extract_text() or ""
            )

        text = "\n\n".join(
            text_parts
        ).strip()

        if not text:
            text = "متنی از PDF استخراج نشد."

        return success(
            "متن PDF استخراج شد.",
            transcribed_text=text
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 11 - عکس به JPG
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

        output = create_output(
            "jpg"
        )

        image.save(
            output,
            "JPEG",
            quality=92
        )

        return success(
            "تصویر به JPG تبدیل شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 12 - عکس به PNG
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

        image = Image.open(
            source
        )

        output = create_output(
            "png"
        )

        image.save(
            output,
            "PNG",
            optimize=True
        )

        return success(
            "تصویر به PNG تبدیل شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 13 - برش عکس
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

        image = Image.open(
            source
        )

        x = max(
            0,
            int(request.form.get("x", 0))
        )

        y = max(
            0,
            int(request.form.get("y", 0))
        )

        width = max(
            1,
            int(
                request.form.get(
                    "width",
                    image.width
                )
            )
        )

        height = max(
            1,
            int(
                request.form.get(
                    "height",
                    image.height
                )
            )
        )

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
                "محدوده برش نامعتبر است."
            )

        result = image.crop(
            (x, y, x2, y2)
        )

        output = create_output(
            "png"
        )

        result.save(
            output,
            "PNG"
        )

        return success(
            "تصویر برش خورد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 14 - چرخاندن عکس
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

        image = Image.open(
            source
        )

        angle = float(
            request.form.get(
                "angle",
                90
            )
        )

        result = image.rotate(
            -angle,
            expand=True
        )

        output = create_output(
            "png"
        )

        result.save(
            output,
            "PNG"
        )

        return success(
            "تصویر چرخانده شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 15 - آینه‌ای کردن عکس
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

        image = Image.open(
            source
        )

        result = ImageOps.mirror(
            image
        )

        output = create_output(
            "png"
        )

        result.save(
            output,
            "PNG"
        )

        return success(
            "تصویر آینه‌ای شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 16 - سیاه و سفید کردن عکس
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

        from PIL import Image
        from PIL import ImageOps

        image = Image.open(
            source
        )

        result = ImageOps.grayscale(
            image
        )

        output = create_output(
            "png"
        )

        result.save(
            output,
            "PNG"
        )

        return success(
            "تصویر سیاه‌وسفید شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 17 - تنظیم روشنایی عکس
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

        from PIL import Image
        from PIL import ImageEnhance

        image = Image.open(
            source
        )

        factor = float(
            request.form.get(
                "factor",
                1.2
            )
        )

        factor = max(
            0,
            min(factor, 3)
        )

        result = ImageEnhance.Brightness(
            image
        ).enhance(
            factor
        )

        output = create_output(
            "png"
        )

        result.save(
            output,
            "PNG"
        )

        return success(
            "روشنایی تصویر تغییر کرد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 18 - تنظیم کنتراست عکس
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

        from PIL import Image
        from PIL import ImageEnhance

        image = Image.open(
            source
        )

        factor = float(
            request.form.get(
                "factor",
                1.2
            )
        )

        factor = max(
            0,
            min(factor, 3)
        )

        result = ImageEnhance.Contrast(
            image
        ).enhance(
            factor
        )

        output = create_output(
            "png"
        )

        result.save(
            output,
            "PNG"
        )

        return success(
            "کنتراست تصویر تغییر کرد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 19 - ویرایشگر عکس
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

        from PIL import Image
        from PIL import ImageEnhance
        from PIL import ImageOps
        from PIL import ImageFilter
        from PIL import ImageDraw

        image = Image.open(
            source
        ).convert("RGBA")

        if request.form.get(
            "mirror"
        ) == "1":

            image = ImageOps.mirror(
                image
            )

        angle = float(
            request.form.get(
                "angle",
                0
            )
        )

        if angle:

            image = image.rotate(
                -angle,
                expand=True
            )

        brightness = float(
            request.form.get(
                "brightness",
                1
            )
        )

        brightness = max(
            0,
            min(brightness, 3)
        )

        image = ImageEnhance.Brightness(
            image
        ).enhance(
            brightness
        )

        contrast = float(
            request.form.get(
                "contrast",
                1
            )
        )

        contrast = max(
            0,
            min(contrast, 3)
        )

        image = ImageEnhance.Contrast(
            image
        ).enhance(
            contrast
        )

        blur = float(
            request.form.get(
                "blur",
                0
            )
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
        )

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

        output = create_output(
            "png"
        )

        image.save(
            output,
            "PNG"
        )

        return success(
            "ویرایش عکس انجام شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)
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

        output = create_output(
            fmt
        )

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            output
        )

        return success(
            "فرمت فایل صوتی تبدیل شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


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

        start = max(
            0,
            float(
                request.form.get(
                    "start",
                    0
                )
            )
        )

        duration = max(
            0.1,
            float(
                request.form.get(
                    "duration",
                    10
                )
            )
        )

        output = create_output(
            "mp3"
        )

        run_command(
            "ffmpeg",
            "-y",
            "-ss",
            start,
            "-i",
            source,
            "-t",
            duration,
            "-c:a",
            "libmp3lame",
            output
        )

        return success(
            "قسمت انتخاب‌شده از صدا جدا شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 22 - تغییر بلندی صدا
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

        volume = float(
            request.form.get(
                "volume",
                1.2
            )
        )

        volume = max(
            0,
            min(volume, 5)
        )

        output = create_output(
            "mp3"
        )

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-af",
            f"volume={volume}",
            "-c:a",
            "libmp3lame",
            output
        )

        return success(
            "بلندی صدا تغییر کرد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 23 - کاهش نویز صوت
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

        output = create_output(
            "mp3"
        )

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-af",
            "afftdn",
            "-c:a",
            "libmp3lame",
            output
        )

        return success(
            "کاهش نویز انجام شد.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 24 - حذف سکوت‌های طولانی
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

        output = create_output(
            "mp3"
        )

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
            output
        )

        return success(
            "سکوت‌های طولانی حذف شدند.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 25 - ادغام چند فایل صوتی
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
            if file
            and file.filename
            and get_extension(file.filename)
            in AUDIO_EXTENSIONS
        ]

        if len(valid_files) < 2:

            raise ValueError(
                "حداقل دو فایل صوتی انتخاب کنید."
            )

        saved_files = []

        for file in valid_files:

            saved_files.append(
                save_uploaded_file(
                    file,
                    AUDIO_EXTENSIONS
                )
            )

        list_file = (
            UPLOAD_DIR
            / f"{uuid.uuid4().hex}.txt"
        )

        with open(
            list_file,
            "w",
            encoding="utf-8"
        ) as f:

            for source in saved_files:

                safe_path = (
                    str(source)
                    .replace("'", "'\\''")
                )

                f.write(
                    f"file '{safe_path}'\n"
                )

        output = create_output(
            "mp3"
        )

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
            output
        )

        return success(
            "فایل‌های صوتی با هم ادغام شدند.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 26 - ادغام چند PDF
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

                writer.add_page(
                    page
                )

        if len(writer.pages) == 0:

            raise ValueError(
                "PDF معتبری پیدا نشد."
            )

        output = create_output(
            "pdf"
        )

        with open(
            output,
            "wb"
        ) as file:

            writer.write(file)

        return success(
            "PDFها با موفقیت ادغام شدند.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


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
                    item.split(
                        "-",
                        1
                    )
                )

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
                number >= 1
                and number <= len(reader.pages)
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

        output = create_output(
            "pdf"
        )

        with open(
            output,
            "wb"
        ) as file:

            writer.write(file)

        return success(
            "صفحات انتخاب‌شده جدا شدند.",
            result_file=output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 28 - تبدیل PDF به JPG
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
                "pdftoppm روی سرور نصب نشده است."
            )

        prefix = (
            OUTPUT_DIR
            / uuid.uuid4().hex
        )

        run_command(
            pdftoppm,
            "-jpeg",
            "-r",
            "150",
            source,
            prefix
        )

        images = sorted(
            OUTPUT_DIR.glob(
                prefix.name + "-*.jpg"
            )
        )

        if not images:

            raise RuntimeError(
                "تبدیل PDF به تصویر انجام نشد."
            )

        return success(
            "صفحه اول PDF به JPG تبدیل شد.",
            result_file=images[0].name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 29 - شمارش کلمات و حروف
# =========================================================

@app.route("/text-stats", methods=["POST"])
def text_stats():

    try:

        text = (
            request.form.get(
                "text_content"
            )
            or request.form.get("text")
            or ""
        )

        characters = len(text)

        characters_without_spaces = len(
            re.sub(
                r"\s+",
                "",
                text
            )
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

        return success(
            "آمار متن محاسبه شد.",
            transcribed_text=result
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 30 - تبدیل حروف بزرگ و کوچک
# =========================================================

@app.route("/text-case", methods=["POST"])
def text_case():

    try:

        text = (
            request.form.get(
                "text_content"
            )
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

        return success(
            "حروف متن تبدیل شدند.",
            transcribed_text=result
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 31 - پاکسازی متن
# =========================================================

@app.route("/text-clean", methods=["POST"])
def text_clean():

    try:

        text = (
            request.form.get(
                "text_content"
            )
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

        return success(
            "متن پاکسازی شد.",
            transcribed_text=text
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 32 - مرتب‌سازی خطوط متن
# =========================================================

@app.route("/text-sort", methods=["POST"])
def text_sort():

    try:

        text = (
            request.form.get(
                "text_content"
            )
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

        result = "\n".join(
            lines
        )

        return success(
            "خطوط متن مرتب شدند.",
            transcribed_text=result
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 33 - شماره‌گذاری متن
# =========================================================

@app.route("/text-number", methods=["POST"])
def text_number():

    try:

        text = (
            request.form.get(
                "text_content"
            )
            or request.form.get("text")
            or ""
        )

        result = "\n".join(
            f"{index}. {line}"
            for index, line in enumerate(
                text.splitlines(),
                start=1
            )
        )

        return success(
            "خطوط متن شماره‌گذاری شدند.",
            transcribed_text=result
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 34 - جستجو و جایگزینی متن
# =========================================================

@app.route("/text-replace", methods=["POST"])
def text_replace():

    try:

        text = (
            request.form.get(
                "text_content"
            )
            or request.form.get("text")
            or ""
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

        return success(
            "جایگزینی انجام شد.",
            transcribed_text=result
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 35 - مقایسه دو متن
# =========================================================

@app.route("/text-compare", methods=["POST"])
def text_compare():

    try:

        import difflib

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

        return success(
            "مقایسه دو متن انجام شد.",
            transcribed_text=result
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 36 - ساخت رمز عبور تصادفی
# =========================================================

@app.route("/password", methods=["POST"])
def password():

    try:

        import secrets
        import string

        length = int(
            request.form.get(
                "length",
                16
            )
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

        return success(
            "رمز عبور ساخته شد.",
            transcribed_text=result
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 37 - عدد تصادفی
# =========================================================

@app.route("/random-number", methods=["POST"])
def random_number():

    try:

        import secrets

        minimum = int(
            request.form.get(
                "minimum",
                1
            )
        )

        maximum = int(
            request.form.get(
                "maximum",
                100
            )
        )

        if minimum > maximum:

            minimum, maximum = (
                maximum,
                minimum
            )

        number = (
            secrets.randbelow(
                maximum - minimum + 1
            )
            + minimum
        )

        return success(
            "عدد تصادفی ساخته شد.",
            transcribed_text=str(
                number
            )
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 38 - تبدیل واحد
# =========================================================

@app.route("/unit-convert", methods=["POST"])
def unit_convert():

    try:

        value = float(
            request.form.get(
                "value",
                0
            )
        )

        conversion = request.form.get(
            "kind",
            "km-m"
        )

        conversions = {

            "km-m":
                value * 1000,

            "m-km":
                value / 1000,

            "kg-g":
                value * 1000,

            "g-kg":
                value / 1000,

            "l-ml":
                value * 1000,

            "ml-l":
                value / 1000,

            "c-f":
                value * 9 / 5 + 32,

            "f-c":
                (value - 32) * 5 / 9
        }

        if conversion not in conversions:

            raise ValueError(
                "نوع تبدیل واحد نامعتبر است."
            )

        result = conversions[
            conversion
        ]

        return success(
            "تبدیل واحد انجام شد.",
            transcribed_text=str(
                result
            )
        )

    except Exception as e:

        return failure(e)


# =========================================================
# 39 - دانلود فایل خروجی
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
# 40 - API وضعیت سایت
# =========================================================

@app.route("/health")
def health():

    return jsonify(
        status="ok",
        service="online"
    )


@app.route("/api/tools")
def api_tools():

    return jsonify(
        status="active",
        tools=40
    )


# =========================================================
# Sitemap
# =========================================================

@app.route("/sitemap.xml")
def sitemap():

    base_url = (
        "https://rt-k9g5.onrender.com"
    )

    routes = [
        "",
        "/about",
        "/contact",
        "/text-to-speech"
    ]

    xml = (
        '<?xml version="1.0" '
        'encoding="UTF-8"?>'
        '<urlset '
        'xmlns="http://www.sitemaps.org/'
        'schemas/sitemap/0.9">'
    )

    for route in routes:

        xml += (
            "<url>"
            f"<loc>{base_url}{route}</loc>"
            "</url>"
        )

    xml += "</urlset>"

    return (
        xml,
        200,
        {
            "Content-Type":
                "application/xml; charset=utf-8"
        }
    )


# =========================================================
# Robots.txt
# =========================================================

@app.route("/robots.txt")
def robots():

    return (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        "Sitemap: "
        "https://rt-k9g5.onrender.com/"
        "sitemap.xml\n"
    )


# =========================================================
# خطای حجم فایل
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    return (
        failure(
            "حجم فایل بیشتر از 100 مگابایت است."
        ),
        413
    )


# =========================================================
# خطای عمومی
# =========================================================

@app.errorhandler(500)
def server_error(error):

    return (
        failure(
            "خطای داخلی سرور رخ داد. "
            "لطفاً دوباره تلاش کنید."
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
