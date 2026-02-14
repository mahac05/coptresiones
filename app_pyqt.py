# app_pyqt.py
# -*- coding: utf-8 -*-
"""
Красивый UI для обработки видео на PyQt6.
Поддержка тёмной и светлой темы с Material Design эстетикой.
Мульти-выбор файлов, параллельные задачи, drag-and-drop.
"""

import sys
import os
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QSlider, QProgressBar, QFrame,
    QStackedWidget, QFileDialog, QRadioButton, QButtonGroup,
    QScrollArea, QTextEdit, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from backend import FFmpegConverter
from core.models import ConversionRequest, CompressionRequest, LectureCompressionRequest, JobResult
from core.settings import (
    TOOLTIPS, PRESETS, get_crf_description,
    DEFAULT_AUDIO_FORMAT, DEFAULT_AUDIO_BITRATE, DEFAULT_CRF,
    DEFAULT_PRESET_RU, DEFAULT_COMP_AUDIO_BITRATE,
    AUDIO_BITRATE_OPTIONS, COMP_AUDIO_BITRATE_OPTIONS,
    MAX_PARALLEL_TASKS,
    DEFAULT_LECTURE_CRF, DEFAULT_LECTURE_FPS, DEFAULT_LECTURE_AUDIO_BITRATE,
    LECTURE_FPS_OPTIONS, LECTURE_AUDIO_BITRATE_OPTIONS,
    QSV_PRESETS,
)
from core.service import ProcessingService
from core.themes import PYQT_THEMES as THEMES
from ui_components_pyqt import (
    WorkerSignals, FileTaskWidget, DropZone, HelpLabel, elide_path, format_duration
)


