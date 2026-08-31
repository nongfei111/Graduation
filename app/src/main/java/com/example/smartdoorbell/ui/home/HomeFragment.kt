package com.example.smartdoorbell.ui.home

import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.example.smartdoorbell.MyApp
import com.example.smartdoorbell.data.api.RetrofitClient
import com.example.smartdoorbell.data.repository.CommandRepository
import com.example.smartdoorbell.data.repository.VisitorRepository
import com.example.smartdoorbell.databinding.FragmentHomeBinding
import kotlinx.coroutines.launch

private const val TAG = "SmartDoorbell.Home"

/**
 * 首页 Fragment
 * 显示统计数据、快捷操作
 *
 * 功能定位索引：
 * - 统计卡片：loadStatistics() / loadServerStatistics()
 * - 设备绑定与在线状态：loadDeviceStatus()
 * - 远程开锁：showUnlockDialog() -> doUnlock() -> CommandRepository.unlock() -> ApiService.unlock(/api/control/unlock)
 * - 远程抓拍：doSnapshot() -> CommandRepository.remoteSnapshot() -> ApiService.remoteSnapshot(/api/control/snapshot)
 */
class HomeFragment : Fragment() {

    private var _binding: FragmentHomeBinding? = null
    private val binding get() = _binding!!

    private lateinit var visitorRepository: VisitorRepository
    private lateinit var commandRepository: CommandRepository
    private lateinit var preferencesManager: MyApp

    // 当前设备 ID
    private var currentDeviceId: String? = null

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentHomeBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        Log.d(TAG, "onViewCreated called")

        preferencesManager = requireActivity().application as MyApp
        val apiService = RetrofitClient.getApiService("http://8.134.196.56:5000/")
        visitorRepository = VisitorRepository(apiService, preferencesManager.preferencesManager)
        commandRepository = CommandRepository(apiService, preferencesManager.preferencesManager)
        Log.d(TAG, "Repositories initialized, familyId=${preferencesManager.preferencesManager.familyId}")

        loadStatistics()
        loadDeviceStatus()
        setupClickListeners()
    }

    private fun setControlsEnabled(enabled: Boolean) {
        binding.btnUnlock.isEnabled = enabled
        binding.btnSnapshot.isEnabled = enabled
    }

    private fun loadStatistics() {
        Log.d(TAG, "loadStatistics called")
        val familyId = preferencesManager.preferencesManager.familyId
        if (familyId == -1) {
            // 尝试从服务器获取统计数据
            Log.d(TAG, "familyId is -1, calling loadServerStatistics")
            loadServerStatistics()
            return
        }

        lifecycleScope.launch {
            Log.d(TAG, "Fetching visitor statistics for familyId=$familyId")
            val result = visitorRepository.getStatistics(familyId, days = 7)
            result.onSuccess { stats ->
                Log.d(TAG, "Statistics loaded successfully: ${stats.summary.totalVisitors} visitors")
                binding.tvTotalVisitors.text = stats.summary.totalVisitors.toString()
                binding.tvMemberVisits.text = stats.summary.memberVisits.toString()
                binding.tvStrangerVisits.text = stats.summary.strangerVisits.toString()
                binding.tvAlertCount.text = stats.summary.alertCount.toString()
                binding.tvTodayVisitors.text = stats.summary.todayVisitors.toString()
            }
            result.onFailure { error ->
                Log.e(TAG, "Failed to load statistics: ${error.message}", error)
                // 尝试从服务器获取统计数据
                loadServerStatistics()
            }
        }
    }

    private fun loadServerStatistics() {
        Log.d(TAG, "loadServerStatistics called")
        lifecycleScope.launch {
            val result = commandRepository.getStatistics()
            result.onSuccess { stats ->
                Log.d(TAG, "Server statistics loaded: ${stats.summary.todayVisitors} today")
                binding.tvTodayVisitors.text = stats.summary.todayVisitors.toString()
                binding.tvTotalVisitors.text = stats.summary.totalVisitors.toString()
                binding.tvMemberVisits.text = stats.summary.memberVisits.toString()
                binding.tvStrangerVisits.text = stats.summary.strangerVisits.toString()
                binding.tvAlertCount.text = stats.summary.alertCount.toString()
            }
            result.onFailure { error ->
                Log.e(TAG, "Failed to load server statistics: ${error.message}", error)
                Toast.makeText(requireContext(), "加载统计失败：${error.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun loadDeviceStatus() {
        Log.d(TAG, "loadDeviceStatus called")
        lifecycleScope.launch {
            val result = commandRepository.getDeviceStatusList()
            result.onSuccess { devices ->
                Log.d(TAG, "Device status loaded: ${devices.size} devices")
                if (devices.isNotEmpty()) {
                    currentDeviceId = devices.first().deviceId
                    setControlsEnabled(true)
                    val onlineCount = devices.count { it.isOnline }
                    Log.d(TAG, "Online devices: $onlineCount")
                    // 可以添加设备状态显示
                } else {
                    currentDeviceId = null
                    setControlsEnabled(false)
                    Toast.makeText(requireContext(), "当前账号未绑定设备", Toast.LENGTH_SHORT).show()
                }
            }
            result.onFailure { error ->
                Log.e(TAG, "Failed to load device status: ${error.message}", error)
                currentDeviceId = null
                setControlsEnabled(false)
                Toast.makeText(requireContext(), "获取设备失败：${error.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun setupClickListeners() {
        Log.d(TAG, "setupClickListeners called")
        // 远程开锁按钮
        binding.btnUnlock.setOnClickListener {
            showUnlockDialog()
        }

        binding.btnSnapshot?.setOnClickListener {
            doSnapshot()
        }

        // 下拉刷新
        binding.swipeRefresh.setOnRefreshListener {
            Log.d(TAG, "Swipe refresh triggered")
            loadStatistics()
            loadDeviceStatus()
            binding.swipeRefresh.isRefreshing = false
        }
    }

    private fun showUnlockDialog() {
        // 远程开锁二次确认（高风险操作：门禁放行）
        android.app.AlertDialog.Builder(requireContext())
            .setTitle("远程开锁")
            .setMessage("确定要远程开锁吗？")
            .setPositiveButton("确定") { _, _ ->
                doUnlock()
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun doUnlock() {
        // 远程开锁主入口（Home -> Repository -> ApiService -> 云端创建命令 -> 设备端执行 -> 回执）
        val deviceId = currentDeviceId
        if (deviceId.isNullOrBlank()) {
            Toast.makeText(requireContext(), "当前账号未绑定设备", Toast.LENGTH_SHORT).show()
            return
        }
        lifecycleScope.launch {
            val result = commandRepository.unlock(deviceId)
            result.onSuccess { resp ->
                Toast.makeText(requireContext(), resp.message ?: "开锁命令已下发", Toast.LENGTH_SHORT).show()
            }
            result.onFailure { error ->
                Toast.makeText(requireContext(), "开锁失败：${error.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun doSnapshot() {
        // 远程抓拍主入口（Home -> Repository -> ApiService -> 云端创建命令 -> 设备端抓拍上传）
        val deviceId = currentDeviceId
        if (deviceId.isNullOrBlank()) {
            Toast.makeText(requireContext(), "当前账号未绑定设备", Toast.LENGTH_SHORT).show()
            return
        }
        lifecycleScope.launch {
            val result = commandRepository.remoteSnapshot(deviceId)
            result.onSuccess {
                Toast.makeText(requireContext(), "抓拍命令已下发", Toast.LENGTH_SHORT).show()
            }
            result.onFailure { error ->
                Toast.makeText(requireContext(), "抓拍失败：${error.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
