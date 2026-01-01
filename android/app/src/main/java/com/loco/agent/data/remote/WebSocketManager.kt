package com.loco.agent.data.remote

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.loco.agent.data.model.WebSocketMessage
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import okhttp3.*
import java.util.concurrent.TimeUnit

class WebSocketManager(
    private val client: OkHttpClient,
    private val gson: Gson,
    private val baseUrl: String
) {
    private var webSocket: WebSocket? = null

    fun connectSession(sessionId: String): Flow<WebSocketMessage> = callbackFlow {
        val wsUrl = baseUrl.replace("http://", "ws://")
            .replace("https://", "wss://") + "/v1/sessions/$sessionId/stream"

        val request = Request.Builder()
            .url(wsUrl)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                // Send client hello
                val helloMessage = mapOf(
                    "type" to "client.hello",
                    "client_info" to mapOf(
                        "platform" to "android",
                        "version" to "1.0.0"
                    )
                )
                webSocket.send(gson.toJson(helloMessage))
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = gson.fromJson(text, JsonObject::class.java)
                    val type = json.get("type")?.asString ?: ""

                    val message = when (type) {
                        "server.hello" -> {
                            val serverInfo = gson.fromJson(
                                json.getAsJsonObject("server_info"),
                                com.loco.agent.data.model.ServerInfo::class.java
                            )
                            WebSocketMessage.ServerHello(
                                protocolVersion = json.get("protocol_version").asString,
                                serverInfo = serverInfo
                            )
                        }
                        "server.thinking" -> {
                            WebSocketMessage.ThinkingEvent(
                                thinking = json.get("thinking").asString
                            )
                        }
                        "server.tool_use" -> {
                            val tool = json.get("tool").asString
                            val input = json.getAsJsonObject("input").asMap()
                                .mapValues { it.value.toString() }
                            WebSocketMessage.ToolUseEvent(tool, input)
                        }
                        "server.tool_result" -> {
                            WebSocketMessage.ToolResultEvent(
                                tool = json.get("tool").asString,
                                output = json.get("output").asString
                            )
                        }
                        "server.text_delta" -> {
                            WebSocketMessage.TextDelta(
                                delta = json.get("delta").asString
                            )
                        }
                        "server.error" -> {
                            val error = gson.fromJson(
                                json.getAsJsonObject("error"),
                                com.loco.agent.data.model.ErrorInfo::class.java
                            )
                            WebSocketMessage.ErrorEvent(error)
                        }
                        "server.complete" -> {
                            WebSocketMessage.Complete(
                                message = json.get("message")?.asString ?: ""
                            )
                        }
                        else -> null
                    }

                    message?.let { trySend(it) }
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                close(t)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
                close()
            }
        })

        awaitClose {
            webSocket?.close(1000, "Client closing")
        }
    }

    fun sendMessage(message: String, context: Map<String, Any> = emptyMap()) {
        val messageJson = mapOf(
            "type" to "client.user_message",
            "message" to message,
            "context" to context
        )
        webSocket?.send(gson.toJson(messageJson))
    }

    fun disconnect() {
        webSocket?.close(1000, "Client disconnect")
        webSocket = null
    }
}
