"""Standalone manual servo tester: python -m deepsight_host.servo_tester."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import yaml
from PySide6.QtCore import Qt, QProcess, QTimer, QSignalBlocker
from PySide6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,
    QLabel,QComboBox,QSpinBox,QSlider,QPushButton,QCheckBox,QLineEdit,QGroupBox)
from deepsight_host.ui.styles import DARK_THEME

NAMES=['Yaw','Pitch','Roll','左舵机','右舵机']


def pulse_for_angle(angle,minimum=1000,maximum=2000):
    if not 500<=minimum<maximum<=2500:raise ValueError('脉宽范围须满足500 ≤ 最小值 < 最大值 ≤ 2500')
    return round(minimum+max(0,min(180,angle))/180*(maximum-minimum))


class ServoTester(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('DeepSight — 舵机逐个手动测试')
        self.setMinimumWidth(650)
        self.setStyleSheet(DARK_THEME)
        self.proc=QProcess(self)
        self.proc.readyReadStandardOutput.connect(self.read_output)
        self.proc.readyReadStandardError.connect(self.read_error)
        self.proc.finished.connect(self.disconnected)
        self.proc.errorOccurred.connect(lambda *_: self.status.setText('连接进程异常：'+self.proc.errorString()))
        self.buffer=b'';self.ready=False;self.pending=None;self.sequence=0
        self.channels=list(range(5))
        config_path=Path('configs/pi_config.yaml')
        if config_path.exists():
            h=yaml.safe_load(config_path.read_text())['hardware']
            self.channels=[next(c['channel'] for c in h['servos'] if c['id']==sid) for sid in range(5)]
        layout=QVBoxLayout(self)
        intro=QLabel('可选择单个或全部舵机。连接后先停止全部PWM，不会自动扫动。\n测试期间Pi主服务暂停；关闭窗口后恢复主服务，舵机会按正常配置回正。')
        intro.setWordWrap(True);layout.addWidget(intro)
        connection=QHBoxLayout();self.address=QLineEdit('192.168.3.161')
        self.connect_button=QPushButton('连接Pi / 进入测试')
        self.connect_button.clicked.connect(self.connect_pi)
        connection.addWidget(QLabel('Pi地址'));connection.addWidget(self.address);connection.addWidget(self.connect_button)
        layout.addLayout(connection)
        self.status=QLabel('未连接；不会发送舵机指令');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.controls=QGroupBox('舵机控制');form=QFormLayout(self.controls)
        self.selector=QComboBox()
        for sid,name in enumerate(NAMES):self.selector.addItem(f'{name} — CH{self.channels[sid]}',self.channels[sid])
        self.selector.addItem('全部舵机 — Yaw / Pitch / Roll / 左 / 右', 'all')
        form.addRow('检查的舵机',self.selector)
        range_row=QHBoxLayout();self.minimum=QSpinBox();self.maximum=QSpinBox()
        for spin,value in ((self.minimum,1000),(self.maximum,2000)):
            spin.setRange(500,2500);spin.setValue(value);spin.setSuffix(' μs')
        range_row.addWidget(self.minimum);range_row.addWidget(QLabel('至'));range_row.addWidget(self.maximum)
        form.addRow('逻辑0–180°映射',range_row)
        angle_row=QHBoxLayout();self.slider=QSlider(Qt.Horizontal);self.slider.setRange(0,180);self.slider.setValue(90)
        self.angle=QSpinBox();self.angle.setRange(0,180);self.angle.setValue(90);self.angle.setSuffix('°')
        angle_row.addWidget(self.slider,1);angle_row.addWidget(self.angle);form.addRow('逻辑角度',angle_row)
        self.relative=QLabel('相对中位：0°');form.addRow('',self.relative)
        self.pulse=QSpinBox();self.pulse.setRange(500,2500);self.pulse.setValue(1500);self.pulse.setSuffix(' μs')
        form.addRow('直接设定PWM脉宽',self.pulse)
        shortcuts=QHBoxLayout()
        for name,pulse in [('1000 μs',1000),('回中 / 1500 μs',1500),('2000 μs',2000)]:
            button=QPushButton(name);button.clicked.connect(lambda checked=False,p=pulse:self.pulse.setValue(p));shortcuts.addWidget(button)
        form.addRow('快捷设定',shortcuts)
        steps=QHBoxLayout()
        for text,delta in [('-5°',-5),('-1°',-1),('+1°',1),('+5°',5)]:
            button=QPushButton(text);button.clicked.connect(lambda checked=False,d=delta:self.angle.setValue(self.angle.value()+d));steps.addWidget(button)
        form.addRow('微调',steps)
        self.enabled=QCheckBox('开始输出到所选舵机（全部模式同时驱动五个）');form.addRow(self.enabled)
        self.readback=QLabel('寄存器回读：未输出（不代表实际舵机角度）');self.readback.setWordWrap(True);form.addRow(self.readback)
        self.controls.setEnabled(False);layout.addWidget(self.controls)
        stop=QPushButton('停止全部舵机PWM输出')
        stop.setStyleSheet('background:#b32b36;font-weight:bold;min-height:40px;')
        stop.clicked.connect(self.stop_outputs);layout.addWidget(stop)
        note=QLabel('角度是软件设定值，不是实测位置。连续旋转型舵机的脉宽可能控制转速和方向。\n供电电压或电流是否充足，需要核对舵机型号并测量；I²C回读不能证明舵机已动作。')
        note.setWordWrap(True);layout.addWidget(note)
        self.slider.valueChanged.connect(self.angle.setValue)
        self.angle.valueChanged.connect(self.angle_changed)
        self.minimum.valueChanged.connect(lambda *_: self.angle_changed(self.angle.value()))
        self.maximum.valueChanged.connect(lambda *_: self.angle_changed(self.angle.value()))
        self.pulse.valueChanged.connect(self.pulse_changed)
        self.enabled.toggled.connect(self.output_toggled)
        self.selector.currentIndexChanged.connect(self.channel_changed)
        self.timer=QTimer(self);self.timer.timeout.connect(self.flush);self.timer.start(100)
        self.keepalive=QTimer(self);self.keepalive.timeout.connect(self.repeat_output);self.keepalive.start(1000)

    def connect_pi(self):
        if self.proc.state()!=QProcess.NotRunning:return
        self.status.setText('连接中；暂停Pi主服务并独占驱动板…')
        self.connect_button.setEnabled(False);self.address.setEnabled(False)
        self.proc.start('ssh',['-o','BatchMode=yes','-o','ConnectTimeout=5',
            'tony@'+self.address.text().strip(),
            'cd /home/tony/deepsight && python3 -u scripts/servo_manual_bridge.py'])

    def send(self,action,**kwargs):
        if not self.ready:return
        self.sequence+=1
        data=dict(action=action,id=self.sequence,**kwargs)
        self.proc.write((json.dumps(data)+'\n').encode())

    def angle_changed(self,value):
        with QSignalBlocker(self.slider):self.slider.setValue(value)
        self.relative.setText(f'相对中位：{value-90:+d}°')
        try:pulse=pulse_for_angle(value,self.minimum.value(),self.maximum.value())
        except ValueError as exc:
            self.stop_outputs();self.status.setText(str(exc));return
        with QSignalBlocker(self.pulse):self.pulse.setValue(pulse)
        self.pending=pulse

    def pulse_changed(self,pulse):
        span=self.maximum.value()-self.minimum.value()
        if span>0:
            angle=round(max(0,min(180,(pulse-self.minimum.value())/span*180)))
            with QSignalBlocker(self.slider):self.slider.setValue(angle)
            with QSignalBlocker(self.angle):self.angle.setValue(angle)
            self.relative.setText(f'相对中位：{angle-90:+d}°（按当前范围换算）')
        self.pending=pulse

    def output_toggled(self,enabled):
        if enabled:self.pending=self.pulse.value();self.flush()
        else:self.pending=None;self.send('off');self.readback.setText('已请求停止全部PWM输出')

    def channel_changed(self,*_):
        self.enabled.setChecked(False);self.pending=None;self.send('off')
        with QSignalBlocker(self.angle):self.angle.setValue(90)
        with QSignalBlocker(self.slider):self.slider.setValue(90)
        with QSignalBlocker(self.pulse):self.pulse.setValue(1500)
        self.relative.setText('相对中位：0°；新通道尚未输出')

    def repeat_output(self):
        # Periodically verify that the selected PWM still writes successfully.
        if self.ready and self.enabled.isChecked():self.pending=self.pulse.value()

    def flush(self):
        if self.ready and self.enabled.isChecked() and self.pending is not None:
            pulse=self.pending;self.pending=None
            self.send('set',channel=self.selector.currentData(),pulse_us=pulse)

    def stop_outputs(self):
        self.enabled.setChecked(False);self.pending=None;self.send('off')

    def read_output(self):
        self.buffer+=bytes(self.proc.readAllStandardOutput())
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:data=json.loads(line)
            except ValueError:continue
            event=data.get('event')
            if event=='ready':
                self.ready=True;self.controls.setEnabled(True)
                self.status.setText(f'Pi已连接，PCA9685 {data["frequency"]}Hz；自动联动与上位机舵机指令已隔离')
            elif event=='applied':
                if data['channel']=='all':
                    readings=' / '.join(f'CH{ch}: {us:g}' for ch,us in data['readbacks'].items())
                    self.readback.setText(f'全部舵机：设定{data["pulse_us"]:g} μs；回读μs：{readings}')
                else:
                    self.readback.setText(f'CH{data["channel"]}：设定{data["pulse_us"]:g} μs，寄存器回读{data["readback_us"]:g} μs')
                self.status.setText('连接正常；PWM写入及寄存器回读成功，传感器联动已隔离')
            elif event=='off':
                self.readback.setText('全部舵机PWM已关闭')
                self.status.setText('连接正常；全部输出已停止，传感器联动已隔离')
            elif event=='error':
                with QSignalBlocker(self.enabled):self.enabled.setChecked(False)
                self.pending=None;self.status.setText('测试错误：'+data.get('detail','未知错误'))

    def read_error(self):
        detail=bytes(self.proc.readAllStandardError()).decode(errors='replace').strip()
        if detail:self.status.setText(detail)

    def disconnected(self,*_):
        self.ready=False;self.controls.setEnabled(False)
        with QSignalBlocker(self.enabled):self.enabled.setChecked(False)
        self.connect_button.setEnabled(True);self.address.setEnabled(True)
        self.status.setText('测试连接已结束；正常退出时Pi主服务已恢复')

    def closeEvent(self,event):
        self.timer.stop();self.keepalive.stop()
        if self.ready:self.send('off');self.send('close')
        self.proc.closeWriteChannel()
        if self.proc.state()!=QProcess.NotRunning:self.proc.waitForFinished(5000)
        event.accept()


def main():
    app=QApplication(sys.argv)
    window=ServoTester();window.show();window.raise_();window.activateWindow()
    sys.exit(app.exec())

if __name__=='__main__':main()
