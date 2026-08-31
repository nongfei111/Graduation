# 智能门铃 Android APP 项目

## 一、项目概述

### 1.1 项目名称
智能门铃客户端（Smart Doorbell）

### 1.2 技术栈
- **语言**: Kotlin
- **架构**: MVVM + Repository
- **网络**: Retrofit2 + OkHttp3
- **图片加载**: Glide
- **本地数据库**: Room
- **异步处理**: Coroutines
- **JDK**: 17.0.2
- **Gradle**: 8.7
- **AGP**: 8.13.0
- **Kotlin**: 2.0.21
- **KSP**: 2.0.21-1.0.27

### 1.3 最小版本要求
- minSdkVersion: 26 (Android 8.0)
- targetSdkVersion: 34 (Android 14)

### 1.4 服务器地址
- 阿里云：`http://8.134.196.56:5000`
- 测试账号：`admin` / `admin123`

---

## 二、项目结构

```
app/
├── src/main/
│   ├── java/com/example/smartdoorbell/
│   │   ├── MyApp.kt                 # Application 类
│   │   ├── ui/
│   │   │   ├── main/
│   │   │   │   └── MainActivity.kt            # 主界面（底部导航）
│   │   │   ├── login/
│   │   │   │   ├── LoginActivity.kt           # 登录界面
│   │   │   │   └── RegisterActivity.kt        # 注册界面
│   │   │   ├── home/
│   │   │   │   └── HomeFragment.kt            # 首页（统计 + 快捷操作）
│   │   │   ├── visitor/
│   │   │   │   ├── VisitorListFragment.kt     # 访客列表
│   │   │   │   ├── VisitorAdapter.kt          # 访客列表适配器
│   │   │   │   └── VisitorDetailActivity.kt   # 访客详情
│   │   │   ├── member/
│   │   │   │   └── MemberListFragment.kt      # 成员列表
│   │   │   └── settings/
│   │   │       └── SettingsFragment.kt        # 设置页面
│   │   ├── data/
│   │   │   ├── api/
│   │   │   │   ├── ApiService.kt              # Retrofit 接口
│   │   │   │   ├── RetrofitClient.kt          # 网络客户端
│   │   │   │   └── model/
│   │   │   │       └── DataModels.kt          # 数据模型
│   │   │   ├── repository/
│   │   │   │   └── Repositories.kt            # 数据仓库（Auth/Visitor/Member/Command）
│   │   │   └── PreferencesManager.kt          # 加密存储
│   │   └── util/
│   │       └── Constants.kt                   # 常量定义
│   ├── res/
│   │   ├── layout/
│   │   │   ├── activity_login.xml
│   │   │   ├── activity_register.xml
│   │   │   ├── activity_main.xml
│   │   │   ├── activity_visitor_detail.xml
│   │   │   ├── fragment_home.xml
│   │   │   ├── fragment_visitor_list.xml
│   │   │   ├── fragment_member_list.xml
│   │   │   ├── fragment_settings.xml
│   │   │   └── item_visitor.xml
│   │   ├── drawable/
│   │   │   ├── ic_home.xml
│   │   │   ├── ic_visitors.xml
│   │   │   ├── ic_members.xml
│   │   │   ├── ic_settings.xml
│   │   │   ├── ic_lock.xml
│   │   │   ├── ic_alert.xml
│   │   │   ├── ic_speak.xml
│   │   │   ├── ic_camera.xml
│   │   │   └── ic_default_avatar.xml
│   │   ├── values/
│   │   │   ├── colors.xml
│   │   │   ├── strings.xml
│   │   │   └── themes.xml
│   │   └── menu/
│   │       └── bottom_nav_menu.xml
│   └── AndroidManifest.xml
├── build.gradle.kts
└── proguard-rules.pro
```

---

## 三、核心代码实现

### 3.1 依赖配置 (build.gradle.kts)

