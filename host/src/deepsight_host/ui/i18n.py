"""Internationalization — runtime Chinese / English switching."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


_translations: dict[str, dict[str, str]] = {
    "app.title": {"zh": "DeepSight — 自由潜水拍摄系统", "en": "DeepSight — ROV Filming System"},
    "app.safety": {"zh": "安全状态", "en": "Safety"},
    "app.ready": {"zh": "就绪", "en": "Ready"},
    "app.running": {"zh": "运行中 | %s | %s", "en": "Running | %s | %s"},
    "app.emu_stop_msg": {"zh": "紧急停止 — 所有电机已停止", "en": "EMERGENCY STOP — all motors halted"},
    "app.node_state": {"zh": "节点 %s: %s → %s", "en": "Node %s: %s → %s"},

    "tab.dashboard": {"zh": "仪表盘", "en": "Dashboard"},
    "tab.nodes": {"zh": "节点", "en": "Nodes"},
    "tab.tracking": {"zh": "追踪", "en": "Tracking"},
    "tab.controls": {"zh": "控制", "en": "Controls"},

    "video.no_video": {"zh": "无视频信号", "en": "No Video"},
    "video.resolution": {"zh": "分辨率", "en": "Resolution"},

    "safety.nominal": {"zh": "正常", "en": "NOMINAL"},
    "safety.degraded": {"zh": "降级", "en": "DEGRADED"},
    "safety.caution": {"zh": "注意", "en": "CAUTION"},
    "safety.safe": {"zh": "安全", "en": "SAFE"},
    "safety.emergency": {"zh": "紧急", "en": "EMERGENCY"},

    "node.host": {"zh": "主机", "en": "Host"},
    "node.pi": {"zh": "树莓派", "en": "Pi 5"},
    "node.pico": {"zh": "Pico", "en": "Pico"},
    "node.stm32": {"zh": "STM32", "en": "STM32"},
    "node.state_healthy": {"zh": "正常", "en": "Healthy"},
    "node.state_degraded": {"zh": "降级", "en": "Degraded"},
    "node.state_lost": {"zh": "失联", "en": "Lost"},
    "node.state_unknown": {"zh": "未知", "en": "Unknown"},

    "control.pan": {"zh": "水平", "en": "Pan"},
    "control.tilt": {"zh": "俯仰", "en": "Tilt"},
    "control.servo_manual": {"zh": "手动舵机控制", "en": "Manual Servo Control"},
    "control.winch": {"zh": "绞车控制", "en": "Winch Control"},
    "control.e_stop": {"zh": "紧急停止", "en": "EMERGENCY STOP"},
    "control.winch_up": {"zh": "收缆 ↑", "en": "Reel ↑"},
    "control.winch_stop": {"zh": "停止", "en": "STOP"},
    "control.winch_down": {"zh": "放缆 ↓", "en": "Release ↓"},

    "tracking.mode": {"zh": "追踪模式", "en": "Tracking Mode"},
    "tracking.fast": {"zh": "快速", "en": "Fast"},
    "tracking.precise": {"zh": "精确", "en": "Precise"},
    "tracking.reset": {"zh": "重置追踪器", "en": "Reset Tracker"},
    "tracking.fps": {"zh": "帧率", "en": "FPS"},
    "tracking.latency": {"zh": "延迟", "en": "Latency"},
    "tracking.target_id": {"zh": "目标ID", "en": "Target ID"},
    "tracking.confidence": {"zh": "置信度", "en": "Confidence"},
    "tracking.pan_angle": {"zh": "水平角度", "en": "Pan Angle"},
    "tracking.tilt_angle": {"zh": "俯仰角度", "en": "Tilt Angle"},

    "tracking.unavailable": {"zh": "追踪不可用 - 模型未加载", "en": "Tracking Unavailable - No Model"},
    "tracking.active": {"zh": "追踪已激活", "en": "Tracking Active"},
    "tracking.reset_done": {"zh": "追踪器已重置", "en": "Tracker reset"},

    "dashboard.imu": {"zh": "IMU", "en": "IMU"},
    "dashboard.depth": {"zh": "深度", "en": "Depth"},
    "dashboard.pressure": {"zh": "压力", "en": "Pressure"},
    "dashboard.env": {"zh": "环境", "en": "Environment"},
    "dashboard.tracking_title": {"zh": "追踪", "en": "Tracking"},
    "dashboard.winch_title": {"zh": "绞车", "en": "Winch"},
    "dashboard.target_x": {"zh": "目标 X", "en": "Target X"},
    "dashboard.target_y": {"zh": "目标 Y", "en": "Target Y"},
    "dashboard.confidence_short": {"zh": "置信度", "en": "Conf"},
    "dashboard.track_id": {"zh": "目标", "en": "Track"},
    "dashboard.winch_pos": {"zh": "缆长", "en": "Cable"},
    "dashboard.winch_speed": {"zh": "速度", "en": "Speed"},
    "dashboard.winch_state": {"zh": "状态", "en": "State"},

    "chart.title": {"zh": "深度 / 时间 (V型剖面)", "en": "Depth / Time (V‑Profile)"},

    "lang.switch": {"zh": "EN", "en": "中文"},
    "lang.label": {"zh": "语言", "en": "Lang"},
}


class I18n(QObject):
    language_changed = Signal(str)  # emits lang code

    _instance: I18n | None = None

    def __init__(self):
        super().__init__()
        self._lang = "zh"

    @classmethod
    def instance(cls) -> I18n:
        if cls._instance is None:
            cls._instance = I18n()
        return cls._instance

    @property
    def lang(self) -> str:
        return self._lang

    def toggle(self):
        self._lang = "en" if self._lang == "zh" else "zh"
        self.language_changed.emit(self._lang)

    def set_lang(self, lang: str):
        if lang in ("zh", "en"):
            self._lang = lang
            self.language_changed.emit(lang)

    def tr(self, key: str, *args) -> str:
        entry = _translations.get(key, {})
        text = entry.get(self._lang, key)
        if args:
            return text % args
        return text


def tr(key: str, *args) -> str:
    return I18n.instance().tr(key, *args)
