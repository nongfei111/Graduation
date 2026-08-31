# CLAUDE 智能门铃系统 - Android APP

基于 Kotlin 开发的智能门铃 Android 客户端，支持人脸识别、访客管理、远程操控等功能。

## 项目结构

```
app/
├── src/main/
│   ├── java/com/example/smartdoorbell/
│   │   ├── MyApp.kt                     # Application 入口
│   │   ├── data/                        # 数据层
│   │   │   ├── PreferencesManager.kt    # 数据存储
│   │   │   ├── api/                     # 网络层
│   │   │   │   ├── ApiService.kt        # API 接口定义
│   │   │   │   ├── RetrofitClient.kt    # Retrofit 客户端
│   │   │   │   └── model/               # 数据模型
│   │   │   │       └── DataModels.kt
│   │   │   └── repository/              # 仓库层
│   │   │       └── Repositories.kt
│   │   ├── ui/                          # UI 层
│   │   │   ├── login/
│   │   │   │   └── LoginActivity.kt     # 登录界面
│   │   │   ├── main/
│   │   │   │   └── MainActivity.kt      # 主界面
│   │   │   ├── home/
│   │   │   │   └── HomeFragment.kt      # 首页
│   │   │   ├── visitor/
│   │   │   │   ├── VisitorListFragment.kt  # 访客列表
│   │   │   │   ├── VisitorAdapter.kt       # 访客适配器
│   │   │   │   └── VisitorDetailActivity.kt # 访客详情
│   │   │   ├── member/
│   │   │   │   └── MemberListFragment.kt   # 成员管理
│   │   │   └── settings/
│   │   │       └── SettingsFragment.kt     # 设置页面
│   │   └── util/
│   │       └── Constants.kt             # 常量定义
│   ├── res/                             # 资源文件
│   ├── AndroidManifest.xml              # 应用清单
│   └── proguard-rules.pro               # ProGuard 规则
├── build.gradle                         # 应用构建配置
├── proguard-rules.pro                   # 混淆规则
```

## 快速开始

### 1. 环境要求

- Android Studio Hedgehog (2023.1.1) 或更高版本
- JDK 17 或 19（Gradle 8.5 兼容）
- Android SDK 34
- 最低支持 Android 8.0 (API 26)

### 2. 配置 Gradle JVM

**重要**：Gradle 8.5 需要 Java 17-21，如使用 Java 21 请确保 Gradle 版本为 8.5+

在 Android Studio 中：
1. File > Settings > Build, Execution, Deployment > Build Tools > Gradle
2. 设置 Gradle JDK 为 Java 17 或 Java 19
3. 点击 Sync Now

### 3. 服务器配置

编辑 `app/src/main/java/com/example/smartdoorbell/util/Constants.kt`：

```kotlin
const val BASE_URL = "http://8.134.196.56:5000"
```

### 4. 构建项目

```bash
# Windows
gradlew.bat assembleDebug

# 或在 Android Studio 中
Build > Make Project
```

### 5. 运行应用

```bash
# 连接 Android 设备或启动模拟器
# 在 Android Studio 中点击 Run
```

## 功能特性

### 已实现功能

- ✅ 用户登录/注册
- ✅ Token 自动管理
- ✅ 实时统计数据
- ✅ 远程开锁
- ✅ 远程警报
- ✅ 远程语音对讲
- ✅ 远程抓拍
- ✅ 访客列表查看
- ✅ 访客详情
- ✅ 家庭成员管理
- ✅ 设置页面
- ✅ 退出登录

### 待实现功能

- [ ] 人脸图片上传
- [ ] 推送通知 (FCM)
- [ ] 离线缓存
- [ ] 多设备管理
- [ ] 深色模式

## 服务器 API

### 云服务器地址

```
http://8.134.196.56:5000
```

### 主要接口

| 功能 | 端点 | 方法 |
|------|------|------|
| 登录 | `/api/auth/login` | POST |
| 注册 | `/api/auth/register` | POST |
| 远程开锁 | `/api/control/unlock` | POST |
| 远程警报 | `/api/control/alert` | POST |
| 远程语音 | `/api/control/speak` | POST |
| 远程抓拍 | `/api/control/snapshot` | POST |
| 访客列表 | `/api/visitor/list` | GET |
| 统计数据 | `/api/stats` | GET |

### 测试账号

- 用户名：`admin`
- 密码：`admin123`

## 技术栈

- **语言**: Kotlin
- **架构**: MVVM
- **网络**: Retrofit + OkHttp
- **异步**: Kotlin Coroutines + Flow
- **DI**: 手动依赖注入
- **存储**: EncryptedSharedPreferences
- **UI**: Material Components + ViewBinding

## 依赖库

```gradle
// AndroidX
implementation 'androidx.core:core-ktx:1.12.0'
implementation 'androidx.appcompat:appcompat:1.6.1'
implementation 'com.google.android.material:material:1.11.0'

// Navigation
implementation 'androidx.navigation:navigation-fragment-ktx:2.7.6'
implementation 'androidx.navigation:navigation-ui-ktx:2.7.6'

// Lifecycle
implementation 'androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0'
implementation 'androidx.lifecycle:lifecycle-livedata-ktx:2.7.0'

// Network
implementation 'com.squareup.retrofit2:retrofit:2.9.0'
implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
implementation 'com.squareup.okhttp3:logging-interceptor:4.12.0'

// Image Loading
implementation 'com.github.bumptech.glide:glide:4.16.0'

// Coroutines
implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3'

// Security
implementation 'androidx.security:security-crypto:1.1.0-alpha06'
```

## 常见问题

### Gradle 同步失败

检查 Gradle JVM 版本是否为 17-19：
```
File > Settings > Build, Execution, Deployment > Build Tools > Gradle > Gradle JDK
```

### 依赖项下载失败

项目已配置阿里云镜像，如仍有问题检查网络连接。

### 服务器连接失败

1. 检查 BASE_URL 配置
2. 确认服务器运行状态
3. 检查网络权限配置

## 相关文档

- [Android App 开发完成报告](./ANDROID_APP_DEVELOPMENT.md)
- [Gradle 配置说明](./GRADLE_SETUP.md)
- [云服务器 API 文档](./CLOUD_CONNECTION_SUMMARY.md)

## 开发者

CLAUDE Code  
2026-04-13
