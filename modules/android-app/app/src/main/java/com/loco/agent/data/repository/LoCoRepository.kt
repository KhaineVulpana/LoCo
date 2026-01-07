package com.loco.agent.data.repository

import com.loco.agent.data.model.*
import com.loco.agent.data.remote.LoCoApiService
import com.loco.agent.data.remote.WebSocketManager
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LoCoRepository @Inject constructor(
    private val apiService: LoCoApiService,
    private val webSocketManager: WebSocketManager
) {
    suspend fun getHealth(): Result<HealthResponse> = runCatching {
        apiService.getHealth()
    }

    suspend fun getWorkspaces(): Result<List<Workspace>> = runCatching {
        apiService.getWorkspaces()
    }

    suspend fun registerWorkspace(path: String, name: String? = null): Result<Workspace> = runCatching {
        apiService.registerWorkspace(WorkspaceCreate(path, name))
    }

    suspend fun getWorkspace(workspaceId: String): Result<Workspace> = runCatching {
        apiService.getWorkspace(workspaceId)
    }

    suspend fun getSessions(workspaceId: String? = null): Result<List<Session>> = runCatching {
        apiService.getSessions(workspaceId)
    }

    suspend fun createSession(
        workspaceId: String,
        modelProvider: String? = null,
        modelName: String? = null
    ): Result<Session> = runCatching {
        apiService.createSession(
            SessionCreate(
                workspaceId = workspaceId,
                modelProvider = modelProvider,
                modelName = modelName
            )
        )
    }

    suspend fun getSession(sessionId: String): Result<Session> = runCatching {
        apiService.getSession(sessionId)
    }

    suspend fun deleteSession(sessionId: String): Result<Boolean> = runCatching {
        apiService.deleteSession(sessionId)["success"] ?: false
    }

    fun connectToSession(sessionId: String): Flow<WebSocketMessage> {
        return webSocketManager.connectSession(sessionId)
    }

    fun sendMessage(message: String, context: Map<String, Any> = emptyMap()) {
        webSocketManager.sendMessage(message, context)
    }

    fun disconnect() {
        webSocketManager.disconnect()
    }
}
