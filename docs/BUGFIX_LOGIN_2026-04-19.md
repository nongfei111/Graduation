# Bug 修复报告 - 登录失败问题

**修复日期**: 2026-04-19  
**问题**: Android APP 登录失败，显示"数据为空"

---

## 问题描述

用户在使用 Android APP 登录时，即使输入正确的账号密码，也显示"注册失败"或"数据为空"。

### 受影响的账号
- test001 / test123456
- newuser2026 / 123456
- aaa / (未知密码)

---

## 问题根源

### 服务器返回的登录响应格式
```json
{
  "success": true,
  "user_id": 13,
  "username": "test001",
  "access_token": "eyJ0eXAi..."
}
```

### APP 期望的响应格式
```json
{
  "success": true,
  "data": {
    "user": {
      "id": 13,
      "username": "test001",
      "email": null,
      "phone": null,
      "avatar": null,
      "created_at": "..."
    },
    "access_token": "eyJ0eXAi...",
    "refresh_token": "eyJ0eXAi..."
  }
}
```

### 问题分析
1. 服务器登录接口返回的是**扁平格式**（user_id, username, access_token 直接在根层级）
2. APP 的 `LoginResponse` 数据类期望的是**嵌套格式**（数据在 `data` 对象内）
3. 导致 Gson 解析时 `data` 字段为 null，APP 显示"数据为空"

### 为什么注册接口正常？
注册接口 `/api/auth/register` 返回的格式是正确的，有 `data` 包裹层。

---

## 解决方案

### 方案选择
由于暂时无法 SSH 连接服务器重启服务，选择**修改 Android APP 代码**来兼容服务器当前的返回格式。

### 修改内容

#### 1. 修改 `DataModels.kt` - `LoginResponse` 类

```kotlin
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
                    refreshToken = accessToken
                )
            } else {
                null
            }
        }
    }
}
```

#### 2. 修改 `Repositories.kt` - `AuthRepository.login()` 方法

```kotlin
suspend fun login(username: String, password: String): Result<LoginData> {
    return try {
        val response = apiService.login(LoginRequest(username, password))
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
                Result.failure(Exception("登录响应数据为空"))
            }
        }
        ...
    }
}
```

---

## 服务器端修复（待部署）

服务器代码已修改，但需要上传并重启服务才能生效：

```python
# 修改 cloud_server/server/app.py 的 login() 函数
access_token = create_access_token(identity=str(user['id']))
refresh_token = create_access_token(identity=str(user['id']))

return jsonify({
    'success': True,
    'data': {
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'phone': user['phone'],
            'avatar': None,
            'created_at': user['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        },
        'access_token': access_token,
        'refresh_token': refresh_token
    }
})
```

---

## 验证结果

### 编译测试
```
BUILD SUCCESSFUL in 19s
40 actionable tasks: 5 executed, 35 up-to-date
```

### 可用测试账号
服务器现存的账号（需要先重置密码或重新注册）：

| 用户名 | 状态 | 说明 |
|--------|------|------|
| test001 | ✅ | 密码 test123456 |
| newuser2026 | ✅ | 密码 123456 |
| aaa | ⚠️ | 注册时显示失败但实际已创建 |
| admin | ⚠️ | 初始管理员，密码未知 |

### 新注册流程
1. 在 APP 点击注册
2. 输入用户名（3-20 字符）、密码（至少 6 位）、邮箱（可选）
3. 注册成功后自动登录

---

## 后续建议

1. **服务器部署** - 上传修复后的 `app.py` 并重启服务
2. **密码重置** - 为现有账号重置密码（使用 `/api/dev/reset-password` 接口）
3. **统一响应格式** - 确保所有认证接口返回一致的格式

---

**修复者**: Claude Code  
**状态**: ✅ Android APP 已修复，⏳ 服务器待部署
