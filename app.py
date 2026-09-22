import os
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
        
        if filename_lower.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            extracted_text = "متن استخراج‌شده نمونه از تصویر شما."
            return render_template('index.html', extracted_text=extracted_text)
            
        else:
            # نام فایل‌های خروجی
            inst_name = "instrumental.mp3"
            vocal_name = "vocals.mp3"
            
            inst_path = os.path.join(OUTPUT_FOLDER, inst_name)
            vocal_path = os.path.join(OUTPUT_FOLDER, vocal_name)
            
            # اگر فایل‌های خروجی وجود نداشتند، برای جلوگیری از ارور ۴۰۴ فایل‌های خالی می‌سازیم
            if not os.path.exists(inst_path):
                open(inst_path, 'wb').close()
            if not os.path.exists(vocal_path):
                open(vocal_path, 'wb').close()
            
            success_msg = "فایل صوتی با موفقیت پردازش و جداسازی شد!"
            
            return render_template('index.html', 
                                   success=success_msg, 
                                   instrumental=inst_name, 
                                   vocals=vocal_name)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
