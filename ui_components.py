# ui_components.py
# -*- coding: utf-8 -*-
"""
Общие UI компоненты для приложения.
"""

import tkinter as tk
from tkinter import ttk


class ToolTip:
    """Всплывающая подсказка при наведении на виджет."""
    
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
    
    def show(self, event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(
            tw, text=self.text, justify="left",
            background="#ffffcc", foreground="#333333",
            relief="solid", borderwidth=1,
            font=("Segoe UI", 9), padx=8, pady=6,
            wraplength=320
        )
        label.pack()
    
    def hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


def create_help_label(parent, tooltip_text: str) -> ttk.Label:
    """Создаёт метку (?) с подсказкой."""
    label = ttk.Label(parent, text="(?)", foreground="#0066cc", cursor="question_arrow")
    ToolTip(label, tooltip_text)
    return label