```kotlin
plugins {
    id("com.android.application") version "8.13.0"
    id("org.jetbrains.kotlin.android") version "2.0.21"
    id("com.google.devtools.ksp") version "2.0.21-1.0.27"
}

android {
    namespace = "com.example.smartdoorbell"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.smartdoorbell.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
        buildConfig = true
    }
}

dependencies {
    // AndroidX Core
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")
    
    // Navigation
    implementation("androidx.navigation:navigation-fragment-ktx:2.7.6")
    implementation("androidx.navigation:navigation-ui-ktx:2.7.6")
    
    // Lifecycle
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-livedata-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    
    // Room
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")
    
    // Retrofit
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    
    // Glide
    implementation("com.github.bumptech.glide:glide:4.16.0")
    ksp("com.github.bumptech.glide:ksp:4.16.0")
    
    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    
    // Security (存储 Token)
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    
    // DataStore
    implementation("androidx.datastore:datastore-preferences:1.0.0")
}
```

---

## 四、API 接口定义

### 4.1 ApiService.kt

```kotlin
interface ApiService {
    // ==================== 认证 ====================
    
    @POST("/api/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>

    @POST("/api/auth/register")
    suspend fun register(@Body request: RegisterRequest): Response<RegisterResponse>

    @POST("/api/auth/refresh")
    suspend fun refreshToken(@Body request: RefreshTokenRequest): Response<RefreshTokenResponse>

    @GET("/api/auth/me")
    suspend fun getCurrentUser(@Header("Authorization") token: String): Response<UserInfo>

    // ==================== 家庭 ====================

    @GET("/api/family/list")
    suspend fun getFamilies(@Header("Authorization") token: String): Response<FamilyListResponse>

    @GET("/api/family/detail/{familyId}")
    suspend fun getFamilyDetail(
        @Header("Authorization") token: String,
        @Path("familyId") familyId: Int
    ): Response<FamilyDetailResponse>

    // ==================== 访客 ====================

    @GET("/api/visitor/list")
    suspend fun getVisitors(
        @Header("Authorization") token: String,
        @Query("family_id") familyId: Int,
        @Query("page") page: Int = 1,
        @Query("per_page") perPage: Int = 20,
        @Query("visitor_type") visitorType: String? = null,
        @Query("is_alert") isAlert: Boolean? = null
    ): Response<VisitorListResponse>

    @GET("/api/visitor/{visitorId}")
    suspend fun getVisitorDetail(
        @Header("Authorization") token: String,
        @Path("visitorId") visitorId: Int
    ): Response<VisitorDetailResponse>

    @GET("/api/visitor/statistics")
    suspend fun getStatistics(
        @Header("Authorization") token: String,
        @Query("family_id") familyId: Int,
        @Query("days") days: Int = 7
    ): Response<StatisticsResponse>

    @GET("/api/visitor/today")
    suspend fun getTodayVisitors(
        @Header("Authorization") token: String,
        @Query("family_id") familyId: Int
    ): Response<TodayVisitorsResponse>

    // ==================== 家庭成员 ====================

    @GET("/api/member/list")
    suspend fun getMembers(
        @Header("Authorization") token: String,
        @Query("family_id") familyId: Int
    ): Response<MemberListResponse>

    @POST("/api/member/add")
    suspend fun addMember(
        @Header("Authorization") token: String,
        @Body request: AddMemberRequest
    ): Response<AddMemberResponse>

    @DELETE("/api/member/{memberId}")
    suspend fun deleteMember(
        @Header("Authorization") token: String,
        @Path("memberId") memberId: Int
    ): Response<DeleteMemberResponse>

    // ==================== 设备控制 ====================

    @POST("/api/control/unlock")
    suspend fun unlock(
        @Header("Authorization") token: String,
        @Body request: UnlockRequest
    ): Response<UnlockResponse>

    @POST("/api/control/alert")
    suspend fun remoteAlert(
        @Header("Authorization") token: String,
        @Body request: AlertRequest
    ): Response<CommandResponse>

    @POST("/api/control/speak")
    suspend fun remoteSpeak(
        @Header("Authorization") token: String,
        @Body request: SpeakRequest
    ): Response<CommandResponse>

    @POST("/api/control/snapshot")
    suspend fun remoteSnapshot(
        @Header("Authorization") token: String,
        @Body request: DeviceRequest
    ): Response<CommandResponse>

    @GET("/api/device/status")
    suspend fun getDeviceStatus(
        @Header("Authorization") token: String
    ): Response<DeviceStatusListResponse>

    // ==================== 报警管理 ====================

    @GET("/api/alert/list")
    suspend fun getAlertList(
        @Header("Authorization") token: String,
        @Query("limit") limit: Int = 100
    ): Response<AlertListResponse>

    @POST("/api/alert/handle")
    suspend fun handleAlert(
        @Header("Authorization") token: String,
        @Body request: HandleAlertRequest
    ): Response<BaseResponse<Unit>>
}
```

