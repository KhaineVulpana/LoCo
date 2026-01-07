package com.loco.agent.data.repository

import com.google.gson.Gson
import com.loco.agent.data.model.*
import com.loco.agent.data.remote.LoCoApiService
import com.loco.agent.data.remote.WebSocketManager
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

private class FakeApiService : LoCoApiService {
    var lastWorkspaceCreate: WorkspaceCreate? = null
    var failSessions: Boolean = false

    override suspend fun getHealth(): HealthResponse {
        return HealthResponse(status = "ok", version = "0.1.0", protocolVersion = "1.0.0")
    }

    override suspend fun getWorkspaces(): List<Workspace> {
        return listOf(buildWorkspace("ws-1"))
    }

    override suspend fun registerWorkspace(workspace: WorkspaceCreate): Workspace {
        lastWorkspaceCreate = workspace
        return buildWorkspace("ws-2", workspace.path, workspace.name ?: "LoCo")
    }

    override suspend fun getWorkspace(workspaceId: String): Workspace {
        return buildWorkspace(workspaceId)
    }

    override suspend fun getSessions(workspaceId: String?): List<Session> {
        if (failSessions) {
            throw IllegalStateException("Failed")
        }
        return listOf(buildSession("sess-1", workspaceId ?: "ws-1"))
    }

    override suspend fun createSession(session: SessionCreate): Session {
        return buildSession("sess-2", session.workspaceId)
    }

    override suspend fun getSession(sessionId: String): Session {
        return buildSession(sessionId, "ws-1")
    }

    override suspend fun deleteSession(sessionId: String): Map<String, Boolean> {
        return mapOf("success" to true)
    }

    private fun buildWorkspace(
        id: String,
        path: String = "C:/Projects/LoCo",
        name: String = "LoCo"
    ): Workspace {
        return Workspace(
            id = id,
            path = path,
            name = name,
            createdAt = "2025-01-01T00:00:00Z",
            indexStatus = "ready",
            totalFiles = 10,
            indexedFiles = 10
        )
    }

    private fun buildSession(id: String, workspaceId: String): Session {
        return Session(
            id = id,
            workspaceId = workspaceId,
            title = null,
            modelProvider = "ollama",
            modelName = "qwen",
            contextWindow = 4096,
            createdAt = "2025-01-01T00:00:00Z",
            status = "active"
        )
    }
}

class LoCoRepositoryTest {
    private val apiService = FakeApiService()
    private val webSocketManager = WebSocketManager(OkHttpClient(), Gson(), "http://localhost")
    private val repository = LoCoRepository(apiService, webSocketManager)

    @Test
    fun getHealth_returns_success() = runBlocking {
        val result = repository.getHealth()
        assertTrue(result.isSuccess)
        assertEquals("ok", result.getOrThrow().status)
    }

    @Test
    fun registerWorkspace_passes_payload() = runBlocking {
        val result = repository.registerWorkspace("C:/Projects/LoCo", "LoCo")
        assertTrue(result.isSuccess)
        assertEquals("C:/Projects/LoCo", apiService.lastWorkspaceCreate?.path)
        assertEquals("LoCo", apiService.lastWorkspaceCreate?.name)
    }

    @Test
    fun getSessions_propagates_failure() = runBlocking {
        apiService.failSessions = true
        val result = repository.getSessions()
        assertTrue(result.isFailure)
    }
}
