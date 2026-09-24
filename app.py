import os
import re
import uuid
import json
import base64
import hashlib
import secrets
import string
import shutil
import subprocess
import datetime
import urllib.parse

from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    send_from_directory,
    jsonify,
    Response
)

from werkzeug.utils import secure_filename


app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 150 * 1024 * 1024


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

VIDEO_EXTENSIONS = {
    "mp4",
    "webm",
    "mkv",
    "mov",
    "avi",
    "m4v"
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

PDF_EXTENSIONS = {
    "pdf"
}


# =========================================================
# HELPERS
# =========================================================

def get_extension(filename):

    filename = secure_filename(filename or "")

    return Path(filename).suffix.lower().replace(".", "")


def save_upload(file, allowed_extensions):

    if not file or not file.filename:

        raise ValueError(
            "لطفاً یک فایل انتخاب کنید."
        )

    extension = get_extension(
        file.filename
    )

    if extension not in allowed_extensions:

        raise ValueError(
            "فرمت فایل پشتیبانی نمی‌شود."
        )

    path = (
        UPLOAD_DIR /
        f"{uuid.uuid4().hex}.{extension}"
    )

    file.save(path)

    return path


def create_output(extension):

    return (
        OUTPUT_DIR /
        f"{uuid.uuid4().hex}.{extension}"
    )


def run_command(*command, timeout=900):

    result = subprocess.run(
        [str(x) for x in command],
        capture_output=True,
        text=True,
        timeout=timeout
    )

    if result.returncode != 0:

        error = (
            result.stderr
            or result.stdout
            or "پردازش ناموفق بود."
        )

        raise RuntimeError(
            error[-3000:]
        )

    return result


def success(
    message,
    result_file=None,
    result_text=None
):

    return render_template(
        "index.html",
        success_text=message,
        result_file=result_file,
        result_text=result_text
    )


def failure(error):

    return render_template(
        "index.html",
        error_text=str(error)
    )


# =========================================================
# MAIN
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


@app.route("/about")
def about():

    return render_template(
        "index.html",
        simple_page="درباره ابزارینو"
    )


@app.route("/contact")
def contact():

    return render_template(
        "index.html",
        simple_page="تماس با ما"
    )


@app.route("/health")
def health():

    return jsonify(
        status="ok",
        service="abzarino"
    )


@app.route("/api/tools")
def api_tools():

    return jsonify(
        status="active",
        tools=70
    )


@app.route("/download/<path:filename>")
def download(filename):

    return send_from_directory(
        OUTPUT_DIR,
        filename,
        as_attachment=True
    )


# =========================================================
# TEXT TO SPEECH
# =========================================================

@app.route(
    "/text-to-speech",
    methods=["POST"]
)
@app.route(
    "/process-text",
    methods=["POST"]
)
def text_to_speech():

    try:

        text = (
            request.form.get("text")
            or request.form.get("text_input")
            or ""
        ).strip()

        if not text:

            raise ValueError(
                "متن را وارد کنید."
            )

        import asyncio
        import edge_tts

        output = create_output(
            "mp3"
        )

        async def generate():

            communicator = edge_tts.Communicate(
                text,
                "fa-IR-DilaraNeural"
            )

            await communicator.save(
                str(output)
            )

        asyncio.run(generate())

        return success(
            "تبدیل متن به صدا انجام شد.",
            output.name
        )

    except Exception as e:

        return failure(e)


# =========================================================
# TEXT TOOLS
# =========================================================

@app.route(
    "/text-stats",
    methods=["POST"]
)
def text_stats():

    text = request.form.get(
        "text",
        ""
    )

    chars = len(text)

    no_spaces = len(
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
        f"تعداد حروف: {chars}\n"
        f"حروف بدون فاصله: {no_spaces}\n"
        f"تعداد کلمات: {words}\n"
        f"تعداد خطوط: {lines}"
    )

    return success(
        "آمار متن آماده شد.",
        result_text=result
    )


@app.route(
    "/text-clean",
    methods=["POST"]
)
def text_clean():

    text = request.form.get(
        "text",
        ""
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
        result_text=text
    )


@app.route(
    "/text-case",
    methods=["POST"]
)
def text_case():

    text = request.form.get(
        "text",
        ""
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
        "تغییر متن انجام شد.",
        result_text=result
    )


@app.route(
    "/text-sort",
    methods=["POST"]
)
def text_sort():

    lines = [
        x
        for x in request.form.get(
            "text",
            ""
        ).splitlines()
        if x.strip()
    ]

    mode = request.form.get(
        "mode",
        "asc"
    )

    lines.sort(
        reverse=mode == "desc"
    )

    return success(
        "مرتب‌سازی انجام شد.",
        result_text="\n".join(lines)
    )


@app.route(
    "/text-number",
    methods=["POST"]
)
def text_number():

    lines = request.form.get(
        "text",
        ""
    ).splitlines()

    result = "\n".join(
        f"{i}. {line}"
        for i, line in enumerate(
            lines,
            1
        )
    )

    return success(
        "شماره‌گذاری انجام شد.",
        result_text=result
    )


@app.route(
    "/text-replace",
    methods=["POST"]
)
def text_replace():

    text = request.form.get(
        "text",
        ""
    )

    find_text = request.form.get(
        "find",
        ""
    )

    replace_text = request.form.get(
        "replace",
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
        result_text=result
    )


@app.route(
    "/text-compare",
    methods=["POST"]
)
def text_compare():

    import difflib

    first = request.form.get(
        "first",
        ""
    )

    second = request.form.get(
        "second",
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
        "مقایسه انجام شد.",
        result_text=result
    )


@app.route(
    "/text-count",
    methods=["POST"]
)
def text_count():

    text = request.form.get(
        "text",
        ""
    )

    result = (
        f"کلمات: "
        f"{len(re.findall(r'\\S+', text))}\n"
        f"حروف: {len(text)}"
    )

    return success(
        "شمارش انجام شد.",
        result_text=result
    )


# =========================================================
# PASSWORD / RANDOM
# =========================================================

@app.route(
    "/password",
    methods=["POST"]
)
def password():

    length = int(
        request.form.get(
            "length",
            16
        )
    )

    length = max(
        4,
        min(
            length,
            128
        )
    )

    characters = (
        string.ascii_letters
        + string.digits
        + "!@#$%^&*_-+="
    )

    result = "".join(
        secrets.choice(characters)
        for _ in range(length)
    )

    return success(
        "رمز عبور ساخته شد.",
        result_text=result
    )


@app.route(
    "/random-number",
    methods=["POST"]
)
def random_number():

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
        result_text=str(number)
    )


