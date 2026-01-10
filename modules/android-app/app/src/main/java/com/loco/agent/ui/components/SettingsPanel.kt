package com.loco.agent.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.shape.RoundedCornerShape

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsPanel(
    serverUrl: String,
    onServerUrlChange: (String) -> Unit,
    onClose: () -> Unit
) {
    var editedServerUrl by remember { mutableStateOf(serverUrl) }
    var isDarkMode by remember { mutableStateOf(false) }
    var autoConnectEnabled by remember { mutableStateOf(true) }
    var terminalFontSize by remember { mutableStateOf(14) }
    var editorFontSize by remember { mutableStateOf(14) }

    Column(
        modifier = Modifier.fillMaxSize()
    ) {
        // Header
        TopAppBar(
            title = { Text("Settings") },
            navigationIcon = {
                IconButton(onClick = onClose) {
                    Icon(Icons.Default.ArrowBack, "Close settings")
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = MaterialTheme.colorScheme.surface
            )
        )

        // Settings Content
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            // Server Settings
            SettingsSection(title = "Server") {
                OutlinedTextField(
                    value = editedServerUrl,
                    onValueChange = { editedServerUrl = it },
                    label = { Text("Server URL") },
                    placeholder = { Text("http://192.168.1.100:3199") },
                    modifier = Modifier.fillMaxWidth(),
                    leadingIcon = {
                        Icon(Icons.Default.Dns, contentDescription = null)
                    },
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = MaterialTheme.colorScheme.primary,
                        unfocusedBorderColor = MaterialTheme.colorScheme.outline,
                        focusedContainerColor = MaterialTheme.colorScheme.surface,
                        unfocusedContainerColor = MaterialTheme.colorScheme.surface
                    )
                )
                
                Spacer(modifier = Modifier.height(8.dp))
                
                Button(
                    onClick = { onServerUrlChange(editedServerUrl) },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.Save, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Save Server URL")
                }
                
                Spacer(modifier = Modifier.height(8.dp))
                
                SettingSwitch(
                    title = "Auto-connect on startup",
                    description = "Automatically connect to server when app starts",
                    checked = autoConnectEnabled,
                    onCheckedChange = { autoConnectEnabled = it }
                )
            }

            // Appearance Settings
            SettingsSection(title = "Appearance") {
                SettingSwitch(
                    title = "Dark Mode",
                    description = "Use dark theme",
                    checked = isDarkMode,
                    onCheckedChange = { isDarkMode = it }
                )
                
                Spacer(modifier = Modifier.height(16.dp))
                
                Text(
                    text = "Editor Font Size: ${editorFontSize}sp",
                    style = MaterialTheme.typography.bodyMedium
                )
                Slider(
                    value = editorFontSize.toFloat(),
                    onValueChange = { editorFontSize = it.toInt() },
                    valueRange = 10f..24f,
                    steps = 13
                )
                
                Spacer(modifier = Modifier.height(16.dp))
                
                Text(
                    text = "Terminal Font Size: ${terminalFontSize}sp",
                    style = MaterialTheme.typography.bodyMedium
                )
                Slider(
                    value = terminalFontSize.toFloat(),
                    onValueChange = { terminalFontSize = it.toInt() },
                    valueRange = 10f..24f,
                    steps = 13
                )
            }

            // About Section
            SettingsSection(title = "About") {
                SettingInfoRow(
                    title = "Version",
                    value = "1.0.0"
                )
                SettingInfoRow(
                    title = "Build",
                    value = "20250101"
                )
                
                Spacer(modifier = Modifier.height(16.dp))
                
                OutlinedButton(
                    onClick = { /* Open GitHub */ },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.Code, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("View on GitHub")
                }
            }

            // Danger Zone
            SettingsSection(
                title = "Danger Zone",
                titleColor = MaterialTheme.colorScheme.error
            ) {
                OutlinedButton(
                    onClick = { /* Clear cache */ },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.error
                    )
                ) {
                    Icon(Icons.Default.Delete, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Clear All Data")
                }
            }
        }
    }
}

@Composable
fun SettingsSection(
    title: String,
    titleColor: androidx.compose.ui.graphics.Color = MaterialTheme.colorScheme.primary,
    content: @Composable ColumnScope.() -> Unit
) {
    Column(
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            color = titleColor
        )
        Surface(
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.surfaceVariant,
            tonalElevation = 1.dp
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                content = content
            )
        }
    }
}

@Composable
fun SettingSwitch(
    title: String,
    description: String?,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column(
            modifier = Modifier.weight(1f)
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyLarge
            )
            description?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange
        )
    }
}

@Composable
fun SettingInfoRow(
    title: String,
    value: String
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.bodyLarge
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
