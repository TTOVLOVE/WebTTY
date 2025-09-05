package com.example.client_android.network

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.io.PrintWriter
import java.net.Socket

class TCPManager private constructor() {

    private var socket: Socket? = null
    private var writer: PrintWriter? = null
    private var reader: BufferedReader? = null

    private val job = Job()
    private val scope = CoroutineScope(Dispatchers.IO + job)

    private val _incomingMessages = MutableSharedFlow<JSONObject>()
    val incomingMessages = _incomingMessages.asSharedFlow()

    private val _connectionState = MutableSharedFlow<ConnectionStatus>()
    val connectionState = _connectionState.asSharedFlow()

    enum class ConnectionStatus { CONNECTING, CONNECTED, DISCONNECTED, ERROR }

    companion object {
        private const val TAG = "TCPManager"
        @Volatile
        private var instance: TCPManager? = null
        fun getInstance(): TCPManager {
            return instance ?: synchronized(this) {
                instance ?: TCPManager().also { instance = it }
            }
        }
    }

    fun connect(serverIp: String, serverPort: Int) {
        if (socket?.isConnected == true) return

        scope.launch {
            _connectionState.emit(ConnectionStatus.CONNECTING)
            try {
                socket = Socket(serverIp, serverPort)
                writer = PrintWriter(OutputStreamWriter(socket!!.getOutputStream(), "UTF-8"), true)
                reader = BufferedReader(InputStreamReader(socket!!.getInputStream(), "UTF-8"))
                _connectionState.emit(ConnectionStatus.CONNECTED)
                Log.d(TAG, "TCP a successful connection to $serverIp:$serverPort")

                // Start listening for messages
                listenForMessages()

            } catch (e: Exception) {
                Log.e(TAG, "Connection failed: ", e)
                _connectionState.emit(ConnectionStatus.ERROR)
                disconnect()
            }
        }
    }

    private fun listenForMessages() {
        scope.launch {
            while (isActive && socket?.isConnected == true) {
                try {
                    val line = reader?.readLine()
                    if (line == null) {
                        Log.d(TAG, "Server closed connection.")
                        break // Connection closed by server
                    }
                    val json = JSONObject(line)
                    _incomingMessages.emit(json)
                } catch (e: Exception) {
                    if (isActive) {
                        Log.e(TAG, "Error reading from socket: ", e)
                        _connectionState.emit(ConnectionStatus.ERROR)
                    }
                    break
                }
            }
            if (isActive) {
                disconnect()
            }
        }
    }

    fun sendMessage(json: JSONObject) {
        scope.launch {
            try {
                writer?.println(json.toString())
            } catch (e: Exception) {
                Log.e(TAG, "Error sending message: ", e)
                _connectionState.emit(ConnectionStatus.ERROR)
                disconnect()
            }
        }
    }

    fun disconnect() {
        try {
            job.cancel() // Cancel all coroutines
            socket?.close()
        } catch (e: Exception) {
            Log.e(TAG, "Error closing socket: ", e)
        }
        socket = null
        writer = null
        reader = null
        scope.launch {
            _connectionState.emit(ConnectionStatus.DISCONNECTED)
        }
        Log.d(TAG, "TCP connection closed.")
    }
}
