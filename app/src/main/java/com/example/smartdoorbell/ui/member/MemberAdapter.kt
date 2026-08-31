package com.example.smartdoorbell.ui.member

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.bumptech.glide.Glide
import com.example.smartdoorbell.data.api.model.MemberInfo
import com.example.smartdoorbell.databinding.ItemMemberBinding

/**
 * 成员列表适配器
 */
class MemberAdapter(
    private val onUploadPhotoClick: (MemberInfo) -> Unit,
    private val onDeleteClick: (MemberInfo) -> Unit
) : ListAdapter<MemberInfo, MemberAdapter.MemberViewHolder>(MemberDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): MemberViewHolder {
        val binding = ItemMemberBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return MemberViewHolder(binding)
    }

    override fun onBindViewHolder(holder: MemberViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class MemberViewHolder(
        private val binding: ItemMemberBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(member: MemberInfo) {
            binding.tvMemberName.text = member.name

            // 成员状态
            binding.tvMemberStatus.text = if (member.isActive) "已激活" else "已禁用"
            binding.tvMemberStatus.setTextColor(
                if (member.isActive)
                    binding.root.context.getColor(com.example.smartdoorbell.R.color.green)
                else
                    binding.root.context.getColor(com.example.smartdoorbell.R.color.gray)
            )

            // 加载成员照片（从服务器 URL）
            // 服务器返回的 face_image 是完整 URL 路径
            val photoUrl = member.faceImage
            if (!photoUrl.isNullOrEmpty()) {
                // 如果是完整 URL，直接使用；否则拼接服务器地址
                val imageUrl = if (photoUrl.startsWith("http")) {
                    photoUrl
                } else {
                    // 服务器路径如：/home/smart_doorbell/server/uploads/members/xxx.jpg
                    // 需要转换为 HTTP URL
                    "http://8.134.196.56:5000${photoUrl.replace("/home/smart_doorbell/server", "")}"
                }
                Glide.with(binding.root.context)
                    .load(imageUrl)
                    .circleCrop()
                    .placeholder(com.example.smartdoorbell.R.drawable.ic_default_avatar)
                    .error(com.example.smartdoorbell.R.drawable.ic_default_avatar)
                    .into(binding.ivMemberAvatar)
            } else {
                binding.ivMemberAvatar.setImageResource(com.example.smartdoorbell.R.drawable.ic_default_avatar)
            }

            // 上传照片按钮点击
            binding.btnUploadPhoto.setOnClickListener {
                onUploadPhotoClick(member)
            }

            // 删除按钮点击
            binding.btnDelete.setOnClickListener {
                onDeleteClick(member)
            }
        }
    }

    class MemberDiffCallback : DiffUtil.ItemCallback<MemberInfo>() {
        override fun areItemsTheSame(oldItem: MemberInfo, newItem: MemberInfo): Boolean {
            return oldItem.id == newItem.id
        }

        override fun areContentsTheSame(oldItem: MemberInfo, newItem: MemberInfo): Boolean {
            return oldItem.name == newItem.name &&
                    oldItem.isActive == newItem.isActive &&
                    oldItem.faceImage == newItem.faceImage
        }
    }
}
