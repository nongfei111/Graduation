package com.example.smartdoorbell.ui.visitor

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.bumptech.glide.Glide
import com.example.smartdoorbell.R
import com.example.smartdoorbell.data.api.model.VisitorInfo
import com.example.smartdoorbell.databinding.ItemVisitorBinding
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * 访客列表适配器
 *
 * 功能定位索引：
 * - 访客头像加载：Glide.load(imageUrl).circleCrop()
 * - 访客类型展示：member/family -> 家人；其他 -> 陌生人
 * - 时间显示：formatServerTime()（兼容云端时间字符串格式）
 */
class VisitorAdapter(
    private val onItemClick: (VisitorInfo) -> Unit,
    private val onDeleteClick: (VisitorInfo) -> Unit
) : ListAdapter<VisitorInfo, VisitorAdapter.VisitorViewHolder>(VisitorDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VisitorViewHolder {
        val binding = ItemVisitorBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return VisitorViewHolder(binding)
    }

    override fun onBindViewHolder(holder: VisitorViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class VisitorViewHolder(
        private val binding: ItemVisitorBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(visitor: VisitorInfo) {
            binding.tvVisitorName.text = visitor.memberName ?: "陌生访客"
            binding.tvVisitorType.text = when (visitor.visitorType.lowercase()) {
                "member", "family" -> "家人"
                else -> "陌生人"
            }
            binding.tvVisitTime.text = formatServerTime(visitor.createdAt)
            binding.tvConfidence.text = String.format(
                "相似度：%.1f%%",
                (visitor.confidence ?: 0f) * 100
            )
            binding.ivAlert.visibility = if (visitor.isAlert) View.VISIBLE else View.GONE

            val imageUrl = buildImageUrl(visitor.thumbnail ?: visitor.captureImage)
            if (imageUrl != null) {
                Glide.with(binding.root.context)
                    .load(imageUrl)
                    .circleCrop()
                    .placeholder(R.drawable.ic_default_avatar)
                    .error(R.drawable.ic_default_avatar)
                    .into(binding.ivVisitorAvatar)
            } else {
                binding.ivVisitorAvatar.setImageResource(R.drawable.ic_default_avatar)
            }

            binding.root.setOnClickListener {
                onItemClick(visitor)
            }

            binding.btnDelete.setOnClickListener {
                onDeleteClick(visitor)
            }
        }

        private fun buildImageUrl(path: String?): String? {
            if (path.isNullOrBlank()) return null
            return when {
                path.startsWith("http://") || path.startsWith("https://") -> path
                path.startsWith("/uploads/") -> "http://8.134.196.56:5000$path"
                path.startsWith("uploads/") -> "http://8.134.196.56:5000/$path"
                else -> "http://8.134.196.56:5000/uploads/$path"
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

    class VisitorDiffCallback : DiffUtil.ItemCallback<VisitorInfo>() {
        override fun areItemsTheSame(oldItem: VisitorInfo, newItem: VisitorInfo): Boolean {
            return oldItem.id == newItem.id
        }

        override fun areContentsTheSame(oldItem: VisitorInfo, newItem: VisitorInfo): Boolean {
            return oldItem == newItem
        }
    }
}
