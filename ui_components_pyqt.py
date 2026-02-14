# ui_components_pyqt.py
# -*- coding: utf-8 -*-
"""
Переиспользуемые UI компоненты для PyQt6 приложения.
"""


def format_duration(ms: int) -> str:
    """Форматирует миллисекунды в человекочитаемую строку (напр. '23м 47с')."""
    if ms < 1000:
        return "<1с"
    total_sec = ms // 1000
    minutes = total_sec // 60
    seconds = total_sec % 60
    if minutes > 0:
        return f"{minutes}м {seconds}с"
    return f"{seconds}с"

import os
import threading
from PyQt6.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QVBoxLayout, QPushButton, 
    QProgressBar, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFontMetrics, QDragEnterEvent, QDropEvent


# ─── Сигналы для thread-safe обновления UI ──────────────────────────
class WorkerSignals(QObject):
    """Сигналы для передачи событий из рабочих потоков в UI."""
    progress = pyqtSignal(int, str)      # percent, file_path
    finished = pyqtSignal(object, str)   # JobResult, file_path
    error = pyqtSignal(str, str)         # error_msg, file_path
    log = pyqtSignal(str)                # log message


# ─── Виджет одного файла в очереди ──────────────────────────────────
class FileTaskWidget(QFrame):
    """Строка файла: имя, прогресс-бар, статус, кнопка отмены."""
    cancel_requested = pyqtSignal(str)  # file_path
    remove_requested = pyqtSignal(str)  # file_path

    # Состояния
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    ERROR = "error"

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.state = self.PENDING
        self.cancel_event = threading.Event()

        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(10)

        # Имя файла (обрезается с многоточием)
        self.name_label = QLabel()
        self.name_label.setFixedWidth(200)
        self.name_label.setToolTip(file_path)
        self._set_elided_name(file_path)
        layout.addWidget(self.name_label)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar, 1)

        # Статус
        self.status_label = QLabel("Ожидание...")
        self.status_label.setFixedWidth(100)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Кнопка отмены / удаления
        self.cancel_btn = QPushButton("❌")
        self.cancel_btn.setFixedSize(32, 32)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setToolTip("Отменить / Удалить")
        self.cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_btn)

    def _set_elided_name(self, path: str):
        name = os.path.basename(path)
        metrics = QFontMetrics(self.name_label.font())
        elided = metrics.elidedText(f"📄 {name}", Qt.TextElideMode.ElideMiddle, 190)
        self.name_label.setText(elided)

    def _on_cancel(self):
        if self.state == self.RUNNING:
            self.cancel_event.set()
            self.set_state(self.CANCELLED)
            self.cancel_requested.emit(self.file_path)
        else:
            self.remove_requested.emit(self.file_path)

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)
        self.status_label.setText(f"{value}%")

    def set_state(self, state: str):
        self.state = state
        if state == self.PENDING:
            self.status_label.setText("Ожидание...")
        elif state == self.RUNNING:
            self.status_label.setText("0%")
        elif state == self.FINISHED:
            self.progress_bar.setValue(100)
            self.status_label.setText("✅ Готово")
        elif state == self.CANCELLED:
            self.status_label.setText("❌ Отмена")
        elif state == self.ERROR:
            self.status_label.setText("⚠️ Ошибка")

    def apply_theme(self, t, is_dark):
        self.setStyleSheet(f"""
            QFrame {{
                background: {'rgba(255,255,255,0.03)' if is_dark else 'rgba(0,0,0,0.02)'};
                border: 1px solid {t['border_light']};
                border-radius: 10px;
            }}
        """)
        self.name_label.setStyleSheet(f"color: {t['text_primary']}; font-size: 13px; border: none; background: transparent;")
        color_map = {
            self.FINISHED: t['success'],
            self.ERROR: t['error'],
            self.CANCELLED: t['text_muted'],
        }
        sc = color_map.get(self.state, t['text_secondary'])
        self.status_label.setStyleSheet(f"color: {sc}; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; font-size: 14px;
            }}
            QPushButton:hover {{
                background: {'rgba(255,255,255,0.08)' if is_dark else 'rgba(0,0,0,0.06)'};
                border-radius: 16px;
            }}
        """)


# ─── Зона drag-and-drop ─────────────────────────────────────────────
class DropZone(QFrame):
    """Зона для выбора файлов кликом или перетаскиванием."""
    files_selected = pyqtSignal(list)  # list of file paths

    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel("🎬")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        self.text_label = QLabel("Нажмите или перетащите видео файлы")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.text_label)

        self.hint_label = QLabel("Поддерживается множественный выбор")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

    def mousePressEvent(self, event):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Выберите видео файлы", "",
            "Видео (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv);;Все файлы (*.*)"
        )
        if files:
            self.files_selected.emit(files)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in self.VIDEO_EXTENSIONS:
                    files.append(path)
        if files:
            self.files_selected.emit(files)

    def apply_theme(self, t, is_dark):
        self.setStyleSheet(f"""
            QFrame {{
                background: {t['bg_card']};
                border: 2px dashed {t['border']};
                border-radius: 18px;
            }}
            QFrame:hover {{
                border-color: {t['accent']};
                background: {'rgba(0, 212, 255, 0.05)' if is_dark else 'rgba(8, 145, 178, 0.05)'};
            }}
        """)
        self.icon_label.setStyleSheet(f"font-size: 40px; background: transparent; border: none;")
        self.text_label.setStyleSheet(f"color: {t['text_secondary']}; font-size: 15px; background: transparent; border: none;")
        self.hint_label.setStyleSheet(f"color: {t['text_muted']}; font-size: 12px; background: transparent; border: none;")


# ─── Метка-подсказка (?) ─────────────────────────────────────────────
class HelpLabel(QLabel):
    """Метка (?) с тултипом-подсказкой."""
    def __init__(self, tooltip_text: str, parent=None):
        super().__init__("(?)", parent)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setToolTip(tooltip_text)
        self.tooltip_text = tooltip_text

    def apply_theme(self, t):
        self.setStyleSheet(f"color: {t['help_color']}; font-size: 13px; font-weight: bold; background: transparent; border: none;")


# ─── Утилита обрезки пути ───────────────────────────────────────────
def elide_path(path: str, max_chars: int = 45) -> str:
    """Обрезает путь с многоточием в середине."""
    if len(path) <= max_chars:
        return path
    half = (max_chars - 3) // 2
    return path[:half] + "..." + path[-half:]
