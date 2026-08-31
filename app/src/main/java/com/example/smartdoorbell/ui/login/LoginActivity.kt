package com.example.smartdoorbell.ui.login

import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.example.smartdoorbell.MyApp
import com.example.smartdoorbell.data.api.RetrofitClient
import com.example.smartdoorbell.data.repository.AuthRepository
import com.example.smartdoorbell.databinding.ActivityLoginBinding
import com.example.smartdoorbell.ui.main.MainActivity
import kotlinx.coroutines.launch

private const val TAG = "SmartDoorbell.Login"

/**
 * 登录界面
 *
 * 功能定位索引：
 * - 点击登录按钮入口：setupClickListeners() -> doLogin()
 * - 实际网络调用：AuthRepository.login() -> ApiService.login(/api/auth/login)
 * - 登录态保存：PreferencesManager.saveLoginInfo()
 * - 登录成功跳转主界面：navigateToMain() -> MainActivity
 */
class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding
    private lateinit var authRepository: AuthRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.d(TAG, "onCreate called, isLoggedIn=${(application as MyApp).preferencesManager.isLoggedIn}")
        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // 初始化 Repository
        val apiService = RetrofitClient.getApiService(com.example.smartdoorbell.util.Constants.BASE_URL)
        authRepository = AuthRepository(apiService, (application as MyApp).preferencesManager)

        // 检查是否已登录
        if ((application as MyApp).preferencesManager.isLoggedIn) {
            Log.d(TAG, "Already logged in, navigating to main")
            navigateToMain()
            return
        }

        setupClickListeners()
    }

    private fun setupClickListeners() {
        // 登录按钮
        binding.btnLogin.setOnClickListener {
            val username = binding.etUsername.text.toString().trim()
            val password = binding.etPassword.text.toString().trim()

            if (username.isEmpty()) {
                binding.tilUsername.error = "请输入用户名"
                return@setOnClickListener
            }
            binding.tilUsername.error = null

            if (password.isEmpty()) {
                binding.tilPassword.error = "请输入密码"
                return@setOnClickListener
            }
            binding.tilPassword.error = null

            doLogin(username, password)
        }

        // 注册按钮 - 跳转注册页面
        binding.tvRegister.setOnClickListener {
            val intent = Intent(this, RegisterActivity::class.java)
            startActivity(intent)
        }
    }

    private fun doLogin(username: String, password: String) {
        showLoading(true)
        Log.d(TAG, "doLogin called for user: $username")

        lifecycleScope.launch {
            val result = authRepository.login(username, password)

            showLoading(false)

            result.onSuccess { loginData ->
                Log.d(TAG, "Login successful, userId=${loginData.user.id}")
                // 登录成功后，尝试获取家庭 ID（可选操作，失败不影响登录）
                val familyResult = authRepository.loadFamilyId()
                if (familyResult.isSuccess) {
                    Log.d(TAG, "Family ID loaded: ${familyResult.getOrNull()}")
                    Toast.makeText(this@LoginActivity, "登录成功", Toast.LENGTH_SHORT).show()
                } else {
                    // 家庭 ID 获取失败也允许登录，只是部分功能受限
                    Log.w(TAG, "Family ID not loaded: ${familyResult.exceptionOrNull()?.message}")
                    Toast.makeText(this@LoginActivity, "登录成功（未找到家庭信息）", Toast.LENGTH_LONG).show()
                }
                navigateToMain()
                finish()
            }

            result.onFailure { error ->
                Log.e(TAG, "Login failed: ${error.message}", error)
                Toast.makeText(this@LoginActivity, "登录失败：${error.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun showLoading(show: Boolean) {
        binding.progressBar.visibility = if (show) android.view.View.VISIBLE else android.view.View.GONE
        binding.btnLogin.isEnabled = !show
    }

    private fun navigateToMain() {
        val intent = Intent(this, MainActivity::class.java)
        startActivity(intent)
    }
}
