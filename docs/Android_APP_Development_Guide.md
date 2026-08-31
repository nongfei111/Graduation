# CLAUDE 智能门铃系统 - Android APP 开发指南

## 一、快速开始

### 1.1 项目配置

在 `build.gradle` 中添加依赖：

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
}
```

### 1.2 权限配置

在 `AndroidManifest.xml` 中添加：

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
```

## 二、网络层实现

### 2.1 API 接口定义

```kotlin
// ApiService.kt
package com.smartdoorbell.api

import com.smartdoorbell.model.*
import retrofit2.Response
import retrofit2.http.*

interface ApiService {
    
    // ==================== 用户认证 ====================
    
    @POST("/api/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>
    
    @POST("/api/auth/register")
    suspend fun register(@Body request: RegisterRequest): Response<RegisterResponse>
    
    @POST("/api/auth/refresh")
    @Headers("Content-Type: application/json")
    suspend fun refreshToken(@Header("Authorization") token: String): Response<RefreshTokenResponse>
    
    // ==================== 设备管理 ====================
    
    @GET("/api/device/status")
    @Headers("Content-Type: application/json")
    suspend fun getDeviceStatus(@Header("Authorization") token: String): Response<DeviceStatusResponse>
    
    @POST("/api/device/heartbeat")
    @Headers("Content-Type: application/json")
    suspend fun deviceHeartbeat(
        @Header("Authorization") token: String,
        @Body request: HeartbeatRequest
    ): Response<HeartbeatResponse>
    
    // ==================== 远程控制 ====================
    
    @POST("/api/control/unlock")
    @Headers("Content-Type: application/json")
    suspend fun remoteUnlock(
        @Header("Authorization") token: String,
        @Body request: DeviceRequest
    ): Response<UnlockResponse>
    
    @POST("/api/control/alert")
    @Headers("Content-Type: application/json")
    suspend fun remoteAlert(
        @Header("Authorization") token: String,
        @Body request: AlertRequest
    ): Response<CommandResponse>
    
    @POST("/api/control/speak")
    @Headers("Content-Type: application/json")
    suspend fun remoteSpeak(
        @Header("Authorization") token: String,
        @Body request: SpeakRequest
    ): Response<CommandResponse>
    
    @POST("/api/control/snapshot")
    @Headers("Content-Type: application/json")
    suspend fun remoteSnapshot(
        @Header("Authorization") token: String,
        @Body request: DeviceRequest
    ): Response<CommandResponse>
    
    // ==================== 访客管理 ====================
    
    @GET("/api/visitor/list")
    @Headers("Content-Type: application/json")
    suspend fun getVisitorList(
        @Header("Authorization") token: String,
        @Query("limit") limit: Int,
        @Query("type") type: String? = null
    ): Response<VisitorListResponse>
    
    // ==================== 报警管理 ====================
    
    @GET("/api/alert/list")
    @Headers("Content-Type: application/json")
    suspend fun getAlertList(
        @Header("Authorization") token: String,
        @Query("limit") limit: Int
    ): Response<AlertListResponse>
    
    @POST("/api/alert/handle")
    @Headers("Content-Type: application/json")
    suspend fun handleAlert(
        @Header("Authorization") token: String,
        @Body request: HandleAlertRequest
    ): Response<BaseResponse>
    
    // ==================== 统计数据 ====================
    
    @GET("/api/stats")
    @Headers("Content-Type: application/json")
    suspend fun getStatistics(@Header("Authorization") token: String): Response<StatisticsResponse>
    
    // ==================== 健康检查 ====================
    
    @GET("/api/health")
    suspend fun healthCheck(): Response<HealthResponse>
}
```

### 2.2 数据模型

