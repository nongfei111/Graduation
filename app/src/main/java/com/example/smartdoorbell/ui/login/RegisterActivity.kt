package com.example.smartdoorbell.ui.login

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.example.smartdoorbell.MyApp
import com.example.smartdoorbell.data.api.RetrofitClient
import com.example.smartdoorbell.data.repository.AuthRepository
import com.example.smartdoorbell.databinding.ActivityRegisterBinding
import com.example.smartdoorbell.ui.main.MainActivity
import kotlinx.coroutines.launch

/**
 * 注册界面
 *
 * 功能定位索引：
 * - 点击注册入口：setupClickListeners() -> doRegister()
 * - 实际网络调用：AuthRepository.register() -> ApiService.register(/api/auth/register)
 * - 注册成功后自动登录：PreferencesManager.saveLoginInfo()
 * - 跳转主界面：navigateToMain() -> MainActivity
 */
class RegisterActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRegisterBinding
    private lateinit var authRepository: AuthRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRegisterBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // 初始化 Repository
        val apiService = RetrofitClient.getApiService(com.example.smartdoorbell.util.Constants.BASE_URL)
        authRepository = AuthRepository(apiService, (application as MyApp).preferencesManager)

        setupClickListeners()
    }

    private fun setupClickListeners() {
        // 注册按钮
        binding.btnRegister.setOnClickListener {
            val username = binding.etUsername.text.toString().trim()
            val email = binding.etEmail.text.toString().trim()
            val password = binding.etPassword.text.toString().trim()
            val confirmPassword = binding.etConfirmPassword.text.toString().trim()

            // 验证输入
            if (username.isEmpty()) {
                binding.tilUsername.error = "请输入用户名"
                return@setOnClickListener
            }
            binding.tilUsername.error = null

            if (username.length < 3 || username.length > 20) {
                binding.tilUsername.error = "用户名长度 3-20 个字符"
                return@setOnClickListener
            }
            binding.tilUsername.error = null

            if (password.isEmpty()) {
                binding.tilPassword.error = "请输入密码"
                return@setOnClickListener
            }
            binding.tilPassword.error = null

            if (password.length < 6) {
                binding.tilPassword.error = "密码至少 6 位"
                return@setOnClickListener
            }
            binding.tilPassword.error = null

            if (password != confirmPassword) {
                binding.tilConfirmPassword.error = "两次输入的密码不一致"
                return@setOnClickListener
            }
            binding.tilConfirmPassword.error = null

            doRegister(username, email, password)
        }

        // 返回登录
        binding.tvLogin.setOnClickListener {
            finish()
        }
    }

    private fun doRegister(username: String, email: String, password: String) {
        showLoading(true)

        lifecycleScope.launch {
            val result = authRepository.register(username, password, email)

            showLoading(false)

            result.onSuccess { loginData ->
                Toast.makeText(this@RegisterActivity, "注册成功", Toast.LENGTH_SHORT).show()

                // 保存登录信息
                (application as MyApp).preferencesManager.saveLoginInfo(
                    loginData.accessToken,
                    loginData.refreshToken,
                    loginData.user.id,
                    0 // familyId 需要在登录家庭后设置
                )

                navigateToMain()
                finish()
            }

            result.onFailure { error ->
                Toast.makeText(this@RegisterActivity, "注册失败：${error.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun showLoading(show: Boolean) {
        binding.progressBar.visibility = if (show) android.view.View.VISIBLE else android.view.View.GONE
        binding.btnRegister.isEnabled = !show
    }

    private fun navigateToMain() {
        val intent = Intent(this, MainActivity::class.java)
        startActivity(intent)
    }
}
