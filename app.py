from audio_separator.separator import Separator

# استفاده از مدل سبک‌تر و سریع‌تر برای اجرا روی CPU
separator = Separator()
separator.load_model(
    'uvr_net_pertoire.onnx'
)  # یا مدل‌های سبک دیگر مثل MDX-Net سبک
