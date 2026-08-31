package com.example.smartdoorbell.ui.member

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.bumptech.glide.Glide
import com.example.smartdoorbell.R
import com.example.smartdoorbell.data.api.model.BlacklistInfo

class BlacklistAdapter(
    private val onDeleteClick: (BlacklistInfo) -> Unit
) : ListAdapter<BlacklistInfo, BlacklistAdapter.BlacklistViewHolder>(BlacklistDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): BlacklistViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_blacklist, parent, false)
        return BlacklistViewHolder(view)
    }

    override fun onBindViewHolder(holder: BlacklistViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class BlacklistViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val ivPhoto: ImageView = itemView.findViewById(R.id.iv_blacklist_photo)
        private val tvName: TextView = itemView.findViewById(R.id.tv_blacklist_name)
        private val btnDelete: ImageButton = itemView.findViewById(R.id.btn_delete_blacklist)

        fun bind(item: BlacklistInfo) {
            tvName.text = item.name

            if (!item.photo.isNullOrEmpty()) {
                Glide.with(itemView.context)
                    .load(item.photo)
                    .circleCrop()
                    .placeholder(R.drawable.ic_default_avatar)
                    .error(R.drawable.ic_default_avatar)
                    .into(ivPhoto)
            } else {
                ivPhoto.setImageResource(R.drawable.ic_default_avatar)
            }

            btnDelete.setOnClickListener {
                onDeleteClick(item)
            }
        }
    }

    class BlacklistDiffCallback : DiffUtil.ItemCallback<BlacklistInfo>() {
        override fun areItemsTheSame(oldItem: BlacklistInfo, newItem: BlacklistInfo): Boolean {
            return oldItem.id == newItem.id
        }

        override fun areContentsTheSame(oldItem: BlacklistInfo, newItem: BlacklistInfo): Boolean {
            return oldItem == newItem
        }
    }
}
