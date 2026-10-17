@file:OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package app.localpassword

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlin.math.roundToInt

@Composable
fun CreatePane(model: PasswordModel) {
    val options = CharacterOptions(model.uppercase, model.lowercase, model.digits, model.symbols,
        model.excludeAmbiguous, model.excludedCharacters)
    LaunchedEffect(options, model.length, model.wordCount, model.wordsMode, model.autoGenerate) {
        delay(350)
        model.regenerateIfOptionsChanged()
    }
    val colors = MaterialTheme.colorScheme
    ScreenSurface {
        Text("Generated password", style = MaterialTheme.typography.titleLarge)
        Text(
            when { model.current.isEmpty() -> "Your next password starts here."
                model.showGenerated -> model.current
                else -> "••••••••••••••••" },
            style = MaterialTheme.typography.titleLarge.copy(fontFamily = FontFamily.Monospace),
            color = colors.onPrimaryContainer,
            modifier = Modifier.fillMaxWidth().background(colors.primaryContainer, MaterialTheme.shapes.medium)
                .padding(AppSpacing.large),
        )
        if (model.current.isNotEmpty()) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
                Text(model.strength, style = MaterialTheme.typography.labelLarge,
                    color = if (model.strength == "Weak") colors.error else colors.primary)
                Text(model.bitsLabel, style = MaterialTheme.typography.bodyMedium)
            }
            LinearProgressIndicator(progress = { model.fraction }, modifier = Modifier.fillMaxWidth(),
                color = if (model.strength == "Weak") colors.error else colors.primary)
            Text("Estimate for the displayed password. ${model.note}", style = MaterialTheme.typography.bodySmall,
                color = colors.onSurfaceVariant)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
                TextButton(onClick = { model.showGenerated = !model.showGenerated }) {
                    Text(if (model.showGenerated) "Hide password" else "Show password")
                }
                TextButton(onClick = { model.copy(model.current) }, enabled = !model.generating) { Text("Copy") }
            }
        }
        if (model.error.isNotEmpty()) {
            Text(model.error, color = colors.error, style = MaterialTheme.typography.bodyMedium)
        }
        Button(onClick = model::generate, enabled = !model.busy && !model.generating,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
            Text(if (model.generating) "Generating…" else if (model.current.isEmpty()) "Generate password" else "Generate another")
        }
        OutlinedButton(onClick = { model.error = ""; model.askSaveName = true },
            enabled = model.current.isNotEmpty() && !model.busy && !model.generating,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Save to Vault") }
    }
    ScreenSurface {
        Text("Generator options", style = MaterialTheme.typography.titleLarge)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
            FilterChip(selected = !model.wordsMode, onClick = { model.wordsMode = false }, label = { Text("Characters") })
            FilterChip(selected = model.wordsMode, onClick = { model.wordsMode = true }, label = { Text("Words") })
        }
        val value = if (model.wordsMode) model.wordCount else model.length
        val maximum = if (model.wordsMode) 20 else 128
        val label = if (model.wordsMode) "Word count" else "Password length"
        fun change(value: Int) { if (model.wordsMode) model.wordCount = value else model.length = value }
        FlowRow(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("$label: $value", style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.align(Alignment.CenterVertically))
            Row {
                TextButton(onClick = { change(value - 1) }, enabled = value > 1,
                    modifier = Modifier.semantics { contentDescription = "Decrease $label" }) { Text("−") }
                TextButton(onClick = { change(value + 1) }, enabled = value < maximum,
                    modifier = Modifier.semantics { contentDescription = "Increase $label" }) { Text("+") }
            }
        }
        Slider(value = value.toFloat(), onValueChange = { change(it.roundToInt()) },
            valueRange = 1f..maximum.toFloat(), steps = maximum - 2,
            modifier = Modifier.semantics { contentDescription = label })
        if (!model.wordsMode) {
            GeneratorToggle("Uppercase (A–Z)", model.uppercase) { model.uppercase = it }
            GeneratorToggle("Lowercase (a–z)", model.lowercase) { model.lowercase = it }
            GeneratorToggle("Numbers (0–9)", model.digits) { model.digits = it }
            GeneratorToggle("Symbols", model.symbols) { model.symbols = it }
            Text("Symbols include quotes, backticks, and backslashes.", style = MaterialTheme.typography.bodySmall)
            GeneratorToggle("Exclude ambiguous characters", model.excludeAmbiguous) { model.excludeAmbiguous = it }
            Text("Omits 0, O, o, 1, l, I and |.", style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(value = model.excludedCharacters, onValueChange = { model.excludedCharacters = it },
                label = { Text("Also exclude") }, supportingText = { Text("Characters a website does not accept") },
                singleLine = true, modifier = Modifier.fillMaxWidth())
        }
        GeneratorToggle("Regenerate when options change", model.autoGenerate) { model.autoGenerate = it }
        Text(if (model.autoGenerate) "After the first result, changing options replaces the generated password."
            else "Options apply when you next choose Generate.",
            style = MaterialTheme.typography.bodySmall, color = colors.onSurfaceVariant)
    }
    if (model.askSaveName) {
        AlertDialog(onDismissRequest = { model.askSaveName = false }, title = { Text("Save to Vault") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
                    OutlinedTextField(value = model.name, onValueChange = { model.name = it }, singleLine = true,
                        modifier = Modifier.fillMaxWidth(), label = { Text("Name") }, placeholder = { Text("Email, bank, router") })
                    Text("Saving under an existing name replaces that entry’s password.", style = MaterialTheme.typography.bodySmall)
                    Text("If you lose both the vault passphrase and recovery key, your saved passwords cannot be recovered.",
                        style = MaterialTheme.typography.bodySmall)
                    if (model.error.isNotEmpty()) Text(model.error, color = colors.error)
                }
            },
            confirmButton = { TextButton(onClick = model::submitGeneratedName,
                enabled = model.name.isNotBlank() && !model.busy) { Text("Continue") } },
            dismissButton = { TextButton(onClick = { model.askSaveName = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun GeneratorToggle(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().heightIn(min = 48.dp)
        .toggleable(value = checked, role = Role.Switch, onValueChange = onCheckedChange),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
        Text(label, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
        Switch(checked = checked, onCheckedChange = null)
    }
}
