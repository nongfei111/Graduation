# Gradle 配置说明

## 解决 Gradle JVM 不兼容问题

### 问题描述
```
Incompatible Gradle JVM version
The project's Gradle version 8.0 is incompatible with the Gradle JVM version 21
```

### 解决方案

#### 方法一：在 Android Studio 中修改 Gradle JVM 设置（推荐）

1. 打开 Android Studio
2. 进入 **File** > **Settings** (Windows) 或 **Android Studio** > **Preferences** (Mac)
3. 导航到 **Build, Execution, Deployment** > **Build Tools** > **Gradle**
4. 找到 **Gradle JDK** 选项
5. 选择 **Java 17** 或 **Java 19**（不要选择 Java 21）
6. 点击 **Apply** 和 **OK**
7. 点击 **Sync Now** 同步项目

#### 方法二：修改 gradle.properties

在 `gradle.properties` 中添加：

```properties
org.gradle.java.home=C:\\Program Files\\Java\\jdk-17
```

（路径根据你的 JDK 安装位置调整）

#### 方法三：下载并安装 JDK 17

如果系统中没有 JDK 17，可以：

1. 下载 JDK 17：
   - [Microsoft OpenJDK 17](https://learn.microsoft.com/en-us/java/openjdk/download)
   - [Oracle JDK 17](https://www.oracle.com/java/technologies/downloads/#java17)
   - [Adoptium JDK 17](https://adoptium.net/temurin/releases/?version=17)

2. 安装后按照方法一设置 Gradle JDK

---

## 项目 Gradle 版本

- **Gradle**: 8.5 (支持 Java 21)
- **Android Gradle Plugin**: 8.1.0
- **Kotlin**: 1.8.20
- **编译 SDK**: 34
- **目标 SDK**: 34
- **最低 SDK**: 26

---

## 在 Android Studio 中打开项目

1. 启动 Android Studio
2. 选择 **File** > **Open**
3. 选择 `C:\Users\HP\Desktop\graduation` 目录
4. 等待 Gradle 同步完成
5. 如果遇到 JVM 版本错误，按照上述方法一修改 Gradle JDK 设置

---

## 常见问题

### 1. Gradle 同步失败
**解决**：检查网络连接，或使用代理

### 2. SDK 未找到
**解决**：在 SDK Manager 中安装 Android SDK 34

### 3. 依赖项下载失败
**解决**：修改 repositories 为国内镜像：
```gradle
maven { url 'https://maven.aliyun.com/repository/google' }
maven { url 'https://maven.aliyun.com/repository/public' }
```

---

**更新时间**: 2026-04-13
