package com.example.smartdoorbell.ui.member

import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.smartdoorbell.MyApp
import com.example.smartdoorbell.data.api.RetrofitClient
import com.example.smartdoorbell.data.api.model.MemberInfo
import com.example.smartdoorbell.data.repository.MemberRepository
import com.example.smartdoorbell.databinding.FragmentMemberListBinding
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileOutputStream

class MemberListFragment : Fragment() {
    // 功能定位索引：
    // - 成员列表：loadMembers() -> MemberRepository.getMembers() -> ApiService.getMembers(/api/member/list)
    // - 添加成员：showAddMemberDialog() -> addMember() -> MemberRepository.addMember() -> ApiService.addMember(/api/member/add)
    // - 上传照片（用于树莓派同步到成员人脸库）：showPhotoPicker() -> uploadMemberPhoto() -> MemberRepository.updateMemberPhoto() -> ApiService.updateMemberPhoto(/api/member/{id}/photo)
    // - 删除成员：showDeleteDialog() -> deleteMember() -> MemberRepository.deleteMember() -> ApiService.deleteMember(/api/member/{id}/delete)

    private var _binding: FragmentMemberListBinding? = null
    private val binding get() = _binding!!

    private lateinit var memberRepository: MemberRepository
    private lateinit var preferencesManager: MyApp
    private lateinit var memberAdapter: MemberAdapter

    private var memberList = mutableListOf<MemberInfo>()
    private var currentMemberId: Int = -1

    private val pickImageLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let {
            uploadMemberPhoto(it)
        }
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentMemberListBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        preferencesManager = requireActivity().application as MyApp
        val apiService = RetrofitClient.getApiService("http://8.134.196.56:5000/")
        memberRepository = MemberRepository(apiService, preferencesManager.preferencesManager)

        setupRecyclerViews()
        setupClickListeners()
        loadMembers()
    }

    private fun setupRecyclerViews() {
        memberAdapter = MemberAdapter(
            onUploadPhotoClick = { member -> showPhotoPicker(member) },
            onDeleteClick = { member -> showDeleteDialog(member) }
        )

        binding.recyclerView.layoutManager = LinearLayoutManager(requireContext())
        binding.recyclerView.adapter = memberAdapter
    }

    private fun setupClickListeners() {
        binding.btnAdd.setOnClickListener {
            showAddMemberDialog()
        }
    }

    private fun loadMembers() {
        val familyId = preferencesManager.preferencesManager.familyId
        if (familyId == -1) {
            Toast.makeText(requireContext(), "请先登录", Toast.LENGTH_SHORT).show()
            return
        }

        showLoading(true)
        lifecycleScope.launch {
            val result = memberRepository.getMembers(familyId)
            showLoading(false)

            result.onSuccess { data ->
                memberList.clear()
                memberList.addAll(data.members)
                memberAdapter.submitList(memberList.toMutableList())
                updateEmptyState()
            }
            result.onFailure { error ->
                Toast.makeText(requireContext(), "加载成员失败：${error.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun updateEmptyState() {
        val isEmpty = memberList.isEmpty()
        binding.emptyState.visibility = if (isEmpty) View.VISIBLE else View.GONE
        binding.recyclerView.visibility = if (isEmpty) View.GONE else View.VISIBLE
    }

    private fun showAddMemberDialog() {
        val editText = android.widget.EditText(requireContext())
        editText.hint = "请输入成员姓名（如：爸爸、妈妈）"

        AlertDialog.Builder(requireContext())
            .setTitle("添加家庭成员")
            .setMessage("请输入要添加的成员姓名，添加后可上传照片用于人脸识别")
            .setView(editText)
            .setPositiveButton("确定") { _, _ ->
                val name = editText.text.toString().trim()
                if (name.isNotEmpty()) {
                    addMember(name, null)
                } else {
                    Toast.makeText(requireContext(), "请输入成员姓名", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun showPhotoPicker(member: MemberInfo) {
        currentMemberId = member.id
        pickImageLauncher.launch("image/*")
    }

    private fun uploadMemberPhoto(uri: Uri) {
        if (currentMemberId == -1) return

        val photoFile = uriToFile(uri)
        if (photoFile == null) {
            Toast.makeText(requireContext(), "图片处理失败", Toast.LENGTH_SHORT).show()
            return
        }

        lifecycleScope.launch {
            val result = memberRepository.updateMemberPhoto(currentMemberId, photoFile)
            result.onSuccess {
                Toast.makeText(requireContext(), "照片已上传", Toast.LENGTH_SHORT).show()
                loadMembers()
            }
            result.onFailure { error ->
                Toast.makeText(requireContext(), "上传失败：${error.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun uriToFile(uri: Uri): File? {
        return try {
            val inputStream = requireContext().contentResolver.openInputStream(uri)
            val file = File(requireContext().cacheDir, "member_photo_${System.currentTimeMillis()}.jpg")
            val outputStream = FileOutputStream(file)
            inputStream?.copyTo(outputStream)
            inputStream?.close()
            outputStream.close()
            file
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    private fun addMember(name: String, photoFile: File?) {
        val familyId = preferencesManager.preferencesManager.familyId
        if (familyId == -1) {
            Toast.makeText(requireContext(), "请先登录", Toast.LENGTH_SHORT).show()
            return
        }

        showLoading(true)
        lifecycleScope.launch {
            val result = memberRepository.addMember(familyId, name, photoFile)
            showLoading(false)

            result.onSuccess { member ->
                Toast.makeText(requireContext(), "添加成员成功：$name", Toast.LENGTH_SHORT).show()
                loadMembers()
            }
            result.onFailure { error ->
                Toast.makeText(requireContext(), "添加失败：${error.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun showDeleteDialog(member: MemberInfo) {
        AlertDialog.Builder(requireContext())
            .setTitle("删除成员")
            .setMessage("确定要删除成员 ${member.name} 吗？")
            .setPositiveButton("删除") { _, _ ->
                deleteMember(member.id)
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun deleteMember(memberId: Int) {
        lifecycleScope.launch {
            val result = memberRepository.deleteMember(memberId)
            result.onSuccess {
                Toast.makeText(requireContext(), "删除成功", Toast.LENGTH_SHORT).show()
                loadMembers()
            }
            result.onFailure { error ->
                Toast.makeText(requireContext(), "删除失败：${error.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun showLoading(show: Boolean) {
        binding.progressBar.visibility = if (show) View.VISIBLE else View.GONE
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
