package com.example.smartdoorbell.data.repository

import com.example.smartdoorbell.data.PreferencesManager
import com.example.smartdoorbell.data.api.ApiService
import com.example.smartdoorbell.data.api.model.*
import com.example.smartdoorbell.util.Constants
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File

/**
 * 认证 Repository
 * 处理登录、注册、Token 刷新等逻辑
 *
 * Repository 层说明（如何快速定位功能代码）：
 * - 登录：AuthRepository.login()
 * - 注册：AuthRepository.register()
 * - 加载家庭 ID：AuthRepository.loadFamilyId()（用于访客列表/成员管理/统计等接口的 family_id）
 * - 远程开锁：CommandRepository.unlock()（调用 ApiService.unlock -> /api/control/unlock）
 * - 远程抓拍：CommandRepository.remoteSnapshot()（调用 ApiService.remoteSnapshot -> /api/control/snapshot）
 * - 访客列表：VisitorRepository.getVisitors()（调用 ApiService.getVisitors -> /api/visitor/list）
 * - 成员管理：MemberRepository.getMembers/addMember/updateMemberPhoto/deleteMember（调用 /api/member/*）
 *
 * 习惯用法：UI(Fragment/Activity) 只调用 Repository，不直接拼 URL、不直接处理 token。
 */
