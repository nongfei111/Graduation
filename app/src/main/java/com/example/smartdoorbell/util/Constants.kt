package com.example.smartdoorbell.util

/**
 * 常量定义
 *
 * 功能定位索引：
 * - 云端地址：BASE_URL（RetrofitClient / 各 Repository 会用到）
 * - Token 存储键：PREF_*（PreferencesManager）
 * - 底部导航 tag：TAG_*（MainActivity / Fragment 切换时可用）
 */
object Constants {

    // 服务器地址（请根据实际情况修改）
    // 本地测试：http://192.168.1.100:5000
    // 阿里云：http://8.134.196.56:5000
    const val BASE_URL = "http://8.134.196.56:5000"

    // 网络超时
    const val CONNECT_TIMEOUT = 30L
    const val READ_TIMEOUT = 30L
    const val WRITE_TIMEOUT = 30L

    // 分页
    const val DEFAULT_PAGE_SIZE = 20

    // 图片压缩质量
    const val IMAGE_COMPRESS_QUALITY = 80

    // SharedPreferences 键
    const val PREF_ACCESS_TOKEN = "access_token"
    const val PREF_REFRESH_TOKEN = "refresh_token"
    const val PREF_USER_ID = "user_id"
    const val PREF_FAMILY_ID = "family_id"
    const val PREF_DEVICE_ID = "device_id"

    // 请求码
    const val REQUEST_CAMERA = 1001
    const val REQUEST_GALLERY = 1002

    // Fragment Tag
    const val TAG_HOME = "home"
    const val TAG_VISITOR = "visitor"
    const val TAG_MEMBER = "member"
    const val TAG_SETTINGS = "settings"
}
