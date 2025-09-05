package com.example.client_android.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp

/**
 * 被控端的主屏幕，用于显示状态和来自服务器的命令日志。
 */
@Composable
fun MainControlScreen(logOutput: String) {
    val scrollState = rememberScrollState()

    // 当日志内容更新时，自动滚动到底部
    LaunchedEffect(logOutput) {
        scrollState.animateScrollTo(scrollState.maxValue)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // 状态信息卡片
        Card(
            modifier = Modifier.fillMaxWidth(),
            elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("设备状态", style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Text("连接状态: 已连接到主服务器", color = Color(0xFF388E3C)) // Green color
                Text("模式: 正在监听指令...")
            }
        }

        // 日志输出区域
        Text("执行日志:", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(horizontal = 8.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .background(Color.Black)
                .padding(8.dp)
        ) {
            Text(
                text = logOutput,
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(scrollState),
                color = Color.White,
                fontFamily = FontFamily.Monospace,
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}

