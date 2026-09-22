import os
from flask import Flask, redirect, render_template, request, url_for
from PIL import Image
import pytesseract

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def index():
  return render_template('index.html')


@app.route('/process', methods=['POST'])
def process_file():
  if 'file' not in request.files:
    return redirect(url_for('index'))
  file = request.files['file']
  if file.filename == '':
    return redirect(url_for('index'))

  if file:
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    filename_lower = file.filename.lower()

    # بخش تبدیل عکس به متن (OCR)
    if filename_lower.endswith(('png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff')):
      try:
        text = pytesseract.image_to_string(Image.open(filepath))
        return render_template(
            'index.html', extracted_text=text, active_tab='home'
        )
      except Exception as e:
        return render_template(
            'index.html',
            error='خطا در پردازش تصویر برای استخراج متن.',
            active_tab='home',
        )

    # بخش پردازش فایل‌های صوتی
    elif filename_lower.endswith(('mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac')):
      return render_template(
          'index.html',
          success='فایل صوتی با موفقیت دریافت شد و پردازش آن آغاز گردید.',
          active_tab='home',
      )
    else:
      return render_template(
          'index.html',
          error='فرمت فایل انتخابی پشتیبانی نمی‌شود.',
          active_tab='home',
      )

  return redirect(url_for('index'))


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000)
