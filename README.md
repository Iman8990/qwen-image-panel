<div dir="rtl">

# پنل کوئن‌ایمیج روی مدال

دو مدل در یک پنل: Qwen-Image-2512 برای ساخت عکس از متن و Qwen-Image-Edit-2511 برای ویرایش عکس (۱ تا ۳ عکس ورودی).

پیش‌نیاز: اکانت مدال + اکانت هاگینگ‌فیس. هر دو مدل عمومی و بدون گیت‌اند (Apache 2.0) و قبول لایسنس نمی‌خواهند؛ فقط یک توکن هاگینگ‌فیس لازم است.

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
modal secret create ideogram4-model-auth HF_TOKEN=xxx
modal secret create ideogram4-panel-auth PANEL_USER=admin PANEL_PASSWORD=xxx
```

<div dir="rtl">

نکته: اگر قبلاً کارگاه ایدیوگرام را انجام داده‌اید، این دو سکرت با همین نام‌ها روی اکانتتان هست و ساخت دوباره‌شان لازم نیست.

هشدار: اگر سکرتی را پاک کردید و دوباره ساختید، اپِ دیپلوی‌شده هنوز به سکرت قبلی وصل است و کانتینرها با ارور Secret not found کرش می‌کنند. بعد از بازسازی هر سکرت، حتماً دوباره دیپلوی کنید: ‎modal deploy gradio_qwen_image_panel.py‎

دیپلوی:

</div>

```bash
modal deploy gradio_qwen_image_panel.py
```

<div dir="rtl">

لینک پنل در انتهای خروجی چاپ می‌شود؛ با همان نام کاربری و رمز وارد شوید.

توجه: اولین اجرای هر تب، مدل همان تب را دانلود می‌کند (هر مدل حدود ۵۸ گیگ) و چند دقیقه طول می‌کشد؛ اجراهای بعدی از کش استفاده می‌کنند و سریع‌اند.

حذف کامل (اپ + سکرت‌ها):

</div>

```bash
modal app stop qwen-image-panel
modal secret delete ideogram4-model-auth -y
modal secret delete ideogram4-panel-auth -y
```

<div dir="rtl">

هشدار مهم: این دو سکرت با پنل و ربات ایدیوگرام مشترک‌اند. حذفشان فقط روی اکانت تازه‌ی خودتان درست است؛ روی اکانتی که ربات ایدیوگرام رویش اجراست پاکشان نکنید، چون ربات و پنل ایدیوگرام از کار می‌افتند.

</div>
