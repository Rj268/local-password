package app.localpassword

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

@Composable
fun ScreenSurface(content: @Composable ColumnScope.() -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surface,
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(Modifier.padding(AppSpacing.large), verticalArrangement = Arrangement.spacedBy(AppSpacing.medium), content = content)
    }
}

/** Navigation state belongs to the existing ViewModel; this shell owns only scroll position. */
@Composable
fun AppShell(section: String, onSectionChange: (String) -> Unit, detailKey: String? = null, content: @Composable ColumnScope.() -> Unit) {
    Scaffold(
        modifier = Modifier.imePadding(),
        contentWindowInsets = WindowInsets.safeDrawing,
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surfaceContainer) {
                listOf("create" to "Create", "saved" to "Vault", "settings" to "Settings").forEach { (route, label) ->
                    NavigationBarItem(
                        selected = section == route,
                        onClick = { onSectionChange(route) },
                        icon = { DestinationIcon(route) },
                        label = { Text(label) },
                        alwaysShowLabel = true,
                    )
                }
            }
        },
    ) { padding ->
        val listScroll = remember(section) { ScrollState(0) }
        val detailScroll = remember(detailKey) { ScrollState(0) }
        val scroll = if (detailKey != null) detailScroll else listScroll
        Column(
            Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
                .verticalScroll(scroll).padding(AppSpacing.page),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.large),
        ) {
            Text("Local Password", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            Text(
                when (section) { "create" -> "Create"; "saved" -> "Vault"; else -> "Settings" },
                style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.semantics { heading() },
            )
            Text(
                when (section) {
                    "create" -> "Make a password. Save it when you’re ready."
                    "saved" -> "Your saved passwords and account details."
                    else -> "Appearance, app lock, and vault transfers."
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            content()
        }
    }
}

/** Decorative icons: NavigationBarItem supplies the spoken label and selected state. */
@Composable
private fun DestinationIcon(route: String) {
    val color = LocalContentColor.current
    Canvas(Modifier.size(24.dp)) {
        val u = size.width / 24f
        val stroke = 2f * u
        fun line(x: Float, y: Float, x2: Float, y2: Float) =
            drawLine(color, Offset(x * u, y * u), Offset(x2 * u, y2 * u), stroke)
        when (route) {
            "create" -> { line(12f, 4f, 12f, 20f); line(4f, 12f, 20f, 12f) }
            "saved" -> {
                drawRoundRect(color, Offset(5f * u, 10f * u), Size(14f * u, 11f * u),
                    androidx.compose.ui.geometry.CornerRadius(2f * u), style = Stroke(stroke))
                drawArc(color, 180f, 180f, false, Offset(8f * u, 3f * u), Size(8f * u, 14f * u), style = Stroke(stroke))
                line(12f, 14f, 12f, 17f)
            }
            else -> {
                listOf(6f to 8f, 12f to 16f, 18f to 10f).forEach { (y, x) ->
                    line(3f, y, 21f, y)
                    drawCircle(color, 3f * u, Offset(x * u, y * u))
                }
            }
        }
    }
}
