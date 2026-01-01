package com.loco.agent.data.remote

import com.loco.agent.data.model.*
import retrofit2.http.*

interface LoCoApiService {
    @GET("/v1/health")
    suspend fun getHealth(): HealthResponse

    @GET("/v1/workspaces")
    suspend fun getWorkspaces(): List<Workspace>

    @POST("/v1/workspaces/register")
    suspend fun registerWorkspace(@Body workspace: WorkspaceCreate): Workspace

    @GET("/v1/workspaces/{id}")
    suspend fun getWorkspace(@Path("id") workspaceId: String): Workspace

    @GET("/v1/sessions")
    suspend fun getSessions(@Query("workspace_id") workspaceId: String? = null): List<Session>

    @POST("/v1/sessions")
    suspend fun createSession(@Body session: SessionCreate): Session

    @GET("/v1/sessions/{id}")
    suspend fun getSession(@Path("id") sessionId: String): Session

    @DELETE("/v1/sessions/{id}")
    suspend fun deleteSession(@Path("id") sessionId: String): Map<String, Boolean>
}
