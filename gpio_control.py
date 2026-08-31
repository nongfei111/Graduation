"""
GPIO 控制模块 - 控制蜂鸣器和步进电机
树莓派 5 使用 lgpio 替代 RPi.GPIO

功能定位索引（设备端硬件抽象层）：
- 蜂鸣器提示：
  - Buzzer.beep()/double_beep()/alarm()（成员识别提示、活体失败提示、报警）
- 门锁联动：
  - StepperMotor.unlock()/lock()（步进电机模拟门锁旋转）
  - DoorbellController.on_member_recognized()（成员识别成功后的统一联动入口：蜂鸣 + 开锁）

调用位置：
- main.py 成员识别成功：doorbell_controller.on_member_recognized()
- remote_control.py 远程开锁：gpio.unlock() -> main.py:_GpioAdapter.unlock() -> motor.unlock()
"""

import os
import time
import threading
from typing import Optional

# 检查是否可以导入 lgpio (树莓派 5)
try:
    import lgpio
    LGPIO_AVAILABLE = True
    print("lgpio 库可用，使用树莓派 5 GPIO 控制")
except ImportError:
    print("警告：lgpio 库未安装，将使用模拟模式")
    LGPIO_AVAILABLE = False


class MockLgpio:
    """模拟 lgpio 用于测试"""
    def gpiochip_open(self, chip):
        return 0
    def gpiochip_close(self, handle):
        pass
    def gpio_claim_output(self, handle, gpio, flags, initial):
        pass
    def gpio_write(self, handle, gpio, level):
        print(f"[模拟] GPIO {gpio} -> {level}")
    def tx_waveforms(self, handle, wave_data):
        pass


# GPIO 引脚定义 (BCM 编号)
# 根据实际接线修改这些值
BUZZER_PIN = 26          # 蜂鸣器 GPIO26
MOTOR_IN1 = 1            # 步进电机 IN1 GPIO1
MOTOR_IN2 = 7            # 步进电机 IN2 GPIO7
MOTOR_IN3 = 8            # 步进电机 IN3 GPIO8
MOTOR_IN4 = 25           # 步进电机 IN4 GPIO25


class Buzzer:
    """蜂鸣器控制（支持无源蜂鸣器）"""

    # 无源蜂鸣器频率（Hz）- 可调整
    BUZZER_FREQUENCY = 2000  # 2kHz，声音较响亮

    def __init__(self, pin: int = BUZZER_PIN, buzzer_type: str = 'passive', frequency: int = None):
        """
        初始化蜂鸣器

        Args:
            pin: GPIO 引脚编号 (BCM)
            buzzer_type: 蜂鸣器类型 ('passive' 无源 或 'active' 有源)
            frequency: 蜂鸣器频率 (Hz)，仅无源蜂鸣器使用
        """
        self.pin = pin
        self.buzzer_type = buzzer_type
        self.frequency = frequency or self.BUZZER_FREQUENCY
        self.handle = None
        self.is_active = False

        if LGPIO_AVAILABLE:
            try:
                self.handle = lgpio.gpiochip_open(0)
                lgpio.gpio_claim_output(self.handle, self.pin, 0, 0)
                print(f"蜂鸣器已初始化 (GPIO{self.pin}, 类型：{buzzer_type}, 频率：{self.frequency}Hz)")
            except Exception as e:
                print(f"蜂鸣器初始化失败：{e}")
                self.handle = None
        else:
            print("蜂鸣器：模拟模式")

    def beep(self, duration: float = 0.5):
        """
        短鸣（无源蜂鸣器使用 PWM 方波）

        Args:
            duration: 鸣叫时长（秒）
        """
        if self.buzzer_type == 'passive' and LGPIO_AVAILABLE and self.handle is not None:
            # 无源蜂鸣器：发送 PWM 方波，duty_cycle 用百分比 (50%)
            try:
                lgpio.tx_pwm(self.handle, self.pin, self.frequency, 50, 0)
                time.sleep(duration)
                lgpio.tx_pwm(self.handle, self.pin, 0, 0, 0)  # 停止 PWM
            except Exception as e:
                print(f"PWM 蜂鸣失败：{e}")
                # 回退到简单开关模式
                self.on()
                time.sleep(duration)
                self.off()
        else:
            # 有源蜂鸣器或模拟模式：简单开关
            self.on()
            time.sleep(duration)
            self.off()

    def double_beep(self, interval: float = 0.2, duration: float = 0.3):
        """双声提示"""
        self.beep(duration)
        time.sleep(interval)
        self.beep(duration)

    def on(self):
        """打开蜂鸣器"""
        if self.handle is not None and LGPIO_AVAILABLE:
            try:
                lgpio.gpio_write(self.handle, self.pin, 1)
            except:
                pass
        else:
            print("[蜂鸣器] ON")

    def off(self):
        """关闭蜂鸣器"""
        if self.handle is not None and LGPIO_AVAILABLE:
            try:
                lgpio.gpio_write(self.handle, self.pin, 0)
            except:
                pass
        else:
            print("[蜂鸣器] OFF")

    def alarm(self, duration: float = 3.0, interval: float = 0.5):
        """
        报警长鸣

        Args:
            duration: 总时长（秒）
            interval: 鸣叫间隔（秒）
        """
        print(f"开始报警，持续{duration}秒...")
        self.is_active = True
        start_time = time.time()

        while time.time() - start_time < duration and self.is_active:
            self.beep(interval)
            time.sleep(interval)

        print("报警结束")

    def stop_alarm(self):
        """停止报警"""
        self.is_active = False

    def cleanup(self):
        """清理资源"""
        self.off()
        if self.handle is not None and LGPIO_AVAILABLE:
            try:
                lgpio.gpiochip_close(self.handle)
            except:
                pass
            self.handle = None