```kotlin
// Model.kt
package com.smartdoorbell.model

import com.google.gson.annotations.SerializedName

// ==================== 基础响应 ====================

data class BaseResponse(
    val success: Boolean,
    val error: String? = null
)

// ==================== 用户认证 ====================

data class LoginRequest(
    val username: String,
    val password: String
)

data class LoginResponse(
    val success: Boolean,
    val user_id: Int,
    val username: String,
    val access_token: String
)

data class RegisterRequest(
    val username: String,
    val password: String,
    val email: String? = null,
    val phone: String? = null
)

data class RegisterResponse(
    val success: Boolean,
    val user_id: Int,
    val access_token: String
)

data class RefreshTokenResponse(
    val success: Boolean,
    val access_token: String
)

// ==================== 设备管理 ====================

data class DeviceStatusResponse(
    val success: Boolean,
    val devices: List<Device>
)

data class Device(
    val device_id: String,
    val device_name: String,
    val device_type: String,
    val firmware_version: String,
    val last_heartbeat: String,
    val is_online: Boolean,
    val created_at: String
)

data class HeartbeatRequest(
    val device_id: String
)

data class HeartbeatResponse(
    val success: Boolean,
    val online: Boolean,
    val command: RemoteCommand?
)

data class RemoteCommand(
    val id: Int,
    val type: String,
    val data: Map<String, Any>
)

// ==================== 远程控制 ====================

data class DeviceRequest(
    val device_id: String
)

data class UnlockResponse(
    val success: Boolean,
    val command_id: Int,
    val message: String
)

data class AlertRequest(
    val device_id: String,
    val message: String
)

data class SpeakRequest(
    val device_id: String,
    val message: String
)

data class CommandResponse(
    val success: Boolean,
    val command_id: Int
)

// ==================== 访客管理 ====================

data class VisitorListResponse(
    val success: Boolean,
    val visitors: List<Visitor>
)

data class Visitor(
    val id: Int,
    val device_id: String,
    val visitor_type: String,  // "family" or "stranger"
    val member_name: String?,
    val confidence: Float,
    val photo_path: String?,
    val created_at: String
)

// ==================== 报警管理 ====================

data class AlertListResponse(
    val success: Boolean,
    val alerts: List<Alert>
)

data class Alert(
    val id: Int,
    val device_id: String,
    val visitor_id: Int?,
    val reason: String,
    val duration: Int,
    val handled: Boolean,
    val created_at: String,
    val visitor_type: String?,
    val member_name: String?
)

data class HandleAlertRequest(
    val alert_id: Int,
    val handled: Boolean = true
)

// ==================== 统计数据 ====================

data class StatisticsResponse(
    val success: Boolean,
    val stats: Statistics
)

data class Statistics(
    val device_count: Int,
    val today_visitors: Int,
    val today_access: Int,
    val unhandled_alerts: Int
)

// ==================== 健康检查 ====================

data class HealthResponse(
    val status: String,
    val timestamp: String,
    val server: String
)
```

### 2.3 网络请求管理器

```kotlin
// ApiClient.kt
package com.smartdoorbell.api

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
    
    // 服务器地址
    private const val BASE_URL = "http://8.134.196.56:5000"
    
    // Token 存储
    var accessToken: String? = null
        private set
    
    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }
    
    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        .addInterceptor { chain ->
            val original = chain.request()
            val requestBuilder = original.newBuilder()
            
            // 添加 Token
            accessToken?.let {
                requestBuilder.addHeader("Authorization", "Bearer $it")
            }
            
            requestBuilder
                .method(original.method, original.body)
                .build()
        }
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()
    
    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
    
    val apiService: ApiService by lazy {
        retrofit.create(ApiService::class.java)
    }
    
    fun setToken(token: String) {
        accessToken = token
    }
    
    fun clearToken() {
        accessToken = null
    }
}
```

### 2.4 仓库层

