package com.example.smartdoorbell.data.api.model

import com.google.gson.annotations.SerializedName

// ==================== 通用响应 ====================

/**
 * 基础响应封装
 *
 * 说明：
 * - 几乎所有 ApiService 接口都最终会落到 BaseResponse / xxxResponse
 * - 如果你想定位“某功能返回字段在哪里定义”，先从 ApiService 找接口，再回到这里找对应 Response/Info 类
 */
data class BaseResponse<T>(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: T?,
    @SerializedName("error") val error: String? = null,
    @SerializedName("message") val message: String? = null
)

// ==================== 认证相关 ====================

/**
 * 登录请求
 */
data class LoginRequest(
    @SerializedName("username") val username: String,
    @SerializedName("password") val password: String
)

/**
 * 登录响应
 * 注意：服务器返回格式为 {success: true, user_id: x, username: xxx, access_token: xxx}
 *
 * 功能定位：
 * - LoginActivity -> AuthRepository.login() -> ApiService.login()
 */
data class LoginResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: LoginData?,
    // 兼容服务器返回的扁平格式
    @SerializedName("user_id") val userId: Int? = null,
    @SerializedName("username") val username: String? = null,
    @SerializedName("access_token") val accessToken: String? = null
) {
    // 提供统一的数据访问
    fun getLoginData(): LoginData? {
        return data ?: run {
            // 如果是扁平格式，构造 LoginData
            if (userId != null && username != null && accessToken != null) {
                LoginData(
                    user = UserInfo(
                        id = userId,
                        username = username,
                        email = null,
                        phone = null,
                        avatar = null,
                        createdAt = ""
                    ),
                    accessToken = accessToken,
                    refreshToken = accessToken // 使用 access_token 作为 refresh_token
                )
            } else {
                null
            }
        }
    }
}

data class LoginData(
    @SerializedName("user") val user: UserInfo,
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String
)

/**
 * 用户信息
 */
data class UserInfo(
    @SerializedName("id") val id: Int,
    @SerializedName("username") val username: String,
    @SerializedName("email") val email: String?,
    @SerializedName("phone") val phone: String?,
    @SerializedName("avatar") val avatar: String?,
    @SerializedName("created_at") val createdAt: String
)

/**
 * 注册请求
 */
data class RegisterRequest(
    @SerializedName("username") val username: String,
    @SerializedName("password") val password: String,
    @SerializedName("email") val email: String? = null,
    @SerializedName("phone") val phone: String? = null
)

/**
 * 注册响应
 *
 * 功能定位：
 * - RegisterActivity -> AuthRepository.register() -> ApiService.register()
 */
data class RegisterResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: LoginData?,
    // 兼容服务器返回的扁平格式
    @SerializedName("user_id") val userId: Int? = null,
    @SerializedName("username") val username: String? = null,
    @SerializedName("access_token") val accessToken: String? = null,
    @SerializedName("email") val email: String? = null
) {
    // 提供统一的数据访问
    fun getLoginData(): LoginData? {
        return data ?: run {
            // 如果是扁平格式，构造 LoginData
            if (userId != null && username != null && accessToken != null) {
                LoginData(
                    user = UserInfo(
                        id = userId,
                        username = username,
                        email = email,
                        phone = null,
                        avatar = null,
                        createdAt = ""
                    ),
                    accessToken = accessToken,
                    refreshToken = accessToken
                )
            } else {
                null
            }
        }
    }
}

/**
 * 刷新 Token 请求
 */
data class RefreshTokenRequest(
    @SerializedName("refresh_token") val refreshToken: String
)

/**
 * 刷新 Token 响应
 */
data class RefreshTokenResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: RefreshTokenData
)

data class RefreshTokenData(
    @SerializedName("access_token") val accessToken: String
)

// ==================== 家庭相关 ====================

data class FamilyListResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: FamilyListData
)

data class FamilyListData(
    @SerializedName("families") val families: List<FamilyInfo>
)