class AuthRepository(
    private val apiService: ApiService,
    private val preferencesManager: PreferencesManager
) {

    /**
     * 登录
     */
    suspend fun login(username: String, password: String): Result<LoginData> {
        return try {
            val response = apiService.login(LoginRequest(username, password))
            if (response.isSuccessful) {
                val body = response.body()
                // 使用新的 getLoginData() 方法兼容两种格式
                val loginData = body?.getLoginData()
                if (loginData != null) {
                    // 保存 Token 和用户信息
                    preferencesManager.saveLoginInfo(
                        accessToken = loginData.accessToken,
                        refreshToken = loginData.refreshToken,
                        userId = loginData.user.id,
                        familyId = -1 // 登录后需要获取家庭列表
                    )
                    Result.success(loginData)
                } else {
                    Result.failure(Exception("登录响应数据为空"))
                }
            } else {
                val errorMsg = response.errorBody()?.string() ?: "登录失败"
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 注册
     */
    suspend fun register(username: String, password: String, email: String? = null): Result<LoginData> {
        return try {
            val response = apiService.register(RegisterRequest(username, password, email))
            if (response.isSuccessful) {
                val body = response.body()
                // 使用新的 getLoginData() 方法兼容两种格式
                val loginData = body?.getLoginData()
                if (loginData != null) {
                    preferencesManager.saveLoginInfo(
                        accessToken = loginData.accessToken,
                        refreshToken = loginData.refreshToken,
                        userId = loginData.user.id,
                        familyId = -1
                    )
                    Result.success(loginData)
                } else {
                    Result.failure(Exception("注册响应数据为空"))
                }
            } else {
                val errorMsg = response.errorBody()?.string() ?: "注册失败"
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 刷新 Token
     */
    suspend fun refreshToken(): Result<String> {
        return try {
            val refreshToken = preferencesManager.refreshToken
            if (refreshToken.isNullOrEmpty()) {
                return Result.failure(Exception("Refresh Token 不存在"))
            }

            val response = apiService.refreshToken(RefreshTokenRequest(refreshToken))
            if (response.isSuccessful) {
                val newAccessToken = response.body()?.data?.accessToken
                if (newAccessToken != null) {
                    preferencesManager.accessToken = newAccessToken
                    Result.success(newAccessToken)
                } else {
                    Result.failure(Exception("刷新 Token 响应为空"))
                }
            } else {
                Result.failure(Exception("刷新 Token 失败"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 获取当前用户信息
     */
    suspend fun getCurrentUser(): Result<UserInfo> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.getCurrentUser(token)
            if (response.isSuccessful) {
                val userInfo = response.body()
                if (userInfo != null) {
                    Result.success(userInfo)
                } else {
                    Result.failure(Exception("用户信息为空"))
                }
            } else {
                Result.failure(Exception("获取用户信息失败"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 退出登录
     */
    fun logout() {
        preferencesManager.clearLoginInfo()
    }

    /**
     * 获取家庭列表并设置默认家庭 ID
     */
    suspend fun loadFamilyId(): Result<Int> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.getFamilies(token)
            if (response.isSuccessful) {
                val data = response.body()?.data
                if (data != null && data.families.isNotEmpty()) {
                    // 使用第一个家庭的 ID
                    val familyId = data.families.first().id
                    preferencesManager.familyId = familyId
                    Result.success(familyId)
                } else {
                    Result.failure(Exception("没有家庭信息"))
                }
            } else {
                Result.failure(Exception("获取家庭列表失败"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

/**
 * 访客 Repository
 */
class VisitorRepository(
    private val apiService: ApiService,
    private val preferencesManager: PreferencesManager
) {

    /**
     * 获取访客列表
     */
    suspend fun getVisitors(
        familyId: Int,
        page: Int = 1,
        perPage: Int = Constants.DEFAULT_PAGE_SIZE,
        visitorType: String? = null,
        isAlert: Boolean? = null
    ): Result<VisitorListData> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.getVisitors(token, familyId, page, perPage, visitorType, isAlert)
            if (response.isSuccessful) {
                val data = response.body()?.data
                if (data != null) {
                    // 返回数据（允许空列表）
                    Result.success(data)
                } else {
                    // 返回空数据结构
                    Result.success(VisitorListData(
                        visitors = emptyList(),
                        pagination = PaginationInfo(page = page, perPage = perPage, total = 0, pages = 0)
                    ))
                }
            } else {
                val errorMsg = response.errorBody()?.string() ?: "获取失败"
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 获取访客详情
     */
    suspend fun getVisitorDetail(visitorId: Int): Result<VisitorInfo> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.getVisitorDetail(token, visitorId)
            if (response.isSuccessful) {
                val data = response.body()?.data
                if (data != null) {
                    Result.success(data)
                } else {
                    Result.failure(Exception("访客详情为空"))
                }
            } else {
                Result.failure(Exception("获取失败"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteVisitor(visitorId: Int): Result<Unit> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.deleteVisitor(token, visitorId)
            val body = response.body()
            if (response.isSuccessful && body?.success == true) {
                Result.success(Unit)
            } else {
                val msg = body?.error
                    ?: body?.message
                    ?: response.errorBody()?.string()
                    ?: "删除失败"
                Result.failure(Exception(msg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 获取统计数据
     */
    suspend fun getStatistics(familyId: Int, days: Int = 7): Result<StatisticsData> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.getStatistics(token)
            val body = response.body()
            if (response.isSuccessful && body?.success == true) {
                val data = body.data
                if (data != null) return Result.success(data)
            }

            val msg = body?.error
                ?: body?.message
                ?: response.errorBody()?.string()
                ?: "获取统计失败"
            Result.failure(Exception(msg))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 获取今日访客
     */
    suspend fun getTodayVisitors(familyId: Int): Result<TodayVisitorsData> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.getTodayVisitors(token, familyId)
            if (response.isSuccessful) {
                val data = response.body()?.data
                if (data != null) {
                    Result.success(data)
                } else {
                    Result.failure(Exception("今日访客列表为空"))
                }
            } else {
                Result.failure(Exception("获取失败"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

/**
 * 家庭成员 Repository
 */
class MemberRepository(
    private val apiService: ApiService,
    private val preferencesManager: PreferencesManager
) {

    /**
     * 获取成员列表
     */
    suspend fun getMembers(familyId: Int): Result<MemberListData> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.getMembers(token, familyId)
            if (response.isSuccessful) {
                val data = response.body()?.data
                if (data != null) {
                    Result.success(data)
                } else {
                    // 返回空数据结构而不是错误
                    Result.success(MemberListData(
                        familyId = familyId,
                        members = emptyList()
                    ))
                }
            } else {
                val errorMsg = response.errorBody()?.string() ?: "获取失败"
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 添加成员（支持上传照片）
     */
    suspend fun addMember(familyId: Int, name: String, photoFile: File? = null): Result<MemberInfo> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))

            val photoPart = if (photoFile != null && photoFile.exists()) {
                val requestFile = photoFile.asRequestBody("image/jpeg".toMediaType())
                MultipartBody.Part.createFormData("photo", photoFile.name, requestFile)
            } else {
                null
            }

            val nameBody = name.toRequestBody("text/plain".toMediaType())
            val response = apiService.addMember(token, familyId, nameBody, photoPart)
            if (response.isSuccessful) {
                val data = response.body()?.data
                if (data != null) {
                    Result.success(data)
                } else {
                    Result.failure(Exception("添加失败：响应数据为空"))
                }
            } else {
                val errorMsg = response.errorBody()?.string() ?: "添加失败"
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 更新成员照片
     */
    suspend fun updateMemberPhoto(memberId: Int, photoFile: File): Result<Unit> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))

            val requestFile = photoFile.asRequestBody("image/jpeg".toMediaType())
            val photoPart = MultipartBody.Part.createFormData("photo", photoFile.name, requestFile)

            val response = apiService.updateMemberPhoto(token, memberId, photoPart)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                val errorMsg = response.errorBody()?.string() ?: "上传失败"
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 删除成员
     */
    suspend fun deleteMember(memberId: Int): Result<Unit> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.deleteMember(token, memberId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                val errorMsg = response.errorBody()?.string() ?: "删除失败"
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

/**
 * 设备控制 Repository
 */
class CommandRepository(
    private val apiService: ApiService,
    private val preferencesManager: PreferencesManager
) {
    private fun parseErrorMessage(raw: String?): String? {
        val s = raw?.trim()?.takeIf { it.isNotEmpty() } ?: return null
        return try {
            val obj = org.json.JSONObject(s)
            when {
                obj.has("error") -> obj.optString("error").takeIf { it.isNotBlank() }
                obj.has("message") -> obj.optString("message").takeIf { it.isNotBlank() }
                else -> s
            }
        } catch (_: Exception) {
            s
        }
    }

    /**
     * 远程开锁
     */
    suspend fun unlock(deviceId: String, familyId: Int? = null): Result<UnlockResponse> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.unlock(token, UnlockRequest(deviceId, familyId))
            val body = response.body()
            if (response.isSuccessful && body?.success == true) return Result.success(body)

            val msg = body?.error
                ?: body?.message
                ?: parseErrorMessage(response.errorBody()?.string())
                ?: "开锁失败"
            Result.failure(Exception(msg))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 远程警报
     */
    suspend fun remoteAlert(deviceId: String, message: String): Result<CommandResponse> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.remoteAlert(token, AlertRequest(deviceId, message))
            val body = response.body()
            if (response.isSuccessful && body?.success == true) return Result.success(body)

            val msg = body?.error
                ?: body?.message
                ?: parseErrorMessage(response.errorBody()?.string())
                ?: "警报失败"
            Result.failure(Exception(msg))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 远程语音
     */
    suspend fun remoteSpeak(deviceId: String, message: String): Result<CommandResponse> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.remoteSpeak(token, SpeakRequest(deviceId, message))
            val body = response.body()
            if (response.isSuccessful && body?.success == true) return Result.success(body)

            val msg = body?.error
                ?: body?.message
                ?: parseErrorMessage(response.errorBody()?.string())
                ?: "语音失败"
            Result.failure(Exception(msg))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 远程抓拍
     */
    suspend fun remoteSnapshot(deviceId: String): Result<CommandResponse> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.remoteSnapshot(token, DeviceRequest(deviceId))
            val body = response.body()
            if (response.isSuccessful && body?.success == true) return Result.success(body)

            val msg = body?.error
                ?: body?.message
                ?: parseErrorMessage(response.errorBody()?.string())
                ?: "抓拍失败"
            Result.failure(Exception(msg))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 获取设备状态列表
     */
    suspend fun getDeviceStatusList(): Result<List<DeviceInfo>> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.getDeviceStatus(token)
            if (response.isSuccessful) {
                val data = response.body()
                if (data != null && data.success) {
                    Result.success(data.devices)
                } else {
                    Result.failure(Exception("获取设备状态失败"))
                }
            } else {
                val msg = parseErrorMessage(response.errorBody()?.string()) ?: "获取失败"
                Result.failure(Exception(msg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 获取统计数据
     */
    suspend fun getStatistics(): Result<StatisticsData> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.getStatistics(token)
            val body = response.body()
            if (response.isSuccessful && body?.success == true) {
                val data = body.data
                if (data != null) return Result.success(data)
            }

            val msg = body?.error
                ?: body?.message
                ?: parseErrorMessage(response.errorBody()?.string())
                ?: "获取统计失败"
            Result.failure(Exception(msg))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 重启设备
     */
    suspend fun restartDevice(deviceId: String): Result<CommandResponse> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.restartDevice(token, DeviceRequest(deviceId))
            val body = response.body()
            if (response.isSuccessful && body?.success == true) return Result.success(body)

            val msg = body?.error
                ?: body?.message
                ?: parseErrorMessage(response.errorBody()?.string())
                ?: "重启失败"
            Result.failure(Exception(msg))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

/**
 * 黑名单 Repository
 */
class BlacklistRepository(
    private val apiService: ApiService,
    private val preferencesManager: PreferencesManager
) {
    /**
     * 获取黑名单列表
     */
    suspend fun getBlacklist(): Result<List<BlacklistInfo>> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.getBlacklist(token)
            if (response.isSuccessful) {
                val data = response.body()?.data
                if (data != null) {
                    Result.success(data.items)
                } else {
                    Result.success(emptyList())
                }
            } else {
                val errorMsg = response.errorBody()?.string() ?: "获取失败"
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 添加黑名单
     */
    suspend fun addBlacklist(name: String, photoFile: File): Result<Unit> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))

            val requestFile = photoFile.asRequestBody("image/jpeg".toMediaType())
            val photoPart = MultipartBody.Part.createFormData("photo", photoFile.name, requestFile)
            val nameBody = name.toRequestBody("text/plain".toMediaType())

            val response = apiService.addBlacklist(token, nameBody, photoPart)
            val body = response.body()
            if (response.isSuccessful && body?.success == true) Result.success(Unit)
            else {
                val msg = body?.error ?: body?.message ?: response.errorBody()?.string() ?: "添加失败"
                Result.failure(Exception(msg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 删除黑名单
     */
    suspend fun deleteBlacklist(blacklistId: Int): Result<Unit> {
        return try {
            val token = preferencesManager.getAuthHeader() ?: return Result.failure(Exception("未登录"))
            val response = apiService.deleteBlacklist(token, blacklistId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                val errorMsg = response.errorBody()?.string() ?: "删除失败"
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
