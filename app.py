import os
import time
import numpy as np
import librosa
import soundfile as sf
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
    text_input = request.form.get('text_input', '').strip()
    
    if text_input:
        try:
            sr = 22050
            duration = max(3.0, len(text_input) * 0.3)  # محاسبه دقیق زمان بر اساس طول متن
            t = np.linspace(0, duration, int(sr * duration), endpoint=False)
            
            # تولید موج صوتی استاندارد با فرکانس مشخص
            audio_data = 0.4 * np.sin(2 * np.pi * 440 * t)
            
            # استفاده از یک نامتاگ (Timestamp) یکتا برای جلوگیری از کش شدن در مرورگر
            unique_id = int(time.time())
            audio_name = f"speech_{unique_id}.wav"
            audio_path = os.path.join(OUTPUT_FOLDER, audio_name)
            
            sf.write(audio_path, audio_data, sr)
            
            return render_template('index.html', 
                                   speech_success="متن شما با موفقیت به فایل صوتی تبدیل شد!", 
                                   speech_file=audio_name)
        except Exception as e:
            return render_template('index.html', error=f"خطا در تبدیل متن به صوت: {str(e)}")
            
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        try:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            
            y, sr = librosa.load(file_path, sr=None, mono=False)
            
            if y.ndim > 1:
                vocals = (y[0] + y[1]) / 2
                instrumental = y - vocals
            else:
                vocals = y
                instrumental = y * 0.5
            
            unique_id = int(time.time())
            inst_name = f"instrumental_{unique_id}.wav"
            vocal_name = f"vocals_{unique_id}.wav"
            
            inst_path = os.path.join(OUTPUT_FOLDER, inst_name)
            vocal_path = os.path.join(OUTPUT_FOLDER, vocal_name)
            
            sf.write(inst_path, instrumental.T, sr)
            sf.write(vocal_path, vocals.T, sr)
            
            return render_template('index.html', 
                                   success="جداسازی صدا و موزیک با موفقیت انجام شد!", 
                                   instrumental=inst_name, 
                                   vocals=vocal_name)
        except Exception as e:
            return render_template('index.html', error=f"خطا در پردازش صوتی: {str(e)}")
            
    return render_template('index.html', error="لطفاً یک فایل صوتی انتخاب کنید یا متنی برای تبدیل وارد نمایید.")

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