# =========================================================
# IMAGE
# =========================================================

@app.route(
    "/image-to-text",
    methods=["POST"]
)
def image_to_text():

    try:

        file = (
            request.files.get("file")
            or request.files.get(
                "image_file"
            )
        )

        source = save_upload(
            file,
            IMAGE_EXTENSIONS
        )

        from PIL import Image
        import pytesseract

        image = Image.open(
            source
        )

        text = pytesseract.image_to_string(
            image,
            lang="fas+eng"
        ).strip()

        if not text:

            text = (
                "متنی در تصویر پیدا نشد."
            )

        return success(
            "متن تصویر استخراج شد.",
            result_text=text
        )

    except Exception as e:

        return failure(e)


@app.route(
    "/image-compress",
    methods=["POST"]
)
def image_compress():

    from PIL import Image

    source = save_upload(
        request.files.get("file"),
        IMAGE_EXTENSIONS
    )

    image = Image.open(
        source
    )

    width = int(
        request.form.get(
            "width",
            1600
        )
    )

    quality = int(
        request.form.get(
            "quality",
            80
        )
    )

    quality = max(
        10,
        min(
            quality,
            95
        )
    )

    if image.width > width:

        ratio = (
            width /
            image.width
        )

        image = image.resize(
            (
                width,
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

    image = image.convert(
        "RGB"
    )

    output = create_output(
        "jpg"
    )

    image.save(
        output,
        "JPEG",
        quality=quality,
        optimize=True
    )

    return success(
        "تصویر فشرده شد.",
        output.name
    )


@app.route(
    "/image-resize",
    methods=["POST"]
)
def image_resize():

    from PIL import Image

    source = save_upload(
        request.files.get("file"),
        IMAGE_EXTENSIONS
    )

    image = Image.open(
        source
    )

    width = int(
        request.form.get(
            "width",
            image.width
        )
    )

    height = int(
        request.form.get(
            "height",
            image.height
        )
    )

    result = image.resize(
        (
            max(1, width),
            max(1, height)
        ),
        Image.Resampling.LANCZOS
    )

    output = create_output(
        "png"
    )

    result.save(
        output,
        "PNG"
    )

    return success(
        "اندازه تصویر تغییر کرد.",
        output.name
    )


@app.route(
    "/image-convert",
    methods=["POST"]
)
def image_convert():

    from PIL import Image

    source = save_upload(
        request.files.get("file"),
        IMAGE_EXTENSIONS
    )

    image = Image.open(
        source
    )

    fmt = request.form.get(
        "format",
        "png"
    ).lower()

    if fmt == "jpg":

        fmt = "jpeg"

    if fmt not in {
        "jpeg",
        "png",
        "webp"
    }:

        raise ValueError(
            "فرمت خروجی نامعتبر است."
        )

    if fmt == "jpeg":

        image = image.convert(
            "RGB"
        )

    output = create_output(
        "jpg"
        if fmt == "jpeg"
        else fmt
    )

    image.save(
        output,
        fmt.upper()
    )

    return success(
        "فرمت تصویر تبدیل شد.",
        output.name
    )


@app.route(
    "/image-crop",
    methods=["POST"]
)
def image_crop():

    from PIL import Image

    source = save_upload(
        request.files.get("file"),
        IMAGE_EXTENSIONS
    )

    image = Image.open(
        source
    )

    x = int(
        request.form.get(
            "x",
            0
        )
    )

    y = int(
        request.form.get(
            "y",
            0
        )
    )

    width = int(
        request.form.get(
            "width"
        )
        or image.width
    )

    height = int(
        request.form.get(
            "height"
        )
        or image.height
    )

    result = image.crop(
        (
            x,
            y,
            min(
                image.width,
                x + width
            ),
            min(
                image.height,
                y + height
            )
        )
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
        output.name
    )


@app.route(
    "/image-rotate",
    methods=["POST"]
)
def image_rotate():

    from PIL import Image

    source = save_upload(
        request.files.get("file"),
        IMAGE_EXTENSIONS
    )

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
        output.name
    )


@app.route(
    "/image-mirror",
    methods=["POST"]
)
def image_mirror():

    from PIL import Image
    from PIL import ImageOps

    source = save_upload(
        request.files.get("file"),
        IMAGE_EXTENSIONS
    )

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
        output.name
    )


