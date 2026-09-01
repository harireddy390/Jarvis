import math
from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QRadialGradient, QFont, QPen
from core.event_bus import event_bus

STATE_THEME = {
    "IDLE":      {"core": QColor(40, 90, 130),  "ring": QColor(0, 140, 200),  "speed": 0.4},
    "WAKE":      {"core": QColor(0, 200, 255),  "ring": QColor(0, 230, 255),  "speed": 2.5},
    "LISTENING": {"core": QColor(0, 220, 255),  "ring": QColor(80, 200, 255), "speed": 1.6},
    "THINKING":  {"core": QColor(150, 90, 255), "ring": QColor(180, 120, 255),"speed": 1.8},
    "EXECUTING": {"core": QColor(255, 150, 30), "ring": QColor(255, 180, 60),"speed": 2.2},
    "SUCCESS":   {"core": QColor(0, 255, 160),  "ring": QColor(80, 255, 190),"speed": 1.0},
    "ERROR":     {"core": QColor(255, 60, 60),  "ring": QColor(255, 100, 100),"speed": 3.0},
}


class JarvisHUD(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(340, 360)

        screen = self.screen().availableGeometry()
        self.move(screen.width() // 2 - 170, screen.height() - 420)

        self.state = "IDLE"
        self.message = "Waiting for 'Hey Jarvis'"
        self.angle = 0.0
        self.pulse_phase = 0.0
        self.bars = [0.15] * 24  # lightweight fake waveform, state-driven

        self.status_label = QLabel(self.message, self)
        self.status_label.setStyleSheet(
            "color: rgba(210,240,255,220); font-size: 13px; font-family: Segoe UI;"
        )
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setGeometry(0, 250, 340, 24)

        self.title_label = QLabel("JARVIS", self)
        self.title_label.setStyleSheet(
            "color: rgba(120,220,255,230); font-size: 15px; font-weight: bold; "
            "font-family: Segoe UI; letter-spacing: 4px;"
        )
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setGeometry(0, 10, 340, 24)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)  # ~30 FPS

        event_bus.state_changed.connect(self._on_state_changed)
        self.show()

    def _on_state_changed(self, state: str, message: str):
        self.state = state if state in STATE_THEME else "IDLE"
        self.message = message or state
        self.status_label.setText(self.message)

    def _tick(self):
        theme = STATE_THEME[self.state]
        self.angle = (self.angle + theme["speed"]) % 360
        self.pulse_phase += 0.12
        active = self.state in ("LISTENING", "EXECUTING", "THINKING", "WAKE")
        for i in range(len(self.bars)):
            target = (0.3 + 0.7 * abs(math.sin(self.pulse_phase + i * 0.4))) if active else 0.12
            self.bars[i] += (target - self.bars[i]) * 0.3
        self.update()

    def paintEvent(self, event):
        theme = STATE_THEME[self.state]
        core_color = theme["core"]
        ring_color = theme["ring"]

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx, cy = 170, 150
        pulse = 6 * math.sin(self.pulse_phase)

        # outer glow
        glow_radius = 95 + pulse
        gradient = QRadialGradient(cx, cy, glow_radius)
        glow_color = QColor(core_color)
        glow_color.setAlpha(60)
        gradient.setColorAt(0, glow_color)
        gradient.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(cx - glow_radius, cy - glow_radius, glow_radius * 2, glow_radius * 2)

        # rotating rings (concentric, alternating direction)
        for i, radius in enumerate([55, 70, 88]):
            painter.save()
            painter.translate(cx, cy)
            direction = 1 if i % 2 == 0 else -1
            painter.rotate(self.angle * direction * (0.6 + i * 0.3))
            pen = QPen(ring_color if i % 2 == 0 else QColor(255, 150, 60, 180))
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            span = 260 - i * 40
            painter.drawArc(-radius, -radius, radius * 2, radius * 2, 0, span * 16)
            painter.restore()

        # central core
        core_radius = 34 + pulse * 0.5
        core_gradient = QRadialGradient(cx, cy, core_radius)
        core_gradient.setColorAt(0, QColor(255, 255, 255, 230))
        core_gradient.setColorAt(0.4, core_color.lighter(140))
        core_gradient.setColorAt(1, core_color)
        painter.setBrush(core_gradient)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(cx - core_radius, cy - core_radius, core_radius * 2, core_radius * 2)

        # waveform bars near bottom of the orb area
        bar_area_w = 220
        bar_x = cx - bar_area_w // 2
        bar_y = 210
        bar_w = bar_area_w / len(self.bars)
        painter.setPen(Qt.NoPen)
        for i, level in enumerate(self.bars):
            h = 4 + level * 26
            color = QColor(ring_color)
            color.setAlpha(200)
            painter.setBrush(color)
            painter.drawRoundedRect(
                bar_x + i * bar_w + 1, bar_y - h / 2, bar_w - 2, h, 2, 2
            )