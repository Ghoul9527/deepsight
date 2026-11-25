# Pico 分离传感器 I²C

MicroPython 使用 `pico/config.py` 常量；CPython 的 YAML 覆盖配置同步在
`configs/pico_config.yaml`。

| 设备 | 控制器 | SDA | SCL | 时钟 |
| --- | --- | --- | --- | --- |
| MPU-6050 | I²C0 | GP20（物理26） | GP21（物理27） | 100 kHz |
| MS5837 | I²C1 | GP18（物理24） | GP19（物理25） | 10 kHz |

两者供电使用 3V3 OUT（物理36），GND 共地。漏水输入仍为 GP2，未修改。
压力驱动在硬件 I²C 初始化后，以 `Pin.init(pull=Pin.PULL_UP)` 明确启用
SDA、SCL 内部上拉，不修改引脚的 I²C 复用功能。内部上拉对应 Pico 3.3V 电平。
温湿度传感器未安装，`BME280_ENABLED=False` 避免旧驱动重新配置 I²C0。

10 kHz 是弱上拉下的调试起点，不代表已验证信号时序或实际接线可靠性。
部署至 Pico 并重启后，应检查 0x68 / 0x76、压力 PROM CRC，以及连续压力和
温度读取；只有地址扫描成功不足以判定工作正常。还需在舵机、补光灯运行时
检查读数和重启后的恢复情况。当前本地测试未代替硬件验证。
