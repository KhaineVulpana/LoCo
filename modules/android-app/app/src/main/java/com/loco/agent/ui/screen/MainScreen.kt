package com.loco.agent.ui.screen

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.window.layout.WindowMetricsCalculator
import com.loco.agent.ui.components.*
import com.loco.agent.ui.viewmodel.MainViewModel
import kotlinx.coroutines.launch
import kotlin.math.absoluteValue
import androidx.compose.ui.platform.LocalContext

enum class DrawerState {
    CLOSED,
    LEFT_OPEN,
    RIGHT_OPEN
}

enum class OverlayState {
    NONE,
    TERMINAL_OPEN,
    SETTINGS_OPEN
}

@Composable
fun MainScreen(
    viewModel: MainViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var drawerState by remember { mutableStateOf(DrawerState.CLOSED) }
    var overlayState by remember { mutableStateOf(OverlayState.NONE) }
    var offsetX by remember { mutableStateOf(0f) }
    var offsetYBottom by remember { mutableStateOf(0f) }
    var offsetYTop by remember { mutableStateOf(0f) }
    val scope = rememberCoroutineScope()
    val configuration = LocalConfiguration.current
    val context = LocalContext.current
    
    // Check if device is in dual-screen mode (unfolded)
    val screenWidthDp = configuration.screenWidthDp
    val isDualScreen = screenWidthDp >= 600 // Typical foldable threshold
    
    val density = LocalDensity.current
    val screenWidthPx = with(density) { screenWidthDp.dp.toPx() }
    val screenHeightPx = with(density) { configuration.screenHeightDp.dp.toPx() }
    
    // Drawer and overlay dimensions
    val drawerWidth = if (isDualScreen) screenWidthPx * 0.5f else screenWidthPx * 0.8f
    val terminalHeight = screenHeightPx * 0.4f
    val dragThreshold = 100f

    Box(
        modifier = Modifier
            .fillMaxSize()
            .pointerInput(Unit) {
                // Horizontal drag for left/right panels
                detectHorizontalDragGestures(
                    onDragEnd = {
                        scope.launch {
                            when {
                                offsetX > dragThreshold && drawerState == DrawerState.CLOSED -> {
                                    drawerState = DrawerState.LEFT_OPEN
                                    offsetX = if (isDualScreen) drawerWidth else drawerWidth
                                }
                                offsetX < -dragThreshold && drawerState == DrawerState.CLOSED -> {
                                    drawerState = DrawerState.RIGHT_OPEN
                                    offsetX = if (isDualScreen) -drawerWidth else -drawerWidth
                                }
                                offsetX < -dragThreshold && drawerState == DrawerState.LEFT_OPEN -> {
                                    drawerState = DrawerState.CLOSED
                                    offsetX = 0f
                                }
                                offsetX > dragThreshold && drawerState == DrawerState.RIGHT_OPEN -> {
                                    drawerState = DrawerState.CLOSED
                                    offsetX = 0f
                                }
                                else -> {
                                    offsetX = when (drawerState) {
                                        DrawerState.LEFT_OPEN -> if (isDualScreen) drawerWidth else drawerWidth
                                        DrawerState.RIGHT_OPEN -> if (isDualScreen) -drawerWidth else -drawerWidth
                                        DrawerState.CLOSED -> 0f
                                    }
                                }
                            }
                        }
                    },
                    onHorizontalDrag = { _, dragAmount ->
                        if (overlayState == OverlayState.NONE) {
                            offsetX = (offsetX + dragAmount).coerceIn(-drawerWidth, drawerWidth)
                        }
                    }
                )
            }
            .pointerInput(Unit) {
                // Vertical drag from bottom for terminal
                detectVerticalDragGestures(
                    onDragEnd = {
                        scope.launch {
                            when {
                                offsetYBottom < -dragThreshold && overlayState == OverlayState.NONE -> {
                                    overlayState = OverlayState.TERMINAL_OPEN
                                    offsetYBottom = -terminalHeight
                                }
                                offsetYBottom > dragThreshold && overlayState == OverlayState.TERMINAL_OPEN -> {
                                    overlayState = OverlayState.NONE
                                    offsetYBottom = 0f
                                }
                                else -> {
                                    offsetYBottom = when (overlayState) {
                                        OverlayState.TERMINAL_OPEN -> -terminalHeight
                                        else -> 0f
                                    }
                                }
                            }
                        }
                    },
                    onVerticalDrag = { change, dragAmount ->
                        val y = change.position.y
                        // Only allow drag from bottom 20% of screen
                        if (y > screenHeightPx * 0.8f || overlayState == OverlayState.TERMINAL_OPEN) {
                            offsetYBottom = (offsetYBottom + dragAmount).coerceIn(-terminalHeight, 0f)
                        }
                    }
                )
            }
            .pointerInput(Unit) {
                // Vertical drag from top for settings
                detectVerticalDragGestures(
                    onDragEnd = {
                        scope.launch {
                            when {
                                offsetYTop > dragThreshold && overlayState == OverlayState.NONE -> {
                                    overlayState = OverlayState.SETTINGS_OPEN
                                    offsetYTop = screenHeightPx
                                }
                                offsetYTop < -dragThreshold && overlayState == OverlayState.SETTINGS_OPEN -> {
                                    overlayState = OverlayState.NONE
                                    offsetYTop = 0f
                                }
                                else -> {
                                    offsetYTop = when (overlayState) {
                                        OverlayState.SETTINGS_OPEN -> screenHeightPx
                                        else -> 0f
                                    }
                                }
                            }
                        }
                    },
                    onVerticalDrag = { change, dragAmount ->
                        val y = change.position.y
                        // Only allow drag from top 20% of screen
                        if (y < screenHeightPx * 0.2f || overlayState == OverlayState.SETTINGS_OPEN) {
                            offsetYTop = (offsetYTop + dragAmount).coerceIn(0f, screenHeightPx)
                        }
                    }
                )
            }
    ) {
        // Left Drawer - Workspace/Files
        Box(
            modifier = Modifier
                .fillMaxHeight()
                .width(with(density) { drawerWidth.toDp() })
                .offset(x = with(density) {
                    val baseOffset = if (isDualScreen) {
                        // In dual screen, drawer slides from left edge
                        if (drawerState == DrawerState.LEFT_OPEN) 0f else -drawerWidth + offsetX.coerceAtLeast(0f)
                    } else {
                        // In single screen, same as before
                        if (drawerState == DrawerState.LEFT_OPEN) 0f else -drawerWidth + offsetX.coerceAtLeast(0f)
                    }
                    baseOffset.toDp()
                })
                .background(MaterialTheme.colorScheme.surfaceVariant)
        ) {
            WorkspacePanel(
                workspaces = uiState.workspaces,
                currentWorkspace = uiState.currentWorkspace,
                fileTree = uiState.fileTree,
                onWorkspaceSelect = { viewModel.selectWorkspace(it) },
                onFileSelect = { viewModel.loadFile(it.path) },
                onClose = { 
                    drawerState = DrawerState.CLOSED
                    offsetX = 0f
                },
                onOpenSettings = {
                    overlayState = OverlayState.SETTINGS_OPEN
                    offsetYTop = screenHeightPx
                },
                onOpenTerminal = {
                    overlayState = OverlayState.TERMINAL_OPEN
                    offsetYBottom = -terminalHeight
                }
            )
        }

        // Center Panel - Chat
        Box(
            modifier = Modifier
                .fillMaxSize()
                .offset(x = with(density) { 
                    val horizontalOffset = if (isDualScreen) {
                        // In dual screen mode, panels slide to opposite sides
                        when (drawerState) {
                            DrawerState.LEFT_OPEN -> drawerWidth / 2
                            DrawerState.RIGHT_OPEN -> -drawerWidth / 2
                            DrawerState.CLOSED -> 0f
                        } + offsetX / 2
                    } else {
                        offsetX
                    }
                    horizontalOffset.toDp()
                })
        ) {
            ChatPanel(
                messages = uiState.chatMessages,
                isConnected = uiState.isConnected,
                serverInfo = uiState.serverInfo,
                currentSession = uiState.currentSession,
                onSendMessage = { viewModel.sendMessage(it) },
                onNewSession = { viewModel.createNewSession() },
                onOpenWorkspace = { 
                    drawerState = DrawerState.LEFT_OPEN
                    offsetX = drawerWidth
                },
                onOpenCodeEditor = { 
                    drawerState = DrawerState.RIGHT_OPEN
                    offsetX = -drawerWidth
                },
                onOpenSettings = {
                    overlayState = OverlayState.SETTINGS_OPEN
                    offsetYTop = screenHeightPx
                },
                onOpenTerminal = {
                    overlayState = OverlayState.TERMINAL_OPEN
                    offsetYBottom = -terminalHeight
                }
            )
        }

        // Right Drawer - Code Editor
        Box(
            modifier = Modifier
                .fillMaxHeight()
                .width(with(density) { drawerWidth.toDp() })
                .offset(x = with(density) {
                    val baseOffset = if (isDualScreen) {
                        // In dual screen, drawer slides from right edge
                        if (drawerState == DrawerState.RIGHT_OPEN) 
                            screenWidthPx - drawerWidth
                        else 
                            screenWidthPx + offsetX.coerceAtMost(0f).absoluteValue
                    } else {
                        // In single screen, same as before
                        if (drawerState == DrawerState.RIGHT_OPEN) 
                            screenWidthPx - drawerWidth 
                        else 
                            screenWidthPx + offsetX.coerceAtMost(0f).absoluteValue
                    }
                    baseOffset.toDp()
                })
                .background(MaterialTheme.colorScheme.surface)
        ) {
            CodeEditorPanel(
                file = uiState.currentFile,
                onSave = { path, content -> viewModel.saveFile(path, content) },
                onClose = { 
                    drawerState = DrawerState.CLOSED
                    offsetX = 0f
                },
                onOpenSettings = {
                    overlayState = OverlayState.SETTINGS_OPEN
                    offsetYTop = screenHeightPx
                },
                onOpenTerminal = {
                    overlayState = OverlayState.TERMINAL_OPEN
                    offsetYBottom = -terminalHeight
                }
            )
        }

        // Bottom Overlay - Terminal (pulls up from bottom)
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(with(density) { terminalHeight.toDp() })
                .offset(y = with(density) {
                    (screenHeightPx + offsetYBottom).toDp()
                })
                .background(MaterialTheme.colorScheme.surface)
        ) {
            TerminalPanel(
                terminalOutput = uiState.terminalOutput,
                onExecuteCommand = { viewModel.executeCommand(it) },
                onClose = {
                    overlayState = OverlayState.NONE
                    offsetYBottom = 0f
                }
            )
        }

        // Top Overlay - Settings (pulls down from top, full screen)
        Box(
            modifier = Modifier
                .fillMaxSize()
                .offset(y = with(density) {
                    (offsetYTop - screenHeightPx).toDp()
                })
                .background(MaterialTheme.colorScheme.background)
        ) {
            SettingsPanel(
                serverUrl = uiState.serverUrl,
                onServerUrlChange = { viewModel.updateServerUrl(it) },
                onClose = {
                    overlayState = OverlayState.NONE
                    offsetYTop = 0f
                }
            )
        }
    }
}