```kotlin
// DoorbellRepository.kt
package com.smartdoorbell.data

import com.smartdoorbell.api.ApiClient
import com.smartdoorbell.model.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class DoorbellRepository {
    
    private val apiService = ApiClient.apiService
    
    // ==================== 用户认证 ====================
    
    suspend fun login(username: String, password: String): Result<LoginResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = apiService.login(LoginRequest(username, password))
                if (response.isSuccessful) {
                    val loginResponse = response.body()
                    if (loginResponse != null && loginResponse.success) {
                        ApiClient.setToken(loginResponse.access_token)
                        Result.success(loginResponse)
                    } else {
                        Result.failure(Exception(response.message()))
                    }
                } else {
                    Result.failure(Exception(response.message()))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    
    // ==================== 设备管理 ====================
    
    suspend fun getDeviceStatus(): Result<DeviceStatusResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = apiService.getDeviceStatus()
                if (response.isSuccessful) {
                    Result.success(response.body())
                } else {
                    Result.failure(Exception(response.message()))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    
    // ==================== 远程控制 ====================
    
    suspend fun remoteUnlock(deviceId: String): Result<UnlockResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = apiService.remoteUnlock(DeviceRequest(deviceId))
                if (response.isSuccessful) {
                    Result.success(response.body())
                } else {
                    Result.failure(Exception(response.message()))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    
    suspend fun remoteAlert(deviceId: String, message: String): Result<CommandResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = apiService.remoteAlert(AlertRequest(deviceId, message))
                if (response.isSuccessful) {
                    Result.success(response.body())
                } else {
                    Result.failure(Exception(response.message()))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    
    suspend fun remoteSpeak(deviceId: String, message: String): Result<CommandResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = apiService.remoteSpeak(SpeakRequest(deviceId, message))
                if (response.isSuccessful) {
                    Result.success(response.body())
                } else {
                    Result.failure(Exception(response.message()))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    
    suspend fun remoteSnapshot(deviceId: String): Result<CommandResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = apiService.remoteSnapshot(DeviceRequest(deviceId))
                if (response.isSuccessful) {
                    Result.success(response.body())
                } else {
                    Result.failure(Exception(response.message()))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    
    // ==================== 访客管理 ====================
    
    suspend fun getVisitorList(limit: Int = 100, type: String? = null): Result<VisitorListResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = apiService.getVisitorList(limit, type)
                if (response.isSuccessful) {
                    Result.success(response.body())
                } else {
                    Result.failure(Exception(response.message()))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    
    // ==================== 报警管理 ====================
    
    suspend fun getAlertList(limit: Int = 100): Result<AlertListResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = apiService.getAlertList(limit)
                if (response.isSuccessful) {
                    Result.success(response.body())
                } else {
                    Result.failure(Exception(response.message()))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    
    suspend fun handleAlert(alertId: Int, handled: Boolean = true): Result<BaseResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = apiService.handleAlert(HandleAlertRequest(alertId, handled))
                if (response.isSuccessful) {
                    Result.success(response.body())
                } else {
                    Result.failure(Exception(response.message()))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    
    // ==================== 统计数据 ====================
    
    suspend fun getStatistics(): Result<StatisticsResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = apiService.getStatistics()
                if (response.isSuccessful) {
                    Result.success(response.body())
                } else {
                    Result.failure(Exception(response.message()))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
}
```

## 三、ViewModel 实现

