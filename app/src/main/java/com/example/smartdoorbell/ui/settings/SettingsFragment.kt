package com.example.smartdoorbell.ui.settings

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.appcompat.app.AlertDialog
import androidx.fragment.app.Fragment
import com.example.smartdoorbell.MyApp
import com.example.smartdoorbell.ui.login.LoginActivity
import com.example.smartdoorbell.databinding.FragmentSettingsBinding

/**
 * 设置 Fragment
 *
 * 功能定位索引：
 * - 退出登录：showLogoutDialog() -> doLogout() -> PreferencesManager.clearLoginInfo() -> LoginActivity
 */
class SettingsFragment : Fragment() {

    private var _binding: FragmentSettingsBinding? = null
    private val binding get() = _binding!!

    private lateinit var preferencesManager: MyApp

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentSettingsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        preferencesManager = requireActivity().application as MyApp

        // 显示用户名
        val username = preferencesManager.preferencesManager.userId
        binding.tvUsername.text = "用户 ID: $username"

        setupClickListeners()
    }

    private fun setupClickListeners() {
        // 退出登录
        binding.btnLogout.setOnClickListener {
            showLogoutDialog()
        }
    }

    private fun showLogoutDialog() {
        AlertDialog.Builder(requireContext())
            .setTitle("退出登录")
            .setMessage("确定要退出登录吗？")
            .setPositiveButton("确定") { _, _ ->
                doLogout()
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun doLogout() {
        // 清除 Token
        preferencesManager.preferencesManager.clearLoginInfo()

        // 跳转到登录页
        val intent = Intent(requireContext(), LoginActivity::class.java)
        intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        startActivity(intent)
        requireActivity().finish()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
