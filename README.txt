# PRECISION ENGINE

Backend Flask لتحليل APK/APKS باستخدام Androguard، مصمم ليعمل على Render Free للاختبار.

## الملفات

- `index.html`: واجهة المشروع الأصلية بعد ربطها بالـ API.
- `precision_engine/server.py`: خادم Flask والتحليل.
- `precision_engine/requirements.txt`: المكتبات.
- `render.yaml`: إعداد اختياري لـ Render.

## تشغيل محلي

```bash
pip install -r precision_engine/requirements.txt
python precision_engine/server.py
```

ثم:
`http://127.0.0.1:10000`

## Render

ارفع المشروع إلى GitHub ثم أنشئ Web Service في Render.

Build Command:
```bash
pip install -r precision_engine/requirements.txt
```

Start Command:
```bash
gunicorn --chdir precision_engine server:app
```

بعد ظهور رابط Render، عدّل السطر `API_URL` في `index.html` إلى:
```js
const API_URL='https://YOUR-SERVICE.onrender.com/api/analyze';
```

## حدود النسخة الأولى

الحد الافتراضي للرفع 35 MB لتقليل استهلاك الذاكرة في الخطة المجانية.
يمكن تغييره في Render عبر المتغير:
`MAX_UPLOAD_MB`

هذه النسخة تبحث عن مؤشرات نصية وأسماء Methods مرتبطة بالفوترة والإعلانات والتحليلات والشبكة. النتيجة تحليلية وليست إثباتًا قانونيًا أو تجاريًا.
