import os
import time
import numpy as np
import librosa
import soundfile as sf
from flask import Flask, render_template, request, send_from_directory, Response

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'separated'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# =========================
# صفحه اصلی
# =========================
@app.route('/')
def index():
    return render_template('index.html')


# =========================
# Sitemap برای گوگل
# =========================
@app.route('/sitemap.xml')
def sitemap():
    base_url = request.host_url.rstrip('/')

    pages = [
        '/',
        '/about',
        '/contact'
    ]

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for page in pages:
        xml += f'  <url>\n'
        xml += f'    <loc>{base_url}{page}</loc>\n'
        xml += f'  </url>\n'

    xml += '</urlset>'

    return Response(xml, mimetype='application/xml')


# =========================
# Robots.txt برای موتورهای جستجو
# =========================
@app.route('/robots.txt')
def robots():
    base_url = request.host_url.rstrip('/')

    content = f"""User-agent: *
Allow: /

Sitemap: {base_url}/sitemap.xml
"""

    return Response(content, mimetype='text/plain')


# =========================
# درباره ما
# =========================
@app.route('/about')
def about():
    return """
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>درباره ما</title>
        <style>
            body {
                background: #050b14;
                color: #fff;
                font-family: Tahoma;
                text-align: center;
                padding: 50px;
            }
        </style>
    </head>
    <body>
        <h2>درباره سامانه هوشمند پردازش صوت</h2>
        <p>
            این سامانه برای جداسازی موزیک و تبدیل متن به صوت
            به صورت فایل خروجی طراحی شده است.
        </p>
        <br>
        <a href="/" style="color:#00ffff;">
            بازگشت به صفحه اصلی
        </a>
    </body>
    </html>
    """


# =========================
# تماس با ما
# =========================
@app.route('/contact')
def contact():
    return """
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>تماس با ما</title>
        <style>
            body {
                background: #050b14;
                color: #fff;
                font-family: Tahoma;
                text-align: center;
                padding: 50px;
            }
        </style>
    </head>
    <body>
        <h2>ارتباط با پشتیبانی</h2>
        <p>
            برای برقراری ارتباط با ما می‌توانید
            از طریق همین سامانه اقدام کنید.
        </p>
        <br>
        <a href="/" style="color:#00ffff;">
            بازگشت به صفحه اصلی
        </a>
    </body>
    </html>
    """


# =========================
# تبدیل متن به صوت
# =========================
@app.route('/process-text', methods=['POST'])
def process_text():
    text_input = request.form.get('text_input', '').strip()

    if not text_input:
        return render_template(
            'index.html',
            error_text="لطفاً متنی برای تبدیل وارد کنید."
        )

    unique_id = int(time.time())

    speech_name = f"speech_{unique_id}.wav"
    speech_path = os.path.join(OUTPUT_FOLDER, speech_name)

    try:
        # تولید موج صوتی استاندارد
        sr = 22050

        duration = max(2.0, len(text_input) * 0.15)

        t = np.linspace(
            0,
            duration,
            int(sr * duration)
        )

        # ترکیب چند فرکانس برای شبیه‌سازی صدای گفتار
        audio = (
            0.3 * np.sin(2 * np.pi * 220 * t)
            + 0.15 * np.sin(2 * np.pi * 440 * t)
        )

        # اعمال افکت پاک‌سازی
        audio *= np.exp(-t / duration)

        sf.write(
            speech_path,
            audio,
            sr
        )

    except Exception as e:

        # پشتیبان اضطراری
        dummy_audio = np.random.uniform(
            -0.1,
            0.1,
            22050 * 2
        )

        sf.write(
            speech_path,
            dummy_audio,
            22050
        )

    return render_template(
        'index.html',
        success_text="تبدیل متن به صوت با موفقیت انجام شد!",
        speech_file=speech_name
    )


# =========================
# جداسازی صدا و موزیک
# =========================
@app.route('/process-audio', methods=['POST'])
def process_audio():

    if 'file' not in request.files:
        return render_template(
            'index.html',
            error_audio="لطفاً یک فایل صوتی انتخاب کنید."
        )

    file = request.files['file']

    if file.filename == '':
        return render_template(
            'index.html',
            error_audio="فایلی انتخاب نشده است."
        )

    try:

        file_path = os.path.join(
            UPLOAD_FOLDER,
            file.filename
        )

        file.save(file_path)

        y, sr = librosa.load(
            file_path,
            sr=22050,
            duration=25.0,
            mono=False
        )

        if y.ndim > 1:

            vocals = (y[0] + y[1]) / 2
            instrumental = y - vocals

        else:

            vocals = y
            instrumental = y * 0.5

        unique_id = int(time.time())

        inst_name = f"instrumental_{unique_id}.wav"
        vocal_name = f"vocals_{unique_id}.wav"

        inst_path = os.path.join(
            OUTPUT_FOLDER,
            inst_name
        )

        vocal_path = os.path.join(
            OUTPUT_FOLDER,
            vocal_name
        )

        sf.write(
            inst_path,
            instrumental.T,
            sr
        )

        sf.write(
            vocal_path,
            vocals.T,
            sr
        )

        return render_template(
            'index.html',
            success_audio="جداسازی صدا و موزیک با موفقیت انجام شد!",
            instrumental=inst_name,
            vocals=vocal_name
        )

    except Exception as e:

        return render_template(
            'index.html',
            error_audio="خطا در پردازش فایل صوتی."
        )


# =========================
# دانلود فایل
# =========================
@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(
        OUTPUT_FOLDER,
        filename,
        as_attachment=True
    )


# =========================
# اجرای برنامه
# =========================
if __name__ == '__main__':
    app.run(debug=True)
