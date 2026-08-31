import os
import time
import signal
import logging

from gpio_control import DoorbellController
from src.sync.cloud_communication import CloudCommunication
from src.sync.remote_control import RemoteController
from src.sync.mqtt_commands import MqttCommandClient
from src.security import lockdown


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class _GpioAdapter:
    def __init__(self, ctrl: DoorbellController):
        self.ctrl = ctrl

    def unlock(self, duration: float = 3.0):
        if lockdown.is_locked():
            return
        self.ctrl.motor.unlock()

    def trigger_alarm(self, duration: float = 5.0):
        self.ctrl.trigger_alarm(duration)


def _load_or_create_device_id() -> str:
    explicit = (os.environ.get('DEVICE_ID') or '').strip()
    if explicit:
        return explicit

    path = (os.environ.get('DEVICE_ID_FILE') or 'data/device_id.txt').strip()
    if not path:
        path = 'data/device_id.txt'

    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)

    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                value = (f.read() or '').strip()
            if value:
                return value
    except Exception:
        pass

    os.makedirs(os.path.dirname(path), exist_ok=True)
    device_id = CloudCommunication(cloud_host='0.0.0.0', cloud_port=0, device_id=None).device_id
    with open(path, 'w', encoding='utf-8') as f:
        f.write(device_id)
    return device_id


def main():
    cloud_host = os.environ.get('SERVER_HOST', '8.134.196.56')
    cloud_port = int(os.environ.get('SERVER_PORT', '5000'))
    device_id = _load_or_create_device_id()
    device_name = os.environ.get('DEVICE_NAME') or '智能门铃'
    username = os.environ.get('DEVICE_USERNAME')
    password = os.environ.get('DEVICE_PASSWORD')
    device_token = os.environ.get('DEVICE_TOKEN')
    heartbeat_interval = int(os.environ.get('HEARTBEAT_INTERVAL', '30'))

    controller = DoorbellController()
    cloud = CloudCommunication(cloud_host=cloud_host, cloud_port=cloud_port, device_id=device_id)

    if device_token:
        cloud.set_device_token(device_token)
    elif not (username and password):
        raise SystemExit('缺少 DEVICE_TOKEN 或 DEVICE_USERNAME/DEVICE_PASSWORD')

    if not device_token:
        while True:
            if not cloud.login(username, password):
                logger.error('登录失败，5秒后重试')
                time.sleep(5)
                continue
            if not cloud.register_device(device_name=device_name):
                logger.error('设备注册失败，5秒后重试')
                time.sleep(5)
                continue
            break

    remote = RemoteController(
        cloud_comm=cloud,
        gpio_controller=_GpioAdapter(controller),
        display=None,
        audio_player=None
    )
    remote.start()
    cloud.start_background_tasks(heartbeat_interval=heartbeat_interval)

    mqtt_client = MqttCommandClient(device_id=device_id)
    mqtt_client.set_on_command(remote._on_cloud_command)
    mqtt_client.start(blocking=False)

    running = True

    def _stop(_signum=None, _frame=None):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    logger.info(f"设备在线：device_id={device_id} server=http://{cloud_host}:{cloud_port} mqtt={mqtt_client.broker}:{mqtt_client.port} topic={mqtt_client.topic_cmd} heartbeat={heartbeat_interval}s")
    while running:
        time.sleep(0.5)

    try:
        mqtt_client.stop()
    except Exception:
        pass
    try:
        cloud.stop_background_tasks()
    except Exception:
        pass
    try:
        controller.cleanup()
    except Exception:
        pass


if __name__ == '__main__':
    main()

