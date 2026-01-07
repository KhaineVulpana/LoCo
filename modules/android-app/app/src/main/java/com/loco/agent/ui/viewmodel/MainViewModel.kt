package com.loco.agent.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.loco.agent.data.model.*
import com.loco.agent.data.repository.LoCoRepository
import com.loco.agent.ui.components.TerminalLine
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class MainUiState(
    val workspaces: List<Workspace> = emptyList(),
    val sessions: List<Session> = emptyList(),
    val currentWorkspace: Workspace? = null,
    val currentSession: Session? = null,
    val chatMessages: List<ChatMessage> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val isConnected: Boolean = false,
    val serverInfo: ServerInfo? = null,
    val fileTree: List<FileNode> = emptyList(),
    val currentFile: FileContent? = null,
    val terminalOutput: List<TerminalLine> = emptyList(),
    val serverUrl: String = "http://192.168.1.100:3199"
)

data class FileContent(
    val path: String,
    val content: String,
    val language: String = "text"
)

@HiltViewModel
class MainViewModel @Inject constructor(
    private val repository: LoCoRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(MainUiState())
    val uiState: StateFlow<MainUiState> = _uiState.asStateFlow()

    private var currentMessageBuilder = StringBuilder()

    init {
        loadWorkspaces()
    }

    fun loadWorkspaces() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            repository.getWorkspaces()
                .onSuccess { workspaces ->
                    _uiState.update { it.copy(workspaces = workspaces, isLoading = false) }
                    if (workspaces.isNotEmpty() && _uiState.value.currentWorkspace == null) {
                        selectWorkspace(workspaces.first())
                    }
                }
                .onFailure { error ->
                    _uiState.update { 
                        it.copy(error = error.message, isLoading = false) 
                    }
                }
        }
    }

    fun selectWorkspace(workspace: Workspace) {
        _uiState.update { it.copy(currentWorkspace = workspace) }
        loadSessionsForWorkspace(workspace.id)
        loadFileTree(workspace.path)
    }

    private fun loadSessionsForWorkspace(workspaceId: String) {
        viewModelScope.launch {
            repository.getSessions(workspaceId)
                .onSuccess { sessions ->
                    _uiState.update { it.copy(sessions = sessions) }
                }
                .onFailure { error ->
                    _uiState.update { it.copy(error = error.message) }
                }
        }
    }

    fun createNewSession() {
        val workspace = _uiState.value.currentWorkspace ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            repository.createSession(workspace.id)
                .onSuccess { session ->
                    _uiState.update { 
                        it.copy(
                            currentSession = session,
                            sessions = it.sessions + session,
                            chatMessages = emptyList(),
                            isLoading = false
                        ) 
                    }
                    connectToSession(session.id)
                }
                .onFailure { error ->
                    _uiState.update { 
                        it.copy(error = error.message, isLoading = false) 
                    }
                }
        }
    }

    fun selectSession(session: Session) {
        _uiState.update { 
            it.copy(
                currentSession = session,
                chatMessages = emptyList()
            ) 
        }
        connectToSession(session.id)
    }

    private fun connectToSession(sessionId: String) {
        viewModelScope.launch {
            repository.connectToSession(sessionId).collect { message ->
                when (message) {
                    is WebSocketMessage.ServerHello -> {
                        _uiState.update { 
                            it.copy(
                                isConnected = true,
                                serverInfo = message.serverInfo
                            ) 
                        }
                    }
                    is WebSocketMessage.TextDelta -> {
                        currentMessageBuilder.append(message.delta)
                        updateOrAddAssistantMessage(currentMessageBuilder.toString())
                    }
                    is WebSocketMessage.Complete -> {
                        currentMessageBuilder.clear()
                    }
                    is WebSocketMessage.ErrorEvent -> {
                        _uiState.update { 
                            it.copy(error = message.error.message) 
                        }
                    }
                    is WebSocketMessage.ThinkingEvent -> {
                        // Could show thinking indicator
                    }
                    is WebSocketMessage.ToolUseEvent -> {
                        // Could show tool usage
                    }
                    is WebSocketMessage.ToolResultEvent -> {
                        // Could show tool results
                    }
                }
            }
        }
    }

    fun sendMessage(text: String) {
        if (text.isBlank()) return
        
        val userMessage = ChatMessage(
            id = java.util.UUID.randomUUID().toString(),
            role = "user",
            content = text
        )
        
        _uiState.update { 
            it.copy(chatMessages = it.chatMessages + userMessage) 
        }
        
        repository.sendMessage(text)
        currentMessageBuilder.clear()
    }

    private fun updateOrAddAssistantMessage(content: String) {
        _uiState.update { state ->
            val messages = state.chatMessages.toMutableList()
            val lastMessage = messages.lastOrNull()
            
            if (lastMessage?.role == "assistant") {
                messages[messages.lastIndex] = lastMessage.copy(content = content)
            } else {
                messages.add(
                    ChatMessage(
                        id = java.util.UUID.randomUUID().toString(),
                        role = "assistant",
                        content = content
                    )
                )
            }
            
            state.copy(chatMessages = messages)
        }
    }

    private fun loadFileTree(workspacePath: String) {
        // Mock file tree - in real implementation, would call API
        val mockTree = listOf(
            FileNode("src", "$workspacePath/src", true, listOf(
                FileNode("main.kt", "$workspacePath/src/main.kt", false),
                FileNode("utils", "$workspacePath/src/utils", true, listOf(
                    FileNode("helpers.kt", "$workspacePath/src/utils/helpers.kt", false)
                ))
            )),
            FileNode("README.md", "$workspacePath/README.md", false)
        )
        _uiState.update { it.copy(fileTree = mockTree) }
    }

    fun loadFile(path: String) {
        // Mock file loading - in real implementation, would read from local storage or API
        viewModelScope.launch {
            val content = "// Sample file content for: $path\nfun main() {\n    println(\"Hello World\")\n}"
            val language = when {
                path.endsWith(".kt") -> "kotlin"
                path.endsWith(".java") -> "java"
                path.endsWith(".py") -> "python"
                path.endsWith(".js") -> "javascript"
                else -> "text"
            }
            _uiState.update { 
                it.copy(
                    currentFile = FileContent(path, content, language)
                ) 
            }
        }
    }

    fun saveFile(path: String, content: String) {
        // Mock file saving - in real implementation, would save to local storage or API
        viewModelScope.launch {
            // Save logic here
        }
    }

    fun toggleFileNode(node: FileNode) {
        // Toggle expansion state
    }

    fun executeCommand(command: String) {
        viewModelScope.launch {
            // Add command to terminal output
            val commandLine = TerminalLine(command, isCommand = true)
            _uiState.update { 
                it.copy(terminalOutput = it.terminalOutput + commandLine)
            }
            
            // Mock command execution - in real app, would execute via backend
            val output = when {
                command.startsWith("ls") -> "file1.kt\nfile2.kt\nREADME.md"
                command.startsWith("pwd") -> "/workspace/project"
                command.startsWith("echo") -> command.substringAfter("echo").trim()
                else -> "Command not found: $command"
            }
            
            val outputLine = TerminalLine(output, isCommand = false)
            _uiState.update { 
                it.copy(terminalOutput = it.terminalOutput + outputLine)
            }
        }
    }

    fun updateServerUrl(url: String) {
        _uiState.update { it.copy(serverUrl = url) }
        // In real app, would reinitialize network module with new URL
    }

    override fun onCleared() {
        super.onCleared()
        repository.disconnect()
    }
}
