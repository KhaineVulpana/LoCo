package com.loco.agent.data.model

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ModelsTest {

    private val gson = Gson()

    @Test
    fun workspace_deserializes_from_json() {
        val json = """
            {
              "id": "ws-1",
              "path": "C:/Projects/LoCo",
              "name": "LoCo",
              "created_at": "2025-01-01T00:00:00Z",
              "index_status": "ready",
              "total_files": 10,
              "indexed_files": 10
            }
        """.trimIndent()

        val workspace = gson.fromJson(json, Workspace::class.java)
        assertEquals("ws-1", workspace.id)
        assertEquals("ready", workspace.indexStatus)
        assertEquals(10, workspace.indexedFiles)
    }

    @Test
    fun session_deserializes_from_json() {
        val json = """
            {
              "id": "sess-1",
              "workspace_id": "ws-1",
              "title": "Test",
              "model_provider": "ollama",
              "model_name": "qwen",
              "context_window": 8192,
              "created_at": "2025-01-01T00:00:00Z",
              "status": "active"
            }
        """.trimIndent()

        val session = gson.fromJson(json, Session::class.java)
        assertEquals("sess-1", session.id)
        assertEquals("ws-1", session.workspaceId)
        assertEquals("ollama", session.modelProvider)
    }

    @Test
    fun chat_message_defaults_timestamp() {
        val message = ChatMessage(id = "m1", role = "user", content = "Hello")
        assertTrue(message.timestamp > 0)
    }

    @Test
    fun file_node_defaults_children() {
        val node = FileNode(name = "root", path = "/tmp", isDirectory = true)
        assertNotNull(node.children)
        assertEquals(0, node.children.size)
    }
}
