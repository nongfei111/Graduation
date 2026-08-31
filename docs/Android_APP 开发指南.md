# CLAUDE 智能门铃 - Android APP 开发指南

## 一、项目概述

这是一个用于远程控制智能门铃的 Android 应用程序，支持以下功能：
- 用户登录/注册
- 远程开门
- 远程警报
- 远程语音对讲
- 远程抓拍
- 访客记录查看
- 报警管理

## 二、服务器配置

```kotlin
// 服务器地址
val BASE_URL = "http://8.134.196.56:5000"

// 登录凭据
val USERNAME = "admin"
val PASSWORD = "admin123456"
```

## 三、项目结构

```
app/
├── src/main/
│   ├── java/com/smartdoorbell/app/
│   │   ├── MainActivity.kt
│   │   ├── api/
│   │   │   ├── ApiService.kt
│   │   │   ├── ApiClient.kt
│   │   │   └── Models.kt
│   │   ├── data/
│   │   │   └── DoorbellRepository.kt
│   │   ├── ui/
│   │   │   ├── LoginFragment.kt
│   │   │   ├── HomeFragment.kt
│   │   │   ├── VisitorsFragment.kt
│   │   │   └── SettingsFragment.kt
│   │   └── viewmodel/
│   │       └── DoorbellViewModel.kt
│   ├── res/
│   │   ├── layout/
│   │   │   ├── activity_main.xml
│   │   │   ├── fragment_login.xml
│   │   │   ├── fragment_home.xml
│   │   │   └── ...
│   │   └── values/
│   │       ├── strings.xml
│   │       └── colors.xml
│   └── AndroidManifest.xml
└── build.gradle
```

## 四、快速开始

### 1. 创建项目

在 Android Studio 中：
1. New Project → Empty Activity
2. Language: Kotlin
3. Minimum SDK: API 21

### 2. 添加依赖

在 `build.gradle` 中添加：

```gradle
dependencies {
    // 网络请求
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
    implementation 'com.squareup.okhttp3:logging-interceptor:4.11.0'
    
    // 协程
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.1'
    
    // 生命周期
    implementation 'androidx.lifecycle:lifecycle-viewmodel-ktx:2.6.1'
    implementation 'androidx.lifecycle:lifecycle-livedata-ktx:2.6.1'
    
    // Material Design
    implementation 'com.google.android.material:material:1.9.0'
}
```

### 3. 配置网络权限

在 `AndroidManifest.xml` 中添加：

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
```

## 五、核心代码

### API 接口定义

```kotlin
// ApiService.kt
interface ApiService {
    @POST("/api/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>
    
    @GET("/api/device/status")
    suspend fun getDeviceStatus(@Header("Authorization") token: String): Response<DeviceStatusResponse>
    
    @POST("/api/control/unlock")
    suspend fun remoteUnlock(@Header("Authorization") token: String, @Body request: DeviceRequest): Response<UnlockResponse>
    
    @POST("/api/control/alert")
    suspend fun remoteAlert(@Header("Authorization") token: String, @Body request: AlertRequest): Response<CommandResponse>
    
    @POST("/api/control/speak")
    suspend fun remoteSpeak(@Header("Authorization") token: String, @Body request: SpeakRequest): Response<CommandResponse>
    
    @POST("/api/control/snapshot")
    suspend fun remoteSnapshot(@Header("Authorization") token: String, @Body request: DeviceRequest): Response<CommandResponse>
    
    @GET("/api/visitor/list")
    suspend fun getVisitorList(@Header("Authorization") token: String, @Query("limit") limit: Int): Response<VisitorListResponse>
    
    @GET("/api/stats")
    suspend fun getStatistics(@Header("Authorization") token: String): Response<StatisticsResponse>
}
```

### 数据模型

```kotlin
// Models.kt
data class LoginRequest(val username: String, val password: String)
data class LoginResponse(val success: Boolean, val user_id: Int, val access_token: String)

data class DeviceRequest(val device_id: String)
data class UnlockResponse(val success: Boolean, val command_id: Int, val message: String)
data class AlertRequest(val device_id: String, val message: String)
data class SpeakRequest(val device_id: String, val message: String)
data class CommandResponse(val success: Boolean, val command_id: Int)

data class Visitor(val id: Int, val visitor_type: String, val member_name: String?, val confidence: Float, val created_at: String)
data class VisitorListResponse(val success: Boolean, val visitors: List<Visitor>)

data class Statistics(val device_count: Int, val today_visitors: Int, val unhandled_alerts: Int)
data class StatisticsResponse(val success: Boolean, val stats: Statistics)
```

### 网络客户端

```kotlin
// ApiClient.kt
object ApiClient {
    private const val BASE_URL = "http://8.134.196.56:5000"
    
    var accessToken: String? = null
    
    private val client = OkHttpClient.Builder()
        .addInterceptor { chain ->
            val request = chain.request().newBuilder()
            accessToken?.let { 
                request.addHeader("Authorization", "Bearer $it")
            }
            chain.proceed(request.build())
        }
        .build()
    
    val apiService: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }
}
```

### ViewModel

```kotlin
// DoorbellViewModel.kt
class DoorbellViewModel : ViewModel() {
    private val repository = DoorbellRepository()
    
    val isLoading = MutableLiveData<Boolean>()
    val errorMessage = MutableLiveData<String>()
    val statistics = MutableLiveData<Statistics>()
    
    fun login(username: String, password: String) = viewModelScope.launch {
        isLoading.value = true
        repository.login(username, password).onSuccess {
            // 登录成功
        }.onFailure {
            errorMessage.value = it.message
        }
        isLoading.value = false
    }
    
    fun remoteUnlock(deviceId: String) = viewModelScope.launch {
        isLoading.value = true
        repository.remoteUnlock(deviceId).onSuccess {
            // 开门成功
        }.onFailure {
            errorMessage.value = it.message
        }
        isLoading.value = false
    }
    
    // 其他方法...
}
```

## 六、UI 布局

### 主界面

```xml
<!-- fragment_home.xml -->
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="16dp">
    
    <com.google.android.material.button.MaterialButton
        android:id="@+id/btnUnlock"
        android:layout_width="match_parent"
        android:layout_height="60dp"
        android:text="远程开门"/>
    
    <com.google.android.material.button.MaterialButton
        android:id="@+id/btnAlert"
        android:layout_width="match_parent"
        android:layout_height="60dp"
        android:text="远程警报"/>
    
    <com.google.android.material.button.MaterialButton
        android:id="@+id/btnSpeak"
        android:layout_width="match_parent"
        android:layout_height="60dp"
        android:text="远程对讲"/>
    
    <com.google.android.material.button.MaterialButton
        android:id="@+id/btnSnapshot"
        android:layout_width="match_parent"
        android:layout_height="60dp"
        android:text="远程抓拍"/>
</LinearLayout>
```

## 七、测试 API 接口

已验证可用的接口：

| 接口 | 状态 | 说明 |
|------|------|------|
| POST /api/auth/login | ✅ | 用户登录 |
| GET /api/device/status | ✅ | 设备状态 |
| POST /api/control/unlock | ✅ | 远程开门 |
| POST /api/control/alert | ✅ | 远程警报 |
| POST /api/control/speak | ✅ | 远程语音 |
| POST /api/control/snapshot | ✅ | 远程抓拍 |
| POST /api/visitor/upload | ✅ | 上传访客 |
| GET /api/stats | ✅ | 统计数据 |

## 八、登录信息

```
服务器：http://8.134.196.56:5000
用户名：admin
密码：admin123456
```

---

**更新时间**: 2026-04-13