```kotlin
// DoorbellViewModel.kt
package com.smartdoorbell.viewmodel

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.smartdoorbell.data.DoorbellRepository
import com.smartdoorbell.model.*
import kotlinx.coroutines.launch

class DoorbellViewModel : ViewModel() {
    
    private val repository = DoorbellRepository()
    
    // UI 状态
    private val _isLoading = MutableLiveData<Boolean>()
    val isLoading: LiveData<Boolean> = _isLoading
    
    private val _errorMessage = MutableLiveData<String>()
    val errorMessage: LiveData<String> = _errorMessage
    
    // 设备状态
    private val _devices = MutableLiveData<List<Device>>()
    val devices: LiveData<List<Device>> = _devices
    
    // 访客列表
    private val _visitors = MutableLiveData<List<Visitor>>()
    val visitors: LiveData<List<Visitor>> = _visitors
    
    // 报警列表
    private val _alerts = MutableLiveData<List<Alert>>()
    val alerts: LiveData<List<Alert>> = _alerts
    
    // 统计数据
    private val _statistics = MutableLiveData<Statistics>()
    val statistics: LiveData<Statistics> = _statistics
    
    // ==================== 用户认证 ====================
    
    fun login(username: String, password: String) {
        viewModelScope.launch {
            _isLoading.value = true
            _errorMessage.value = null
            
            repository.login(username, password).onSuccess { response ->
                // 登录成功，导航到主界面
            }.onFailure { error ->
                _errorMessage.value = error.message
            }
            
            _isLoading.value = false
        }
    }
    
    // ==================== 设备管理 ====================
    
    fun loadDeviceStatus() {
        viewModelScope.launch {
            _isLoading.value = true
            
            repository.getDeviceStatus().onSuccess { response ->
                if (response != null && response.success) {
                    _devices.value = response.devices
                }
            }.onFailure { error ->
                _errorMessage.value = error.message
            }
            
            _isLoading.value = false
        }
    }
    
    // ==================== 远程控制 ====================
    
    fun remoteUnlock(deviceId: String, onSuccess: () -> Unit = {}) {
        viewModelScope.launch {
            _isLoading.value = true
            
            repository.remoteUnlock(deviceId).onSuccess { response ->
                if (response != null && response.success) {
                    onSuccess()
                }
            }.onFailure { error ->
                _errorMessage.value = error.message
            }
            
            _isLoading.value = false
        }
    }
    
    fun remoteAlert(deviceId: String, message: String, onSuccess: () -> Unit = {}) {
        viewModelScope.launch {
            _isLoading.value = true
            
            repository.remoteAlert(deviceId, message).onSuccess { response ->
                if (response != null && response.success) {
                    onSuccess()
                }
            }.onFailure { error ->
                _errorMessage.value = error.message
            }
            
            _isLoading.value = false
        }
    }
    
    fun remoteSpeak(deviceId: String, message: String, onSuccess: () -> Unit = {}) {
        viewModelScope.launch {
            _isLoading.value = true
            
            repository.remoteSpeak(deviceId, message).onSuccess { response ->
                if (response != null && response.success) {
                    onSuccess()
                }
            }.onFailure { error ->
                _errorMessage.value = error.message
            }
            
            _isLoading.value = false
        }
    }
    
    fun remoteSnapshot(deviceId: String, onSuccess: () -> Unit = {}) {
        viewModelScope.launch {
            _isLoading.value = true
            
            repository.remoteSnapshot(deviceId).onSuccess { response ->
                if (response != null && response.success) {
                    onSuccess()
                }
            }.onFailure { error ->
                _errorMessage.value = error.message
            }
            
            _isLoading.value = false
        }
    }
    
    // ==================== 访客管理 ====================
    
    fun loadVisitors(limit: Int = 100, type: String? = null) {
        viewModelScope.launch {
            _isLoading.value = true
            
            repository.getVisitorList(limit, type).onSuccess { response ->
                if (response != null && response.success) {
                    _visitors.value = response.visitors
                }
            }.onFailure { error ->
                _errorMessage.value = error.message
            }
            
            _isLoading.value = false
        }
    }
    
    // ==================== 报警管理 ====================
    
    fun loadAlerts(limit: Int = 100) {
        viewModelScope.launch {
            _isLoading.value = true
            
            repository.getAlertList(limit).onSuccess { response ->
                if (response != null && response.success) {
                    _alerts.value = response.alerts
                }
            }.onFailure { error ->
                _errorMessage.value = error.message
            }
            
            _isLoading.value = false
        }
    }
    
    fun handleAlert(alertId: Int, handled: Boolean = true) {
        viewModelScope.launch {
            _isLoading.value = true
            
            repository.handleAlert(alertId, handled).onSuccess {
                // 刷新列表
                loadAlerts()
            }.onFailure { error ->
                _errorMessage.value = error.message
            }
            
            _isLoading.value = false
        }
    }
    
    // ==================== 统计数据 ====================
    
    fun loadStatistics() {
        viewModelScope.launch {
            _isLoading.value = true
            
            repository.getStatistics().onSuccess { response ->
                if (response != null && response.success) {
                    _statistics.value = response.stats
                }
            }.onFailure { error ->
                _errorMessage.value = error.message
            }
            
            _isLoading.value = false
        }
    }
}
```

## 四、UI 实现示例

### 4.1 主界面 Fragment

