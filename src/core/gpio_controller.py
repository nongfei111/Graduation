"""
CLAUDE 智能门铃系统 - GPIO 控制模块
蜂鸣器和物理按键控制
"""

try:
    from gpiozero import Buzzer, Button
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("警告：gpiozero 未安装，GPIO 功能将不可用")

from typing import Callable, Optional
import time


class GPIOController:
    """
    GPIO 控制器
    管理蜂鸣器、物理按键和门锁控制
    """

    def __init__(self, buzzer_pin: int = 17, button_pin: int = 27, door_lock_pin: int = 22):
        """
        初始化 GPIO 控制器

        Args:
            buzzer_pin: 蜂鸣器 GPIO 引脚（BCM 编码）
            button_pin: 物理按键 GPIO 引脚（BCM 编码）
            door_lock_pin: 门锁控制 GPIO 引脚（BCM 编码）
        """
        self.buzzer_pin = buzzer_pin
        self.button_pin = button_pin
        self.door_lock_pin = door_lock_pin
        self.buzzer = None
        self.button = None
        self.door_lock = None
        self.is_initialized = False

        if GPIO_AVAILABLE:
            self._initialize()

    def _initialize(self):
        """初始化 GPIO 设备"""
        try:
            # 初始化蜂鸣器
            self.buzzer = Buzzer(self.buzzer_pin)
            self.buzzer.off()

            # 初始化按键
            self.button = Button(self.button_pin, pull_up=True)

            # 初始化门锁继电器
            try:
                from gpiozero import OutputDevice
                self.door_lock = OutputDevice(self.door_lock_pin)
                self.door_lock.off()  # 初始状态关闭
                print(f"GPIO 初始化成功 - 蜂鸣器：GPIO{self.buzzer_pin}, 按键：GPIO{self.button_pin}, 门锁：GPIO{self.door_lock_pin}")
            except Exception as e:
                print(f"门锁初始化失败：{e}，将使用蜂鸣器模拟")
                self.door_lock = None

            self.is_initialized = True

        except Exception as e:
            print(f"GPIO 初始化失败：{e}")
            self.is_initialized = False

    # ==================== 蜂鸣器控制 ====================

    def beep(self, duration: float = 0.5):
        """
        短鸣

        Args:
            duration: 鸣叫时长（秒）
        """
        if not self.is_initialized:
            return

        try:
            self.buzzer.on()
            time.sleep(duration)
            self.buzzer.off()
        except Exception as e:
            print(f"蜂鸣器控制失败：{e}")

    def beep_alert(self, count: int = 3, interval: float = 0.3):
        """
        警报鸣叫

        Args:
            count: 鸣叫次数
            interval: 间隔时长
        """
        if not self.is_initialized:
            return

        for _ in range(count):
            self.beep(0.5)
            time.sleep(interval)

    def beep_success(self):
        """成功提示音"""
        if self.is_initialized:
            self.buzzer.on()
            time.sleep(0.1)
            self.buzzer.off()
            time.sleep(0.1)
            self.buzzer.on()
            time.sleep(0.1)
            self.buzzer.off()

    def beep_error(self):
        """错误提示音"""
        if self.is_initialized:
            self.buzzer.on()
            time.sleep(0.3)
            self.buzzer.off()
            time.sleep(0.1)
            self.buzzer.on()
            time.sleep(0.3)
            self.buzzer.off()

    # ==================== 按键控制 ====================

    def set_button_callback(self, callback: Callable):
        """
        设置按键回调函数

        Args:
            callback: 按键按下时调用的函数
        """
        if not self.is_initialized:
            return

        try:
            self.button.when_pressed = callback
            print("按键回调已设置")
        except Exception as e:
            print(f"设置按键回调失败：{e}")

    def is_button_pressed(self) -> bool:
        """检查按键是否被按下"""
        if not self.is_initialized:
            return False
        return self.button.is_pressed

    # ==================== 门锁控制 ====================

    def unlock(self, duration: float = 1.0):
        """
        打开门锁

        Args:
            duration: 继电器吸合时长（秒）
        """
        if not self.is_initialized:
            print("[模拟] 门锁已打开")
            return True

        try:
            if self.door_lock:
                self.door_lock.on()  # 吸合继电器
                time.sleep(duration)
                self.door_lock.off()  # 断开继电器
                print("门锁已打开")
                return True
            else:
                # 使用蜂鸣器模拟开门提示音
                self.beep_success()
                print("[模拟] 门锁已打开")
                return True
        except Exception as e:
            print(f"开门失败：{e}")
            return False

    def lock(self):
        """关闭门锁（断电解锁型门锁不需要此操作）"""
        if not self.is_initialized:
            print("[模拟] 门锁已关闭")
            return True

        try:
            if self.door_lock:
                self.door_lock.off()
                print("门锁已关闭")
                return True
            else:
                print("[模拟] 门锁已关闭")
                return True
        except Exception as e:
            print(f"关门失败：{e}")
            return False

    def trigger_alarm(self, duration: float = 5.0):
        """
        触发警报

        Args:
            duration: 警报时长（秒）
        """
        if not self.is_initialized:
            print(f"[模拟] 触发警报 {duration} 秒")
            return True

        try:
            if self.buzzer:
                end_time = time.time() + duration
                while time.time() < end_time:
                    self.buzzer.on()
                    time.sleep(0.3)
                    self.buzzer.off()
                    time.sleep(0.2)
                print(f"警报触发完成 (时长：{duration}秒)")
                return True
            else:
                print("[模拟] 警报触发")
                return True
        except Exception as e:
            print(f"警报触发失败：{e}")
            return False

    # ==================== 资源释放 ====================

    def cleanup(self):
        """清理 GPIO 资源"""
        if self.is_initialized:
            try:
                if self.buzzer:
                    self.buzzer.off()
                if self.button:
                    self.button.close()
                print("GPIO 资源已清理")
            except Exception as e:
                print(f"GPIO 清理失败：{e}")
            finally:
                self.is_initialized = False

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.cleanup()


