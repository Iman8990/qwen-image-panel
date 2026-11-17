<div dir="rtl">

# پنل کوئن‌ایمیج روی مدال

پیش‌نیاز: اکانت مدال + اکانت هاگینگ‌فیس. هر دو مدل این پنل (Qwen-Image-2512 و Qwen-Image-Edit-2511) عمومی و بدون گیت‌اند (Apache 2.0) و قبول لایسنس نمی‌خواهند.

</div>

<div dir="rtl">

گرفتن پروژه و نصب مدال (در ترمینال کیلرکودا):

</div>

```bash
git clone https://github.com/Iman8990/qwen-image-panel.git
cd qwen-image-panel
pip install modal --break-system-packages --ignore-installed
modal setup
```

<div dir="rtl">

نکته: در اوبونتوهای جدید (مثل کیلرکودا) دستور ساده‌ی pip دو ارور می‌دهد: externally-managed-environment و Cannot uninstall برای پکیج‌هایی که خود اوبونتو نصب کرده. دو فلگ بالا هر دو را حل می‌کنند و در این محیط تمرینی اشکالی ندارند.

</div>

<div dir="rtl">

ساخت سکرت‌ها (توکن هاگینگ‌فیس: Settings ← Access Tokens):

</div>

```bash
modal secret create qwen-image-auth HF_TOKEN=xxx
modal secret create qwen-image-panel-auth PANEL_USER=admin PANEL_PASSWORD=xxx
```

<div dir="rtl">

هشدار: اگر سکرتی را پاک کردید و دوباره ساختید، اپِ دیپلوی‌شده هنوز به سکرت قبلی وصل است و کانتینرها با ارور Secret not found کرش می‌کنند. بعد از بازسازی هر سکرت، حتماً دوباره دیپلوی کنید: ‎modal deploy gradio_qwen_image_panel.py‎

دیپلوی:

</div>

```bash
modal deploy gradio_qwen_image_panel.py
```

<div dir="rtl">

لینک پنل در انتهای خروجی چاپ می‌شود؛ با همان نام کاربری و رمز وارد شوید. اولین اجرای هر تب، مدل همان تب را دانلود می‌کند (هر مدل حدود ۵۸ گیگ) و چند دقیقه طول می‌کشد؛ اجراهای بعدی از کش استفاده می‌کنند و سریع‌اند.

حذف کامل (اپ + سکرت‌ها):

</div>

```bash
modal app stop qwen-image-panel
modal secret delete qwen-image-auth -y
modal secret delete qwen-image-panel-auth -y
```
