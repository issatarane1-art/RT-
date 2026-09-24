import os
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import soundfile as sf
import edge_tts
import pytesseract
from PIL import Image, ImageOps, ImageFilter
from flask import Flask, render_template, request, send_from_directory, jsonify, abort, Response
from werkzeug.utils import secure_filename

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
SEPARATED = BASE / "separated"
WHISPER_CACHE = BASE / "whisper_cache"

for folder in (UPLOADS, SEPARATED, WHISPER_CACHE):
    folder.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.config["JSON_AS_ASCII"] = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rt-tools")

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".webm"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"}
TTS_VOICE = "fa-IR-DilaraNeural"
MAX_TEXT = 12000
_whisper = None


def clean_name(name):
    name = secure_filename(name or "")
    return name[:120] or "file"


def make_name(original, ext=None):
    original = clean_name(original)
    stem = Path(original).stem or "file"
    suffix = ext if ext is not None else Path(original).suffix.lower()
    return f"{stem}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{suffix}"


def save_upload(storage, allowed):
    if not storage or not storage.filename:
        raise ValueError("فایلی انتخاب نشده است.")
    suffix = Path(storage.filename).suffix.lower()
    if suffix not in allowed:
        raise ValueError("فرمت فایل پشتیبانی نمی‌شود.")
    name = make_name(storage.filename)
    path = UPLOADS / name
    storage.save(path)
    return path


def remove(path):
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def context(**kwargs):
    data = dict(
        success_text=None,
        error_text=None,
        speech_file=None,
        vocals_file=None,
        instrumental_file=None,
        transcribed_text=None,
        image_text=None,
    )
    data.update(kwargs)
    return data


async def _tts(text, output):
    await edge_tts.Communicate(
        text=text,
        voice=TTS_VOICE,
        rate="+0%",
        volume="+0%"
    ).save(str(output))


def make_tts(text):
    import asyncio
    name = make_name("speech", ".mp3")
    asyncio.run(_tts(text, UPLOADS / name))
    return name


def separate_audio(path):
    data, sr = sf.read(str(path), always_2d=True)
    if data.shape[1] < 2:
        raise ValueError("برای این نوع جداسازی، فایل باید استریو باشد.")

    left = data[:, 0].astype(np.float32)
    right = data[:, 1].astype(np.float32)

    vocals = (left + right) / 2
    instrumental = (left - right) / 2

    peak = max(
        float(np.max(np.abs(vocals))) if vocals.size else 0,
        float(np.max(np.abs(instrumental))) if instrumental.size else 0,
        1.0
    )
    vocals = vocals / peak * 0.98
    instrumental = instrumental / peak * 0.98

    stem = Path(path).stem
    a = f"{stem}_vocals_{uuid.uuid4().hex[:8]}.wav"
    b = f"{stem}_instrumental_{uuid.uuid4().hex[:8]}.wav"

    sf.write(str(SEPARATED / a), vocals, sr)
    sf.write(str(SEPARATED / b), instrumental, sr)
    return a, b


def whisper_model():
    global _whisper
    if WhisperModel is None:
        raise RuntimeError("faster-whisper در دسترس نیست.")
    if _whisper is None:
        logger.info("Loading Whisper tiny CPU model...")
        _whisper = WhisperModel(
            "tiny",
            device="cpu",
            compute_type="int8",
            download_root=str(WHISPER_CACHE)
        )
    return _whisper


def transcribe(path):
    model = whisper_model()
    segments, _ = model.transcribe(
        str(path),
        language="fa",
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False
    )
    return " ".join(
        s.text.strip() for s in segments if s.text and s.text.strip()
    ).strip()


def ocr(path):
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        img = ImageOps.autocontrast(img)
        img = img.filter(ImageFilter.SHARPEN)
        return pytesseract.image_to_string(
            img, lang="fas+eng", config="--psm 6"
        ).strip()


@app.route("/")
def home():
    return render_template("index.html", **context())


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/text-to-speech")
def text_to_speech():
    return render_template("text-to-speech.html")


@app.route("/process-text", methods=["POST"])
def process_text():
    text = (request.form.get("text_input") or request.form.get("text") or "").strip()
    if not text:
        return render_template("index.html", **context(error_text="لطفاً متن وارد کنید."))
    if len(text) > MAX_TEXT:
        return render_template("index.html", **context(
            error_text=f"حداکثر طول متن {MAX_TEXT} کاراکتر است."
        ))
    try:
        name = make_tts(text)
        if request.args.get("format") == "json":
            return jsonify(ok=True, audio_file=name)
        return render_template("index.html", **context(
            success_text="صدا با موفقیت ساخته شد.", speech_file=name
        ))
    except Exception:
        logger.exception("TTS error")
        return render_template("index.html", **context(
            error_text="ساخت فایل صوتی انجام نشد."
        )), 500


