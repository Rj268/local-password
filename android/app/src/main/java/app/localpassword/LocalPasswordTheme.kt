package app.localpassword

import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.fragment.app.FragmentActivity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.activity.compose.LocalActivity
import androidx.compose.ui.unit.dp

private val EmeraldDark = darkColorScheme(
    primary = Color(0xFF72DBB4), onPrimary = Color(0xFF003828),
    primaryContainer = Color(0xFF00513C), onPrimaryContainer = Color(0xFF9CF2CE),
    secondary = Color(0xFFB0CCC0), onSecondary = Color(0xFF1D352B),
    secondaryContainer = Color(0xFF344C41), onSecondaryContainer = Color(0xFFCDE9DC),
    background = Color(0xFF0C1511), onBackground = Color(0xFFE1EAE3),
    surface = Color(0xFF121E18), onSurface = Color(0xFFE1EAE3),
    surfaceVariant = Color(0xFF263A30), onSurfaceVariant = Color(0xFFBCCDC2),
    surfaceContainer = Color(0xFF19271F), surfaceContainerHigh = Color(0xFF203027),
    surfaceContainerHighest = Color(0xFF293B30), surfaceContainerLow = Color(0xFF142219),
    outline = Color(0xFF86998D), outlineVariant = Color(0xFF3D5145),
    error = Color(0xFFFFB4AB), onError = Color(0xFF690005),
)

private val EmeraldLight = lightColorScheme(
    primary = Color(0xFF006C4E), onPrimary = Color.White,
    primaryContainer = Color(0xFF9CF2CE), onPrimaryContainer = Color(0xFF002116),
    secondary = Color(0xFF4C6357), onSecondary = Color.White,
    secondaryContainer = Color(0xFFCDE9DC), onSecondaryContainer = Color(0xFF092017),
    background = Color(0xFFF3F8F3), onBackground = Color(0xFF17231C),
    surface = Color(0xFFFAFDF9), onSurface = Color(0xFF17231C),
    surfaceVariant = Color(0xFFDCE9DF), onSurfaceVariant = Color(0xFF405348),
    surfaceContainer = Color(0xFFE8F1E9), surfaceContainerHigh = Color(0xFFE2ECE3),
    surfaceContainerHighest = Color(0xFFDCE6DD), surfaceContainerLow = Color(0xFFEDF5EE),
    outline = Color(0xFF6E8275), outlineVariant = Color(0xFFBDCEC1),
    error = Color(0xFFBA1A1A), onError = Color.White,
)

object AppSpacing {
    val small = 8.dp
    val medium = 12.dp
    val large = 16.dp
    val page = 20.dp
}

@Composable
fun LocalPasswordTheme(appearance: String, content: @Composable () -> Unit) {
    val dark = when (appearance) {
        "dark" -> true
        "light" -> false
        else -> isSystemInDarkTheme()
    }
    val activity = LocalActivity.current as? FragmentActivity
    SideEffect {
        activity?.enableEdgeToEdge(
            statusBarStyle = if (dark) SystemBarStyle.dark(android.graphics.Color.TRANSPARENT)
                else SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
            navigationBarStyle = if (dark) SystemBarStyle.dark(android.graphics.Color.TRANSPARENT)
                else SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
        )
    }
    MaterialTheme(
        colorScheme = if (dark) EmeraldDark else EmeraldLight,
        typography = Typography(),
        shapes = Shapes(
            extraSmall = RoundedCornerShape(8.dp), small = RoundedCornerShape(12.dp),
            medium = RoundedCornerShape(16.dp), large = RoundedCornerShape(24.dp),
            extraLarge = RoundedCornerShape(28.dp),
        ),
        content = content,
    )
}