---

## 五、功能模块说明

### 5.1 登录注册
- **登录**: 用户名/密码登录，支持自动登录（Token 持久化）
- **注册**: 新用户注册，用户名长度 3-20 字符，密码至少 6 位
- **Token 管理**: 使用 EncryptedSharedPreferences 加密存储 Token
- **家庭绑定**: 登录成功后自动获取家庭列表并绑定默认家庭 ID

### 5.2 首页 (HomeFragment)
- **今日访客**: 显示今日来访人数
- **近 7 天统计**: 总访客数、家人来访数、陌生人来访数、警报次数
- **快捷操作**:
  - 远程开锁：远程触发门锁开启
  - 远程警报：触发设备警报声
  - 远程对讲：发送语音到设备
  - 远程抓拍：远程触发摄像头拍照

### 5.3 访客列表 (VisitorListFragment)
- **列表展示**: RecyclerView 展示访客记录
- **下拉刷新**: 重新加载最新数据
- **上拉加载**: 分页加载历史数据（每页 20 条）
- **访客类型**: 家人（绿色标签）/ 陌生人（橙色标签）
- **警报标识**: 异常访问显示警报图标
- **点击详情**: 跳转 VisitorDetailActivity 查看大图和详细信息

### 5.4 成员管理 (MemberListFragment)
- **成员列表**: 显示当前家庭所有成员
- **添加成员**: 输入成员姓名添加到家庭
- **删除成员**: 删除家庭成员（需确认）

### 5.5 设置 (SettingsFragment)
- **账户信息**: 显示当前登录用户 ID
- **推送通知**: 开关控制（暂未实现 FCM）
- **退出登录**: 清除 Token 并返回登录页

---

## 六、编译运行

### 6.1 环境要求
- Android Studio Hedgehog | 2023.1.1 或更高版本
- JDK 17.0.2 或更高版本
- Android SDK (API 26+)

### 6.2 编译步骤
```bash
# 在 Android Studio 中打开项目
# 或使用命令行编译
cd app
./gradlew assembleDebug
```

### 6.3 配置服务器地址
编辑 `util/Constants.kt`:
```kotlin
object Constants {
    const val BASE_URL = "http://8.134.196.56:5000"
    const val CONNECT_TIMEOUT = 30L
    const val READ_TIMEOUT = 30L
}
```

### 6.4 测试账号
- 用户名：`admin`
- 密码：`admin123`

---

## 七、后续开发计划

### 7.1 功能增强
- [ ] 添加家庭成员人脸图片上传
- [ ] 访客详情图片放大查看（支持手势缩放）
- [ ] 推送通知（FCM）
- [ ] 离线缓存（Room 数据库）
- [ ] 多设备管理

### 7.2 UI/UX 优化
- [ ] 加载动画优化
- [ ] 空状态页面设计
- [ ] 错误处理提示优化
- [ ] 深色模式支持

### 7.3 性能优化
- [ ] 图片缓存优化（Glide 自定义缓存策略）
- [ ] 列表分页优化
- [ ] 网络请求缓存
- [ ] 内存泄漏检测

### 7.4 安全性
- [ ] HTTPS 支持
- [ ] Token 自动刷新机制
- [ ] 生物识别登录（指纹/面部）
- [ ] 数据加密存储

---

## 八、常见问题

### 8.1 Gradle 同步失败
确保 JDK 17 已安装并在 `gradle.properties` 中配置正确路径：
```properties
org.gradle.java.home=C:\\Users\\HP\\jdks\\jdk-17.0.2
```

### 8.2 网络请求失败
1. 检查服务器地址是否正确
2. 检查网络权限配置
3. 确认服务器支持 HTTP 明文传输（或配置 HTTPS）

### 8.3 Token 失效
Token 有效期为 24 小时，过期后需要重新登录。后续将实现自动刷新机制。

---

**文档版本**: v2.0  
**最后更新**: 2026-04-19  
**开发者**: CLAUDE 智能门铃项目组
