package com.example.smartdoorbell.ui.visitor

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.bumptech.glide.Glide
import com.example.smartdoorbell.R
import com.example.smartdoorbell.data.api.model.VisitorInfo
import com.example.smartdoorbell.databinding.ActivityVisitorDetailBinding
import com.google.gson.Gson
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * 访客详情界面
 */
class VisitorDetailActivity : AppCompatActivity() {

    private lateinit var binding: ActivityVisitorDetailBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityVisitorDetailBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        binding.toolbar.setNavigationOnClickListener {
            finish()
        }

        // 获取传递的访客数据（使用 JSON 序列化）
        val visitorJson = intent.getStringExtra("visitor_json")
        if (visitorJson != null) {
            val visitor = Gson().fromJson(visitorJson, VisitorInfo::class.java)
            showVisitorDetail(visitor)
        }
    }

    private fun showVisitorDetail(visitor: VisitorInfo) {
        supportActionBar?.title = visitor.memberName ?: "陌生访客"

        binding.tvVisitorName.text = visitor.memberName ?: "陌生访客"
        binding.tvVisitorType.text = if (visitor.visitorType == "member") "家人" else "陌生人"
        binding.tvVisitTime.text = formatServerTime(visitor.createdAt)
        binding.tvConfidence.text = String.format("相似度：%.1f%%", (visitor.confidence ?: 0f) * 100)
        binding.tvDuration.text = String.format("停留时长：%d 秒", visitor.duration)
        binding.tvAlertReason.text = visitor.alertReason ?: "无"

        // 加载大图
        visitor.captureImage?.let { imageUrl ->
            val fullUrl = "http://8.134.196.56:5000/uploads/${imageUrl}"
            Glide.with(this)
                .load(fullUrl)
                .placeholder(R.drawable.ic_default_avatar)
                .error(R.drawable.ic_default_avatar)
                .into(binding.ivVisitorImage)
        }
    }

    private fun formatServerTime(raw: String?): String {
        if (raw.isNullOrBlank()) return "--"
        val candidates = listOf(
            "yyyy-MM-dd HH:mm:ss",
            "yyyy-MM-dd'T'HH:mm:ss",
            "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
            "yyyy-MM-dd'T'HH:mm:ss'Z'"
        )
        for (pattern in candidates) {
            try {
                val parser = SimpleDateFormat(pattern, Locale.getDefault())
                if (pattern.contains("'Z'")) {
                    parser.timeZone = TimeZone.getTimeZone("UTC")
                }
                val date: Date = parser.parse(raw) ?: continue
                val formatter = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())
                formatter.timeZone = TimeZone.getDefault()
                return formatter.format(date)
            } catch (_: Exception) {
            }
        }
        return raw
    }
}