```kotlin
// HomeFragment.kt
package com.smartdoorbell.ui

import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import com.smartdoorbell.R
import com.smartdoorbell.databinding.FragmentHomeBinding
import com.smartdoorbell.viewmodel.DoorbellViewModel

class HomeFragment : Fragment(R.layout.fragment_home) {
    
    private var _binding: FragmentHomeBinding? = null
    private val binding get() = _binding!!
    
    private val viewModel: DoorbellViewModel by viewModels()
    
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        
        _binding = FragmentHomeBinding.bind(view)
        
        setupObservers()
        setupClickListeners()
        
        // 加载数据
        viewModel.loadDeviceStatus()
        viewModel.loadStatistics()
    }
    
    private fun setupObservers() {
        // 观察设备状态
        viewModel.devices.observe(viewLifecycleOwner) { devices ->
            val onlineCount = devices.count { it.is_online }
            binding.tvOnlineDevices.text = "在线设备：$onlineCount"
        }
        
        // 观察统计数据
        viewModel.statistics.observe(viewLifecycleOwner) { stats ->
            binding.tvTodayVisitors.text = "今日访客：${stats.today_visitors}"
            binding.tvTodayAccess.text = "开门次数：${stats.today_access}"
            binding.tvUnhandledAlerts.text = "未处理警报：${stats.unhandled_alerts}"
        }
        
        // 观察加载状态
        viewModel.isLoading.observe(viewLifecycleOwner) { isLoading ->
            binding.progressBar.isVisible = isLoading
        }
        
        // 观察错误信息
        viewModel.errorMessage.observe(viewLifecycleOwner) { error ->
            error?.let {
                Toast.makeText(context, error, Toast.LENGTH_SHORT).show()
            }
        }
    }
    
    private fun setupClickListeners() {
        // 远程开门按钮
        binding.btnUnlock.setOnClickListener {
            val deviceId = getCurrentDeviceId()
            viewModel.remoteUnlock(deviceId) {
                Toast.makeText(context, "开门成功", Toast.LENGTH_SHORT).show()
            }
        }
        
        // 警报按钮
        binding.btnAlert.setOnClickListener {
            val deviceId = getCurrentDeviceId()
            viewModel.remoteAlert(deviceId, "警告！请勿靠近！") {
                Toast.makeText(context, "警报已发送", Toast.LENGTH_SHORT).show()
            }
        }
        
        // 语音按钮
        binding.btnSpeak.setOnClickListener {
            val deviceId = getCurrentDeviceId()
            viewModel.remoteSpeak(deviceId, "您好，请问有什么事吗？") {
                Toast.makeText(context, "语音已发送", Toast.LENGTH_SHORT).show()
            }
        }
        
        // 抓拍按钮
        binding.btnSnapshot.setOnClickListener {
            val deviceId = getCurrentDeviceId()
            viewModel.remoteSnapshot(deviceId) {
                Toast.makeText(context, "抓拍命令已发送", Toast.LENGTH_SHORT).show()
            }
        }
    }
    
    private fun getCurrentDeviceId(): String {
        return viewModel.devices.value?.firstOrNull()?.device_id ?: "doorbell_001"
    }
    
    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
```

### 4.2 布局文件

