import os
from flask import Flask, redirect, render_template, request, url_for
from PIL import Image
import pytesseract

app = Flask(name)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def index():
  return render_template('index.html')


@app.route('/process', methods=['POST'])
def process_file():
  if 'file' not in request.files:
    return redirect(request.url)
  file = request.files['file']
  if file.filename == '':
    return redirect(request.url)

  if file:
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    # بررسی نوع فایل (اگر عکس باشد، متن آن استخراج می‌شود)
    if file.filename.lower().endswith(('png', 'jpg', 'jpeg', 'webp')):
      try:
        text = pytesseract.image_to_string(Image.open(filepath))
        return render_template('index.html', extracted_text=text)
      except Exception as e:
        return render_template(
            'index.html', error='خطا در پردازش تصویر برای استخراج متن.'
        )

    # برای فایل‌های صوتی
    return render_template(
        'index.html',
        success='فایل صوتی با موفقیت دریافت شد و در صف پردازش قرار گرفت.',
    )

  return redirect(url_for('index'))


if name == 'main':
  app.run(host='0.0.0.0', port=5000)