# ═══════════════════════════════════════════════════════════════════
#  ГЛАВНОЕ ОКНО
# ═══════════════════════════════════════════════════════════════════
class VideoProcessorApp(QMainWindow):
    """Главное окно приложения."""

    def __init__(self):
        super().__init__()
        self.current_theme = "dark"

        # Сервис обработки — заменяет thread-per-file + Semaphore
        self._service = ProcessingService(max_workers=MAX_PARALLEL_TASKS)

        # Списки файлов и виджетов для каждой вкладки
        self.conv_file_widgets: dict[str, FileTaskWidget] = {}
        self.comp_file_widgets: dict[str, FileTaskWidget] = {}
        self.lect_file_widgets: dict[str, FileTaskWidget] = {}

        # Списки help-label для тем
        self._help_labels: list[HelpLabel] = []

        self.conv_output_folder = ""
        self.comp_output_folder = ""
        self.lect_output_folder = ""

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        self.setWindowTitle("🎬 Видео Обработчик")
        self.setMinimumSize(950, 700)
        self.resize(1050, 780)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === Боковая панель ===
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 15)
        sidebar_layout.setSpacing(0)

        self.logo = QLabel("🎬 Обработчик")
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

        self.nav_lecture = QPushButton("📚  Лекция")
        self.nav_lecture.setCheckable(True)
        self.nav_lecture.setMinimumHeight(55)
        self.nav_lecture.clicked.connect(lambda: self._switch_tab(2))

        sidebar_layout.addWidget(self.nav_audio)
        sidebar_layout.addWidget(self.nav_compress)
        sidebar_layout.addWidget(self.nav_lecture)
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
        self.stack.addWidget(self._create_lecture_page())

        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.stack)

        main_layout.addWidget(content_wrapper)

    # ─── Темы ───────────────────────────────────────────────────────
    def _toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self._apply_theme()

    def _apply_theme(self):
        t = THEMES[self.current_theme]
        is_dark = self.current_theme == "dark"

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
                border-radius: 6px;
                height: 12px;
                text-align: center;
                color: transparent;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {t['accent']}, stop:1 {t['accent_secondary']});
                border-radius: 6px;
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
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {t['border']};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        # Боковая панель
        self.sidebar.setStyleSheet(f"""
            QFrame {{
                background: {t['bg_sidebar']};
                border-right: 1px solid {t['border']};
            }}
        """)

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
        self.nav_lecture.setStyleSheet(nav_checked if self.nav_lecture.isChecked() else nav_unchecked)

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

        self.stack.setStyleSheet("background: transparent;")

        # Обновляем виджеты
        self._update_themed_widgets(t, is_dark)

    def _update_themed_widgets(self, t, is_dark):
        # Карточки настроек
        card_style = f"""
            QFrame {{
                background: {t['bg_card']};
                border: 1px solid {t['border_light']};
                border-radius: 18px;
            }}
        """
        for attr in ['conv_settings_card', 'comp_settings_card', 'lect_settings_card']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(card_style)

        # Заголовки
        for attr in ['conv_header', 'comp_header', 'lect_header']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"font-size: 30px; font-weight: bold; color: {t['text_primary']};")

        # Drop zones
        for attr in ['conv_drop_zone', 'comp_drop_zone', 'lect_drop_zone']:
            if hasattr(self, attr):
                getattr(self, attr).apply_theme(t, is_dark)

        # Кнопки запуска
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
        for attr in ['conv_run_btn', 'comp_run_btn', 'lect_run_btn']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(btn_style)

        # Вторичные кнопки
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
        for attr in ['conv_folder_btn', 'comp_folder_btn', 'lect_folder_btn']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(sec_btn_style)

        # CRF
        for attr in ['comp_crf_value', 'lect_crf_value']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"color: {t['accent']}; font-size: 15px;")

        # Help labels
        for hl in self._help_labels:
            hl.apply_theme(t)

        # Журналы
        log_style = f"""
            QTextEdit {{
                background: {t['log_bg']};
                color: {t['log_text']};
                border: 1px solid {t['border_light']};
                border-radius: 10px;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }}
        """
        for attr in ['conv_log', 'comp_log', 'lect_log']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(log_style)

        # Лейблы журнала
        for attr in ['conv_log_label', 'comp_log_label', 'lect_log_label']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"color: {t['text_secondary']}; font-size: 14px; font-weight: bold;")

        # Файловые виджеты
        for fw in list(self.conv_file_widgets.values()) + list(self.comp_file_widgets.values()) + list(self.lect_file_widgets.values()):
            fw.apply_theme(t, is_dark)

        # Путь к папке
        for attr in ['conv_folder_label', 'comp_folder_label', 'lect_folder_label']:
            if hasattr(self, attr):
                w = getattr(self, attr)
                if w.text():
                    w.setStyleSheet(f"color: {t['success']}; font-size: 14px;")

    def _switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        self.nav_audio.setChecked(index == 0)
        self.nav_compress.setChecked(index == 1)
        self.nav_lecture.setChecked(index == 2)
        self._apply_theme()

    # ─── Вспомогательные ────────────────────────────────────────────
    def _make_help(self, key: str) -> HelpLabel:
        hl = HelpLabel(TOOLTIPS[key])
        self._help_labels.append(hl)
        return hl

    def _make_scroll_page(self, inner_widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner_widget)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return scroll

    # ==================== КОНВЕРТАЦИЯ ====================

    def _create_convert_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        layout.setContentsMargins(35, 35, 35, 35)

        # Заголовок
        self.conv_header = QLabel("🎵 Конвертация в аудио")
        layout.addWidget(self.conv_header)

        # Зона выбора файлов
        self.conv_drop_zone = DropZone()
        self.conv_drop_zone.files_selected.connect(self._conv_add_files)
        layout.addWidget(self.conv_drop_zone)

        # Список файлов
        self.conv_file_list_widget = QWidget()
        self.conv_file_list_layout = QVBoxLayout(self.conv_file_list_widget)
        self.conv_file_list_layout.setContentsMargins(0, 0, 0, 0)
        self.conv_file_list_layout.setSpacing(6)

        conv_file_scroll = QScrollArea()
        conv_file_scroll.setWidgetResizable(True)
        conv_file_scroll.setWidget(self.conv_file_list_widget)
        conv_file_scroll.setMaximumHeight(200)
        conv_file_scroll.setMinimumHeight(0)
        conv_file_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        conv_file_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.conv_file_scroll = conv_file_scroll
        layout.addWidget(conv_file_scroll)

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

        fmt_lbl = QLabel("Формат:")
        format_layout.addWidget(fmt_lbl)
        format_layout.addWidget(self._make_help("format"))

        self.conv_format = QComboBox()
        self.conv_format.addItems(list(FFmpegConverter.AUDIO_FORMATS.keys()))
        self.conv_format.setCurrentText(DEFAULT_AUDIO_FORMAT)
        format_layout.addWidget(self.conv_format)
        format_layout.addSpacing(35)

        br_lbl = QLabel("Битрейт:")
        format_layout.addWidget(br_lbl)
        format_layout.addWidget(self._make_help("bitrate"))

        self.conv_bitrate = QComboBox()
        self.conv_bitrate.addItems(AUDIO_BITRATE_OPTIONS)
        self.conv_bitrate.setCurrentText(DEFAULT_AUDIO_BITRATE)
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

        # Кнопка запуска
        self.conv_run_btn = QPushButton("▶ Конвертировать")
        self.conv_run_btn.setMinimumWidth(220)
        self.conv_run_btn.setMinimumHeight(55)
        self.conv_run_btn.clicked.connect(self._conv_run)
        layout.addWidget(self.conv_run_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Журнал
        self.conv_log_label = QLabel("📋 Журнал")
        layout.addWidget(self.conv_log_label)

        self.conv_log = QTextEdit()
        self.conv_log.setReadOnly(True)
        self.conv_log.setMaximumHeight(180)
        self.conv_log.setMinimumHeight(80)
        layout.addWidget(self.conv_log)

        layout.addStretch()

        return self._make_scroll_page(page)

    def _conv_add_files(self, files: list):
        t = THEMES[self.current_theme]
        is_dark = self.current_theme == "dark"
        for f in files:
            if f not in self.conv_file_widgets:
                fw = FileTaskWidget(f)
                fw.remove_requested.connect(self._conv_remove_file)
                fw.cancel_requested.connect(lambda p: self._conv_log_msg(f"❌ Отменено: {os.path.basename(p)}"))
                fw.apply_theme(t, is_dark)
                self.conv_file_widgets[f] = fw
                self.conv_file_list_layout.addWidget(fw)
        # Обновляем высоту скролла
        count = len(self.conv_file_widgets)
        self.conv_file_scroll.setMaximumHeight(min(200, count * 54 + 10))
        self._conv_log_msg(f"📂 Добавлено файлов: {len(files)}")

    def _conv_remove_file(self, path: str):
        fw = self.conv_file_widgets.pop(path, None)
        if fw:
            self.conv_file_list_layout.removeWidget(fw)
            fw.deleteLater()
            count = len(self.conv_file_widgets)
            self.conv_file_scroll.setMaximumHeight(min(200, max(0, count * 54 + 10)))

    def _conv_save_mode_changed(self, checked):
        self.conv_folder_btn.setVisible(checked)
        self.conv_folder_label.setVisible(checked and bool(self.conv_output_folder))

    def _conv_pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.conv_output_folder = folder
            t = THEMES[self.current_theme]
            self.conv_folder_label.setText(f"📁 {elide_path(folder)}")
            self.conv_folder_label.setToolTip(folder)
            self.conv_folder_label.setStyleSheet(f"color: {t['success']}; font-size: 14px;")
            self.conv_folder_label.show()

    def _conv_log_msg(self, msg: str):
        self.conv_log.append(msg)

    def _conv_run(self):
        # Собираем файлы в ожидании
        pending = [fw for fw in self.conv_file_widgets.values() if fw.state == FileTaskWidget.PENDING]
        if not pending:
            self._conv_log_msg("⚠️ Нет файлов для конвертации!")
            return

        if self.conv_save_custom.isChecked() and not self.conv_output_folder:
            self._conv_log_msg("⚠️ Выберите папку для сохранения!")
            return

        ext = self.conv_format.currentText()
        bitrate = self.conv_bitrate.currentText()

        # Сигналы для thread-safe обновления UI
        signals = WorkerSignals()
        signals.progress.connect(self._conv_update_progress)
        signals.finished.connect(self._conv_task_finished)
        signals.log.connect(self._conv_log_msg)

        for fw in pending:
            fw.set_state(FileTaskWidget.RUNNING)
            t_obj = THEMES[self.current_theme]
            fw.apply_theme(t_obj, self.current_theme == "dark")

            base = os.path.splitext(os.path.basename(fw.file_path))[0]
            folder = self.conv_output_folder if self.conv_save_custom.isChecked() else os.path.dirname(fw.file_path)
            output_file = os.path.join(folder, f"{base}.{ext}")

            request = ConversionRequest(
                input_file=fw.file_path,
                output_file=output_file,
                output_format=ext,
                bitrate=bitrate,
            )

            self._service.submit_conversion(
                request=request,
                cancel_event=fw.cancel_event,
                on_progress=lambda p, fp: signals.progress.emit(p, fp),
                on_finished=lambda result, fp: signals.finished.emit(result, fp),
                on_log=lambda msg: signals.log.emit(msg),
            )

        self._conv_log_msg(f"⏳ Запущено задач: {len(pending)} (макс. параллельно: {self._service.max_workers})")

    def _conv_update_progress(self, value, file_path):
        fw = self.conv_file_widgets.get(file_path)
        if fw and fw.state == FileTaskWidget.RUNNING:
            fw.set_progress(value)

    def _conv_task_finished(self, result, file_path):
        fw = self.conv_file_widgets.get(file_path)
        if not fw:
            return
        t = THEMES[self.current_theme]
        name = os.path.basename(file_path)
        if fw.state == FileTaskWidget.CANCELLED:
            self._conv_log_msg(f"❌ Отменено: {name}")
        elif isinstance(result, JobResult) and result.ok:
            fw.set_state(FileTaskWidget.FINISHED)
            self._conv_log_msg(f"✅ Готово: {name} ({format_duration(result.duration_ms)})")
        else:
            fw.set_state(FileTaskWidget.ERROR)
            error_detail = result.error_message if isinstance(result, JobResult) else ""
            self._conv_log_msg(f"⚠️ Ошибка: {name}" + (f" — {error_detail}" if error_detail else ""))
        fw.apply_theme(t, self.current_theme == "dark")

    # ==================== СЖАТИЕ ====================

    def _create_compress_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        layout.setContentsMargins(35, 35, 35, 35)

        # Заголовок
        self.comp_header = QLabel("📦 Сжатие видео")
        layout.addWidget(self.comp_header)

        # Зона выбора файлов
        self.comp_drop_zone = DropZone()
        self.comp_drop_zone.files_selected.connect(self._comp_add_files)
        layout.addWidget(self.comp_drop_zone)

        # Список файлов
        self.comp_file_list_widget = QWidget()
        self.comp_file_list_layout = QVBoxLayout(self.comp_file_list_widget)
        self.comp_file_list_layout.setContentsMargins(0, 0, 0, 0)
        self.comp_file_list_layout.setSpacing(6)

        comp_file_scroll = QScrollArea()
        comp_file_scroll.setWidgetResizable(True)
        comp_file_scroll.setWidget(self.comp_file_list_widget)
        comp_file_scroll.setMaximumHeight(200)
        comp_file_scroll.setMinimumHeight(0)
        comp_file_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        comp_file_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.comp_file_scroll = comp_file_scroll
        layout.addWidget(comp_file_scroll)

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
        crf_lbl = QLabel("Качество (CRF):")
        crf_layout.addWidget(crf_lbl)
        crf_layout.addWidget(self._make_help("crf"))
        crf_layout.addStretch()

        self.comp_crf_value = QLabel("23 (стандартное)")
        crf_layout.addWidget(self.comp_crf_value)
        card_layout.addLayout(crf_layout)

        self.comp_crf_slider = QSlider(Qt.Orientation.Horizontal)
        self.comp_crf_slider.setRange(18, 40)
        self.comp_crf_slider.setValue(23)
        self.comp_crf_slider.valueChanged.connect(self._comp_crf_changed)
        card_layout.addWidget(self.comp_crf_slider)

        # Пресет и аудио
        preset_layout = QHBoxLayout()

        preset_lbl = QLabel("Скорость:")
        preset_layout.addWidget(preset_lbl)
        preset_layout.addWidget(self._make_help("preset"))

        self.comp_preset = QComboBox()
        self.comp_preset.addItems(list(PRESETS.keys()))
        self.comp_preset.setCurrentText(DEFAULT_PRESET_RU)
        preset_layout.addWidget(self.comp_preset)
        preset_layout.addSpacing(35)

        audio_lbl = QLabel("Звук:")
        preset_layout.addWidget(audio_lbl)
        preset_layout.addWidget(self._make_help("audio_bitrate"))

        self.comp_audio = QComboBox()
        self.comp_audio.addItems(COMP_AUDIO_BITRATE_OPTIONS)
        self.comp_audio.setCurrentText(DEFAULT_COMP_AUDIO_BITRATE)
        preset_layout.addWidget(self.comp_audio)
        preset_layout.addStretch()

        card_layout.addLayout(preset_layout)

        # GPU
        gpu_layout = QHBoxLayout()
        self.comp_gpu_checkbox = QCheckBox("🚀 GPU (Intel QSV)")
        self.comp_gpu_checkbox.setToolTip(TOOLTIPS.get("gpu_qsv", ""))
        self.comp_gpu_checkbox.stateChanged.connect(self._comp_gpu_toggled)
        gpu_layout.addWidget(self.comp_gpu_checkbox)
        gpu_layout.addWidget(self._make_help("gpu_qsv"))
        gpu_layout.addStretch()
        card_layout.addLayout(gpu_layout)

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

        # Кнопка запуска
        self.comp_run_btn = QPushButton("▶ Сжать видео")
        self.comp_run_btn.setMinimumWidth(220)
        self.comp_run_btn.setMinimumHeight(55)
        self.comp_run_btn.clicked.connect(self._comp_run)
        layout.addWidget(self.comp_run_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Журнал
        self.comp_log_label = QLabel("📋 Журнал")
        layout.addWidget(self.comp_log_label)

        self.comp_log = QTextEdit()
        self.comp_log.setReadOnly(True)
        self.comp_log.setMaximumHeight(180)
        self.comp_log.setMinimumHeight(80)
        layout.addWidget(self.comp_log)

        layout.addStretch()

        return self._make_scroll_page(page)

    def _comp_add_files(self, files: list):
        t = THEMES[self.current_theme]
        is_dark = self.current_theme == "dark"
        for f in files:
            if f not in self.comp_file_widgets:
                fw = FileTaskWidget(f)
                fw.remove_requested.connect(self._comp_remove_file)
                fw.cancel_requested.connect(lambda p: self._comp_log_msg(f"❌ Отменено: {os.path.basename(p)}"))
                fw.apply_theme(t, is_dark)
                self.comp_file_widgets[f] = fw
                self.comp_file_list_layout.addWidget(fw)
        count = len(self.comp_file_widgets)
        self.comp_file_scroll.setMaximumHeight(min(200, count * 54 + 10))
        self._comp_log_msg(f"📂 Добавлено файлов: {len(files)}")

    def _comp_remove_file(self, path: str):
        fw = self.comp_file_widgets.pop(path, None)
        if fw:
            self.comp_file_list_layout.removeWidget(fw)
            fw.deleteLater()
            count = len(self.comp_file_widgets)
            self.comp_file_scroll.setMaximumHeight(min(200, max(0, count * 54 + 10)))

    def _comp_crf_changed(self, value):
        desc = get_crf_description(value)
        self.comp_crf_value.setText(f"{value} {desc}")

    def _comp_save_mode_changed(self, checked):
        self.comp_folder_btn.setVisible(checked)
        self.comp_folder_label.setVisible(checked and bool(self.comp_output_folder))

    def _comp_pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.comp_output_folder = folder
            t = THEMES[self.current_theme]
            self.comp_folder_label.setText(f"📁 {elide_path(folder)}")
            self.comp_folder_label.setToolTip(folder)
            self.comp_folder_label.setStyleSheet(f"color: {t['success']}; font-size: 14px;")
            self.comp_folder_label.show()

    def _comp_log_msg(self, msg: str):
        self.comp_log.append(msg)

    def _comp_gpu_toggled(self, state):
        """При переключении GPU обновляет список пресетов."""
        use_gpu = bool(state)
        current_text = self.comp_preset.currentText()
        self.comp_preset.clear()
        if use_gpu:
            self.comp_preset.addItems(list(QSV_PRESETS.keys()))
            if current_text in QSV_PRESETS:
                self.comp_preset.setCurrentText(current_text)
            else:
                self.comp_preset.setCurrentText("Стандарт")
        else:
            self.comp_preset.addItems(list(PRESETS.keys()))
            if current_text in PRESETS:
                self.comp_preset.setCurrentText(current_text)
            else:
                self.comp_preset.setCurrentText(DEFAULT_PRESET_RU)

    def _comp_run(self):
        pending = [fw for fw in self.comp_file_widgets.values() if fw.state == FileTaskWidget.PENDING]
        if not pending:
            self._comp_log_msg("⚠️ Нет файлов для сжатия!")
            return

        if self.comp_save_custom.isChecked() and not self.comp_output_folder:
            self._comp_log_msg("⚠️ Выберите папку для сохранения!")
            return

        crf = self.comp_crf_slider.value()
        preset_ru = self.comp_preset.currentText()
        use_gpu = self.comp_gpu_checkbox.isChecked()
        presets_map = QSV_PRESETS if use_gpu else PRESETS
        preset_en = presets_map.get(preset_ru, "medium")
        audio_br = self.comp_audio.currentText()

        signals = WorkerSignals()
        signals.progress.connect(self._comp_update_progress)
        signals.finished.connect(self._comp_task_finished)
        signals.log.connect(self._comp_log_msg)

        for fw in pending:
            fw.set_state(FileTaskWidget.RUNNING)
            t_obj = THEMES[self.current_theme]
            fw.apply_theme(t_obj, self.current_theme == "dark")

            base = os.path.splitext(os.path.basename(fw.file_path))[0]
            folder = self.comp_output_folder if self.comp_save_custom.isChecked() else os.path.dirname(fw.file_path)
            output_file = os.path.join(folder, f"{base}_сжатое.mp4")

            request = CompressionRequest(
                input_file=fw.file_path,
                output_file=output_file,
                crf=crf,
                preset=preset_en,
                audio_bitrate=audio_br,
                use_gpu=self.comp_gpu_checkbox.isChecked(),
            )

            self._service.submit_compression(
                request=request,
                cancel_event=fw.cancel_event,
                on_progress=lambda p, fp: signals.progress.emit(p, fp),
                on_finished=lambda result, fp: signals.finished.emit(result, fp),
                on_log=lambda msg: signals.log.emit(msg),
            )

        self._comp_log_msg(f"⏳ Запущено задач: {len(pending)} (макс. параллельно: {self._service.max_workers})")

    def _comp_update_progress(self, value, file_path):
        fw = self.comp_file_widgets.get(file_path)
        if fw and fw.state == FileTaskWidget.RUNNING:
            fw.set_progress(value)

    def _comp_task_finished(self, result, file_path):
        fw = self.comp_file_widgets.get(file_path)
        if not fw:
            return
        t = THEMES[self.current_theme]
        name = os.path.basename(file_path)
        if fw.state == FileTaskWidget.CANCELLED:
            self._comp_log_msg(f"❌ Отменено: {name}")
        elif isinstance(result, JobResult) and result.ok:
            fw.set_state(FileTaskWidget.FINISHED)
            self._comp_log_msg(f"✅ Готово: {name} ({format_duration(result.duration_ms)})")
        else:
            fw.set_state(FileTaskWidget.ERROR)
            error_detail = result.error_message if isinstance(result, JobResult) else ""
            self._comp_log_msg(f"⚠️ Ошибка: {name}" + (f" — {error_detail}" if error_detail else ""))
        fw.apply_theme(t, self.current_theme == "dark")

    # ==================== СЖАТИЕ ЛЕКЦИЙ ====================

    def _create_lecture_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        layout.setContentsMargins(35, 35, 35, 35)

        # Заголовок
        self.lect_header = QLabel("📚 Сжатие лекции")
        layout.addWidget(self.lect_header)

        # Зона выбора файлов
        self.lect_drop_zone = DropZone()
        self.lect_drop_zone.files_selected.connect(self._lect_add_files)
        layout.addWidget(self.lect_drop_zone)

        # Список файлов
        self.lect_file_list_widget = QWidget()
        self.lect_file_list_layout = QVBoxLayout(self.lect_file_list_widget)
        self.lect_file_list_layout.setContentsMargins(0, 0, 0, 0)
        self.lect_file_list_layout.setSpacing(6)

        lect_file_scroll = QScrollArea()
        lect_file_scroll.setWidgetResizable(True)
        lect_file_scroll.setWidget(self.lect_file_list_widget)
        lect_file_scroll.setMaximumHeight(200)
        lect_file_scroll.setMinimumHeight(0)
        lect_file_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lect_file_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.lect_file_scroll = lect_file_scroll
        layout.addWidget(lect_file_scroll)

        # Настройки
        self.lect_settings_card = QFrame()
        card_layout = QVBoxLayout(self.lect_settings_card)
        card_layout.setContentsMargins(28, 22, 28, 28)
        card_layout.setSpacing(18)

        title_label = QLabel("⚙️ Настройки сжатия лекции")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        card_layout.addWidget(title_label)

        info_label = QLabel("💡 Оптимизировано для слайдов: -tune stillimage, пониженный FPS, моно-звук")
        info_label.setStyleSheet("font-size: 13px; font-style: italic;")
        info_label.setWordWrap(True)
        card_layout.addWidget(info_label)

        # CRF
        crf_layout = QHBoxLayout()
        crf_lbl = QLabel("Качество (CRF):")
        crf_layout.addWidget(crf_lbl)
        crf_layout.addWidget(self._make_help("lecture_crf"))
        crf_layout.addStretch()

        self.lect_crf_value = QLabel(f"{DEFAULT_LECTURE_CRF} (рекомендуется)")
        crf_layout.addWidget(self.lect_crf_value)
        card_layout.addLayout(crf_layout)

        self.lect_crf_slider = QSlider(Qt.Orientation.Horizontal)
        self.lect_crf_slider.setRange(18, 40)
        self.lect_crf_slider.setValue(DEFAULT_LECTURE_CRF)
        self.lect_crf_slider.valueChanged.connect(self._lect_crf_changed)
        card_layout.addWidget(self.lect_crf_slider)

        # Пресет, FPS, аудио
        row_layout = QHBoxLayout()

        preset_lbl = QLabel("Скорость:")
        row_layout.addWidget(preset_lbl)
        row_layout.addWidget(self._make_help("preset"))

        self.lect_preset = QComboBox()
        self.lect_preset.addItems(list(PRESETS.keys()))
        self.lect_preset.setCurrentText(DEFAULT_PRESET_RU)
        row_layout.addWidget(self.lect_preset)
        row_layout.addSpacing(20)

        fps_lbl = QLabel("FPS:")
        row_layout.addWidget(fps_lbl)
        row_layout.addWidget(self._make_help("lecture_fps"))

        self.lect_fps = QComboBox()
        self.lect_fps.addItems(LECTURE_FPS_OPTIONS)
        self.lect_fps.setCurrentText(str(DEFAULT_LECTURE_FPS))
        row_layout.addWidget(self.lect_fps)
        row_layout.addSpacing(20)

        audio_lbl = QLabel("Звук:")
        row_layout.addWidget(audio_lbl)
        row_layout.addWidget(self._make_help("audio_bitrate"))

        self.lect_audio = QComboBox()
        self.lect_audio.addItems(LECTURE_AUDIO_BITRATE_OPTIONS)
        self.lect_audio.setCurrentText(DEFAULT_LECTURE_AUDIO_BITRATE)
        row_layout.addWidget(self.lect_audio)
        row_layout.addStretch()

        card_layout.addLayout(row_layout)

        # Сохранение
        save_label = QLabel("Сохранить:")
        card_layout.addWidget(save_label)

        self.lect_save_same = QRadioButton("В той же папке")
        self.lect_save_custom = QRadioButton("Выбрать папку")
        self.lect_save_same.setChecked(True)

        self.lect_save_group = QButtonGroup()
        self.lect_save_group.addButton(self.lect_save_same)
        self.lect_save_group.addButton(self.lect_save_custom)
        self.lect_save_custom.toggled.connect(self._lect_save_mode_changed)

        save_layout = QHBoxLayout()
        save_layout.addWidget(self.lect_save_same)
        save_layout.addWidget(self.lect_save_custom)
        save_layout.addStretch()
        card_layout.addLayout(save_layout)

        self.lect_folder_btn = QPushButton("📁 Выбрать папку...")
        self.lect_folder_btn.hide()
        self.lect_folder_btn.clicked.connect(self._lect_pick_folder)
        card_layout.addWidget(self.lect_folder_btn)

        self.lect_folder_label = QLabel("")
        self.lect_folder_label.hide()
        card_layout.addWidget(self.lect_folder_label)

        layout.addWidget(self.lect_settings_card)

        # Кнопка запуска
        self.lect_run_btn = QPushButton("▶ Сжать лекцию")
        self.lect_run_btn.setMinimumWidth(220)
        self.lect_run_btn.setMinimumHeight(55)
        self.lect_run_btn.clicked.connect(self._lect_run)
        layout.addWidget(self.lect_run_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Журнал
        self.lect_log_label = QLabel("📋 Журнал")
        layout.addWidget(self.lect_log_label)

        self.lect_log = QTextEdit()
        self.lect_log.setReadOnly(True)
        self.lect_log.setMaximumHeight(180)
        self.lect_log.setMinimumHeight(80)
        layout.addWidget(self.lect_log)

        layout.addStretch()

        return self._make_scroll_page(page)

    def _lect_add_files(self, files: list):
        t = THEMES[self.current_theme]
        is_dark = self.current_theme == "dark"
        for f in files:
            if f not in self.lect_file_widgets:
                fw = FileTaskWidget(f)
                fw.remove_requested.connect(self._lect_remove_file)
                fw.cancel_requested.connect(lambda p: self._lect_log_msg(f"❌ Отменено: {os.path.basename(p)}"))
                fw.apply_theme(t, is_dark)
                self.lect_file_widgets[f] = fw
                self.lect_file_list_layout.addWidget(fw)
        count = len(self.lect_file_widgets)
        self.lect_file_scroll.setMaximumHeight(min(200, count * 54 + 10))
        self._lect_log_msg(f"📂 Добавлено файлов: {len(files)}")

    def _lect_remove_file(self, path: str):
        fw = self.lect_file_widgets.pop(path, None)
        if fw:
            self.lect_file_list_layout.removeWidget(fw)
            fw.deleteLater()
            count = len(self.lect_file_widgets)
            self.lect_file_scroll.setMaximumHeight(min(200, max(0, count * 54 + 10)))

    def _lect_crf_changed(self, value):
        desc = get_crf_description(value)
        self.lect_crf_value.setText(f"{value} {desc}")

    def _lect_save_mode_changed(self, checked):
        self.lect_folder_btn.setVisible(checked)
        self.lect_folder_label.setVisible(checked and bool(self.lect_output_folder))

    def _lect_pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.lect_output_folder = folder
            t = THEMES[self.current_theme]
            self.lect_folder_label.setText(f"📁 {elide_path(folder)}")
            self.lect_folder_label.setToolTip(folder)
            self.lect_folder_label.setStyleSheet(f"color: {t['success']}; font-size: 14px;")
            self.lect_folder_label.show()

    def _lect_log_msg(self, msg: str):
        self.lect_log.append(msg)

    def _lect_run(self):
        pending = [fw for fw in self.lect_file_widgets.values() if fw.state == FileTaskWidget.PENDING]
        if not pending:
            self._lect_log_msg("⚠️ Нет файлов для сжатия!")
            return

        if self.lect_save_custom.isChecked() and not self.lect_output_folder:
            self._lect_log_msg("⚠️ Выберите папку для сохранения!")
            return

        crf = self.lect_crf_slider.value()
        preset_ru = self.lect_preset.currentText()
        preset_en = PRESETS.get(preset_ru, "medium")
        audio_br = self.lect_audio.currentText()
        fps = int(self.lect_fps.currentText())

        signals = WorkerSignals()
        signals.progress.connect(self._lect_update_progress)
        signals.finished.connect(self._lect_task_finished)
        signals.log.connect(self._lect_log_msg)

        for fw in pending:
            fw.set_state(FileTaskWidget.RUNNING)
            t_obj = THEMES[self.current_theme]
            fw.apply_theme(t_obj, self.current_theme == "dark")

            base = os.path.splitext(os.path.basename(fw.file_path))[0]
            folder = self.lect_output_folder if self.lect_save_custom.isChecked() else os.path.dirname(fw.file_path)
            output_file = os.path.join(folder, f"{base}_лекция.mp4")

            request = LectureCompressionRequest(
                input_file=fw.file_path,
                output_file=output_file,
                crf=crf,
                preset=preset_en,
                audio_bitrate=audio_br,
                fps=fps,
            )

            self._service.submit_lecture_compression(
                request=request,
                cancel_event=fw.cancel_event,
                on_progress=lambda p, fp: signals.progress.emit(p, fp),
                on_finished=lambda result, fp: signals.finished.emit(result, fp),
                on_log=lambda msg: signals.log.emit(msg),
            )

        self._lect_log_msg(f"⏳ Запущено задач: {len(pending)} (макс. параллельно: {self._service.max_workers})")

    def _lect_update_progress(self, value, file_path):
        fw = self.lect_file_widgets.get(file_path)
        if fw and fw.state == FileTaskWidget.RUNNING:
            fw.set_progress(value)

    def _lect_task_finished(self, result, file_path):
        fw = self.lect_file_widgets.get(file_path)
        if not fw:
            return
        t = THEMES[self.current_theme]
        name = os.path.basename(file_path)
        if fw.state == FileTaskWidget.CANCELLED:
            self._lect_log_msg(f"❌ Отменено: {name}")
        elif isinstance(result, JobResult) and result.ok:
            fw.set_state(FileTaskWidget.FINISHED)
            self._lect_log_msg(f"✅ Готово: {name} ({format_duration(result.duration_ms)})")
        else:
            fw.set_state(FileTaskWidget.ERROR)
            error_detail = result.error_message if isinstance(result, JobResult) else ""
            self._lect_log_msg(f"⚠️ Ошибка: {name}" + (f" — {error_detail}" if error_detail else ""))
        fw.apply_theme(t, self.current_theme == "dark")


# ═══════════════════════════════════════════════════════════════════
def main():
    from core.logging_config import setup_logging
    setup_logging()
    
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 11))
    window = VideoProcessorApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
