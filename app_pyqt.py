# app_pyqt.py
# -*- coding: utf-8 -*-
"""
Красивый UI для обработки видео на PyQt6.
Поддержка тёмной и светлой темы с Material Design эстетикой.
"""

import sys
import os
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSlider, QProgressBar,
    QFileDialog, QFrame, QStackedWidget, QRadioButton, QButtonGroup,
    QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QIcon

from backend import FFmpegConverter


# Темы
THEMES = {
    "dark": {
        "bg_primary": "#0f0f1a",
        "bg_secondary": "#1a1a2e",
        "bg_card": "rgba(37, 37, 66, 0.8)",
        "bg_sidebar": "rgba(26, 26, 46, 0.95)",
        "text_primary": "#ffffff",
        "text_secondary": "#a0a0b0",
        "text_muted": "#666680",
        "border": "#333350",
        "border_light": "rgba(255, 255, 255, 0.1)",
        "accent": "#00d4ff",
        "accent_secondary": "#7c3aed",
        "success": "#22c55e",
        "error": "#ef4444",
        "input_bg": "#252542",
        "slider_bg": "#333350",
    },
    "light": {
        "bg_primary": "#f5f7fa",
        "bg_secondary": "#ffffff",
        "bg_card": "rgba(255, 255, 255, 0.95)",
        "bg_sidebar": "#ffffff",
        "text_primary": "#1a1a2e",
        "text_secondary": "#64748b",
        "text_muted": "#94a3b8",
        "border": "#e2e8f0",
        "border_light": "rgba(0, 0, 0, 0.08)",
        "accent": "#0891b2",
        "accent_secondary": "#7c3aed",
        "success": "#16a34a",
        "error": "#dc2626",
        "input_bg": "#f8fafc",
        "slider_bg": "#e2e8f0",
    }
}


# Сигналы для thread-safe обновления UI
class WorkerSignals(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)


