package com.example.smartdoorbell.data.api

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Retrofit 网络客户端
 * 单例模式，提供 ApiService 实例
 *
 * 功能定位索引：
 * - 全部接口定义：ApiService.kt
 * - BaseUrl 来源：Constants.BASE_URL（或 HomeFragment/VisitorListFragment 等处临时写死的 URL）
 * - 调试请求日志：HttpLoggingInterceptor（抓接口问题时最常用）
 */
object RetrofitClient {

    private var retrofit: Retrofit? = null
    private var apiService: ApiService? = null

    /**
     * 获取 ApiService 实例
     */
    fun getApiService(baseUrl: String): ApiService {
        if (apiService == null) {
            retrofit = createRetrofit(baseUrl)
            apiService = retrofit?.create(ApiService::class.java)
        }
        return apiService!!
    }

    /**
     * 创建 Retrofit 实例
     */
    private fun createRetrofit(baseUrl: String): Retrofit {
        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        val okHttpClient = OkHttpClient.Builder()
            .addInterceptor(loggingInterceptor)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()

        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    /**
     * 创建新的 ApiService（用于切换服务器）
     */
    fun createNewApiService(baseUrl: String): ApiService {
        val newRetrofit = createRetrofit(baseUrl)
        return newRetrofit.create(ApiService::class.java)
    }
}
