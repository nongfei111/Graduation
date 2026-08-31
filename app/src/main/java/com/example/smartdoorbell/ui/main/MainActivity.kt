package com.example.smartdoorbell.ui.main

import android.os.Bundle
import android.util.Log
import android.view.MenuItem
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import com.example.smartdoorbell.R
import com.example.smartdoorbell.databinding.ActivityMainBinding
import com.example.smartdoorbell.ui.home.HomeFragment
import com.example.smartdoorbell.ui.member.MemberListFragment
import com.example.smartdoorbell.ui.settings.SettingsFragment
import com.example.smartdoorbell.ui.visitor.VisitorListFragment

private const val TAG = "SmartDoorbell.Main"

/**
 * 主界面
 * 使用 BottomNavigationView 实现底部导航
 *
 * 功能定位索引（页面入口）：
 * - 首页（统计/远程开锁/抓拍）：HomeFragment
 * - 访客列表（查看/删除/详情）：VisitorListFragment
 * - 成员管理（增删/上传照片）：MemberListFragment
 * - 设置（退出登录）：SettingsFragment
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.d(TAG, "onCreate called")
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbar)
        supportActionBar?.title = "智能门铃"
        supportActionBar?.setDisplayShowTitleEnabled(true)

        setupBottomNavigation()

        // 默认显示首页
        if (savedInstanceState == null) {
            Log.d(TAG, "Loading HomeFragment for first time")
            loadFragment(HomeFragment())
        }
    }

    private fun setupBottomNavigation() {
        binding.bottomNavigation.setOnItemSelectedListener { item ->
            Log.d(TAG, "Bottom navigation item selected: ${item.itemId}")
            when (item.itemId) {
                R.id.nav_home -> {
                    loadFragment(HomeFragment())
                    true
                }
                R.id.nav_visitors -> {
                    loadFragment(VisitorListFragment())
                    true
                }
                R.id.nav_members -> {
                    loadFragment(MemberListFragment())
                    true
                }
                R.id.nav_settings -> {
                    loadFragment(SettingsFragment())
                    true
                }
                else -> false
            }
        }
    }

    private fun loadFragment(fragment: Fragment) {
        Log.d(TAG, "Loading fragment: ${fragment.javaClass.simpleName}")
        supportFragmentManager.beginTransaction()
            .replace(R.id.fragment_container, fragment)
            .commit()
    }

    override fun onBackPressed() {
        // 返回当前选中的 Fragment
        val currentFragment = supportFragmentManager.findFragmentById(R.id.fragment_container)
        if (currentFragment is VisitorListFragment || currentFragment is MemberListFragment) {
            // 如果在子页面，返回主页
            binding.bottomNavigation.selectedItemId = R.id.nav_home
        } else {
            super.onBackPressed()
        }
    }
}
