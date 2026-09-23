import os
import time
import numpy as np
import librosa
import soundfile as sf
from gtts import gTTS
from flask import Flask, render_template, request, send_from_directory

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'separated'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return """
    <html dir="rtl">
    <head><title>درباره ما</title><style>body{background:#050b14;color:#fff;font-family:Tahoma;text-align:center;padding:50px;}</style></head>
    <body>
        <h2>درباره سامانه هوشمند پردازش صوت</h2>
        <p>این سامانه برای جداسازی موزیک و تبدیل متن به صوت به صورت فایل خروجی طراحی شده است.</p>
        <br><a href="/" style="color:#00ffff;">بازگشت به صفحه اصلی</a>
    </body>
    </html>
    """

@app.route('/contact')
def contact():
    return """
    <html dir="rtl">
    <head><title>تماس با ما</title><style>body{background:#050b14;color:#fff;font-family:Tahoma;text-align:center;padding:50px;}</style></head>
    <body>
        <h2>ارتباط با پشتیبانی</h2>
        <p>برای برقراری ارتباط با ما می‌توانید از طریق همین سامانه اقدام کنید.</p>
        <br><a href="/" style="color:#00ffff;">بازگشت به صفحه اصلی</a>
    </body>
    </html>
    """

@app.route('/process-text', methods=['POST'])
def process_text():
    text_input = request.form.get('text_input', '').strip()
    if not text_input:
        return render_template('index.html', error_text="لطفاً متنی برای تبدیل وارد کنید.")
    try:
        tts = gTTS(text=text_input, lang='ar', slow=False)
        unique_id = int(time.time())
        temp_mp3 = os.path.join(OUTPUT_FOLDER, f"temp_{unique_id}.mp3")
        speech_name = f"speech_{unique_id}.wav"
        speech_path = os.path.join(OUTPUT_FOLDER, speech_name)
        
        tts.save(temp_mp3)
        y, sr = librosa.load(temp_mp3, sr=22050)
        sf.write(speech_path, y, sr)
        
        if os.path.exists(temp_mp3):
            os.remove(temp_mp3)
            
        return render_template('index.html', 
                               success_text="تبدیل متن به صوت با موفقیت انجام شد!", 
                               speech_file=speech_name)
    except Exception as e:
        return render_template('index.html', error_text="خطا در تبدیل متن به صوت.")

@app.route('/process-audio', methods=['POST'])
def process_audio():
    if 'file' not in request.files:
        return render_template('index.html', error_audio="لطفاً یک فایل صوتی انتخاب کنید.")
        
    file = request.files['file']
    if file.filename == '':
        return render_template('index.html', error_audio="فایلی انتخاب نشده است.")
        
    try:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        
        y, sr = librosa.load(file_path, sr=22050, duration=25.0, mono=False)
        
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
                               success_audio="جداسازی صدا و موزیک با موفقیت انجام شد!", 
                               instrumental=inst_name, 
                               vocals=vocal_name)
    except Exception as e:
        return render_template('index.html', error_audio="خطا در پردازش فایل صوتی.")

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