data class FamilyInfo(
    @SerializedName("id") val id: Int,
    @SerializedName("name") val name: String,
    @SerializedName("owner_id") val ownerId: Int,
    @SerializedName("address") val address: String?,
    @SerializedName("device_id") val deviceId: Int?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("member_count") val memberCount: Int = 0,
    @SerializedName("visitor_count") val visitorCount: Int = 0
)

data class FamilyDetailResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: FamilyDetailInfo
)

data class FamilyDetailInfo(
    @SerializedName("id") val id: Int,
    @SerializedName("name") val name: String,
    @SerializedName("owner_id") val ownerId: Int,
    @SerializedName("address") val address: String?,
    @SerializedName("device") val device: DeviceInfo?,
    @SerializedName("member_count") val memberCount: Int,
    @SerializedName("today_visitor_count") val todayVisitorCount: Int
)

data class DeviceInfo(
    @SerializedName("id") val id: Int,
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("device_name") val deviceName: String,
    @SerializedName("device_type") val deviceType: String,
    @SerializedName("ip_address") val ipAddress: String?,
    @SerializedName("is_online") val isOnline: Boolean,
    @SerializedName("last_heartbeat") val lastHeartbeat: String?,
    @SerializedName("firmware_version") val firmwareVersion: String
)

// ==================== 访客相关 ====================

data class VisitorListResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: VisitorListData
)

// 功能定位：
// - VisitorListFragment -> VisitorRepository.getVisitors() -> ApiService.getVisitors()

data class VisitorListData(
    @SerializedName("visitors") val visitors: List<VisitorInfo>,
    @SerializedName("pagination") val pagination: PaginationInfo
)

data class VisitorDetailResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: VisitorInfo
)

data class VisitorInfo(
    @SerializedName("id") val id: Int,
    @SerializedName("family_id") val familyId: Int,
    @SerializedName("visitor_type") val visitorType: String, // "member" 或 "stranger"
    @SerializedName("member_id") val memberId: Int?,
    @SerializedName("member_name") val memberName: String?,
    @SerializedName("capture_image") val captureImage: String?,
    @SerializedName("thumbnail") val thumbnail: String?,
    @SerializedName("confidence") val confidence: Float?,
    @SerializedName("duration") val duration: Int,
    @SerializedName("is_alert") val isAlert: Boolean,
    @SerializedName("alert_reason") val alertReason: String?,
    @SerializedName("created_at") val createdAt: String
)

data class PaginationInfo(
    @SerializedName("page") val page: Int,
    @SerializedName("per_page") val perPage: Int,
    @SerializedName("total") val total: Int,
    @SerializedName("pages") val pages: Int
)

data class TodayVisitorsResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: TodayVisitorsData
)

data class TodayVisitorsData(
    @SerializedName("count") val count: Int,
    @SerializedName("visitors") val visitors: List<VisitorInfo>
)

// ==================== 统计相关 ====================

data class StatisticsResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: StatisticsData? = null,
    @SerializedName("error") val error: String? = null,
    @SerializedName("message") val message: String? = null
)

data class StatisticsData(
    @SerializedName("period") val period: StatisticsPeriod,
    @SerializedName("summary") val summary: StatisticsSummary,
    @SerializedName("daily_stats") val dailyStats: List<DailyStat>
)

data class StatisticsPeriod(
    @SerializedName("days") val days: Int,
    @SerializedName("from") val from: String,
    @SerializedName("to") val to: String
)

data class StatisticsSummary(
    @SerializedName("total_visitors") val totalVisitors: Int,
    @SerializedName("member_visits") val memberVisits: Int,
    @SerializedName("stranger_visits") val strangerVisits: Int,
    @SerializedName("alert_count") val alertCount: Int,
    @SerializedName("today_visitors") val todayVisitors: Int
)

data class DailyStat(
    @SerializedName("date") val date: String,
    @SerializedName("total") val total: Int,
    @SerializedName("member") val member: Int,
    @SerializedName("stranger") val stranger: Int
)

// ==================== 家庭成员相关 ====================

data class MemberListResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: MemberListData
)

