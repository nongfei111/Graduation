package com.example.smartdoorbell.data.api

import com.example.smartdoorbell.data.api.model.*
import okhttp3.MultipartBody
import retrofit2.Response
import retrofit2.http.*


interface ApiService {

    // ==================== 认证 ====================
    // 对应 UI：LoginActivity / RegisterActivity
    // 对应 Repository：AuthRepository

    @POST("/api/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>

    @POST("/api/auth/register")
    suspend fun register(@Body request: RegisterRequest): Response<RegisterResponse>

    @POST("/api/auth/refresh")
    suspend fun refreshToken(@Body request: RefreshTokenRequest): Response<RefreshTokenResponse>

    @GET("/api/auth/me")
    suspend fun getCurrentUser(@Header("Authorization") token: String): Response<UserInfo>

    // ==================== 家庭 ====================
    // 对应 UI：登录后加载家庭信息 / 绑定关系
    // 对应 Repository：AuthRepository / FamilyRepository（若存在）

    @GET("/api/family/list")
    suspend fun getFamilies(@Header("Authorization") token: String): Response<FamilyListResponse>

    @GET("/api/family/detail/{familyId}")
    suspend fun getFamilyDetail(
        @Header("Authorization") token: String,
        @Path("familyId") familyId: Int
    ): Response<FamilyDetailResponse>

    // ==================== 访客 ====================
    // 对应 UI：访客列表 VisitorListFragment / 访客详情 VisitorDetailActivity
    // 对应 Repository：VisitorRepository

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

    @DELETE("/api/visitor/{visitorId}/delete")
    suspend fun deleteVisitor(
        @Header("Authorization") token: String,
        @Path("visitorId") visitorId: Int
    ): Response<DeleteVisitorResponse>

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
    // 对应 UI：成员管理 MemberListFragment
    // 对应 Repository：MemberRepository
    // 说明：成员照片上传后会被设备端同步，用于树莓派端人脸识别成员库更新

    @GET("/api/member/list")
    suspend fun getMembers(
        @Header("Authorization") token: String,
        @Query("family_id") familyId: Int
    ): Response<MemberListResponse>

    @Multipart
    @POST("/api/member/add")
    suspend fun addMember(
        @Header("Authorization") token: String,
        @Part("family_id") familyId: Int,
        @Part("name") name: okhttp3.RequestBody,
        @Part photo: MultipartBody.Part?
    ): Response<AddMemberResponse>

    @DELETE("/api/member/{memberId}/delete")
    suspend fun deleteMember(
        @Header("Authorization") token: String,
        @Path("memberId") memberId: Int
    ): Response<DeleteMemberResponse>

    @Multipart
    @PUT("/api/member/{memberId}/photo")
    suspend fun updateMemberPhoto(
        @Header("Authorization") token: String,
        @Path("memberId") memberId: Int,
        @Part photo: MultipartBody.Part
    ): Response<BaseResponse<Unit>>

    // ==================== 设备控制 ====================
    // 对应 UI：HomeFragment（远程开锁/抓拍）
    // 对应 Repository：CommandRepository
    // 说明：这些接口通常只负责“创建命令并投递”，设备端收到命令后再执行并回执

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

    @POST("/api/device/register")
    suspend fun registerDevice(
        @Header("Authorization") token: String,
        @Body request: RegisterDeviceRequest
    ): Response<RegisterDeviceResponse>

    @POST("/api/device/heartbeat")
    suspend fun deviceHeartbeat(
        @Header("Authorization") token: String,
        @Body request: HeartbeatRequest
    ): Response<HeartbeatResponse>

    // ==================== 报警管理 ====================
    // 对应 UI：若有报警列表页/处理页
    // 对应 Repository：AlertRepository（若存在）

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

    // ==================== 统计数据 ====================
    // 对应 UI：首页统计卡片（HomeFragment.loadServerStatistics）

    @GET("/api/stats")
    suspend fun getStatistics(
        @Header("Authorization") token: String
    ): Response<StatisticsResponse>

    // ==================== 黑名单管理 ====================
    // 当前项目中黑名单 UI 可能为历史功能/备用功能
    // 若启用：可用于云端黑名单列表管理，并由设备端同步后执行本地拦截

    @GET("/api/blacklist/list")
    suspend fun getBlacklist(
        @Header("Authorization") token: String
    ): Response<BlacklistResponse>

    @Multipart
    @POST("/api/blacklist/add")
    suspend fun addBlacklist(
        @Header("Authorization") token: String,
        @Part("name") name: okhttp3.RequestBody,
        @Part photo: MultipartBody.Part
    ): Response<BaseResponse<BlacklistAddData>>

    @DELETE("/api/blacklist/{blacklistId}")
    suspend fun deleteBlacklist(
        @Header("Authorization") token: String,
        @Path("blacklistId") blacklistId: Int
    ): Response<BaseResponse<Unit>>

    // ==================== 设备重启 ====================

    @POST("/api/control/restart")
    suspend fun restartDevice(
        @Header("Authorization") token: String,
        @Body request: DeviceRequest
    ): Response<CommandResponse>

    // ==================== 健康检查 ====================

    @GET("/api/health")
    suspend fun healthCheck(): Response<HealthResponse>
}
