# 🎬 Видео Обработчик

Десктопное приложение для конвертации и сжатия видео. Построено на PyQt6 + FFmpeg.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-green)
![FFmpeg](https://img.shields.io/badge/FFmpeg-8.0-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Возможности

- 🎵 **Конвертация видео в аудио** — MP3, AAC, FLAC, WAV, OGG
- 🗜️ **Сжатие видео** — настраиваемое качество (CRF), пресеты скорости
- 📚 **Режим лекций** — агрессивное сжатие для записей со слайдами (10–50×)
- 🎮 **GPU ускорение** — NVIDIA NVENC, Intel QSV
- 📊 **Многофайловая обработка** — drag-and-drop, параллельные задачи
- 🎨 **Тёмная и светлая темы**

## Скачать

Готовый exe (Windows, не требует установки):
👉 [Releases](../../releases)

## Запуск из исходников

### Требования

- Python 3.8+
- FFmpeg

### Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/mahac05/coptresiones.git
cd obrabotchik_vidio

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Скачать FFmpeg (Windows)
.\download_ffmpeg.ps1

# 4. Запустить
python app_pyqt.py
```

### Установка FFmpeg вручную

Если скрипт не работает:
1. Скачайте FFmpeg: https://github.com/BtbN/FFmpeg-Builds/releases
2. Извлеките `ffmpeg.exe` и `ffprobe.exe`
3. Поместите в `resources/ffmpeg/`

## Сборка в exe

```bash
pip install pyinstaller
pyinstaller VideoProcessor.spec
```

Результат: `dist/VideoProcessor.exe`

## Структура проекта

```
├── app_pyqt.py              # UI (PyQt6)
├── backend.py               # FFmpeg команды
├── ui_components_pyqt.py    # UI компоненты
├── core/                    # Ядро
│   ├── models.py            # Модели данных
│   ├── settings.py          # Настройки
│   ├── service.py           # Сервис обработки
│   ├── validators.py        # Валидация
│   ├── themes.py            # Темы
│   └── logging_config.py    # Логирование
├── tests/                   # Тесты
├── resources/ffmpeg/        # FFmpeg бинарники (не в git)
├── requirements.txt
├── VideoProcessor.spec      # Конфигурация PyInstaller
└── download_ffmpeg.ps1      # Скрипт загрузки FFmpeg
```

## Лицензия

[MIT](LICENSE)