class StepperMotor:
    """步进电机控制（4 线 28BYJ-48 + ULN2003 驱动）"""

    # 半步激励序列
    SEQUENCE = [
        [1, 0, 0, 0],  # 1
        [1, 1, 0, 0],  # 1+2
        [0, 1, 0, 0],  # 2
        [0, 1, 1, 0],  # 2+3
        [0, 0, 1, 0],  # 3
        [0, 0, 1, 1],  # 3+4
        [0, 0, 0, 1],  # 4
        [1, 0, 0, 1],  # 4+1
    ]

    def __init__(self, in1: int = MOTOR_IN1, in2: int = MOTOR_IN2,
                 in3: int = MOTOR_IN3, in4: int = MOTOR_IN4,
                 steps_per_rev: int = 2048):
        """
        初始化步进电机

        Args:
            in1, in2, in3, in4: 驱动板输入引脚
            steps_per_rev: 每转步数（28BYJ-48 减速后约 2048）
        """
        self.pins = [in1, in2, in3, in4]
        self.steps_per_rev = steps_per_rev
        self.handle = None

        if LGPIO_AVAILABLE:
            try:
                self.handle = lgpio.gpiochip_open(0)
                for pin in self.pins:
                    lgpio.gpio_claim_output(self.handle, pin, 0, 0)
                print(f"步进电机已初始化 (IN1={in1}, IN2={in2}, IN3={in3}, IN4={in4})")
            except Exception as e:
                print(f"步进电机初始化失败：{e}")
                self.handle = None
        else:
            print("步进电机：模拟模式")

        self._running = False

    def _set_pins(self, state):
        """设置 4 个引脚状态"""
        if self.handle is None:
            return
        for i, pin in enumerate(self.pins):
            lgpio.gpio_write(self.handle, pin, state[i])

    def _step(self, step_index):
        """走一步"""
        state = self.SEQUENCE[step_index % len(self.SEQUENCE)]
        self._set_pins(state)

    def rotate(self, revolutions: float = 0.25, clockwise: bool = True,
               step_delay: float = 0.002):
        """
        旋转指定圈数

        Args:
            revolutions: 圈数
            clockwise: 是否顺时针
            step_delay: 每步延迟（秒），越小越快
        """
        steps_needed = int(revolutions * self.steps_per_rev)
        self._running = True

        for i in range(steps_needed):
            if not self._running:
                break
            if clockwise:
                step_idx = i % len(self.SEQUENCE)
            else:
                step_idx = (-i - 1) % len(self.SEQUENCE)
            self._step(step_idx)
            time.sleep(step_delay)

        # 归零
        self._set_pins([0, 0, 0, 0])

    def unlock(self, step_delay: float = 0.002):
        """模拟开锁（旋转 90 度 = 0.25 圈，顺时针）"""
        print("[电机] 开锁动作...")
        self.rotate(0.25, clockwise=True, step_delay=step_delay)
        print("[电机] 开锁完成")

    def lock(self, step_delay: float = 0.002):
        """模拟上锁（旋转 90 度，逆时针）"""
        print("[电机] 上锁动作...")
        self.rotate(0.25, clockwise=False, step_delay=step_delay)
        print("[电机] 上锁完成")

    def stop(self):
        """停止旋转"""
        self._running = False
        self._set_pins([0, 0, 0, 0])

    def cleanup(self):
        """清理资源"""
        self.stop()
        if self.handle is not None and LGPIO_AVAILABLE:
            try:
                lgpio.gpiochip_close(self.handle)
            except:
                pass
            self.handle = None


class DoorbellController:
    """门铃控制器 - 统一管理蜂鸣器和电机"""

    def __init__(self):
        """初始化门铃控制器"""
        self.buzzer = Buzzer()
        self.motor = StepperMotor()

    def on_member_recognized(self, member_name: str):
        """
        家庭成员识别成功时的响应

        Args:
            member_name: 成员姓名
        """
        print(f"\n=== {member_name} 识别成功 ===")
        self.buzzer.double_beep()  # 双声提示
        self.motor.unlock()  # 开锁
        print(f"欢迎回家，{member_name}！")

    def on_unknown_visitor(self, duration: int = 30):
        """
        发现陌生访客

        Args:
            duration: 允许停留时长（秒）
        """
        print(f"\n=== 陌生访客 detected ===")
        print(f"允许停留 {duration} 秒...")
        # 这里可以启动计时器，超时后报警

    def trigger_alarm(self, duration: float = 5.0):
        """
        触发报警

        Args:
            duration: 报警时长（秒）
        """
        print("\n!!! 触发报警 !!!")
        self.buzzer.alarm(duration)

    def cleanup(self):
        """清理资源"""
        self.buzzer.cleanup()
        self.motor.cleanup()


# ==================== 测试 ====================

if __name__ == '__main__':
    print("=== GPIO 控制模块测试 ===\n")

    controller = DoorbellController()

    print("\n1. 测试蜂鸣器...")
    controller.buzzer.double_beep()

    print("\n2. 测试步进电机...")
    controller.motor.unlock()
    time.sleep(1)
    controller.motor.lock()

    print("\n3. 测试家庭成员识别响应...")
    controller.on_member_recognized("张三")

    print("\n测试完成")
    controller.cleanup()