@app.route(
    "/image-gray",
    methods=["POST"]
)
def image_gray():

    from PIL import Image
    from PIL import ImageOps

    source = save_upload(
        request.files.get("file"),
        IMAGE_EXTENSIONS
    )

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
        output.name
    )


@app.route(
    "/image-adjust",
    methods=["POST"]
)
def image_adjust():

    from PIL import Image
    from PIL import ImageEnhance
    from PIL import ImageFilter

    source = save_upload(
        request.files.get("file"),
        IMAGE_EXTENSIONS
    )

    image = Image.open(
        source
    ).convert(
        "RGBA"
    )

    brightness = float(
        request.form.get(
            "brightness",
            1
        )
    )

    contrast = float(
        request.form.get(
            "contrast",
            1
        )
    )

    blur = float(
        request.form.get(
            "blur",
            0
        )
    )

    image = ImageEnhance.Brightness(
        image
    ).enhance(
        max(
            0,
            min(
                3,
                brightness
            )
        )
    )

    image = ImageEnhance.Contrast(
        image
    ).enhance(
        max(
            0,
            min(
                3,
                contrast
            )
        )
    )

    if blur > 0:

        image = image.filter(
            ImageFilter.GaussianBlur(
                min(
                    20,
                    blur
                )
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
        "تنظیمات تصویر اعمال شد.",
        output.name
    )


@app.route(
    "/image-watermark",
    methods=["POST"]
)
def image_watermark():

    from PIL import Image
    from PIL import ImageDraw

    source = save_upload(
        request.files.get("file"),
        IMAGE_EXTENSIONS
    )

    image = Image.open(
        source
    ).convert(
        "RGBA"
    )

    text = request.form.get(
        "text",
        "ابزارینو"
    )

    draw = ImageDraw.Draw(
        image
    )

    draw.text(
        (30, 30),
        text[:300],
        fill=(
            255,
            255,
            255,
            220
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
        "واترمارک اضافه شد.",
        output.name
    )


@app.route(
    "/favicon",
    methods=["POST"]
)
def favicon():

    from PIL import Image

    source = save_upload(
        request.files.get("file"),
        IMAGE_EXTENSIONS
    )

    image = Image.open(
        source
    ).convert(
        "RGBA"
    )

    image.thumbnail(
        (
            512,
            512
        ),
        Image.Resampling.LANCZOS
    )

    output = create_output(
        "ico"
    )

    image.save(
        output,
        "ICO",
        sizes=[
            (32, 32),
            (64, 64),
            (128, 128)
        ]
    )

    return success(
        "Favicon ساخته شد.",
        output.name
    )


# =========================================================
# AUDIO
# =========================================================

@app.route(
    "/audio-convert",
    methods=["POST"]
)
def audio_convert():

    source = save_upload(
        request.files.get("file"),
        AUDIO_EXTENSIONS
        | VIDEO_EXTENSIONS
    )

    fmt = request.form.get(
        "format",
        "mp3"
    )

    output = create_output(
        fmt
    )

    codecs = {

        "mp3": [
            "-c:a",
            "libmp3lame"
        ],

        "wav": [
            "-c:a",
            "pcm_s16le"
        ],

        "ogg": [
            "-c:a",
            "libvorbis"
        ],

        "flac": [
            "-c:a",
            "flac"
        ],

        "m4a": [
            "-c:a",
            "aac"
        ]

    }

    run_command(
        "ffmpeg",
        "-y",
        "-i",
        source,
        *codecs.get(
            fmt,
            []
        ),
        output
    )

    return success(
        "فرمت صوت تبدیل شد.",
        output.name
    )


@app.route(
    "/audio-cut",
    methods=["POST"]
)
def audio_cut():

    source = save_upload(
        request.files.get("file"),
        AUDIO_EXTENSIONS
        | VIDEO_EXTENSIONS
    )

    start = float(
        request.form.get(
            "start",
            0
        )
    )

    duration = float(
        request.form.get(
            "duration",
            10
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
        "قسمت انتخاب‌شده جدا شد.",
        output.name
    )


@app.route(
    "/audio-volume",
    methods=["POST"]
)
def audio_volume():

    source = save_upload(
        request.files.get("file"),
        AUDIO_EXTENSIONS
        | VIDEO_EXTENSIONS
    )

    volume = float(
        request.form.get(
            "volume",
            1.2
        )
    )

    volume = max(
        0,
        min(
            5,
            volume
        )
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
        output.name
    )


@app.route(
    "/audio-clean",
    methods=["POST"]
)
def audio_clean():

    source = save_upload(
        request.files.get("file"),
        AUDIO_EXTENSIONS
        | VIDEO_EXTENSIONS
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
        output.name
    )


@app.route(
    "/extract-audio",
    methods=["POST"]
)
def extract_audio():

    source = save_upload(
        request.files.get("file"),
        VIDEO_EXTENSIONS
    )

    output = create_output(
        "mp3"
    )

    run_command(
        "ffmpeg",
        "-y",
        "-i",
        source,
        "-vn",
        "-c:a",
        "libmp3lame",
        output
    )

    return success(
        "صوت از ویدئو استخراج شد.",
        output.name
    )


# =========================================================
# VIDEO
# =========================================================

@app.route(
    "/video-cut",
    methods=["POST"]
)
def video_cut():

    source = save_upload(
        request.files.get("file"),
        VIDEO_EXTENSIONS
    )

    start = float(
        request.form.get(
            "start",
            0
        )
    )

    duration = float(
        request.form.get(
            "duration",
            10
        )
    )

    output = create_output(
        "mp4"
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
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        output
    )

    return success(
        "ویدئو برش خورد.",
        output.name
    )


@app.route(
    "/video-mp3",
    methods=["POST"]
)
def video_mp3():

    return extract_audio()


@app.route(
    "/video-gif",
    methods=["POST"]
)
def video_gif():

    source = save_upload(
        request.files.get("file"),
        VIDEO_EXTENSIONS
    )

    output = create_output(
        "gif"
    )

    run_command(
        "ffmpeg",
        "-y",
        "-i",
        source,
        "-vf",
        "fps=10,scale=480:-1:flags=lanczos",
        "-t",
        "10",
        output
    )

    return success(
        "GIF ساخته شد.",
        output.name
    )


@app.route(
    "/video-frame",
    methods=["POST"]
)
def video_frame():

    source = save_upload(
        request.files.get("file"),
        VIDEO_EXTENSIONS
    )

    second = float(
        request.form.get(
            "time",
            0
        )
    )

    output = create_output(
        "jpg"
    )

    run_command(
        "ffmpeg",
        "-y",
        "-ss",
        second,
        "-i",
        source,
        "-frames:v",
        "1",
        output
    )

    return success(
        "فریم استخراج شد.",
        output.name
    )


@app.route(
    "/video-resize",
    methods=["POST"]
)
def video_resize():

    source = save_upload(
        request.files.get("file"),
        VIDEO_EXTENSIONS
    )

    width = int(
        request.form.get(
            "width",
            1280
        )
    )

    height = int(
        request.form.get(
            "height",
            720
        )
    )

    output = create_output(
        "mp4"
    )

    run_command(
        "ffmpeg",
        "-y",
        "-i",
        source,
        "-vf",
        f"scale={width}:{height}",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        output
    )

    return success(
        "اندازه ویدئو تغییر کرد.",
        output.name
    )


@app.route(
    "/video-compress",
    methods=["POST"]
)
def video_compress():

    source = save_upload(
        request.files.get("file"),
        VIDEO_EXTENSIONS
    )

    output = create_output(
        "mp4"
    )

    run_command(
        "ffmpeg",
        "-y",
        "-i",
        source,
        "-c:v",
        "libx264",
        "-crf",
        "28",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        output
    )

    return success(
        "ویدئو فشرده شد.",
        output.name
    )


# =========================================================
# SPEECH TO TEXT
# =========================================================

@app.route(
    "/speech-to-text",
    methods=["POST"]
)
def speech_to_text():

    try:

        source = save_upload(
            request.files.get("file"),
            AUDIO_EXTENSIONS
            | VIDEO_EXTENSIONS
        )

        wav = create_output(
            "wav"
        )

        run_command(
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-ac",
            "1",
            "-ar",
            "16000",
            wav
        )

        from faster_whisper import WhisperModel

        model = WhisperModel(
            "tiny",
            device="cpu",
            compute_type="int8"
        )

        segments, info = model.transcribe(
            str(wav),
            language="fa",
            vad_filter=True
        )

        text = " ".join(
            segment.text.strip()
            for segment in segments
        ).strip()

        if not text:

            text = (
                "متنی از صوت شناسایی نشد."
            )

        return success(
            "تبدیل صوت به متن انجام شد.",
            result_text=text
        )

    except Exception as e:

        return failure(e)


# =========================================================
# PDF
# =========================================================

@app.route(
    "/image-to-pdf",
    methods=["POST"]
)
def image_to_pdf():

    from PIL import Image

    files = [
        x
        for x in request.files.getlist(
            "files"
        )
        if x.filename
    ]

    if not files:

        file = request.files.get(
            "file"
        )

        if file:

            files = [file]

    if not files:

        raise ValueError(
            "حداقل یک تصویر انتخاب کنید."
        )

    images = []

    for file in files:

        source = save_upload(
            file,
            IMAGE_EXTENSIONS
        )

        images.append(
            Image.open(
                source
            ).convert(
                "RGB"
            )
        )

    output = create_output(
        "pdf"
    )

    images[0].save(
        output,
        "PDF",
        save_all=True,
        append_images=images[1:]
    )

    return success(
        "PDF ساخته شد.",
        output.name
    )


@app.route(
    "/text-to-pdf",
    methods=["POST"]
)
def text_to_pdf():

    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    text = request.form.get(
        "text",
        ""
    )

    if not text.strip():

        raise ValueError(
            "متنی وارد نشده است."
        )

    output = create_output(
        "pdf"
    )

    pdf = canvas.Canvas(
        str(output),
        pagesize=A4
    )

    width, height = A4

    y = height - 50

    pdf.setFont(
        "Helvetica",
        11
    )

    for line in (
        text.splitlines()
        or [""]
    ):

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
        output.name
    )


@app.route(
    "/pdf-text",
    methods=["POST"]
)
def pdf_text():

    from pypdf import PdfReader

    source = save_upload(
        request.files.get("file"),
        PDF_EXTENSIONS
    )

    reader = PdfReader(
        str(source)
    )

    text = "\n\n".join(
        page.extract_text()
        or ""
        for page in reader.pages
    )

    return success(
        "متن PDF استخراج شد.",
        result_text=text
    )


@app.route(
    "/pdf-merge",
    methods=["POST"]
)
def pdf_merge():

    from pypdf import (
        PdfReader,
        PdfWriter
    )

    files = [
        x
        for x in request.files.getlist(
            "files"
        )
        if x.filename
    ]

    if len(files) < 2:

        raise ValueError(
            "حداقل دو PDF انتخاب کنید."
        )

    writer = PdfWriter()

    for file in files:

        source = save_upload(
            file,
            PDF_EXTENSIONS
        )

        reader = PdfReader(
            str(source)
        )

        for page in reader.pages:

            writer.add_page(
                page
            )

    output = create_output(
        "pdf"
    )

    with open(
        output,
        "wb"
    ) as f:

        writer.write(f)

    return success(
        "PDFها ادغام شدند.",
        output.name
    )


@app.route(
    "/pdf-split",
    methods=["POST"]
)
def pdf_split():

    from pypdf import (
        PdfReader,
        PdfWriter
    )

    source = save_upload(
        request.files.get("file"),
        PDF_EXTENSIONS
    )

    reader = PdfReader(
        str(source)
    )

    pages = request.form.get(
        "pages",
        "1"
    )

    selected = []

    for item in pages.split(","):

        item = item.strip()

        if "-" in item:

            a, b = map(
                int,
                item.split("-")
            )

            selected.extend(
                range(a, b + 1)
            )

        else:

            selected.append(
                int(item)
            )

    writer = PdfWriter()

    for number in selected:

        if (
            1 <= number
            <= len(reader.pages)
        ):

            writer.add_page(
                reader.pages[
                    number - 1
                ]
            )

    if not writer.pages:

        raise ValueError(
            "شماره صفحه معتبر نیست."
        )

    output = create_output(
        "pdf"
    )

    with open(
        output,
        "wb"
    ) as f:

        writer.write(f)

    return success(
        "صفحات PDF استخراج شدند.",
        output.name
    )


@app.route(
    "/pdf-compress",
    methods=["POST"]
)
def pdf_compress():

    source = save_upload(
        request.files.get("file"),
        PDF_EXTENSIONS
    )

    gs = shutil.which(
        "gs"
    )

    if not gs:

        raise RuntimeError(
            "Ghostscript نصب نشده است."
        )

    output = create_output(
        "pdf"
    )

    run_command(
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dPDFSETTINGS=/ebook",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        f"-sOutputFile={output}",
        source
    )

    return success(
        "PDF فشرده شد.",
        output.name
    )


@app.route(
    "/pdf-jpg",
    methods=["POST"]
)
def pdf_jpg():

    source = save_upload(
        request.files.get("file"),
        PDF_EXTENSIONS
    )

    executable = shutil.which(
        "pdftoppm"
    )

    if not executable:

        raise RuntimeError(
            "pdftoppm نصب نشده است."
        )

    prefix = (
        OUTPUT_DIR /
        uuid.uuid4().hex
    )

    run_command(
        executable,
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
            "تبدیل PDF انجام نشد."
        )

    return success(
        "صفحه اول PDF به JPG تبدیل شد.",
        images[0].name
    )


# =========================================================
# QR
# =========================================================

@app.route(
    "/qr-code",
    methods=["POST"]
)
def qr_code():

    import qrcode

    data = request.form.get(
        "data",
        ""
    ).strip()

    if not data:

        raise ValueError(
            "متن یا لینک QR را وارد کنید."
        )

    output = create_output(
        "png"
    )

    image = qrcode.make(
        data
    )

    image.save(
        output
    )

    return success(
        "QR Code ساخته شد.",
        output.name
    )


# =========================================================
# PROGRAMMING
# =========================================================

@app.route(
    "/json-format",
    methods=["POST"]
)
def json_format():

    text = request.form.get(
        "text",
        ""
    )

    try:

        result = json.dumps(
            json.loads(text),
            ensure_ascii=False,
            indent=2
        )

    except Exception as e:

        raise ValueError(
            f"JSON نامعتبر است: {e}"
        )

    return success(
        "JSON قالب‌بندی شد.",
        result_text=result
    )


@app.route(
    "/json-validate",
    methods=["POST"]
)
def json_validate():

    text = request.form.get(
        "text",
        ""
    )

    try:

        json.loads(text)

        result = (
            "JSON معتبر است."
        )

    except Exception as e:

        result = (
            f"JSON نامعتبر است:\n{e}"
        )

    return success(
        "اعتبارسنجی انجام شد.",
        result_text=result
    )


@app.route(
    "/base64",
    methods=["POST"]
)
def base64_tool():

    text = request.form.get(
        "text",
        ""
    )

    mode = request.form.get(
        "mode",
        "encode"
    )

    try:

        if mode == "encode":

            result = (
                base64.b64encode(
                    text.encode(
                        "utf-8"
                    )
                ).decode()
            )

        else:

            result = (
                base64.b64decode(
                    text
                ).decode(
                    "utf-8"
                )
            )

    except Exception as e:

        raise ValueError(
            f"Base64 نامعتبر است: {e}"
        )

    return success(
        "Base64 پردازش شد.",
        result_text=result
    )


@app.route(
    "/url-code",
    methods=["POST"]
)
def url_code():

    text = request.form.get(
        "text",
        ""
    )

    mode = request.form.get(
        "mode",
        "encode"
    )

    if mode == "encode":

        result = urllib.parse.quote(
            text,
            safe=""
        )

    else:

        result = urllib.parse.unquote(
            text
        )

    return success(
        "URL پردازش شد.",
        result_text=result
    )


@app.route(
    "/hash",
    methods=["POST"]
)
def hash_tool():

    text = request.form.get(
        "text",
        ""
    ).encode()

    algorithm = request.form.get(
        "algorithm",
        "sha256"
    )

    allowed = {
        "md5",
        "sha1",
        "sha256",
        "sha512"
    }

    if algorithm not in allowed:

        raise ValueError(
            "الگوریتم نامعتبر است."
        )

    result = hashlib.new(
        algorithm,
        text
    ).hexdigest()

    return success(
        "Hash ساخته شد.",
        result_text=result
    )


@app.route(
    "/uuid",
    methods=["POST"]
)
def uuid_tool():

    return success(
        "UUID ساخته شد.",
        result_text=str(
            uuid.uuid4()
        )
    )


# =========================================================
# CALCULATORS
# =========================================================

@app.route(
    "/percent",
    methods=["POST"]
)
def percent():

    value = float(
        request.form.get(
            "value",
            0
        )
    )

    total = float(
        request.form.get(
            "total",
            0
        )
    )

    result = (
        value /
        total *
        100
    ) if total else 0

    return success(
        "درصد محاسبه شد.",
        result_text=f"{result:g}%"
    )


@app.route(
    "/discount",
    methods=["POST"]
)
def discount():

    price = float(
        request.form.get(
            "price",
            0
        )
    )

    discount_value = float(
        request.form.get(
            "discount",
            0
        )
    )

    final = (
        price *
        (1 - discount_value / 100)
    )

    result = (
        f"قیمت اصلی: {price:g}\n"
        f"درصد تخفیف: {discount_value:g}%\n"
        f"مبلغ نهایی: {final:g}\n"
        f"مقدار تخفیف: "
        f"{price-final:g}"
    )

    return success(
        "تخفیف محاسبه شد.",
        result_text=result
    )


@app.route(
    "/bmi",
    methods=["POST"]
)
def bmi():

    weight = float(
        request.form.get(
            "weight",
            0
        )
    )

    height = (
        float(
            request.form.get(
                "height",
                0
            )
        ) / 100
    )

    if height <= 0:

        raise ValueError(
            "قد نامعتبر است."
        )

    value = (
        weight /
        (height * height)
    )

    return success(
        "BMI محاسبه شد.",
        result_text=f"BMI = {value:.2f}"
    )


@app.route(
    "/age",
    methods=["POST"]
)
def age():

    birthday = datetime.date.fromisoformat(
        request.form.get(
            "birth"
        )
    )

    today = datetime.date.today()

    years = (
        today.year -
        birthday.year -
        (
            (
                today.month,
                today.day
            )
            <
            (
                birthday.month,
                birthday.day
            )
        )
    )

    return success(
        "سن محاسبه شد.",
        result_text=f"سن: {years} سال"
    )


# =========================================================
# SEO
# =========================================================

@app.route(
    "/robots-generator",
    methods=["POST"]
)
def robots_generator():

    site = request.form.get(
        "site",
        ""
    ).rstrip("/")

    result = (
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {site}/sitemap.xml"
    )

    return success(
        "robots.txt ساخته شد.",
        result_text=result
    )


@app.route(
    "/sitemap-generator",
    methods=["POST"]
)
def sitemap_generator():

    site = request.form.get(
        "site",
        ""
    ).rstrip("/")

    pages = request.form.get(
        "pages",
        "/"
    ).splitlines()

    xml = (
        '<?xml version="1.0" '
        'encoding="UTF-8"?>'
        '<urlset '
        'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    )

    for page in pages:

        page = page.strip()

        if not page:
            continue

        xml += (
            "<url><loc>"
            f"{site}/{page.lstrip('/')}"
            "</loc></url>"
        )

    xml += "</urlset>"

    return success(
        "Sitemap ساخته شد.",
        result_text=xml
    )


@app.route(
    "/og-generator",
    methods=["POST"]
)
def og_generator():

    title = request.form.get(
        "title",
        ""
    )

    description = request.form.get(
        "description",
        ""
    )

    url = request.form.get(
        "url",
        ""
    )

    result = (
        f'<meta property="og:title" '
        f'content="{title}">\n'
        f'<meta property="og:description" '
        f'content="{description}">\n'
        f'<meta property="og:url" '
        f'content="{url}">'
    )

    return success(
        "تگ‌های Open Graph ساخته شدند.",
        result_text=result
    )


# =========================================================
# SITEMAP / ROBOTS
# =========================================================

@app.route(
    "/sitemap.xml"
)
def sitemap():

    base = (
        "https://rt-k9g5.onrender.com"
    )

    routes = [
        "",
        "/about",
        "/contact"
    ]

    xml = (
        '<?xml version="1.0" '
        'encoding="UTF-8"?>'
        '<urlset '
        'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    )

    for route in routes:

        xml += (
            f"<url><loc>"
            f"{base}{route}"
            f"</loc></url>"
        )

    xml += "</urlset>"

    return Response(
        xml,
        mimetype="application/xml"
    )


@app.route(
    "/robots.txt"
)
def robots():

    return Response(
        "User-agent: *\n"
        "Allow: /\n\n"
        "Sitemap: "
        "https://rt-k9g5.onrender.com/sitemap.xml\n",
        mimetype="text/plain"
    )


# =========================================================
# ERRORS
# =========================================================

@app.errorhandler(413)
def too_large(error):

    return failure(
        "حجم فایل بیشتر از 150 مگابایت است."
    ), 413


@app.errorhandler(500)
def server_error(error):

    return failure(
        "خطای داخلی سرور رخ داد."
    ), 500


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
