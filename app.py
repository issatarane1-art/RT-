import os
import sys
import subprocess
from flask import Flask, request, render_template, send_from_directory

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'separated')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_audio():
    if 'audio' not in request.files:
        return "فایلی انتخاب نشده است", 400
    
    file = request.files['audio']
    if file.filename == '':
        return "هیچ فایلی انتخاب نشده", 400

    clean_filename = file.filename.replace(' ', '_')
    filepath = os.path.join(UPLOAD_FOLDER, clean_filename)
    file.save(filepath)

    python_executable = sys.executable

    command = [
        python_executable,
        "-m", "demucs",
        "--two-stems=vocals",
        filepath,
        "-o", OUTPUT_FOLDER
    ]

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        return f"خطا در اجرای هوش مصنوعی: {e}", 500

    filename_without_ext = os.path.splitext(clean_filename)[0]
    
    return render_template('index.html', 
                           processed=True, 
                           folder_name=filename_without_ext)

@app.route('/download/<folder_name>/<filename>')
def download_file(folder_name, filename):
    for root, dirs, files in os.walk(OUTPUT_FOLDER):
        if os.path.basename(root) == folder_name and filename in files:
            return send_from_directory(root, filename, as_attachment=True)
    return "فایل مورد نظر پیدا نشد", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)