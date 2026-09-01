from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """
    Thread-safe event bus: background threads (voice loop, tools) emit signals,
    the GUI thread (HUD) receives them safely across threads via Qt's built-in
    queued connections.
    """
    state_changed = Signal(str, str)  # (state_name, message)

    def emit_state(self, state: str, message: str = ""):
        self.state_changed.emit(state, message)


event_bus = EventBus()