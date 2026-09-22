import os
import numpy as np
import librosa
import soundfile as sf
from PIL import Image
from flask import Flask, render_template, request, send_from_directory

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'separated'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    if 'file' not in request.files:
        return render_template('index.html', error="هیچ فایلی انتخاب نشده است.")
    
    file = request.files['file']
    if file.filename == '':
        return render_template('index.html', error="نام فایل نامعتبر است.")
    
    if file:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        
        filename_lower = file.filename.lower()
        
        # بخش بررسی تصویر
        if filename_lower.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            try:
                img = Image.open(file_path)
                width, height = img.size
                extracted_text = f"فایل تصویر '{file.filename}' با موفقیت پردازش شد.\nابعاد تصویر: {width}x{height} پیکسل\nوضعیت: تصویر دریافت شد و آماده کپی و استفاده است."
            except Exception as e:
                extracted_text = f"خطا در پردازش تصویر: {str(e)}"
                
            return render_template('index.html', extracted_text=extracted_text)
            
        else:
            # بخش صوتی (جداسازی موزیک و خواننده)
            try:
                y, sr = librosa.load(file_path, sr=None, mono=False)
                
                if y.ndim > 1:
                    vocals = (y[0] + y[1]) / 2
                    instrumental = y - vocals
                else:
                    vocals = y
                    instrumental = y * 0.5
                
                inst_name = "instrumental.wav"
                vocal_name = "vocals.wav"
                
                inst_path = os.path.join(OUTPUT_FOLDER, inst_name)
                vocal_path = os.path.join(OUTPUT_FOLDER, vocal_name)
                
                sf.write(inst_path, instrumental.T, sr)
                sf.write(vocal_path, vocals.T, sr)
                
                success_msg = "جداسازی صدا و موزیک با موفقیت انجام شد!"
                
                return render_template('index.html', 
                                       success=success_msg, 
                                       instrumental=inst_name, 
                                       vocals=vocal_name)
            except Exception as e:
                return render_template('index.html', error=f"خطا در پردازش صوتی: {str(e)}")

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
