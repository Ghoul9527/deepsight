#!/usr/bin/env python3
"""Exclusive JSON/stdio servo test bridge. Run on Pi over SSH."""
import fcntl
import json
import signal
import subprocess
import sys
from pathlib import Path
import time
import yaml


def apply_servo_command(pca, allowed, channel, pulse):
    targets = sorted(allowed) if channel == 'all' else [channel]
    if any(ch not in allowed for ch in targets) or not 500 <= pulse <= 2500:
        raise ValueError('Channel/pulse outside permitted test range')
    for other in sorted(allowed - set(targets)):
        pca.set_duty_cycle(other, 0)
    readbacks = {}
    for ch in targets:
        pca.set_pwm(ch, pulse)
        data = pca._bus.read_i2c_block_data(pca._addr, 6 + 4 * ch, 4)
        count = ((data[3] & 15) << 8) | data[2]
        expected = int(4096 / pca._period_us * pulse)
        if data[1] & 16 or data[3] & 16 or count != expected:
            raise RuntimeError(f'CH{ch} PWM register readback mismatch')
        readbacks[str(ch)] = round(count / 4096 * pca._period_us, 1)
    return readbacks


def main():
    lock=open('/tmp/deepsight-servo-manual.lock','w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    root=Path('/home/tony/deepsight')
    config=yaml.safe_load((root/'configs/pi_config.yaml').read_text())
    h=config['hardware'];pc=h['pca9685']
    allowed={c['channel'] for c in h['servos']}
    was_active=subprocess.run(['systemctl','is-active','--quiet','deepsight-pi']).returncode==0
    pca=None
    log=(root/'logs'/('servo-manual-'+str(time.time_ns())+'.jsonl')).open('w',buffering=1)
    def reply(**data):
        data['timestamp']=time.time()
        log.write(json.dumps(data)+'\n')
        print(json.dumps(data),flush=True)
    def stop(signum,frame):raise SystemExit(0)
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    def off():
        if pca is not None:
            for channel in sorted(allowed):pca.set_duty_cycle(channel,0)
    try:
        subprocess.run(['sudo','-n','systemctl','stop','deepsight-pi'],check=True)
        if subprocess.run(['systemctl','is-active','--quiet','deepsight-pi']).returncode==0:
            raise RuntimeError('Pi service did not stop; refusing competing PWM access')
        from deepsight_pi.hardware.pca9685 import PCA9685
        pca=PCA9685(pc.get('i2c_bus',1),pc.get('i2c_address',64),pc.get('pwm_freq',50))
        off()
        pca.set_duty_cycle(h.get('lights',[{'channel':5}])[0]['channel'],0)
        reply(event='ready',frequency=pc.get('pwm_freq',50),log=str(log.name),outputs='off')
        for line in sys.stdin:
            request={}
            try:
                request=json.loads(line)
                action=request.get('action')
                if action=='close':break
                if action=='off':
                    off();reply(event='off',id=request.get('id'));continue
                if action!='set':raise ValueError('Unknown action')
                channel=request['channel'];pulse=float(request['pulse_us'])
                readbacks=apply_servo_command(pca,allowed,channel,pulse)
                reply(event='applied',id=request.get('id'),channel=channel,
                      pulse_us=pulse,readbacks=readbacks,
                      readback_us=next(iter(readbacks.values())))
            except Exception as exc:
                try:off()
                except Exception:pass
                reply(event='error',id=request.get('id'),detail=str(exc))
    except Exception as exc:
        reply(event='error',detail=str(exc))
    finally:
        if pca is not None:
            try:off()
            except Exception as exc:
                log.write(json.dumps({'event':'cleanup_error','detail':str(exc)})+'\n')
            try:pca.close()
            except Exception:pass
        if was_active:
            result=subprocess.run(['sudo','-n','systemctl','start','deepsight-pi'])
            log.write(json.dumps({'event':'service_restored','ok':result.returncode==0})+'\n')
        log.close()

if __name__=='__main__':main()