```xml
<!-- fragment_home.xml -->
<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout 
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:padding="16dp">
    
    <!-- 进度条 -->
    <ProgressBar
        android:id="@+id/progressBar"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:visibility="gone"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent"/>
    
    <!-- 统计卡片 -->
    <com.google.android.material.card.MaterialCardView
        android:id="@+id/statsCard"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:layout_marginBottom="16dp"
        app:cardCornerRadius="12dp"
        app:cardElevation="4dp"
        app:layout_constraintTop_toTopOf="parent">
        
        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:orientation="vertical"
            android:padding="16dp">
            
            <TextView
                android:id="@+id/tvOnlineDevices"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:text="在线设备：0"
                android:textSize="16sp"/>
            
            <TextView
                android:id="@+id/tvTodayVisitors"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:text="今日访客：0"
                android:textSize="16sp"/>
            
            <TextView
                android:id="@+id/tvTodayAccess"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:text="开门次数：0"
                android:textSize="16sp"/>
            
            <TextView
                android:id="@+id/tvUnhandledAlerts"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:text="未处理警报：0"
                android:textSize="16sp"/>
        </LinearLayout>
    </com.google.android.material.card.MaterialCardView>
    
    <!-- 控制按钮 -->
    <com.google.android.material.button.MaterialButton
        android:id="@+id/btnUnlock"
        android:layout_width="match_parent"
        android:layout_height="60dp"
        android:layout_marginTop="16dp"
        android:text="远程开门"
        android:textSize="18sp"
        app:icon="@drawable/ic_unlock"
        app:layout_constraintTop_toBottomOf="@id/statsCard"/>
    
    <com.google.android.material.button.MaterialButton
        android:id="@+id/btnAlert"
        android:layout_width="match_parent"
        android:layout_height="60dp"
        android:layout_marginTop="8dp"
        android:text="远程警报"
        android:textSize="18sp"
        app:icon="@drawable/ic_alert"
        app:layout_constraintTop_toBottomOf="@id/btnUnlock"/>
    
    <com.google.android.material.button.MaterialButton
        android:id="@+id/btnSpeak"
        android:layout_width="match_parent"
        android:layout_height="60dp"
        android:layout_marginTop="8dp"
        android:text="远程对讲"
        android:textSize="18sp"
        app:icon="@drawable/ic_speak"
        app:layout_constraintTop_toBottomOf="@id/btnAlert"/>
    
    <com.google.android.material.button.MaterialButton
        android:id="@+id/btnSnapshot"
        android:layout_width="match_parent"
        android:layout_height="60dp"
        android:layout_marginTop="8dp"
        android:text="远程抓拍"
        android:textSize="18sp"
        app:icon="@drawable/ic_camera"
        app:layout_constraintTop_toBottomOf="@id/btnSpeak"/>
    
</androidx.constraintlayout.widget.ConstraintLayout>
```

## 五、API 接口说明

### 5.1 服务器地址

```
BASE_URL = "http://8.134.196.56:5000"
```

### 5.2 认证方式

所有需要认证的接口都需要在请求头中添加：

```
Authorization: Bearer <access_token>
```

### 5.3 接口列表

| 功能 | 端点 | 方法 | 需要认证 |
|------|------|------|----------|
| 健康检查 | `/api/health` | GET | 否 |
| 用户登录 | `/api/auth/login` | POST | 否 |
| 用户注册 | `/api/auth/register` | POST | 否 |
| 刷新 Token | `/api/auth/refresh` | POST | 是 |
| 设备状态 | `/api/device/status` | GET | 是 |
| 设备心跳 | `/api/device/heartbeat` | POST | 是 |
| 远程开门 | `/api/control/unlock` | POST | 是 |
| 远程警报 | `/api/control/alert` | POST | 是 |
| 远程语音 | `/api/control/speak` | POST | 是 |
| 远程抓拍 | `/api/control/snapshot` | POST | 是 |
| 访客列表 | `/api/visitor/list` | GET | 是 |
| 报警列表 | `/api/alert/list` | GET | 是 |
| 处理报警 | `/api/alert/handle` | POST | 是 |
| 统计数据 | `/api/stats` | GET | 是 |

## 六、测试说明

### 6.1 使用 Python 测试脚本

```bash
# 测试所有 API 接口
python cloud_server/test_app_api.py

# 交互模式
python cloud_server/test_app_api.py -i
```

### 6.2 使用 curl 测试

```bash
# 健康检查
curl http://8.134.196.56:5000/api/health

# 登录
curl -X POST http://8.134.196.56:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 远程开门
curl -X POST http://8.134.196.56:5000/api/control/unlock \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"device_id":"doorbell_001"}'
```

## 七、常见问题

### 7.1 网络连接失败

检查：
1. 服务器是否运行
2. 防火墙是否开放 5000 端口
3. 设备网络是否正常

### 7.2 Token 过期

Token 有效期为 24 小时，过期后需要重新登录或使用 `/api/auth/refresh` 刷新。

### 7.3 设备不在线

设备需要定期发送心跳（建议 30 秒一次），否则会被标记为离线。

---

**文档版本**: v1.0  
**更新日期**: 2026-04-13
