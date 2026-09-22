import os
from flask import Flask, render_template, request, send_from_directory

app = Flask(__name__)

# پوشه‌های ذخیره‌سازی
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
        
        # بررسی نوع فایل (صوتی یا تصویر)
        filename_lower = file.filename.lower()
        
        if filename_lower.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            # اگر فایل عکس بود، عملیات OCR انجام شود
            # (اگر کتابخانه pytesseract دارید می‌توانید اینجا متصل کنید، فعلاً یک متن نمونه قرار داده شده)
            extracted_text = "متن استخراج‌شده نمونه از تصویر شما."
            return render_template('index.html', extracted_text=extracted_text)
            
        else:
            # اگر فایل صوتی بود، بخش جداسازی صدا و موزیک بی‌کلام
            # اینجا کتابخانه جداسازی صوت (مثل Spleeter یا Demucs) قرار می‌گیرد
            # برای نمونه، فرض می‌کنیم فایل‌های خروجی با این نام‌ها ذخیره شده‌اند:
            
            success_msg = "فایل صوتی با موفقیت پردازش و جداسازی شد!"
            
            return render_template('index.html', 
                                   success=success_msg, 
                                   instrumental="instrumental.mp3", 
                                   vocals="vocals.mp3")

# مسیر دانلود فایل‌های خروجی صوتی
@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
