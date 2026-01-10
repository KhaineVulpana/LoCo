package com.loco.agent.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.loco.agent.ui.viewmodel.FileContent
import androidx.compose.foundation.shape.RoundedCornerShape

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CodeEditorPanel(
    file: FileContent?,
    onSave: (String, String) -> Unit,
    onClose: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenTerminal: () -> Unit
) {
    var editedContent by remember(file?.path) { 
        mutableStateOf(file?.content ?: "") 
    }
    var hasUnsavedChanges by remember(file?.path) { mutableStateOf(false) }

    LaunchedEffect(file?.content) {
        file?.content?.let { 
            editedContent = it
            hasUnsavedChanges = false
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.surface)
    ) {
        // Header
        TopAppBar(
            title = { 
                Column {
                    Text(
                        text = file?.path?.substringAfterLast("/") ?: "Code Editor",
                        style = MaterialTheme.typography.titleMedium
                    )
                    file?.path?.let {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            },
            navigationIcon = {
                IconButton(onClick = onClose) {
                    Icon(Icons.Default.Close, "Close")
                }
            },
            actions = {
                IconButton(onClick = onOpenTerminal) {
                    Icon(Icons.Default.Terminal, "Open terminal")
                }
                IconButton(onClick = onOpenSettings) {
                    Icon(Icons.Default.Settings, "Open settings")
                }
                if (hasUnsavedChanges) {
                    TextButton(
                        onClick = { 
                            file?.path?.let { path ->
                                onSave(path, editedContent)
                                hasUnsavedChanges = false
                            }
                        }
                    ) {
                        Icon(Icons.Default.Save, contentDescription = null)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Save")
                    }
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = MaterialTheme.colorScheme.surface
            )
        )

        // Editor
        if (file != null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.surface)
                    .padding(16.dp)
            ) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Box(modifier = Modifier.padding(16.dp)) {
                        BasicTextField(
                            value = editedContent,
                            onValueChange = {
                                editedContent = it
                                hasUnsavedChanges = it != file.content
                            },
                            modifier = Modifier.fillMaxSize(),
                            textStyle = TextStyle(
                                fontFamily = FontFamily.Monospace,
                                fontSize = 14.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            ),
                            cursorBrush = SolidColor(MaterialTheme.colorScheme.primary)
                        )
                    }
                }
            }
        } else {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = androidx.compose.ui.Alignment.Center
            ) {
                Column(
                    horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Icon(
                        Icons.Default.Code,
                        contentDescription = null,
                        modifier = Modifier.size(48.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                    Text(
                        text = "No file selected",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = "Select a file from the workspace to edit",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}
