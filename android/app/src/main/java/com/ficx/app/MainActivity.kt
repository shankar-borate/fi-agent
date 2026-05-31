package com.ficx.app

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.ficx.app.databinding.ActivityMainBinding
import com.ficx.app.ui.FiSessionActivity
import com.vmadalin.easypermissions.EasyPermissions
import com.vmadalin.easypermissions.dialogs.SettingsDialog

class MainActivity : AppCompatActivity(), EasyPermissions.PermissionCallbacks {

    private lateinit var binding: ActivityMainBinding

    companion object {
        private const val RC_PERMISSIONS = 100

        private val REQUIRED_PERMISSIONS = buildList {
            add(Manifest.permission.CAMERA)
            add(Manifest.permission.RECORD_AUDIO)
            add(Manifest.permission.ACCESS_FINE_LOCATION)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                add(Manifest.permission.READ_MEDIA_IMAGES)
                add(Manifest.permission.READ_MEDIA_VIDEO)
                add(Manifest.permission.READ_MEDIA_AUDIO)
            } else {
                add(Manifest.permission.READ_EXTERNAL_STORAGE)
                if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.P) {
                    add(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                }
            }
        }.toTypedArray()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnStartFi.setOnClickListener {
            if (allPermissionsGranted()) {
                openFiSession()
            } else {
                requestPermissions()
            }
        }
    }

    private fun allPermissionsGranted() =
        EasyPermissions.hasPermissions(this, *REQUIRED_PERMISSIONS)

    private fun requestPermissions() {
        EasyPermissions.requestPermissions(
            this,
            "Camera, microphone and location access are required to conduct the FI session.",
            RC_PERMISSIONS,
            *REQUIRED_PERMISSIONS
        )
    }

    private fun openFiSession() {
        startActivity(Intent(this, FiSessionActivity::class.java))
    }

    override fun onPermissionsGranted(requestCode: Int, perms: List<String>) {
        if (allPermissionsGranted()) openFiSession()
    }

    override fun onPermissionsDenied(requestCode: Int, perms: List<String>) {
        if (EasyPermissions.somePermissionPermanentlyDenied(this, perms)) {
            SettingsDialog.Builder(this).build().show()
        } else {
            Toast.makeText(this, "All permissions are required to start the session.", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        EasyPermissions.onRequestPermissionsResult(requestCode, permissions, grantResults, this)
    }
}
