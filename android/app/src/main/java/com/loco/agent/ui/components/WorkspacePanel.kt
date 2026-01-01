package com.loco.agent.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.loco.agent.data.model.FileNode
import com.loco.agent.data.model.Workspace

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WorkspacePanel(
    workspaces: List<Workspace>,
    currentWorkspace: Workspace?,
    fileTree: List<FileNode>,
    onWorkspaceSelect: (Workspace) -> Unit,
    onFileSelect: (FileNode) -> Unit,
    onClose: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenTerminal: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxSize()
    ) {
        // Header
        TopAppBar(
            title = { Text("Workspaces") },
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
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant
            )
        )

        // Workspace Selector
        if (workspaces.isNotEmpty()) {
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                shape = MaterialTheme.shapes.medium,
                tonalElevation = 2.dp
            ) {
                Column(
                    modifier = Modifier.padding(16.dp)
                ) {
                    Text(
                        text = "Current Workspace",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    workspaces.forEach { workspace ->
                        WorkspaceItem(
                            workspace = workspace,
                            isSelected = workspace.id == currentWorkspace?.id,
                            onClick = { onWorkspaceSelect(workspace) }
                        )
                    }
                }
            }
        }

        // File Tree
        if (currentWorkspace != null) {
            Divider(modifier = Modifier.padding(vertical = 8.dp))
            
            Text(
                text = "Files",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                fontWeight = FontWeight.Bold
            )

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(horizontal = 16.dp)
            ) {
                items(fileTree) { node ->
                    FileTreeItem(
                        node = node,
                        level = 0,
                        onFileSelect = onFileSelect
                    )
                }
            }
        } else {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Icon(
                        Icons.Default.Folder,
                        contentDescription = null,
                        modifier = Modifier.size(48.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                    Text(
                        text = "No workspace selected",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
fun WorkspaceItem(
    workspace: Workspace,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        color = if (isSelected) 
            MaterialTheme.colorScheme.primaryContainer 
        else 
            MaterialTheme.colorScheme.surface,
        shape = MaterialTheme.shapes.small
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Default.Folder,
                contentDescription = null,
                tint = if (isSelected) 
                    MaterialTheme.colorScheme.onPrimaryContainer 
                else 
                    MaterialTheme.colorScheme.onSurface
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = workspace.name,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                    color = if (isSelected) 
                        MaterialTheme.colorScheme.onPrimaryContainer 
                    else 
                        MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = workspace.path,
                    style = MaterialTheme.typography.bodySmall,
                    color = if (isSelected) 
                        MaterialTheme.colorScheme.onPrimaryContainer 
                    else 
                        MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
fun FileTreeItem(
    node: FileNode,
    level: Int,
    onFileSelect: (FileNode) -> Unit
) {
    var isExpanded by remember { mutableStateOf(node.isExpanded) }

    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable {
                    if (node.isDirectory) {
                        isExpanded = !isExpanded
                    } else {
                        onFileSelect(node)
                    }
                }
                .padding(
                    start = (16 * level).dp,
                    top = 8.dp,
                    bottom = 8.dp,
                    end = 8.dp
                ),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = when {
                    node.isDirectory && isExpanded -> Icons.Default.KeyboardArrowDown
                    node.isDirectory -> Icons.Default.KeyboardArrowRight
                    else -> Icons.Default.Description
                },
                contentDescription = null,
                modifier = Modifier.size(20.dp),
                tint = if (node.isDirectory) 
                    MaterialTheme.colorScheme.primary 
                else 
                    MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = node.name,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
        }

        if (node.isDirectory && isExpanded) {
            node.children.forEach { childNode ->
                FileTreeItem(
                    node = childNode,
                    level = level + 1,
                    onFileSelect = onFileSelect
                )
            }
        }
    }
}
