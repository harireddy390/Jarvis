
import sys
import psutil

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)


class JarvisHUD(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("JARVIS HUD")

        # Frameless window
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )

        # Transparent background
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setup_ui()

        # Update system information
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_system_status)
        self.timer.start(1000)

    def setup_ui(self):

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 30, 40, 30)

        # -----------------------------
        # TITLE
        # -----------------------------

        self.title = QLabel("J A R V I S")
        self.title.setAlignment(Qt.AlignCenter)

        self.title.setFont(
            QFont("Segoe UI", 28, QFont.Bold)
        )

        self.title.setStyleSheet(
            "color: white;"
        )

        main_layout.addWidget(self.title)

        # -----------------------------
        # STATUS
        # -----------------------------

        self.status = QLabel("● SYSTEM ONLINE")
        self.status.setAlignment(Qt.AlignCenter)

        self.status.setFont(
            QFont("Segoe UI", 13)
        )

        self.status.setStyleSheet(
            "color: white;"
        )

        main_layout.addWidget(self.status)

        # -----------------------------
        # MAIN MESSAGE
        # -----------------------------

        self.message = QLabel(
            "WAITING FOR WAKE WORD"
        )

        self.message.setAlignment(Qt.AlignCenter)

        self.message.setFont(
            QFont("Segoe UI", 16, QFont.Bold)
        )

        self.message.setStyleSheet(
            """
            color: white;
            padding: 25px;
            """
        )

        main_layout.addWidget(self.message)

        # -----------------------------
        # SYSTEM INFO
        # -----------------------------

        info_layout = QHBoxLayout()

        self.cpu_label = QLabel("CPU: --%")
        self.ram_label = QLabel("RAM: --%")

        for label in [self.cpu_label, self.ram_label]:

            label.setFont(
                QFont("Segoe UI", 11)
            )

            label.setStyleSheet(
                "color: white;"
            )

            info_layout.addWidget(
                label,
                alignment=Qt.AlignCenter
            )

        main_layout.addLayout(info_layout)

        self.setLayout(main_layout)

        # -----------------------------
        # WINDOW SIZE
        # -----------------------------

        self.resize(600, 250)

    def update_system_status(self):

        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent

        self.cpu_label.setText(
            f"CPU: {cpu:.0f}%"
        )

        self.ram_label.setText(
            f"RAM: {ram:.0f}%"
        )


def main():

    app = QApplication(sys.argv)

    hud = JarvisHUD()

    hud.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

