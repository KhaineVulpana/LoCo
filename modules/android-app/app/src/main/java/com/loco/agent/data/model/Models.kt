package com.loco.agent.data.model

import com.google.gson.annotations.SerializedName

data class Workspace(
    val id: String,
    val path: String,
    val name: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("index_status") val indexStatus: String,
    @SerializedName("total_files") val totalFiles: Int,
    @SerializedName("indexed_files") val indexedFiles: Int
)

data class WorkspaceCreate(
    val path: String,
    val name: String? = null
)

data class Session(
    val id: String,
    @SerializedName("workspace_id") val workspaceId: String,
    val title: String?,
    @SerializedName("model_provider") val modelProvider: String,
    @SerializedName("model_name") val modelName: String,
    @SerializedName("context_window") val contextWindow: Int,
    @SerializedName("created_at") val createdAt: String,
    val status: String
)

data class SessionCreate(
    @SerializedName("workspace_id") val workspaceId: String,
    @SerializedName("model_provider") val modelProvider: String? = null,
    @SerializedName("model_name") val modelName: String? = null,
    @SerializedName("context_window") val contextWindow: Int? = null
)

data class HealthResponse(
    val status: String,
    val version: String,
    @SerializedName("protocol_version") val protocolVersion: String
)

data class ChatMessage(
    val id: String,
    val role: String, // "user" or "assistant"
    val content: String,
    val timestamp: Long = System.currentTimeMillis()
)

sealed class WebSocketMessage {
    data class ServerHello(
        @SerializedName("protocol_version") val protocolVersion: String,
        @SerializedName("server_info") val serverInfo: ServerInfo
    ) : WebSocketMessage()

    data class ThinkingEvent(
        val thinking: String
    ) : WebSocketMessage()

    data class ToolUseEvent(
        val tool: String,
        val input: Map<String, Any>
    ) : WebSocketMessage()

    data class ToolResultEvent(
        val tool: String,
        val output: String
    ) : WebSocketMessage()

    data class TextDelta(
        val delta: String
    ) : WebSocketMessage()

    data class ErrorEvent(
        val error: ErrorInfo
    ) : WebSocketMessage()

    data class Complete(
        val message: String
    ) : WebSocketMessage()
}

data class ServerInfo(
    val version: String,
    val model: ModelInfo,
    val capabilities: List<String>
)

data class ModelInfo(
    val provider: String,
    @SerializedName("model_name") val modelName: String,
    val capabilities: List<String>
)

data class ErrorInfo(
    val code: String,
    val message: String
)

data class FileNode(
    val name: String,
    val path: String,
    val isDirectory: Boolean,
    val children: List<FileNode> = emptyList(),
    var isExpanded: Boolean = false
)
