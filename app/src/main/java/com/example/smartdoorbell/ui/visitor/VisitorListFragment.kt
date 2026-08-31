package com.example.smartdoorbell.ui.visitor

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.smartdoorbell.MyApp
import com.example.smartdoorbell.data.api.RetrofitClient
import com.example.smartdoorbell.data.api.model.VisitorInfo
import com.example.smartdoorbell.data.repository.VisitorRepository
import com.example.smartdoorbell.databinding.FragmentVisitorListBinding
import com.google.gson.Gson
import kotlinx.coroutines.launch

/**
 * 访客列表 Fragment
 *
 * 功能定位索引：
 * - 拉取列表：loadVisitors() -> VisitorRepository.getVisitors() -> ApiService.getVisitors(/api/visitor/list)
 * - 删除记录：deleteVisitor() -> VisitorRepository.deleteVisitor() -> ApiService.deleteVisitor(/api/visitor/{id}/delete)
 * - 打开详情：openVisitorDetail() -> VisitorDetailActivity
 */
class VisitorListFragment : Fragment() {

    private var _binding: FragmentVisitorListBinding? = null
    private val binding get() = _binding!!

    private lateinit var visitorRepository: VisitorRepository
    private lateinit var preferencesManager: MyApp
    private lateinit var visitorAdapter: VisitorAdapter

    private var currentPage = 1
    private val pageSize = 20
    private var isLoading = false
    private var hasMore = true

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentVisitorListBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        preferencesManager = requireActivity().application as MyApp
        val apiService = RetrofitClient.getApiService("http://8.134.196.56:5000/")
        visitorRepository = VisitorRepository(apiService, preferencesManager.preferencesManager)

        setupRecyclerView()
        loadVisitors()
    }

    private fun setupRecyclerView() {
        visitorAdapter = VisitorAdapter(
            onItemClick = { visitor ->
                openVisitorDetail(visitor)
            },
            onDeleteClick = { visitor ->
                showDeleteDialog(visitor)
            }
        )

        binding.recyclerView.layoutManager = LinearLayoutManager(requireContext())
        binding.recyclerView.adapter = visitorAdapter

        // 下拉刷新
        binding.swipeRefresh.setOnRefreshListener {
            currentPage = 1
            hasMore = true
            loadVisitors()
        }

        // 上拉加载
        binding.recyclerView.addOnScrollListener(object : androidx.recyclerview.widget.RecyclerView.OnScrollListener() {
            override fun onScrolled(recyclerView: androidx.recyclerview.widget.RecyclerView, dx: Int, dy: Int) {
                super.onScrolled(recyclerView, dx, dy)
                if (!recyclerView.canScrollVertically(1) && !isLoading && hasMore) {
                    currentPage++
                    loadVisitors()
                }
            }
        })
    }

    private fun loadVisitors() {
        if (isLoading || !hasMore) return

        isLoading = true
        val familyId = preferencesManager.preferencesManager.familyId

        if (familyId == -1) {
            Toast.makeText(requireContext(), "请先选择家庭", Toast.LENGTH_SHORT).show()
            isLoading = false
            return
        }

        lifecycleScope.launch {
            val result = visitorRepository.getVisitors(familyId, currentPage, pageSize)

            isLoading = false
            binding.swipeRefresh.isRefreshing = false

            result.onSuccess { data ->
                if (currentPage == 1) {
                    visitorAdapter.submitList(mutableListOf())
                }

                val newList = visitorAdapter.currentList.toMutableList()
                newList.addAll(data.visitors)
                visitorAdapter.submitList(newList)

                hasMore = data.pagination.page < data.pagination.pages

                // 显示空状态提示
                if (data.visitors.isEmpty() && currentPage == 1) {
                    Toast.makeText(requireContext(), "暂无访客记录", Toast.LENGTH_SHORT).show()
                }
            }

            result.onFailure { error ->
                Toast.makeText(requireContext(), "加载失败：${error.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun showDeleteDialog(visitor: VisitorInfo) {
        AlertDialog.Builder(requireContext())
            .setTitle("删除访客记录")
            .setMessage("确定要删除这条访客记录吗？")
            .setPositiveButton("删除") { _, _ ->
                deleteVisitor(visitor)
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun deleteVisitor(visitor: VisitorInfo) {
        lifecycleScope.launch {
            val visitorId = visitor.id
            val result = visitorRepository.deleteVisitor(visitorId)
            result.onSuccess {
                val newList = visitorAdapter.currentList.filter { it.id != visitorId }
                visitorAdapter.submitList(newList)
                Toast.makeText(requireContext(), "删除成功", Toast.LENGTH_SHORT).show()
            }
            result.onFailure { error ->
                Toast.makeText(requireContext(), "删除失败：${error.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun openVisitorDetail(visitor: VisitorInfo) {
        val intent = Intent(requireContext(), VisitorDetailActivity::class.java)
        // 使用 JSON 序列化传递数据
        val visitorJson = com.google.gson.Gson().toJson(visitor)
        intent.putExtra("visitor_json", visitorJson)
        startActivity(intent)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
