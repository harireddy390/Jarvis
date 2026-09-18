"""
JARVIS Premium HUD — Siri-style glowing orb + holographic overlay.

Design:
- Dark glassmorphic card
- Central animated JARVIS orb
- Reactive waveform
- Smooth state/color transitions
- CPU/RAM telemetry
- Draggable always-on-top window
- Double-click opacity toggle
"""

import math
import psutil

from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF
from PySide6.QtGui import (
    QPainter,
    QColor,
    QRadialGradient,
    QLinearGradient,
    QPen,
    QPainterPath,
)

from core.event_bus import event_bus


# ---------------------------------------------------------------------------
# State themes
# ---------------------------------------------------------------------------

STATE_THEME = {
    "IDLE": {
        "orb_colors": [
            QColor(0, 100, 180),
            QColor(0, 60, 130),
            QColor(0, 20, 70),
        ],
        "glow": QColor(0, 120, 200, 40),
        "accent": QColor(60, 160, 255),
        "badge_bg": "rgba(0, 120, 200, 0.15)",
        "badge_border": "rgba(60, 160, 255, 0.4)",
        "badge_text": "#60a8ff",
        "tag": "STANDBY",
        "orb_speed": 0.4,
        "orb_pulse_amp": 0.5,
        "wave_active": False,
    },

    "WAKE": {
        "orb_colors": [
            QColor(0, 230, 255),
            QColor(0, 180, 240),
            QColor(0, 100, 200),
        ],
        "glow": QColor(0, 230, 255, 90),
        "accent": QColor(100, 240, 255),
        "badge_bg": "rgba(0, 230, 255, 0.2)",
        "badge_border": "rgba(100, 240, 255, 0.8)",
        "badge_text": "#a0f8ff",
        "tag": "ACTIVE",
        "orb_speed": 4.0,
        "orb_pulse_amp": 3.5,
        "wave_active": True,
    },

    "LISTENING": {
        "orb_colors": [
            QColor(0, 200, 150),
            QColor(0, 160, 220),
            QColor(0, 80, 160),
        ],
        "glow": QColor(0, 200, 180, 80),
        "accent": QColor(80, 255, 200),
        "badge_bg": "rgba(0, 200, 150, 0.2)",
        "badge_border": "rgba(80, 255, 200, 0.8)",
        "badge_text": "#6effc7",
        "tag": "LISTENING",
        "orb_speed": 3.5,
        "orb_pulse_amp": 5.0,
        "wave_active": True,
    },

    "THINKING": {
        "orb_colors": [
            QColor(160, 60, 255),
            QColor(200, 100, 255),
            QColor(100, 30, 180),
        ],
        "glow": QColor(160, 60, 255, 75),
        "accent": QColor(210, 130, 255),
        "badge_bg": "rgba(160, 60, 255, 0.2)",
        "badge_border": "rgba(200, 130, 255, 0.8)",
        "badge_text": "#e0b0ff",
        "tag": "ANALYZING",
        "orb_speed": 3.0,
        "orb_pulse_amp": 3.0,
        "wave_active": True,
    },

    "EXECUTING": {
        "orb_colors": [
            QColor(255, 150, 0),
            QColor(255, 200, 40),
            QColor(200, 100, 0),
        ],
        "glow": QColor(255, 160, 0, 75),
        "accent": QColor(255, 210, 80),
        "badge_bg": "rgba(255, 150, 0, 0.2)",
        "badge_border": "rgba(255, 200, 60, 0.8)",
        "badge_text": "#ffd570",
        "tag": "EXECUTING",
        "orb_speed": 3.8,
        "orb_pulse_amp": 4.0,
        "wave_active": True,
    },

    "SUCCESS": {
        "orb_colors": [
            QColor(0, 230, 120),
            QColor(0, 200, 180),
            QColor(0, 120, 80),
        ],
        "glow": QColor(0, 230, 120, 70),
        "accent": QColor(80, 255, 180),
        "badge_bg": "rgba(0, 230, 120, 0.2)",
        "badge_border": "rgba(80, 255, 180, 0.8)",
        "badge_text": "#75ffbb",
        "tag": "DONE",
        "orb_speed": 1.0,
        "orb_pulse_amp": 1.5,
        "wave_active": False,
    },

    "ERROR": {
        "orb_colors": [
            QColor(255, 50, 80),
            QColor(255, 100, 120),
            QColor(180, 20, 50),
        ],
        "glow": QColor(255, 50, 80, 80),
        "accent": QColor(255, 120, 140),
        "badge_bg": "rgba(255, 50, 80, 0.2)",
        "badge_border": "rgba(255, 120, 140, 0.8)",
        "badge_text": "#ff8899",
        "tag": "ERROR",
        "orb_speed": 5.0,
        "orb_pulse_amp": 6.0,
        "wave_active": True,
    },
}


