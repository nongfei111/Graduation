package com.example.smartdoorbell.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.example.smartdoorbell.util.Constants

/**
 * SharedPreferences 管理器
 * 安全存储 Token 等敏感信息
 *
 * 功能定位索引：
 * - 登录态判断：isLoggedIn
 * - Authorization 头：getAuthHeader()（Repository 调接口时统一从这里取）
 * - 退出登录清理：clearLoginInfo()（SettingsFragment -> 退出登录）
 */
class PreferencesManager(private val context: Context) {

    private lateinit var prefs: SharedPreferences

    init {
        // 使用加密 SharedPreferences（Android 10+ 需要）
        try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            prefs = EncryptedSharedPreferences.create(
                context,
                "secure_prefs",
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) {
            // 降级到普通 SharedPreferences
            prefs = context.getSharedPreferences("smart_doorbell_prefs", Context.MODE_PRIVATE)
        }
    }

    // ==================== Token 管理 ====================
    // 对应云端：JWT access_token / refresh_token

    var accessToken: String?
        get() = prefs.getString(Constants.PREF_ACCESS_TOKEN, null)
        set(value) = prefs.edit().putString(Constants.PREF_ACCESS_TOKEN, value).apply()

    var refreshToken: String?
        get() = prefs.getString(Constants.PREF_REFRESH_TOKEN, null)
        set(value) = prefs.edit().putString(Constants.PREF_REFRESH_TOKEN, value).apply()

    // ==================== 用户信息 ====================

    var userId: Int
        get() = prefs.getInt(Constants.PREF_USER_ID, -1)
        set(value) = prefs.edit().putInt(Constants.PREF_USER_ID, value).apply()

    var familyId: Int
        get() = prefs.getInt(Constants.PREF_FAMILY_ID, -1)
        set(value) = prefs.edit().putInt(Constants.PREF_FAMILY_ID, value).apply()

    var deviceId: String?
        get() = prefs.getString(Constants.PREF_DEVICE_ID, null)
        set(value) = prefs.edit().putString(Constants.PREF_DEVICE_ID, value).apply()

    // ==================== 登录状态 ====================

    val isLoggedIn: Boolean
        get() = !accessToken.isNullOrEmpty() && userId != -1

    /**
     * 保存登录信息
     */
    fun saveLoginInfo(accessToken: String, refreshToken: String, userId: Int, familyId: Int) {
        this.accessToken = accessToken
        this.refreshToken = refreshToken
        this.userId = userId
        this.familyId = familyId
    }

    /**
     * 清除登录信息（退出登录）
     */
    fun clearLoginInfo() {
        prefs.edit().apply {
            remove(Constants.PREF_ACCESS_TOKEN)
            remove(Constants.PREF_REFRESH_TOKEN)
            remove(Constants.PREF_USER_ID)
            remove(Constants.PREF_FAMILY_ID)
        }.apply()
    }

    /**
     * 获取授权头
     */
    fun getAuthHeader(): String? {
        return accessToken?.let { "Bearer $it" }
    }
}
