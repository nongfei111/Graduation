package com.example.smartdoorbell

import android.app.Application
import android.util.Log
import com.example.smartdoorbell.data.PreferencesManager

/**
 * Application 类
 * 全局初始化
 *
 * 功能定位索引：
 * - 全局 SharedPreferences（Token / userId / familyId）：preferencesManager
 * - 登录态判断：PreferencesManager.isLoggedIn（LoginActivity 会用）
 */
class MyApp : Application() {

    companion object {
        const val TAG = "SmartDoorbell"
        lateinit var instance: MyApp
            private set
    }

    lateinit var preferencesManager: PreferencesManager
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this
        preferencesManager = PreferencesManager(this)
        Log.i(TAG, "Application 启动")
    }
}
