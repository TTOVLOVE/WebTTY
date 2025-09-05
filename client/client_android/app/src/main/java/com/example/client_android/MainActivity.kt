package com.example.client_android

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.media.projection.MediaProjectionManager
import android.os.Bundle
import android.util.Base64
import android.util.Log
import android.view.View
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.client_android.network.TCPManager
import com.example.client_android.ui.MainControlScreen
import com.example.client_android.ui.theme.Client_androidTheme
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStreamReader

class MainActivity : ComponentActivity() {

    private val tcpManager = TCPManager.getInstance()
    private lateinit var mediaProjectionManager: MediaProjectionManager

    private val screenCaptureLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val data = result.data
            if (data != null) {
                val serviceIntent = Intent(this, ScreenshotService::class.java).apply {
                    action = ScreenshotService.ACTION_START
                    putExtra(ScreenshotService.EXTRA_RESULT_CODE, result.resultCode)
                    putExtra(ScreenshotService.EXTRA_DATA, data)
                }
                startForegroundService(serviceIntent)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        mediaProjectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager

        val serverIp = "192.168.54.102"
        val serverPort = 2383

        setContent {
            Client_androidTheme {
                var connectionStatus by remember { mutableStateOf(TCPManager.ConnectionStatus.DISCONNECTED) }
                var logOutput by remember { mutableStateOf("客户端初始化...\n") }

                LaunchedEffect(Unit) {
                    CoroutineScope(Dispatchers.Main).launch {
                        tcpManager.connectionState.collect { status ->
                            connectionStatus = status
                            val statusMessage = when (status) {
                                TCPManager.ConnectionStatus.CONNECTING -> "正在连接到 $serverIp:$serverPort...\n"
                                TCPManager.ConnectionStatus.CONNECTED -> {
                                    val deviceInfo = JSONObject().apply {
                                        put("status", "connected")
                                        put("user", "Android Device")
                                        put("os", "Android ${android.os.Build.VERSION.RELEASE}")
                                        put("cwd", filesDir.absolutePath)
                                    }
                                    tcpManager.sendMessage(deviceInfo)
                                    "成功连接到主服务器。\n"
                                }
                                TCPManager.ConnectionStatus.DISCONNECTED -> "连接已断开。\n"
                                TCPManager.ConnectionStatus.ERROR -> "连接发生错误。\n"
                            }
                            logOutput += statusMessage
                        }
                    }
                }

                LaunchedEffect(Unit) {
                    CoroutineScope(Dispatchers.Main).launch {
                        tcpManager.incomingMessages.collect { json ->
                            handleServerCommand(json) { output ->
                                logOutput += output
                            }
                        }
                    }
                }

                LaunchedEffect(Unit) {
                    tcpManager.connect(serverIp, serverPort)
                }

                Scaffold(modifier = Modifier.fillMaxSize()) {
                    Box(modifier = Modifier.padding(it)) {
                        if (connectionStatus == TCPManager.ConnectionStatus.CONNECTED) {
                            ControlInterface(logOutput = logOutput) {
                                screenCaptureLauncher.launch(mediaProjectionManager.createScreenCaptureIntent())
                            }
                        } else {
                            ConnectionStatusScreen(status = connectionStatus)
                        }
                    }
                }
            }
        }
    }