def _lerp_color(
    c1: QColor,
    c2: QColor,
    t: float,
) -> QColor:
    """Linearly interpolate between two QColors."""
    t = max(0.0, min(1.0, t))

    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


class JarvisHUD(QWidget):
    """
    Premium JARVIS HUD.

    Layout:

      ┌──────────────────────────────────────────────────┐
      │  [ORB]       JARVIS // AI ASSISTANT     [BADGE] │
      │              Current status / message            │
      │              ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓                  │
      │              SYS // CPU / RAM / F8               │
      └──────────────────────────────────────────────────┘
    """

    WIDTH = 460
    HEIGHT = 200

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        # Bottom-right positioning.
        screen = self.screen().availableGeometry()

        self.move(
            screen.width() - self.WIDTH - 24,
            screen.height() - self.HEIGHT - 24,
        )

        # -------------------------------------------------------------------
        # State
        # -------------------------------------------------------------------

        self.state = "IDLE"
        self.message = "Say 'Hey Jarvis' or press F8"

        # Animation.
        self.phase = 0.0
        self.pulse = 0.0
        self.orb_scale = 1.0
        self.orb_target = 1.0

        # Color transition.
        self.color_t = 1.0
        self._prev_theme = STATE_THEME["IDLE"]
        self._cur_theme = STATE_THEME["IDLE"]

        # Waveform.
        self.bars = [0.08] * 18

        # Telemetry.
        self.cpu_val = 0
        self.ram_val = 0

        # Dragging.
        self._drag_pos = QPoint()

        self._init_labels()

        # -------------------------------------------------------------------
        # Animation timer
        # -------------------------------------------------------------------

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(16)  # ~60 FPS

        # -------------------------------------------------------------------
        # Telemetry timer
        # -------------------------------------------------------------------

        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.timeout.connect(
            self._update_telemetry
        )
        self._telemetry_timer.start(1500)

        self._update_telemetry()

        # -------------------------------------------------------------------
        # Event bus
        # -------------------------------------------------------------------

        event_bus.state_changed.connect(
            self._on_state_changed
        )

        self.show()

    # -----------------------------------------------------------------------
    # Labels
    # -----------------------------------------------------------------------

    def _init_labels(self):
        text_x = 130

        self.title_label = QLabel(
            "JARVIS // AI ASSISTANT",
            self,
        )

        self.title_label.setGeometry(
            text_x,
            16,
            210,
            18,
        )

        self.title_label.setStyleSheet(
            "color: rgba(140, 200, 255, 200); "
            "font-size: 10px; "
            "font-weight: 700; "
            "font-family: 'Segoe UI', 'Arial'; "
            "letter-spacing: 2.5px;"
        )

        self.badge_label = QLabel(
            "STANDBY",
            self,
        )

        self.badge_label.setGeometry(
            346,
            13,
            100,
            22,
        )

        self.badge_label.setAlignment(
            Qt.AlignCenter
        )

        self._apply_badge_style(
            self._cur_theme
        )

        self.status_label = QLabel(
            self.message,
            self,
        )

        self.status_label.setGeometry(
            text_x,
            42,
            318,
            68,
        )

        self.status_label.setWordWrap(True)

        self.status_label.setAlignment(
            Qt.AlignLeft | Qt.AlignTop
        )

        self.status_label.setStyleSheet(
            "color: #ddf0ff; "
            "font-size: 12px; "
            "font-family: 'Segoe UI', 'Arial'; "
            "font-weight: 500;"
        )

        self.telemetry_label = QLabel(
            "CPU: 0%  •  RAM: 0%",
            self,
        )

        self.telemetry_label.setGeometry(
            text_x,
            175,
            318,
            16,
        )

        self.telemetry_label.setStyleSheet(
            "color: rgba(100, 160, 210, 160); "
            "font-size: 9px; "
            "font-weight: 600; "
            "font-family: 'Consolas', 'Segoe UI', monospace; "
            "letter-spacing: 1px;"
        )

    def _apply_badge_style(self, theme: dict):
        self.badge_label.setText(
            theme["tag"]
        )

        self.badge_label.setStyleSheet(
            f"background-color: {theme['badge_bg']}; "
            f"border: 1px solid {theme['badge_border']}; "
            f"color: {theme['badge_text']}; "
            "border-radius: 10px; "
            "font-size: 8px; "
            "font-weight: 700; "
            "letter-spacing: 1.5px;"
        )

    # -----------------------------------------------------------------------
    # Event handlers
    # -----------------------------------------------------------------------

    def _on_state_changed(
        self,
        state: str,
        message: str,
    ):
        new_state = (
            state
            if state in STATE_THEME
            else "IDLE"
        )

        new_theme = STATE_THEME[new_state]

        if new_state != self.state:
            self._prev_theme = self._cur_theme
            self._cur_theme = new_theme
            self.color_t = 0.0

        self.state = new_state
        self.message = message or new_state

        self.status_label.setText(
            self.message
        )

        self._apply_badge_style(
            self._cur_theme
        )

        # Orb response to state.
        if new_state in ("WAKE", "LISTENING"):
            self.orb_target = 1.15

        elif new_state in ("THINKING", "EXECUTING"):
            self.orb_target = 1.08

        elif new_state == "SUCCESS":
            self.orb_target = 1.20

        elif new_state == "ERROR":
            self.orb_target = 0.85

        else:
            self.orb_target = 1.0

    def _update_telemetry(self):
        try:
            self.cpu_val = int(
                psutil.cpu_percent()
            )

            self.ram_val = int(
                psutil.virtual_memory().percent
            )

            self.telemetry_label.setText(
                f"CPU: {self.cpu_val}%  •  "
                f"RAM: {self.ram_val}%  •  "
                "Press [F8] to activate"
            )

        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Animation
    # -----------------------------------------------------------------------

    def _tick(self):
        theme = self._cur_theme

        speed = theme["orb_speed"]

        self.phase += speed * 0.04

        self.pulse = (
            theme["orb_pulse_amp"]
            * math.sin(self.phase * 2.1)
        )

        # Smooth color transition.
        if self.color_t < 1.0:
            self.color_t = min(
                1.0,
                self.color_t + 0.06,
            )

        # Smooth orb scale.
        diff = (
            self.orb_target
            - self.orb_scale
        )

        self.orb_scale += diff * 0.12

        # Gradually return to normal scale.
        self.orb_target += (
            1.0 - self.orb_target
        ) * 0.03

        # Waveform.
        for i in range(len(self.bars)):

            if theme["wave_active"]:
                target = (
                    0.2
                    + 0.8
                    * abs(
                        math.sin(
                            self.phase * 1.3
                            + i * 0.55
                        )
                    )
                )

            else:
                target = (
                    0.06
                    + 0.04
                    * abs(
                        math.sin(
                            self.phase * 0.5
                            + i * 0.3
                        )
                    )
                )

            self.bars[i] += (
                target - self.bars[i]
            ) * 0.22

        self.update()

    # -----------------------------------------------------------------------
    # Painting
    # -----------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        painter.setRenderHint(
            QPainter.SmoothPixmapTransform
        )

        w = self.WIDTH
        h = self.HEIGHT

        theme = self._cur_theme

        # -------------------------------------------------------------------
        # Interpolated colors
        # -------------------------------------------------------------------

        accent = _lerp_color(
            self._prev_theme["accent"],
            theme["accent"],
            self.color_t,
        )

        glow_color = _lerp_color(
            self._prev_theme["glow"],
            theme["glow"],
            self.color_t,
        )

        # -------------------------------------------------------------------
        # Ambient outer glow
        # -------------------------------------------------------------------

        outer_glow = QRadialGradient(
            w * 0.25,
            h * 0.5,
            h * 0.8,
        )

        outer_glow.setColorAt(
            0,
            QColor(
                glow_color.red(),
                glow_color.green(),
                glow_color.blue(),
                30,
            ),
        )

        outer_glow.setColorAt(
            1,
            QColor(0, 0, 0, 0),
        )

        painter.setBrush(
            outer_glow
        )

        painter.setPen(
            Qt.NoPen
        )

        painter.drawEllipse(
            QRectF(
                -20,
                -20,
                w + 40,
                h + 40,
            )
        )

        # -------------------------------------------------------------------
        # Glassmorphic card
        # -------------------------------------------------------------------

        card = QPainterPath()

        card.addRoundedRect(
            QRectF(
                6,
                6,
                w - 12,
                h - 12,
            ),
            20,
            20,
        )

        bg_grad = QLinearGradient(
            0,
            0,
            0,
            h,
        )

        bg_grad.setColorAt(
            0,
            QColor(10, 16, 30, 238),
        )

        bg_grad.setColorAt(
            0.5,
            QColor(8, 12, 22, 242),
        )

        bg_grad.setColorAt(
            1,
            QColor(5, 8, 18, 248),
        )

        painter.fillPath(
            card,
            bg_grad,
        )

        # Inner highlight.
        inner_glow = QLinearGradient(
            0,
            0,
            0,
            h * 0.4,
        )

        inner_glow.setColorAt(
            0,
            QColor(255, 255, 255, 12),
        )

        inner_glow.setColorAt(
            1,
            QColor(0, 0, 0, 0),
        )

        painter.fillPath(
            card,
            inner_glow,
        )

        # Neon border.
        border_pen = QPen(
            QColor(
                accent.red(),
                accent.green(),
                accent.blue(),
                100,
            ),
            1.5,
        )

        painter.setPen(
            border_pen
        )

        painter.setBrush(
            Qt.NoBrush
        )

        painter.drawPath(
            card
        )

        # Top glint.
        painter.setPen(
            QPen(
                QColor(255, 255, 255, 35),
                1.0,
            )
        )

        painter.drawLine(
            26,
            8,
            w - 26,
            8,
        )

        # -------------------------------------------------------------------
        # JARVIS orb
        # -------------------------------------------------------------------

        cx = 65
        cy = 100

        orb_r = int(
            42 * self.orb_scale
            + self.pulse * 0.6
        )

        # Ambient halo.
        halo_r = (
            orb_r
            + 22
            + abs(self.pulse) * 0.8
        )

        halo = QRadialGradient(
            cx,
            cy,
            halo_r,
        )

        halo.setColorAt(
            0,
            QColor(
                glow_color.red(),
                glow_color.green(),
                glow_color.blue(),
                60,
            ),
        )

        halo.setColorAt(
            0.5,
            QColor(
                glow_color.red(),
                glow_color.green(),
                glow_color.blue(),
                20,
            ),
        )

        halo.setColorAt(
            1,
            QColor(0, 0, 0, 0),
        )

        painter.setBrush(
            halo
        )

        painter.setPen(
            Qt.NoPen
        )

        painter.drawEllipse(
            QRectF(
                cx - halo_r,
                cy - halo_r,
                halo_r * 2,
                halo_r * 2,
            )
        )

        # -------------------------------------------------------------------
        # Rotating outer ring
        # -------------------------------------------------------------------

        painter.save()

        painter.translate(
            cx,
            cy,
        )

        painter.rotate(
            self.phase * 25
        )

        ring_pen = QPen(
            QColor(
                accent.red(),
                accent.green(),
                accent.blue(),
                120,
            ),
            1.5,
        )

        painter.setPen(
            ring_pen
        )

        painter.setBrush(
            Qt.NoBrush
        )

        ring_r = orb_r + 10

        for seg in range(6):
            start_angle = (
                seg * 60 * 16
            )

            painter.drawArc(
                -ring_r,
                -ring_r,
                ring_r * 2,
                ring_r * 2,
                start_angle,
                40 * 16,
            )

        painter.restore()

        # -------------------------------------------------------------------
        # Counter-rotating inner ring
        # -------------------------------------------------------------------

        painter.save()

        painter.translate(
            cx,
            cy,
        )

        painter.rotate(
            -self.phase * 18
        )

        ring2_pen = QPen(
            QColor(
                accent.red(),
                accent.green(),
                accent.blue(),
                80,
            ),
            1.0,
        )

        painter.setPen(
            ring2_pen
        )

        ring2_r = orb_r + 4

        for seg in range(4):
            start_angle = (
                seg * 90 * 16
            )

            painter.drawArc(
                -ring2_r,
                -ring2_r,
                ring2_r * 2,
                ring2_r * 2,
                start_angle,
                55 * 16,
            )

        painter.restore()

        # -------------------------------------------------------------------
        # Orb body
        # -------------------------------------------------------------------

        orb_grad = QRadialGradient(
            cx - orb_r * 0.25,
            cy - orb_r * 0.3,
            orb_r * 1.4,
        )

        prev_colors = self._prev_theme[
            "orb_colors"
        ]

        cur_colors = theme[
            "orb_colors"
        ]

        t = self.color_t

        c0 = _lerp_color(
            prev_colors[0],
            cur_colors[0],
            t,
        )

        c1 = _lerp_color(
            prev_colors[1],
            cur_colors[1],
            t,
        )

        c2 = _lerp_color(
            prev_colors[2],
            cur_colors[2],
            t,
        )

        orb_grad.setColorAt(
            0,
            QColor(255, 255, 255, 200),
        )

        orb_grad.setColorAt(
            0.15,
            c0.lighter(140),
        )

        orb_grad.setColorAt(
            0.45,
            c0,
        )

        orb_grad.setColorAt(
            0.75,
            c1,
        )

        orb_grad.setColorAt(
            1.0,
            c2.darker(120),
        )

        painter.setBrush(
            orb_grad
        )

        painter.setPen(
            Qt.NoPen
        )

        painter.drawEllipse(
            QRectF(
                cx - orb_r,
                cy - orb_r,
                orb_r * 2,
                orb_r * 2,
            )
        )

        # -------------------------------------------------------------------
        # Specular glint
        # -------------------------------------------------------------------

        glint_path = QPainterPath()

        glint_x = (
            cx - orb_r * 0.28
        )

        glint_y = (
            cy - orb_r * 0.38
        )

        glint_path.addEllipse(
            QRectF(
                glint_x,
                glint_y,
                orb_r * 0.45,
                orb_r * 0.22,
            )
        )

        glint_grad = QRadialGradient(
            glint_x + orb_r * 0.1,
            glint_y + orb_r * 0.05,
            orb_r * 0.25,
        )

        glint_grad.setColorAt(
            0,
            QColor(255, 255, 255, 160),
        )

        glint_grad.setColorAt(
            1,
            QColor(255, 255, 255, 0),
        )

        painter.setBrush(
            glint_grad
        )

        painter.drawPath(
            glint_path
        )

        # -------------------------------------------------------------------
        # Waveform
        # -------------------------------------------------------------------

        wave_y = 148
        bar_w = 8
        gap = 3
        wave_x = 130

        painter.setPen(
            Qt.NoPen
        )

        for i, val in enumerate(
            self.bars
        ):
            bar_h = max(
                3,
                int(3 + val * 28),
            )

            x = (
                wave_x
                + i * (bar_w + gap)
            )

            y = (
                wave_y
                - bar_h // 2
            )

            bar_grad = QLinearGradient(
                x,
                y,
                x,
                y + bar_h,
            )

            bar_grad.setColorAt(
                0,
                QColor(
                    accent.red(),
                    accent.green(),
                    accent.blue(),
                    220,
                ),
            )

            bar_grad.setColorAt(
                0.5,
                QColor(
                    accent.red(),
                    accent.green(),
                    accent.blue(),
                    160,
                ),
            )

            bar_grad.setColorAt(
                1,
                QColor(
                    accent.red(),
                    accent.green(),
                    accent.blue(),
                    60,
                ),
            )

            painter.setBrush(
                bar_grad
            )

            painter.drawRoundedRect(
                QRectF(
                    x,
                    y,
                    bar_w,
                    bar_h,
                ),
                2,
                2,
            )

        # -------------------------------------------------------------------
        # Separator
        # -------------------------------------------------------------------

        sep_x = 118

        sep_grad = QLinearGradient(
            sep_x,
            20,
            sep_x,
            h - 20,
        )

        sep_grad.setColorAt(
            0,
            QColor(
                accent.red(),
                accent.green(),
                accent.blue(),
                0,
            ),
        )

        sep_grad.setColorAt(
            0.3,
            QColor(
                accent.red(),
                accent.green(),
                accent.blue(),
                80,
            ),
        )

        sep_grad.setColorAt(
            0.7,
            QColor(
                accent.red(),
                accent.green(),
                accent.blue(),
                80,
            ),
        )

        sep_grad.setColorAt(
            1,
            QColor(
                accent.red(),
                accent.green(),
                accent.blue(),
                0,
            ),
        )

        painter.setPen(
            QPen(
                sep_grad,
                1.0,
            )
        )

        painter.drawLine(
            sep_x,
            18,
            sep_x,
            h - 18,
        )

    # -----------------------------------------------------------------------
    # Drag support
    # -----------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

            event.accept()

    def mouseMoveEvent(self, event):
        if (
            event.buttons() == Qt.LeftButton
            and not self._drag_pos.isNull()
        ):
            self.move(
                event.globalPosition().toPoint()
                - self._drag_pos
            )

            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        """
        Double-click toggles HUD opacity.
        """
        if self.windowOpacity() < 1.0:
            self.setWindowOpacity(1.0)
        else:
            self.setWindowOpacity(0.3)

        event.accept()