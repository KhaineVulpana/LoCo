package com.loco.agent.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val DarkColorScheme = darkColorScheme(
    primary = Color(0xFFF2A162),
    onPrimary = Color(0xFF2B1B10),
    secondary = Color(0xFF7DD3A5),
    onSecondary = Color(0xFF0F1A14),
    tertiary = Color(0xFFF2C14E),
    onTertiary = Color(0xFF1F1404),
    background = Color(0xFF0F1115),
    onBackground = Color(0xFFF5F6F8),
    surface = Color(0xFF151922),
    onSurface = Color(0xFFF5F6F8),
    surfaceVariant = Color(0xFF1E2431),
    onSurfaceVariant = Color(0xFFB6BCC8),
    outline = Color(0xFF2A3242),
    error = Color(0xFFFF7A7A),
    onError = Color(0xFF2B1111),
    errorContainer = Color(0xFF3A1A1A),
    onErrorContainer = Color(0xFFFBC0C0)
)

private val LightColorScheme = lightColorScheme(
    primary = Color(0xFF1976D2),
    secondary = Color(0xFF388E3C),
    tertiary = Color(0xFFF57C00),
    background = Color(0xFFFFFBFE),
    surface = Color(0xFFFFFFFF),
    surfaceVariant = Color(0xFFF5F5F5)
)

@Composable
fun LoCoTheme(
    darkTheme: Boolean = true,
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }
    
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = false
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
