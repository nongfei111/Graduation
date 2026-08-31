# 工作日志 - CLAUDE 智能门铃系统开发

## 项目信息
- **项目名称**: CLAUDE 智能门铃系统
- **硬件平台**: 树莓派 5 + 官方摄像头 (CSI)
- **显示**: 7 英寸触摸屏 (本地 GUI)
- **家庭成员**: 最多 20 位
- **通知**: 本地化，无网络推送

## 开发日志

### 2026-03-30 (第一天)
#### 完成内容：
1. **技术选型确认**
   - 人脸识别模型：MobileFaceNet (ONNX 格式，~3MB)
   - 人脸检测：UltraFace (轻量级，~1MB)
   - 开发语言：Python 3.11+
   - GUI 框架：PyQt5
   - 数据库：SQLite
   - 推理引擎：ONNX Runtime

2. **项目目录结构创建**
   ```
   graduation/
   ├── assets/models/         # 模型文件
   ├── data/                  # 数据目录
   ├── src/core/             # 核心模块
   ├── src/modules/          # 功能模块
   ├── src/ui/               # 用户界面
   ├── src/utils/            # 工具类
   ├── config/               # 配置文件
   ├── docs/                 # 文档
   └── tests/                # 测试文件
   ```

3. **核心模块实现** (已完成 5/5)
   - `database.py` - SQLite 数据库管理 (支持成员、人脸特征、访客记录、系统日志)
   - `camera.py` - 树莓派 5 官方摄像头控制 (支持 Picamera2)
   - `face_detector.py` - UltraFace 人脸检测 (支持 OpenCV Haar 级联备选)
   - `face_recognizer.py` - MobileFaceNet 人脸识别 (128 维特征向量)
   - `gpio_controller.py` - 蜂鸣器和按键控制 (支持模拟器)

4. **功能模块实现** (已完成 3/3)
   - `face_enrollment.py` - 人脸采集与注册 (支持 20 张/人采集)
   - `visitor_manager.py` - 访客记录管理 (支持统计、查询、导出)
   - `alert_system.py` - 预警系统 (陌生人停留检测、蜂鸣器报警)

#### 进行中：
- [ ] 工具模块 (config.py, helpers.py)
- [ ] PyQt5 GUI 界面
- [ ] 主程序入口
- [ ] 模型文件下载
- [ ] 系统联调测试

#### 论文章节规划：
1. 绪论（背景、意义、国内外研究现状）
2. 系统总体设计
3. 硬件系统设计
4. 软件系统设计
5. 核心算法实现
6. 系统测试与分析
7. 总结与展望

---