@app.route("/process-audio", methods=["POST"])
def process_audio():
    storage = request.files.get("audio_file") or request.files.get("audio")
    path = None
    try:
        path = save_upload(storage, AUDIO_EXT)
        vocals, instrumental = separate_audio(path)
        remove(path)
        return render_template("index.html", **context(
            success_text="پردازش صوت انجام شد.",
            vocals_file=vocals,
            instrumental_file=instrumental
        ))
    except ValueError as e:
        return render_template("index.html", **context(error_text=str(e))), 400
    except Exception:
        logger.exception("Audio error")
        remove(path)
        return render_template("index.html", **context(
            error_text="پردازش فایل صوتی انجام نشد."
        )), 500


@app.route("/speech-to-text", methods=["POST"])
def speech_to_text():
    storage = (
        request.files.get("speech_file")
        or request.files.get("speech")
        or request.files.get("audio")
    )
    path = None
    try:
        path = save_upload(storage, AUDIO_EXT)
        text = transcribe(path)
        remove(path)
        return render_template("index.html", **context(
            success_text="تبدیل صوت به متن انجام شد.",
            transcribed_text=text or "متنی شناسایی نشد."
        ))
    except ValueError as e:
        return render_template("index.html", **context(error_text=str(e))), 400
    except Exception:
        logger.exception("STT error")
        remove(path)
        return render_template("index.html", **context(
            error_text="تبدیل صوت به متن انجام نشد."
        )), 500


@app.route("/image-to-text", methods=["POST"])
def image_to_text():
    storage = request.files.get("image_file") or request.files.get("image")
    path = None
    try:
        path = save_upload(storage, IMAGE_EXT)
        text = ocr(path)
        remove(path)
        return render_template("index.html", **context(
            success_text="متن تصویر استخراج شد.",
            image_text=text or "متنی در تصویر پیدا نشد."
        ))
    except ValueError as e:
        return render_template("index.html", **context(error_text=str(e))), 400
    except Exception:
        logger.exception("OCR error")
        remove(path)
        return render_template("index.html", **context(
            error_text="استخراج متن از تصویر انجام نشد."
        )), 500


@app.route("/download/<path:name>")
def download(name):
    name = Path(name).name
    for folder in (SEPARATED, UPLOADS):
        path = folder / name
        if path.exists() and path.is_file():
            return send_from_directory(folder, name, as_attachment=True)
    abort(404)


@app.route("/health")
def health():
    return jsonify(
        ok=True,
        service="rt-k9g5",
        time=datetime.now(timezone.utc).isoformat()
    )


@app.route("/api/tools")
def tools():
    return jsonify(ok=True, tools=[
        {"name": "متن به صدا", "url": "/text-to-speech", "endpoint": "/process-text"},
        {"name": "صوت به متن", "url": "/", "endpoint": "/speech-to-text"},
        {"name": "عکس به متن", "url": "/", "endpoint": "/image-to-text"},
        {"name": "پردازش صوت", "url": "/", "endpoint": "/process-audio"},
    ])


@app.route("/sitemap.xml")
def sitemap():
    base = request.url_root.rstrip("/")
    pages = ["/", "/text-to-speech", "/about", "/contact"]
    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in pages:
        body += ["<url>", f"<loc>{base}{page}</loc>", "</url>"]
    body.append("</urlset>")
    return Response("\n".join(body), mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    base = request.url_root.rstrip("/")
    return Response(
        f"User-agent: *\nAllow: /\nDisallow: /download/\nSitemap: {base}/sitemap.xml\n",
        mimetype="text/plain"
    )


@app.errorhandler(413)
def too_large(_):
    return render_template("index.html", **context(
        error_text="حجم فایل بیش از ۵۰ مگابایت است."
    )), 413


@app.errorhandler(404)
def not_found(_):
    return render_template("index.html", **context(
        error_text="صفحه موردنظر پیدا نشد."
    )), 404


@app.errorhandler(500)
def server_error(_):
    logger.exception("500")
    return render_template("index.html", **context(
        error_text="خطای داخلی سرور رخ داد."
    )), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "10000")),
        debug=False
    )