class VideoProcessorApp(QMainWindow):
    """Главное окно приложения."""
    
    PRESETS = {
        "Мгновенно": "ultrafast",
        "Быстро": "veryfast", 
        "Стандарт": "medium",
        "Медленно": "slow",
        "Максимум": "veryslow",
    }
    
    def __init__(self):
        super().__init__()
        self.converter = FFmpegConverter()
        self.conv_input_file = ""
        self.conv_output_folder = ""
        self.comp_input_file = ""
        self.comp_output_folder = ""
        self.current_theme = "dark"
        self._setup_ui()
        self._apply_theme()
        
    def _setup_ui(self):
        self.setWindowTitle("🎬 Видео Обработчик")
        self.setMinimumSize(950, 700)
        self.resize(1000, 750)
        
        # Центральный виджет
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === Боковая панель ===
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(220)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 25, 0, 25)
        sidebar_layout.setSpacing(8)
        
        # Логотип
        self.logo = QLabel("🎬 Видео\nОбработчик")
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(self.logo)
        sidebar_layout.addSpacing(35)
        
        # Навигация
        self.nav_audio = QPushButton("🎵  Аудио")
        self.nav_audio.setCheckable(True)
        self.nav_audio.setChecked(True)
        self.nav_audio.setMinimumHeight(55)
        self.nav_audio.clicked.connect(lambda: self._switch_tab(0))
        
        self.nav_compress = QPushButton("📦  Сжатие")
        self.nav_compress.setCheckable(True)
        self.nav_compress.setMinimumHeight(55)
        self.nav_compress.clicked.connect(lambda: self._switch_tab(1))
        
        sidebar_layout.addWidget(self.nav_audio)
        sidebar_layout.addWidget(self.nav_compress)
        sidebar_layout.addStretch()
        
        # Переключатель темы
        self.theme_btn = QPushButton("🌙 Тёмная тема")
        self.theme_btn.setMinimumHeight(50)
        self.theme_btn.clicked.connect(self._toggle_theme)
        sidebar_layout.addWidget(self.theme_btn)
        
        main_layout.addWidget(self.sidebar)
        
        # === Контент ===
        self.stack = QStackedWidget()
        
        self.stack.addWidget(self._create_convert_page())
        self.stack.addWidget(self._create_compress_page())
        
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(35, 35, 35, 35)
        content_layout.addWidget(self.stack)
        
        main_layout.addWidget(content_wrapper)
    
    def _toggle_theme(self):
        """Переключение темы."""
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self._apply_theme()
    
    def _apply_theme(self):
        """Применяет текущую тему."""
        t = THEMES[self.current_theme]
        is_dark = self.current_theme == "dark"
        
        # Обновляем кнопку темы
        self.theme_btn.setText("☀️ Светлая тема" if is_dark else "🌙 Тёмная тема")
        
        # Главный стиль
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {t['bg_primary']};
            }}
            QWidget {{
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel {{
                color: {t['text_primary']};
                font-size: 15px;
            }}
            QComboBox {{
                background: {t['input_bg']};
                color: {t['text_primary']};
                border: 2px solid {t['border']};
                border-radius: 10px;
                padding: 10px 15px;
                min-width: 120px;
                font-size: 15px;
            }}
            QComboBox:hover {{
                border-color: {t['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 35px;
            }}
            QComboBox QAbstractItemView {{
                background: {t['input_bg']};
                color: {t['text_primary']};
                selection-background-color: {t['accent']};
                font-size: 15px;
            }}
            QSlider::groove:horizontal {{
                background: {t['slider_bg']};
                height: 8px;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {t['accent']};
                width: 22px;
                height: 22px;
                margin: -7px 0;
                border-radius: 11px;
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {t['accent']}, stop:1 {t['accent_secondary']});
                border-radius: 4px;
            }}
            QProgressBar {{
                background: {t['slider_bg']};
                border: none;
                border-radius: 8px;
                height: 16px;
                text-align: center;
                color: transparent;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {t['accent']}, stop:1 {t['accent_secondary']});
                border-radius: 8px;
            }}
            QRadioButton {{
                color: {t['text_secondary']};
                spacing: 10px;
                font-size: 15px;
            }}
            QRadioButton::indicator {{
                width: 22px;
                height: 22px;
                border-radius: 11px;
                border: 2px solid {t['border']};
                background: transparent;
            }}
            QRadioButton::indicator:checked {{
                border-color: {t['accent']};
                background: {t['accent']};
            }}
            QRadioButton:hover {{
                color: {t['text_primary']};
            }}
        """)
        
        # Боковая панель
        self.sidebar.setStyleSheet(f"""
            QFrame {{
                background: {t['bg_sidebar']};
                border-right: 1px solid {t['border']};
            }}
        """)
        
        # Логотип
        self.logo.setStyleSheet(f"""
            color: {t['text_primary']};
            font-size: 22px;
            font-weight: bold;
            padding: 20px;
            background: transparent;
        """)
        
        # Стили навигации
        nav_checked = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0, 212, 255, 0.2), stop:1 rgba(124, 58, 237, 0.2));
                color: {t['accent']};
                border: none;
                border-left: 4px solid {t['accent']};
                border-radius: 0;
                padding: 18px 22px;
                font-size: 17px;
                font-weight: bold;
                text-align: left;
            }}
        """
        
        nav_unchecked = f"""
            QPushButton {{
                background: transparent;
                color: {t['text_secondary']};
                border: none;
                border-left: 4px solid transparent;
                border-radius: 0;
                padding: 18px 22px;
                font-size: 17px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {'rgba(255, 255, 255, 0.05)' if is_dark else 'rgba(0, 0, 0, 0.03)'};
                color: {t['text_primary']};
            }}
        """
        
        self.nav_audio.setStyleSheet(nav_checked if self.nav_audio.isChecked() else nav_unchecked)
        self.nav_compress.setStyleSheet(nav_checked if self.nav_compress.isChecked() else nav_unchecked)
        
        # Кнопка темы
        self.theme_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {t['text_secondary']};
                border: 2px solid {t['border']};
                border-radius: 12px;
                padding: 12px 18px;
                font-size: 15px;
                margin: 8px 15px;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
            }}
        """)
        
        # Стек
        self.stack.setStyleSheet("background: transparent;")
        
        # Обновляем все карточки и зоны
        self._update_themed_widgets(t, is_dark)
    
    def _update_themed_widgets(self, t, is_dark):
        """Обновляет стили виджетов с учётом темы."""
        # Drop zones
        drop_style = f"""
            QFrame {{
                background: {t['bg_card']};
                border: 2px dashed {t['border']};
                border-radius: 18px;
            }}
            QFrame:hover {{
                border-color: {t['accent']};
                background: {'rgba(0, 212, 255, 0.05)' if is_dark else 'rgba(8, 145, 178, 0.05)'};
            }}
        """
        
        if hasattr(self, 'conv_drop_zone'):
            self.conv_drop_zone.setStyleSheet(drop_style)
            for child in self.conv_drop_zone.findChildren(QLabel):
                if "не выбран" in child.text() or "Файл" in child.text():
                    child.setStyleSheet(f"color: {t['text_muted']}; font-size: 15px; background: transparent; border: none;")
                elif "Нажмите" in child.text():
                    child.setStyleSheet(f"color: {t['text_secondary']}; font-size: 16px; background: transparent; border: none;")
                else:
                    child.setStyleSheet(f"font-size: 48px; background: transparent; border: none;")
        
        if hasattr(self, 'comp_drop_zone'):
            self.comp_drop_zone.setStyleSheet(drop_style)
            for child in self.comp_drop_zone.findChildren(QLabel):
                if "не выбран" in child.text() or "Файл" in child.text():
                    child.setStyleSheet(f"color: {t['text_muted']}; font-size: 15px; background: transparent; border: none;")
                elif "Нажмите" in child.text():
                    child.setStyleSheet(f"color: {t['text_secondary']}; font-size: 16px; background: transparent; border: none;")
                else:
                    child.setStyleSheet(f"font-size: 48px; background: transparent; border: none;")
        
        # Cards
        card_style = f"""
            QFrame {{
                background: {t['bg_card']};
                border: 1px solid {t['border_light']};
                border-radius: 18px;
            }}
        """
        
        if hasattr(self, 'conv_settings_card'):
            self.conv_settings_card.setStyleSheet(card_style)
        if hasattr(self, 'comp_settings_card'):
            self.comp_settings_card.setStyleSheet(card_style)
        
        # Headers
        if hasattr(self, 'conv_header'):
            self.conv_header.setStyleSheet(f"font-size: 30px; font-weight: bold; color: {t['text_primary']};")
        if hasattr(self, 'comp_header'):
            self.comp_header.setStyleSheet(f"font-size: 30px; font-weight: bold; color: {t['text_primary']};")
        
        # Primary buttons
        btn_style = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {t['accent']}, stop:1 {t['accent_secondary']});
                color: #ffffff;
                border: none;
                border-radius: 14px;
                padding: 16px 32px;
                font-size: 17px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #33e0ff, stop:1 #9456ff);
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00b8d4, stop:1 #6a2ec0);
            }}
            QPushButton:disabled {{
                background: {t['slider_bg']};
                color: {t['text_muted']};
            }}
        """
        
        if hasattr(self, 'conv_run_btn'):
            self.conv_run_btn.setStyleSheet(btn_style)
        if hasattr(self, 'comp_run_btn'):
            self.comp_run_btn.setStyleSheet(btn_style)
        
        # Secondary buttons
        sec_btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {t['accent']};
                border: 2px solid {t['accent']};
                border-radius: 12px;
                padding: 14px 26px;
                font-size: 15px;
            }}
            QPushButton:hover {{
                background: {'rgba(0, 212, 255, 0.1)' if is_dark else 'rgba(8, 145, 178, 0.1)'};
            }}
        """
        
        if hasattr(self, 'conv_folder_btn'):
            self.conv_folder_btn.setStyleSheet(sec_btn_style)
        if hasattr(self, 'comp_folder_btn'):
            self.comp_folder_btn.setStyleSheet(sec_btn_style)
        
        # Labels
        if hasattr(self, 'conv_progress_label'):
            self.conv_progress_label.setStyleSheet(f"color: {t['text_secondary']}; font-size: 16px; min-width: 50px;")
        if hasattr(self, 'comp_progress_label'):
            self.comp_progress_label.setStyleSheet(f"color: {t['text_secondary']}; font-size: 16px; min-width: 50px;")
        
        if hasattr(self, 'comp_crf_value'):
            self.comp_crf_value.setStyleSheet(f"color: {t['accent']}; font-size: 15px;")
    
    def _switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        self.nav_audio.setChecked(index == 0)
        self.nav_compress.setChecked(index == 1)
        self._apply_theme()  # Обновляем стили навигации
    
    # ==================== КОНВЕРТАЦИЯ ====================
    
    def _create_convert_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(22)
        
        # Заголовок
        self.conv_header = QLabel("🎵 Конвертация в аудио")
        layout.addWidget(self.conv_header)
        
        # Выбор файла
        self.conv_drop_zone = QFrame()
        self.conv_drop_zone.setMinimumHeight(160)
        self.conv_drop_zone.setCursor(Qt.CursorShape.PointingHandCursor)
        self.conv_drop_zone.mousePressEvent = lambda e: self._conv_pick_file()
        
        drop_layout = QVBoxLayout(self.conv_drop_zone)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel("🎬")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        text_label = QLabel("Нажмите для выбора видео")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.conv_file_label = QLabel("Файл не выбран")
        self.conv_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        drop_layout.addWidget(icon_label)
        drop_layout.addWidget(text_label)
        drop_layout.addWidget(self.conv_file_label)
        
        layout.addWidget(self.conv_drop_zone)
        
        # Настройки
        self.conv_settings_card = QFrame()
        card_layout = QVBoxLayout(self.conv_settings_card)
        card_layout.setContentsMargins(28, 22, 28, 28)
        card_layout.setSpacing(18)
        
        title_label = QLabel("⚙️ Настройки")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        card_layout.addWidget(title_label)
        
        # Формат и битрейт
        format_layout = QHBoxLayout()
        
        format_label = QLabel("Формат:")
        self.conv_format = QComboBox()
        self.conv_format.addItems(list(FFmpegConverter.AUDIO_FORMATS.keys()))
        self.conv_format.setCurrentText("m4a")
        
        bitrate_label = QLabel("Битрейт:")
        self.conv_bitrate = QComboBox()
        self.conv_bitrate.addItems(["96k", "128k", "192k", "256k", "320k"])
        self.conv_bitrate.setCurrentText("192k")
        
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.conv_format)
        format_layout.addSpacing(35)
        format_layout.addWidget(bitrate_label)
        format_layout.addWidget(self.conv_bitrate)
        format_layout.addStretch()
        
        card_layout.addLayout(format_layout)
        
        # Сохранение
        save_label = QLabel("Сохранить:")
        card_layout.addWidget(save_label)
        
        self.conv_save_same = QRadioButton("В той же папке")
        self.conv_save_custom = QRadioButton("Выбрать папку")
        self.conv_save_same.setChecked(True)
        
        self.conv_save_group = QButtonGroup()
        self.conv_save_group.addButton(self.conv_save_same)
        self.conv_save_group.addButton(self.conv_save_custom)
        self.conv_save_custom.toggled.connect(self._conv_save_mode_changed)
        
        save_layout = QHBoxLayout()
        save_layout.addWidget(self.conv_save_same)
        save_layout.addWidget(self.conv_save_custom)
        save_layout.addStretch()
        card_layout.addLayout(save_layout)
        
        self.conv_folder_btn = QPushButton("📁 Выбрать папку...")
        self.conv_folder_btn.hide()
        self.conv_folder_btn.clicked.connect(self._conv_pick_folder)
        card_layout.addWidget(self.conv_folder_btn)
        
        self.conv_folder_label = QLabel("")
        self.conv_folder_label.hide()
        card_layout.addWidget(self.conv_folder_label)
        
        layout.addWidget(self.conv_settings_card)
        
        # Кнопка и прогресс
        action_layout = QVBoxLayout()
        action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.conv_run_btn = QPushButton("▶ Конвертировать")
        self.conv_run_btn.setMinimumWidth(220)
        self.conv_run_btn.setMinimumHeight(55)
        self.conv_run_btn.clicked.connect(self._conv_run)
        action_layout.addWidget(self.conv_run_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        progress_layout = QHBoxLayout()
        progress_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.conv_progress = QProgressBar()
        self.conv_progress.setFixedWidth(420)
        self.conv_progress.setFixedHeight(16)
        self.conv_progress.setValue(0)
        
        self.conv_progress_label = QLabel("0%")
        
        progress_layout.addWidget(self.conv_progress)
        progress_layout.addWidget(self.conv_progress_label)
        action_layout.addLayout(progress_layout)
        
        self.conv_status = QLabel("")
        self.conv_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        action_layout.addWidget(self.conv_status)
        
        layout.addLayout(action_layout)
        layout.addStretch()
        
        return page
    
    def _conv_pick_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Выберите видео",
            "", "Видео (*.mp4 *.mkv *.avi *.mov *.webm);;Все файлы (*.*)"
        )
        if file:
            self.conv_input_file = file
            self.conv_file_label.setText(os.path.basename(file))
            t = THEMES[self.current_theme]
            self.conv_file_label.setStyleSheet(f"color: {t['success']}; font-size: 15px; background: transparent; border: none;")
    
    def _conv_save_mode_changed(self, checked):
        self.conv_folder_btn.setVisible(checked)
        self.conv_folder_label.setVisible(checked and bool(self.conv_output_folder))
    
    def _conv_pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.conv_output_folder = folder
            self.conv_folder_label.setText(f"📁 {folder}")
            t = THEMES[self.current_theme]
            self.conv_folder_label.setStyleSheet(f"color: {t['success']}; font-size: 14px;")
            self.conv_folder_label.show()
    
    def _conv_run(self):
        t = THEMES[self.current_theme]
        
        if not self.conv_input_file:
            self.conv_status.setText("⚠️ Выберите видео файл!")
            self.conv_status.setStyleSheet(f"color: {t['error']}; font-size: 18px; font-weight: bold;")
            return
        
        if self.conv_save_custom.isChecked() and not self.conv_output_folder:
            self.conv_status.setText("⚠️ Выберите папку!")
            self.conv_status.setStyleSheet(f"color: {t['error']}; font-size: 18px; font-weight: bold;")
            return
        
        # Формируем путь
        ext = self.conv_format.currentText()
        base = os.path.splitext(os.path.basename(self.conv_input_file))[0]
        folder = self.conv_output_folder if self.conv_save_custom.isChecked() else os.path.dirname(self.conv_input_file)
        output_file = os.path.join(folder, f"{base}.{ext}")
        
        # UI
        self.conv_run_btn.setEnabled(False)
        self.conv_progress.setValue(0)
        self.conv_progress_label.setText("0%")
        self.conv_status.setText("⏳ Конвертация...")
        self.conv_status.setStyleSheet(f"color: {t['text_secondary']}; font-size: 18px; font-weight: bold;")
        
        # Сигналы
        signals = WorkerSignals()
        signals.progress.connect(self._conv_update_progress)
        signals.finished.connect(self._conv_finished)
        
        def worker():
            def progress_cb(p):
                signals.progress.emit(p)
            
            try:
                ok = self.converter.convert_mp4_to_audio(
                    input_file=self.conv_input_file,
                    output_format=self.conv_format.currentText(),
                    bitrate=self.conv_bitrate.currentText(),
                    output_file=output_file,
                    show_progress=True,
                    progress_callback=progress_cb,
                )
                signals.finished.emit(ok)
            except Exception as e:
                signals.error.emit(str(e))
                signals.finished.emit(False)
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _conv_update_progress(self, value):
        self.conv_progress.setValue(value)
        self.conv_progress_label.setText(f"{value}%")
    
    def _conv_finished(self, success):
        t = THEMES[self.current_theme]
        self.conv_run_btn.setEnabled(True)
        if success:
            self.conv_status.setText("✅ Готово!")
            self.conv_status.setStyleSheet(f"color: {t['success']}; font-size: 18px; font-weight: bold;")
        else:
            self.conv_status.setText("❌ Ошибка")
            self.conv_status.setStyleSheet(f"color: {t['error']}; font-size: 18px; font-weight: bold;")
    
    # ==================== СЖАТИЕ ====================
    
    def _create_compress_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(22)
        
        # Заголовок
        self.comp_header = QLabel("📦 Сжатие видео")
        layout.addWidget(self.comp_header)
        
        # Выбор файла
        self.comp_drop_zone = QFrame()
        self.comp_drop_zone.setMinimumHeight(160)
        self.comp_drop_zone.setCursor(Qt.CursorShape.PointingHandCursor)
        self.comp_drop_zone.mousePressEvent = lambda e: self._comp_pick_file()
        
        drop_layout = QVBoxLayout(self.comp_drop_zone)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel("🎬")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        text_label = QLabel("Нажмите для выбора видео")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.comp_file_label = QLabel("Файл не выбран")
        self.comp_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        drop_layout.addWidget(icon_label)
        drop_layout.addWidget(text_label)
        drop_layout.addWidget(self.comp_file_label)
        
        layout.addWidget(self.comp_drop_zone)
        
        # Настройки
        self.comp_settings_card = QFrame()
        card_layout = QVBoxLayout(self.comp_settings_card)
        card_layout.setContentsMargins(28, 22, 28, 28)
        card_layout.setSpacing(18)
        
        title_label = QLabel("⚙️ Настройки сжатия")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        card_layout.addWidget(title_label)
        
        # CRF
        crf_layout = QHBoxLayout()
        crf_label = QLabel("Качество (CRF):")
        
        self.comp_crf_value = QLabel("23 (стандартное)")
        
        crf_layout.addWidget(crf_label)
        crf_layout.addStretch()
        crf_layout.addWidget(self.comp_crf_value)
        card_layout.addLayout(crf_layout)
        
        self.comp_crf_slider = QSlider(Qt.Orientation.Horizontal)
        self.comp_crf_slider.setRange(18, 40)
        self.comp_crf_slider.setValue(23)
        self.comp_crf_slider.valueChanged.connect(self._comp_crf_changed)
        card_layout.addWidget(self.comp_crf_slider)
        
        # Пресет и аудио
        preset_layout = QHBoxLayout()
        
        preset_label = QLabel("Скорость:")
        self.comp_preset = QComboBox()
        self.comp_preset.addItems(list(self.PRESETS.keys()))
        self.comp_preset.setCurrentText("Стандарт")
        
        audio_label = QLabel("Звук:")
        self.comp_audio = QComboBox()
        self.comp_audio.addItems(["96k", "128k", "192k", "256k"])
        self.comp_audio.setCurrentText("128k")
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.comp_preset)
        preset_layout.addSpacing(35)
        preset_layout.addWidget(audio_label)
        preset_layout.addWidget(self.comp_audio)
        preset_layout.addStretch()
        card_layout.addLayout(preset_layout)
        
        # Сохранение
        save_label = QLabel("Сохранить:")
        card_layout.addWidget(save_label)
        
        self.comp_save_same = QRadioButton("В той же папке")
        self.comp_save_custom = QRadioButton("Выбрать папку")
        self.comp_save_same.setChecked(True)
        
        self.comp_save_group = QButtonGroup()
        self.comp_save_group.addButton(self.comp_save_same)
        self.comp_save_group.addButton(self.comp_save_custom)
        self.comp_save_custom.toggled.connect(self._comp_save_mode_changed)
        
        save_layout = QHBoxLayout()
        save_layout.addWidget(self.comp_save_same)
        save_layout.addWidget(self.comp_save_custom)
        save_layout.addStretch()
        card_layout.addLayout(save_layout)
        
        self.comp_folder_btn = QPushButton("📁 Выбрать папку...")
        self.comp_folder_btn.hide()
        self.comp_folder_btn.clicked.connect(self._comp_pick_folder)
        card_layout.addWidget(self.comp_folder_btn)
        
        self.comp_folder_label = QLabel("")
        self.comp_folder_label.hide()
        card_layout.addWidget(self.comp_folder_label)
        
        layout.addWidget(self.comp_settings_card)
        
        # Кнопка и прогресс
        action_layout = QVBoxLayout()
        action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.comp_run_btn = QPushButton("▶ Сжать видео")
        self.comp_run_btn.setMinimumWidth(220)
        self.comp_run_btn.setMinimumHeight(55)
        self.comp_run_btn.clicked.connect(self._comp_run)
        action_layout.addWidget(self.comp_run_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        progress_layout = QHBoxLayout()
        progress_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.comp_progress = QProgressBar()
        self.comp_progress.setFixedWidth(420)
        self.comp_progress.setFixedHeight(16)
        self.comp_progress.setValue(0)
        
        self.comp_progress_label = QLabel("0%")
        
        progress_layout.addWidget(self.comp_progress)
        progress_layout.addWidget(self.comp_progress_label)
        action_layout.addLayout(progress_layout)
        
        self.comp_status = QLabel("")
        self.comp_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        action_layout.addWidget(self.comp_status)
        
        layout.addLayout(action_layout)
        layout.addStretch()
        
        return page
    
    def _comp_pick_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Выберите видео",
            "", "Видео (*.mp4 *.mkv *.avi *.mov *.webm);;Все файлы (*.*)"
        )
        if file:
            self.comp_input_file = file
            self.comp_file_label.setText(os.path.basename(file))
            t = THEMES[self.current_theme]
            self.comp_file_label.setStyleSheet(f"color: {t['success']}; font-size: 15px; background: transparent; border: none;")
    
    def _comp_crf_changed(self, value):
        if value <= 20:
            desc = "высокое качество"
        elif value <= 25:
            desc = "стандартное"
        elif value <= 30:
            desc = "хорошее сжатие"
        else:
            desc = "сильное сжатие"
        self.comp_crf_value.setText(f"{value} ({desc})")
    
    def _comp_save_mode_changed(self, checked):
        self.comp_folder_btn.setVisible(checked)
        self.comp_folder_label.setVisible(checked and bool(self.comp_output_folder))
    
    def _comp_pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.comp_output_folder = folder
            self.comp_folder_label.setText(f"📁 {folder}")
            t = THEMES[self.current_theme]
            self.comp_folder_label.setStyleSheet(f"color: {t['success']}; font-size: 14px;")
            self.comp_folder_label.show()
    
    def _comp_run(self):
        t = THEMES[self.current_theme]
        
        if not self.comp_input_file:
            self.comp_status.setText("⚠️ Выберите видео файл!")
            self.comp_status.setStyleSheet(f"color: {t['error']}; font-size: 18px; font-weight: bold;")
            return
        
        if self.comp_save_custom.isChecked() and not self.comp_output_folder:
            self.comp_status.setText("⚠️ Выберите папку!")
            self.comp_status.setStyleSheet(f"color: {t['error']}; font-size: 18px; font-weight: bold;")
            return
        
        # Формируем путь
        base = os.path.splitext(os.path.basename(self.comp_input_file))[0]
        folder = self.comp_output_folder if self.comp_save_custom.isChecked() else os.path.dirname(self.comp_input_file)
        output_file = os.path.join(folder, f"{base}_сжатое.mp4")
        
        # UI
        self.comp_run_btn.setEnabled(False)
        self.comp_progress.setValue(0)
        self.comp_progress_label.setText("0%")
        self.comp_status.setText("⏳ Сжатие...")
        self.comp_status.setStyleSheet(f"color: {t['text_secondary']}; font-size: 18px; font-weight: bold;")
        
        # Сигналы
        signals = WorkerSignals()
        signals.progress.connect(self._comp_update_progress)
        signals.finished.connect(self._comp_finished)
        
        def worker():
            def progress_cb(p):
                signals.progress.emit(p)
            
            try:
                preset_en = self.PRESETS.get(self.comp_preset.currentText(), "medium")
                ok = self.converter.compress_mp4_video(
                    input_file=self.comp_input_file,
                    output_file=output_file,
                    crf=self.comp_crf_slider.value(),
                    preset=preset_en,
                    audio_bitrate=self.comp_audio.currentText(),
                    show_progress=True,
                    progress_callback=progress_cb,
                )
                signals.finished.emit(ok)
            except Exception as e:
                signals.error.emit(str(e))
                signals.finished.emit(False)
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _comp_update_progress(self, value):
        self.comp_progress.setValue(value)
        self.comp_progress_label.setText(f"{value}%")
    
    def _comp_finished(self, success):
        t = THEMES[self.current_theme]
        self.comp_run_btn.setEnabled(True)
        if success:
            self.comp_status.setText("✅ Готово!")
            self.comp_status.setStyleSheet(f"color: {t['success']}; font-size: 18px; font-weight: bold;")
        else:
            self.comp_status.setText("❌ Ошибка")
            self.comp_status.setStyleSheet(f"color: {t['error']}; font-size: 18px; font-weight: bold;")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = VideoProcessorApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
