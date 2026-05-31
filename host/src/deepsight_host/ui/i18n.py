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
    "tab.nodes": {"zh": "节点", "en": "Nodes"},  # LEGACY
    "tab.components": {"zh": "组件", "en": "Components"},
    "tab.tracking": {"zh": "追踪", "en": "Tracking"},
    "tab.controls": {"zh": "控制", "en": "Controls"},

    "video.no_video": {"zh": "无视频信号", "en": "No Video"},
    "video.resolution": {"zh": "分辨率", "en": "Resolution"},
    "video.battery": {"zh": "电量", "en": "Bat"},
    "video.locked_overlay": {"zh": "已锁定 — 按 Start 解锁", "en": "LOCKED — Press Start to unlock"},

    "safety.nominal": {"zh": "正常", "en": "NOMINAL"},
    "safety.degraded": {"zh": "降级", "en": "DEGRADED"},
    "safety.caution": {"zh": "注意", "en": "CAUTION"},
    "safety.safe": {"zh": "安全", "en": "SAFE"},
    "safety.emergency": {"zh": "紧急", "en": "EMERGENCY"},
    "safety.locked": {"zh": "已锁定", "en": "LOCKED"},
    "safety.unlocked": {"zh": "已解锁", "en": "UNLOCKED"},

    "node.host": {"zh": "主机", "en": "Host"},  # LEGACY
    "node.pi": {"zh": "水下网关", "en": "UW Gateway"},  # LEGACY
    "node.pico": {"zh": "控制器", "en": "Controller"},  # LEGACY
    "node.stm32": {"zh": "绞车驱动", "en": "Winch Driver"},  # LEGACY
    "node.gopro": {"zh": "相机模组", "en": "Camera"},  # LEGACY
    "node.state_healthy": {"zh": "正常", "en": "Healthy"},  # LEGACY
    "node.state_degraded": {"zh": "降级", "en": "Degraded"},  # LEGACY
    "node.state_lost": {"zh": "失联", "en": "Lost"},  # LEGACY
    "node.state_unknown": {"zh": "未知", "en": "Unknown"},  # LEGACY
    "node.state_offline": {"zh": "未连接", "en": "Offline"},  # LEGACY
    "node.state_online": {"zh": "在线", "en": "Online"},  # LEGACY
    "component.host": {"zh": "主机", "en": "Host"},
    "component.pi": {"zh": "水下网关", "en": "UW Gateway"},
    "component.pico": {"zh": "控制器", "en": "Controller"},
    "component.stm32": {"zh": "绞车驱动", "en": "Winch Driver"},
    "component.gopro": {"zh": "相机模组", "en": "Camera"},
    "component.gamepad": {"zh": "手柄", "en": "Gamepad"},
    "component.state_healthy": {"zh": "正常", "en": "Healthy"},
    "component.state_degraded": {"zh": "降级", "en": "Degraded"},
    "component.state_lost": {"zh": "失联", "en": "Lost"},
    "component.state_unknown": {"zh": "未知", "en": "Unknown"},
    "component.state_offline": {"zh": "未连接", "en": "Offline"},
    "component.state_online": {"zh": "在线", "en": "Online"},
    "component.connected": {"zh": "已连接", "en": "Connected"},
    "component.disconnected": {"zh": "未连接", "en": "Disconnected"},

    "control.pan": {"zh": "水平", "en": "Pan"},  # LEGACY
    "control.tilt": {"zh": "俯仰", "en": "Tilt"},  # LEGACY
    "control.servo_manual": {"zh": "手动舵机控制", "en": "Manual Servo Control"},  # LEGACY
    "control.winch": {"zh": "绞车控制", "en": "Winch Control"},  # LEGACY
    "gimbal.title": {"zh": "云台偏转", "en": "Gimbal Deflection"},
    "gimbal.pan": {"zh": "水平", "en": "Pan"},
    "gimbal.tilt": {"zh": "俯仰", "en": "Tilt"},
    "motion.title": {"zh": "运动状态", "en": "Motion State"},
    "motion.descending": {"zh": "下降", "en": "Descending"},
    "motion.hovering": {"zh": "悬停", "en": "Hovering"},
    "motion.ascending": {"zh": "上升", "en": "Ascending"},
    "motion.speed": {"zh": "速度", "en": "Speed"},
    "motion.depth": {"zh": "深度", "en": "Depth"},
    "motion.mock_hint": {"zh": "(模拟数据)", "en": "(Mock Data)"},
    "status.gimbal_mode": {"zh": "追踪模式", "en": "Tracking"},
    "status.mode_auto": {"zh": "自动", "en": "AUTO"},
    "status.mode_manual": {"zh": "手动", "en": "MANUAL"},
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
    "tracking.target_lost": {"zh": "目标丢失", "en": "TARGET LOST"},
    "tracking.no_tracking": {"zh": "追踪不可用", "en": "TRACKING UNAVAILABLE"},
    "tracking.active": {"zh": "追踪已激活", "en": "Tracking Active"},
    "tracking.reset_done": {"zh": "追踪器已重置", "en": "Tracker reset"},

    "dashboard.imu": {"zh": "IMU", "en": "IMU"},  # LEGACY
    "dashboard.gyro": {"zh": "陀螺仪", "en": "Gyroscope"},
    "dashboard.depth": {"zh": "深度", "en": "Depth"},
    "dashboard.pressure": {"zh": "压力", "en": "Pressure"},
    "dashboard.env": {"zh": "环境", "en": "Environment"},
    "dashboard.light": {"zh": "光照", "en": "Light"},
    "dashboard.light_lux": {"zh": "照度", "en": "Lux"},
    "dashboard.ebay": {"zh": "电子仓气压", "en": "E-Bay Press"},
    "dashboard.ebay_pressure": {"zh": "压力", "en": "Press"},
    "dashboard.ebay_temp": {"zh": "温度", "en": "Temp"},
    "dashboard.ebay_humidity": {"zh": "湿度", "en": "Hum"},
    "dashboard.cambay": {"zh": "摄像仓气压", "en": "Cam Bay Press"},
    "dashboard.cambay_pressure": {"zh": "压力", "en": "Press"},
    "dashboard.cambay_temp": {"zh": "温度", "en": "Temp"},
    "dashboard.cambay_humidity": {"zh": "湿度", "en": "Hum"},
    "dashboard.tracking_title": {"zh": "追踪", "en": "Tracking"},
    "dashboard.winch_title": {"zh": "绞车", "en": "Winch"},
    "dashboard.target_x": {"zh": "目标 X", "en": "Target X"},
    "dashboard.target_y": {"zh": "目标 Y", "en": "Target Y"},
    "dashboard.confidence_short": {"zh": "置信度", "en": "Conf"},
    "dashboard.track_id": {"zh": "目标", "en": "Track"},
    # Short metric labels — shown inline as "Label: valueUnit"
    "metric.yaw": {"zh": "偏航", "en": "Yaw"},
    "metric.pitch": {"zh": "俯仰", "en": "Pitch"},
    "metric.roll": {"zh": "横滚", "en": "Roll"},
    "metric.depth": {"zh": "深度", "en": "Depth"},
    "metric.pressure": {"zh": "压力", "en": "Press"},
    "metric.water_temp": {"zh": "水温", "en": "Water"},
    "metric.lux": {"zh": "照度", "en": "Lux"},
    "metric.ebay_pressure": {"zh": "压力", "en": "Press"},
    "metric.ebay_temp": {"zh": "温度", "en": "Temp"},
    "metric.ebay_humidity": {"zh": "湿度", "en": "Hum"},
    "metric.cambay_pressure": {"zh": "压力", "en": "Press"},
    "metric.cambay_temp": {"zh": "温度", "en": "Temp"},
    "metric.cambay_humidity": {"zh": "湿度", "en": "Hum"},
    "metric.env_temp": {"zh": "温度", "en": "Temp"},
    "metric.humidity": {"zh": "湿度", "en": "Hum"},
    "metric.env_pressure": {"zh": "气压", "en": "Baro"},
    "metric.confidence": {"zh": "置信", "en": "Conf"},
    "metric.target_x": {"zh": "X", "en": "X"},
    "metric.target_y": {"zh": "Y", "en": "Y"},
    "dashboard.winch_pos": {"zh": "缆长", "en": "Cable"},
    "dashboard.winch_speed": {"zh": "速度", "en": "Speed"},
    "dashboard.winch_state": {"zh": "状态", "en": "State"},

    "chart.title": {"zh": "深度 / 时间 (V型剖面)", "en": "Depth / Time (V‑Profile)"},

    "lang.switch": {"zh": "EN", "en": "中文"},
    "lang.label": {"zh": "语言", "en": "Lang"},

    # ── Menu ──
    "menu.settings": {"zh": "设置(&S)", "en": "&Settings"},
    "menu.settings_action": {"zh": "系统设置...", "en": "System Settings..."},
    "menu.gopro_control": {"zh": "相机控制...", "en": "Camera Control..."},
    "menu.gopro_presets": {"zh": "相机预设...", "en": "Camera Presets..."},
    "menu.album": {"zh": "相册(&A)", "en": "&Album"},
    "menu.album_media": {"zh": "录制素材...", "en": "Recorded Media..."},
    "menu.about": {"zh": "关于(&A)", "en": "&About"},

    # ── Media browser ──
    "media.title": {"zh": "录制素材", "en": "Recorded Media"},
    "media.refresh": {"zh": "刷新", "en": "Refresh"},
    "media.select_all": {"zh": "全选", "en": "Select All"},
    "media.deselect_all": {"zh": "取消全选", "en": "Deselect All"},
    "media.download": {"zh": "下载", "en": "Download"},
    "media.delete": {"zh": "删除", "en": "Delete"},
    "media.close": {"zh": "关闭", "en": "Close"},
    "media.filename": {"zh": "文件名", "en": "Filename"},
    "media.size": {"zh": "大小", "en": "Size"},
    "media.date": {"zh": "日期", "en": "Date"},
    "media.loading": {"zh": "正在加载...", "en": "Loading..."},
    "media.no_files": {"zh": "SD 卡上没有视频文件", "en": "No video files on SD card"},
    "media.offline": {"zh": "相机离线", "en": "Camera offline"},
    "media.selected_count": {"zh": "已选 {n} / 共 {total} 个文件", "en": "{n} / {total} selected"},
    "media.total_size": {"zh": "总计: {size}", "en": "Total: {size}"},
    "media.downloading": {"zh": "下载中...", "en": "Downloading..."},
    "media.download_ok": {"zh": "下载完成: {name}", "en": "Downloaded: {name}"},
    "media.download_fail": {"zh": "下载失败: {name}", "en": "Download failed: {name}"},
    "media.delete_confirm": {"zh": "确认删除 {n} 个文件？此操作不可撤销。", "en": "Delete {n} files? This cannot be undone."},
    "media.delete_ok": {"zh": "已删除: {name}", "en": "Deleted: {name}"},
    "media.delete_fail": {"zh": "删除失败: {name}", "en": "Delete failed: {name}"},
    "media.deleting": {"zh": "删除中...", "en": "Deleting..."},

    # ── Settings dialog ──
    "settings.title": {"zh": "系统设置", "en": "System Settings"},
    "settings.tab_network": {"zh": "网络", "en": "Network"},
    "settings.tab_tracking": {"zh": "追踪", "en": "Tracking"},
    "settings.tab_control": {"zh": "控制", "en": "Control"},
    "settings.tab_safety": {"zh": "安全", "en": "Safety"},
    "settings.tab_gimbal": {"zh": "云台", "en": "Gimbal"},
    "settings.tab_plate": {"zh": "舵板", "en": "Plate"},
    "settings.tab_logging": {"zh": "日志", "en": "Logging"},
    "settings.pi_ip": {"zh": "水下节点 IP", "en": "UW Node IP"},
    "settings.udp_port": {"zh": "UDP 端口", "en": "UDP Port"},
    "settings.ws_port": {"zh": "WebSocket 端口", "en": "WS Port"},
    "settings.video_port": {"zh": "视频流端口", "en": "Video Stream Port"},
    "settings.restart_hint": {"zh": "修改网络设置后需重启生效", "en": "Network changes require restart"},
    "settings.tracking_mode": {"zh": "追踪模式", "en": "Tracking Mode"},
    "settings.confidence": {"zh": "置信度阈值", "en": "Confidence Threshold"},
    "settings.iou": {"zh": "IOU 阈值", "en": "IOU Threshold"},
    "settings.max_servo_speed": {"zh": "最大舵机速度", "en": "Max Servo Speed"},
    "settings.dead_zone": {"zh": "死区", "en": "Dead Zone"},
    "settings.dead_zone_tip": {"zh": "画面中心死区比例", "en": "Fraction of frame center dead zone"},
    "settings.pos_deadband": {"zh": "位置死区", "en": "Position Deadband"},
    "settings.pos_deadband_tip": {"zh": "过滤 YOLO 逐帧抖动，不影响跟手速度，单位画面比例", "en": "Filters YOLO frame jitter, unit frame fraction. Does not affect follow speed."},
    "settings.out_ema": {"zh": "输出平滑", "en": "Output Smoothing"},
    "settings.out_ema_tip": {"zh": "舵机指令平滑度，越小越平滑但响应慢，1.0=关闭", "en": "Servo command smoothness. Lower = smoother but slower response. 1.0 = off."},
    "settings.neutral_angle": {"zh": "中立角度", "en": "Neutral Angle"},
    "settings.gimbal_yaw_max": {"zh": "航向最大偏转角", "en": "Yaw Max Angle"},
    "settings.gimbal_pitch_max": {"zh": "俯仰最大偏转角", "en": "Pitch Max Angle"},
    "settings.plate_max": {"zh": "舵板最大偏转角", "en": "Plate Max Angle"},
    "settings.lost_hold": {"zh": "丢失保持时间", "en": "Lost Hold Time"},
    "settings.lost_neutral": {"zh": "丢失回中时间", "en": "Lost Neutral Time"},
    "settings.log_level": {"zh": "日志级别", "en": "Log Level"},
    "settings.telemetry_record": {"zh": "遥测录制", "en": "Telemetry Record"},
    "settings.off": {"zh": "关闭", "en": "Off"},
    "settings.on": {"zh": "开启", "en": "On"},
    "settings.reset_defaults": {"zh": "恢复默认", "en": "Reset Defaults"},
    "settings.ok": {"zh": "确定", "en": "OK"},
    "settings.cancel": {"zh": "取消", "en": "Cancel"},
    "settings.restart_title": {"zh": "需要重启", "en": "Restart Required"},
    "settings.restart_message": {"zh": "网络设置已修改，重启后生效。", "en": "Network settings changed. Restart to apply."},

    # ── GoPro standalone dialog ──
    "gopro.title": {"zh": "相机控制", "en": "Camera Control"},
    "gopro.offline": {"zh": "离线", "en": "Offline"},
    "gopro.close": {"zh": "关闭", "en": "Close"},
    "gopro.group_mode": {"zh": "拍摄模式", "en": "Mode"},
    "gopro.group_video": {"zh": "视频设置", "en": "Video"},
    "gopro.group_quality": {"zh": "画质设置", "en": "Quality"},
    "gopro.group_lens": {"zh": "镜头与防抖", "en": "Lens & Stabilization"},
    "gopro.group_control": {"zh": "控制模式", "en": "Control"},
    "gopro.group_photo": {"zh": "照片设置", "en": "Photo"},
    "gopro.group_timelapse": {"zh": "延时设置", "en": "Timelapse"},
    "gopro.group_duration": {"zh": "录制时长", "en": "Duration"},
    "gopro.group_display": {"zh": "显示与音频", "en": "Display & Audio"},
    "gopro.group_system": {"zh": "系统设置", "en": "System"},
    "gopro.group_presets": {"zh": "视频预设", "en": "Presets"},
    "gopro.group_webcam": {"zh": "摄像头模式", "en": "Webcam"},
    "gopro.setting": {"zh": "正在设置 {name} 为 {val}...", "en": "Setting {name} to {val}..."},
    "gopro.set_ok": {"zh": "{name} 已设置为 {val}  ✓", "en": "{name} set to {val}  ✓"},
    "gopro.set_fail": {"zh": "{name} 设置失败  ✗", "en": "{name} failed  ✗"},
    "gopro.sent_mode": {"zh": "切换模式: {mode}", "en": "Mode: {mode}"},
    "gopro.mode_video": {"zh": "视频", "en": "Video"},
    "gopro.mode_photo": {"zh": "照片", "en": "Photo"},
    "gopro.mode_timelapse": {"zh": "延时", "en": "Timelapse"},
    "gopro.refreshing": {"zh": "正在查询相机设置...", "en": "Refreshing camera settings..."},
    "gopro.refreshed": {"zh": "相机设置已更新", "en": "Camera settings updated"},
    "gopro.tab_video": {"zh": "视频", "en": "Video"},
    "gopro.tab_photo": {"zh": "照片", "en": "Photo"},
    "gopro.tab_timelapse": {"zh": "延时", "en": "Time Lapse"},
    "gopro.tab_other": {"zh": "系统", "en": "System"},
    "settings.gopro_mode": {"zh": "模式", "en": "Mode"},
    "settings.gopro_resolution": {"zh": "分辨率与宽高比", "en": "Resolution & Aspect"},
    "settings.gopro_fps": {"zh": "帧率", "en": "FPS"},
    "settings.gopro_lens": {"zh": "镜头视角", "en": "Lens / FOV"},
    "settings.gopro_lens_wide": {"zh": "宽 (Wide)", "en": "Wide"},
    "settings.gopro_lens_narrow": {"zh": "窄 (Narrow)", "en": "Narrow"},
    "settings.gopro_lens_superview": {"zh": "超广角 (SuperView)", "en": "SuperView"},
    "settings.gopro_lens_linear": {"zh": "线性矫正 (Linear)", "en": "Linear"},
    "settings.gopro_lens_linear_horizon_lvl": {"zh": "线性+水平锁定 (Linear+HL)", "en": "Linear + Horizon Lock"},
    "settings.gopro_lens_hyperview": {"zh": "超视角 (HyperView)", "en": "HyperView"},
    "settings.gopro_lens_linear_horizon_lock": {"zh": "线性+完全水平锁定", "en": "Linear + Horizon Lock"},
    "settings.gopro_lens_ultra_superview": {"zh": "Ultra 超广角", "en": "Ultra SuperView"},
    "settings.gopro_lens_ultra_wide": {"zh": "Ultra 宽", "en": "Ultra Wide"},
    "settings.gopro_lens_ultra_linear": {"zh": "Ultra 线性", "en": "Ultra Linear"},
    "settings.gopro_lens_ultra_hyperview": {"zh": "Ultra 超视角", "en": "Ultra HyperView"},
    "settings.gopro_hypersmooth": {"zh": "防抖", "en": "Hypersmooth"},
    "settings.gopro_hs_off": {"zh": "关闭", "en": "Off"},
    "settings.gopro_hs_low": {"zh": "低", "en": "Low"},
    "settings.gopro_hs_auto_boost": {"zh": "自动增强", "en": "Auto Boost"},
    "settings.gopro_max_lens_mod": {"zh": "Max Lens Mod", "en": "Max Lens Mod"},
    "settings.gopro_mlm_none": {"zh": "标准镜头", "en": "Standard Lens"},
    "settings.gopro_mlm_max2": {"zh": "Max Lens 2.0", "en": "Max Lens 2.0"},
    "settings.gopro_mlm_max2_5": {"zh": "Max Lens 2.5", "en": "Max Lens 2.5"},
    "settings.gopro_mlm_macro": {"zh": "微距", "en": "Macro"},
    "settings.gopro_mlm_anamorphic": {"zh": "变形镜头", "en": "Anamorphic"},
    "settings.gopro_mlm_nd4": {"zh": "ND 4", "en": "ND 4"},
    "settings.gopro_mlm_nd8": {"zh": "ND 8", "en": "ND 8"},
    "settings.gopro_mlm_nd16": {"zh": "ND 16", "en": "ND 16"},
    "settings.gopro_mlm_nd32": {"zh": "ND 32", "en": "ND 32"},
    "settings.gopro_mlm_auto": {"zh": "自动检测", "en": "Auto Detect"},
    "settings.gopro_anti_flicker": {"zh": "抗频闪", "en": "Anti-Flicker"},
    "settings.gopro_flicker_ntsc": {"zh": "60 Hz (NTSC)", "en": "60 Hz (NTSC)"},
    "settings.gopro_flicker_pal": {"zh": "50 Hz (PAL)", "en": "50 Hz (PAL)"},
    "settings.gopro_bitrate": {"zh": "码率", "en": "Bitrate"},
    "settings.gopro_bitrate_standard": {"zh": "标准", "en": "Standard"},
    "settings.gopro_bitrate_high": {"zh": "高", "en": "High"},
    "settings.gopro_bit_depth": {"zh": "位深", "en": "Bit Depth"},
    "settings.gopro_bitdepth_8bit": {"zh": "8-bit", "en": "8-bit"},
    "settings.gopro_bitdepth_10bit": {"zh": "10-bit", "en": "10-bit"},
    "settings.gopro_profiles": {"zh": "色彩", "en": "Color"},
    "settings.gopro_profile_standard": {"zh": "标准", "en": "Standard"},
    "settings.gopro_profile_hdr": {"zh": "HDR", "en": "HDR"},
    "settings.gopro_profile_log": {"zh": "Log", "en": "Log"},
    "settings.gopro_profile_hlg_hdr": {"zh": "HLG HDR", "en": "HLG HDR"},
    "settings.gopro_control_mode": {"zh": "控制模式", "en": "Control Mode"},
    "settings.gopro_control_easy": {"zh": "简易", "en": "Easy"},
    "settings.gopro_control_pro": {"zh": "专业", "en": "Pro"},
    "settings.gopro_sys_video_mode": {"zh": "系统视频质量", "en": "System Video Quality"},
    "settings.gopro_quality_highest": {"zh": "最高", "en": "Highest"},
    "settings.gopro_quality_standard": {"zh": "标准", "en": "Standard"},
    "settings.gopro_quality_basic": {"zh": "基础", "en": "Basic"},
    "settings.gopro_auto_off": {"zh": "自动关机", "en": "Auto Off"},
    "settings.gopro_auto_off_never": {"zh": "从不", "en": "Never"},
    "settings.gopro_auto_off_1min": {"zh": "1 分钟", "en": "1 min"},
    "settings.gopro_auto_off_5min": {"zh": "5 分钟", "en": "5 min"},
    "settings.gopro_auto_off_15min": {"zh": "15 分钟", "en": "15 min"},
    "settings.gopro_auto_off_30min": {"zh": "30 分钟", "en": "30 min"},
    "settings.gopro_media_format": {"zh": "媒体格式", "en": "Media Format"},
    "settings.gopro_media_timelapse_video": {"zh": "延时视频", "en": "Time Lapse Video"},
    "settings.gopro_media_timelapse_photo": {"zh": "延时照片", "en": "Time Lapse Photo"},
    "settings.gopro_media_night_lapse_photo": {"zh": "夜景延时照片", "en": "Night Lapse Photo"},
    "settings.gopro_media_night_lapse_video": {"zh": "夜景延时视频", "en": "Night Lapse Video"},
    "settings.gopro_aspect_ratio": {"zh": "宽高比", "en": "Aspect Ratio"},
    "settings.gopro_refresh": {"zh": "查询当前设置", "en": "Refresh Settings"},

    # ── GoPro Presets dialog ──
    "presets.title": {"zh": "相机预设", "en": "Camera Presets"},
    "presets.video_group": {"zh": "视频预设", "en": "Video Presets"},
    "presets.photo_group": {"zh": "照片预设", "en": "Photo Presets"},
    "presets.timelapse_group": {"zh": "延时预设", "en": "Time Lapse Presets"},
    "presets.loading": {"zh": "正在加载预设...", "en": "Loading presets..."},
    "presets.active": {"zh": "当前", "en": "Active"},
    "presets.switching": {"zh": "正在切换...", "en": "Switching..."},
    "presets.close": {"zh": "关闭", "en": "Close"},
    "presets.refresh": {"zh": "刷新", "en": "Refresh"},
    "presets.switch_hint": {"zh": "点击预设以切换", "en": "Click a preset to switch"},

    # ── GoPro setting labels (OpenGoPro HERO13 HTTP API) ──
    "gopro.setting.2": {"zh": "视频分辨率", "en": "Video Resolution"},
    "gopro.setting.3": {"zh": "帧率", "en": "Frames Per Second"},
    "gopro.setting.5": {"zh": "视频延时速率", "en": "Video Timelapse Rate"},
    "gopro.setting.30": {"zh": "照片延时速率", "en": "Photo Timelapse Rate"},
    "gopro.setting.32": {"zh": "夜景延时速率", "en": "Nightlapse Rate"},
    "gopro.setting.43": {"zh": "摄像头镜头", "en": "Webcam Digital Lenses"},
    "gopro.setting.59": {"zh": "自动关机", "en": "Auto Power Down"},
    "gopro.setting.83": {"zh": "GPS", "en": "GPS"},
    "gopro.setting.88": {"zh": "屏幕亮度", "en": "LCD Brightness"},
    "gopro.setting.91": {"zh": "指示灯", "en": "LED"},
    "gopro.setting.108": {"zh": "视频宽高比", "en": "Video Aspect Ratio"},
    "gopro.setting.121": {"zh": "视频镜头", "en": "Video Lens"},
    "gopro.setting.122": {"zh": "照片镜头", "en": "Photo Lens"},
    "gopro.setting.123": {"zh": "延时镜头", "en": "Time Lapse Digital Lenses"},
    "gopro.setting.125": {"zh": "照片输出", "en": "Photo Output"},
    "gopro.setting.128": {"zh": "媒体格式", "en": "Media Format"},
    "gopro.setting.134": {"zh": "抗频闪", "en": "Anti-Flicker"},
    "gopro.setting.135": {"zh": "防抖", "en": "Hypersmooth"},
    "gopro.setting.150": {"zh": "视频水平校准", "en": "Video Horizon Leveling"},
    "gopro.setting.151": {"zh": "照片水平校准", "en": "Photo Horizon Leveling"},
    "gopro.setting.156": {"zh": "视频录制时长", "en": "Video Duration"},
    "gopro.setting.157": {"zh": "连拍时长", "en": "Multi Shot Duration"},
    "gopro.setting.162": {"zh": "Max 镜头", "en": "Max Lens"},
    "gopro.setting.167": {"zh": "HindSight", "en": "HindSight"},
    "gopro.setting.168": {"zh": "定时拍摄", "en": "Scheduled Capture"},
    "gopro.setting.171": {"zh": "照片单张间隔", "en": "Photo Single Interval"},
    "gopro.setting.172": {"zh": "照片间隔时长", "en": "Photo Interval Duration"},
    "gopro.setting.173": {"zh": "视频性能模式", "en": "Video Performance Mode"},
    "gopro.setting.175": {"zh": "控制模式", "en": "Control Mode"},
    "gopro.setting.176": {"zh": "简易模式速度", "en": "Easy Mode Speed"},
    "gopro.setting.177": {"zh": "夜景照片", "en": "Enable Night Photo"},
    "gopro.setting.178": {"zh": "无线频段", "en": "Wireless Band"},
    "gopro.setting.179": {"zh": "星轨长度", "en": "Star Trails Length"},
    "gopro.setting.180": {"zh": "系统视频模式", "en": "System Video Mode"},
    "gopro.setting.182": {"zh": "视频码率", "en": "Video Bit Rate"},
    "gopro.setting.183": {"zh": "位深", "en": "Bit Depth"},
    "gopro.setting.184": {"zh": "配置文件", "en": "Profiles"},
    "gopro.setting.186": {"zh": "视频简易模式", "en": "Video Easy Mode"},
    "gopro.setting.187": {"zh": "延时模式", "en": "Lapse Mode"},
    "gopro.setting.189": {"zh": "Max 镜头模块", "en": "Max Lens Mod"},
    "gopro.setting.190": {"zh": "Max 镜头启用", "en": "Max Lens Mod Enable"},
    "gopro.setting.191": {"zh": "简易夜景照片", "en": "Easy Night Photo"},
    "gopro.setting.192": {"zh": "连拍宽高比", "en": "Multi Shot Aspect Ratio"},
    "gopro.setting.193": {"zh": "取景", "en": "Framing"},
    "gopro.setting.194": {"zh": "相机模式", "en": "Camera Mode"},
    "gopro.setting.216": {"zh": "提示音音量", "en": "Beep Volume"},
    "gopro.setting.219": {"zh": "屏幕保护", "en": "Setup Screen Saver"},
    "gopro.setting.223": {"zh": "语言", "en": "Setup Language"},
    "gopro.setting.227": {"zh": "照片模式", "en": "Photo Mode"},
    "gopro.setting.232": {"zh": "视频取景", "en": "Video Framing"},
    "gopro.setting.233": {"zh": "连拍取景", "en": "Multi Shot Framing"},
    "gopro.setting.234": {"zh": "照片帧率", "en": "Frame Rate"},
    "gopro.setting.236": {"zh": "自动 WiFi", "en": "Automatic Wi-Fi Access Point"},
    "gopro.setting.237": {"zh": "USB 开机", "en": "Auto Power On USB"},
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

    def tr(self, key: str, *args, **kwargs) -> str:
        entry = _translations.get(key, {})
        text = entry.get(self._lang, key)
        if kwargs:
            return text.format(**kwargs)
        if args:
            return text % args
        return text


def tr(key: str, *args, **kwargs) -> str:
    return I18n.instance().tr(key, *args, **kwargs)