    private fun handleServerCommand(commandJson: JSONObject, appendLog: (String) -> Unit) {
        val action = commandJson.optString("action", "")
        val arg = commandJson.optString("arg", "")
        appendLog(">>> 收到命令: $action $arg\n")

        CoroutineScope(Dispatchers.IO).launch {
            when (action) {
                "list_dir" -> {
                    try {
                        val path = if (arg.isNotEmpty()) arg else filesDir.absolutePath
                        val file = File(path)
                        if (!file.exists() || !file.canRead()) throw SecurityException("权限不足或文件不存在")
                        val entries = JSONArray()
                        file.listFiles()?.forEach { f ->
                            val entry = JSONObject().apply {
                                put("name", f.name)
                                put("is_dir", f.isDirectory)
                                put("size", f.length())
                                put("mtime", f.lastModified() / 1000)
                            }
                            entries.put(entry)
                        }
                        val response = JSONObject().apply {
                            put("dir_list", JSONObject().apply {
                                put("cwd", file.absolutePath)
                                put("entries", entries)
                            })
                        }
                        tcpManager.sendMessage(response)
                        withContext(Dispatchers.Main) { appendLog("目录列表已发送。\n") }
                    } catch (e: Exception) {
                        val errorMsg = "列目录失败: ${e.message}\n"
                        tcpManager.sendMessage(JSONObject().put("output", errorMsg))
                        withContext(Dispatchers.Main) { appendLog(errorMsg) }
                    }
                }

                "screenshot" -> {
                    withContext(Dispatchers.Main) {
                        takeScreenshot { base64Image ->
                            CoroutineScope(Dispatchers.IO).launch {
                                val response = JSONObject()
                                if (base64Image != null) {
                                    response.put("file", "screenshot.png")
                                    response.put("data", base64Image)
                                    withContext(Dispatchers.Main) { appendLog("截图成功并已发送。\n") }
                                } else {
                                    response.put("output", "在安卓客户端截图失败。")
                                    withContext(Dispatchers.Main) { appendLog("截图失败。\n") }
                                }
                                tcpManager.sendMessage(response)
                            }
                        }
                    }
                }

                "start_screen_stream" -> {
                    withContext(Dispatchers.Main) {
                        screenCaptureLauncher.launch(mediaProjectionManager.createScreenCaptureIntent())
                        appendLog("已远程请求屏幕共享权限...请在设备上确认。\n")
                    }
                }

                else -> {
                    try {
                        val command = if (arg.isNotEmpty()) "$action $arg" else action
                        val process = Runtime.getRuntime().exec(command)
                        val reader = BufferedReader(InputStreamReader(process.inputStream))
                        val errorReader = BufferedReader(InputStreamReader(process.errorStream))
                        var output = ""
                        reader.forEachLine { output += "$it\n" }
                        errorReader.forEachLine { output += "[ERROR] $it\n" }
                        process.waitFor()
                        withContext(Dispatchers.Main) { appendLog(output) }
                        tcpManager.sendMessage(JSONObject().put("output", output))
                    } catch (e: Exception) {
                        val errorMsg = "命令执行失败: ${e.message}\n"
                        withContext(Dispatchers.Main) { appendLog(errorMsg) }
                        tcpManager.sendMessage(JSONObject().put("output", errorMsg))
                    }
                }
            }
        }
    }

    private fun takeScreenshot(callback: (String?) -> Unit) {
        runOnUiThread {
            try {
                val rootView: View = window.decorView.rootView
                rootView.isDrawingCacheEnabled = true
                val bitmap = Bitmap.createBitmap(rootView.drawingCache)
                rootView.isDrawingCacheEnabled = false

                val outputStream = ByteArrayOutputStream()
                bitmap.compress(Bitmap.CompressFormat.PNG, 80, outputStream)
                val byteArray = outputStream.toByteArray()
                val encodedString = Base64.encodeToString(byteArray, Base64.DEFAULT)

                callback(encodedString)
            } catch (e: Exception) {
                Log.e("MainActivity", "Screenshot failed", e)
                callback(null)
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        val serviceIntent = Intent(this, ScreenshotService::class.java).apply {
            action = ScreenshotService.ACTION_STOP
        }
        startService(serviceIntent)
        tcpManager.disconnect()
    }
}

@Composable
fun ControlInterface(logOutput: String, onStartCapture: () -> Unit) {
    Column(modifier = Modifier.fillMaxSize()) {
        MainControlScreen(logOutput = logOutput)
        Spacer(modifier = Modifier.height(8.dp))
        Button(onClick = onStartCapture, modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp)) {
            Text("启动屏幕共享")
        }
    }
}

@Composable
fun ConnectionStatusScreen(status: TCPManager.ConnectionStatus, modifier: Modifier = Modifier) {
    Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            if (status == TCPManager.ConnectionStatus.CONNECTING) {
                CircularProgressIndicator()
                Spacer(modifier = Modifier.height(16.dp))
                Text(text = "正在连接...")
            } else {
                Text(text = "连接已断开或发生错误", modifier = Modifier.padding(16.dp))
            }
        }
    }
}