class GPIOControllerSimulator:
    """
    GPIO 模拟器（用于开发测试，无需真实硬件）
    """

    def __init__(self, buzzer_pin: int = 17, button_pin: int = 27, door_lock_pin: int = 22):
        """初始化模拟器"""
        self.buzzer_pin = buzzer_pin
        self.button_pin = button_pin
        self.door_lock_pin = door_lock_pin
        self.is_buzzer_on = False
        self.is_door_open = False
        self.button_callback = None
        self.is_initialized = True
        print("GPIO 模拟器已初始化（无真实硬件）")

    def beep(self, duration: float = 0.5):
        """模拟蜂鸣"""
        print(f"[GPIO 模拟] 蜂鸣器鸣叫 {duration} 秒")
        self.is_buzzer_on = True
        time.sleep(duration)
        self.is_buzzer_on = False

    def beep_alert(self, count: int = 3, interval: float = 0.3):
        """模拟警报"""
        print(f"[GPIO 模拟] 警报鸣叫 {count} 次")
        for i in range(count):
            self.beep(0.5)
            time.sleep(interval)

    def beep_success(self):
        """模拟成功提示音"""
        print("[GPIO 模拟] 成功提示音：滴 - 滴")

    def beep_error(self):
        """模拟错误提示音"""
        print("[GPIO 模拟] 错误提示音：嘟 - 嘟")

    def set_button_callback(self, callback: Callable):
        """设置按键回调（模拟）"""
        self.button_callback = callback
        print("[GPIO 模拟] 按键回调已设置")
        print("[GPIO 模拟] 调用 callback() 模拟按键按下")

    def unlock(self, duration: float = 1.0):
        """模拟开门"""
        print(f"[GPIO 模拟] 门锁已打开 (时长：{duration}秒)")
        self.is_door_open = True
        time.sleep(duration)
        self.is_door_open = False
        return True

    def lock(self):
        """模拟关门"""
        print("[GPIO 模拟] 门锁已关闭")
        return True

    def trigger_alarm(self, duration: float = 5.0):
        """模拟警报"""
        print(f"[GPIO 模拟] 触发警报 {duration} 秒")
        self.beep_alert(count=int(duration/0.5))
        return True

    def cleanup(self):
        """清理资源"""
        print("[GPIO 模拟] 资源已清理")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