data class MemberListData(
    @SerializedName("family_id") val familyId: Int,
    @SerializedName("members") val members: List<MemberInfo>
)

data class MemberInfo(
    @SerializedName("id") val id: Int,
    @SerializedName("family_id") val familyId: Int,
    @SerializedName("name") val name: String,
    @SerializedName("face_image") val faceImage: String?,
    @SerializedName("is_active") val isActive: Boolean,
    @SerializedName("created_at") val createdAt: String
)

data class AddMemberRequest(
    @SerializedName("family_id") val familyId: Int,
    @SerializedName("name") val name: String
)

data class AddMemberResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: MemberInfo
)

data class DeleteMemberResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("message") val message: String
)

data class DeleteVisitorResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("message") val message: String? = null,
    @SerializedName("error") val error: String? = null
)

// ==================== 设备控制相关 ====================

data class UnlockRequest(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("family_id") val familyId: Int? = null
)

data class UnlockResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("command_id") val commandId: Int? = null,
    @SerializedName("message") val message: String? = null,
    @SerializedName("error") val error: String? = null
)

data class DeviceStatusResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: DeviceInfo
)

// ==================== 设备控制新增 ====================

/**
 * 设备状态列表响应（/api/device/status）
 */
data class DeviceStatusListResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("devices") val devices: List<DeviceInfo>
)

/**
 * 注册设备请求
 */
data class RegisterDeviceRequest(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("device_name") val deviceName: String = "智能门铃",
    @SerializedName("user_id") val userId: Int,
    @SerializedName("device_type") val deviceType: String = "raspberry_pi_4b",
    @SerializedName("firmware_version") val firmwareVersion: String = "1.0.0"
)

data class RegisterDeviceResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("message") val message: String
)

/**
 * 心跳请求/响应
 */
data class HeartbeatRequest(
    @SerializedName("device_id") val deviceId: String
)

data class HeartbeatResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("online") val online: Boolean,
    @SerializedName("command") val command: RemoteCommand?
)

data class RemoteCommand(
    @SerializedName("id") val id: Int,
    @SerializedName("type") val type: String,
    @SerializedName("data") val data: Map<String, Any>
)

/**
 * 通用设备请求
 */
data class DeviceRequest(
    @SerializedName("device_id") val deviceId: String
)

/**
 * 警报请求
 */
data class AlertRequest(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("message") val message: String
)

/**
 * 语音请求
 */
data class SpeakRequest(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("message") val message: String
)

/**
 * 命令响应
 */
data class CommandResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("command_id") val commandId: Int? = null,
    @SerializedName("message") val message: String? = null,
    @SerializedName("error") val error: String? = null
)

// ==================== 报警管理 ====================

data class AlertListResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("alerts") val alerts: List<AlertInfo>
)

data class AlertInfo(
    @SerializedName("id") val id: Int,
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("visitor_id") val visitorId: Int?,
    @SerializedName("reason") val reason: String,
    @SerializedName("duration") val duration: Int,
    @SerializedName("handled") val handled: Boolean,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("visitor_type") val visitorType: String?,
    @SerializedName("member_name") val memberName: String?
)

data class HandleAlertRequest(
    @SerializedName("alert_id") val alertId: Int,
    @SerializedName("handled") val handled: Boolean = true
)

// ==================== 黑名单相关 ====================

data class BlacklistResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: BlacklistData?
)

data class BlacklistData(
    @SerializedName("items") val items: List<BlacklistInfo>
)

data class BlacklistInfo(
    @SerializedName("id") val id: Int,
    @SerializedName("name") val name: String,
    @SerializedName("photo") val photo: String?,
    @SerializedName("is_active") val isActive: Boolean,
    @SerializedName("updated_at") val updatedAt: String
)

data class BlacklistAddData(
    @SerializedName("id") val id: Int,
    @SerializedName("photo") val photo: String?
)

// ==================== 健康检查 ====================

data class HealthResponse(
    @SerializedName("status") val status: String,
    @SerializedName("timestamp") val timestamp: String,
    @SerializedName("server") val server: String
)
