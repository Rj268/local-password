package app.localpassword

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

private val Green = Color(0xFF0E6B52)
private val Cream = Color(0xFFEBE4D8)
private val Card = Color(0xFFF7F3EC)
private val Ink = Color(0xFF1C1915)
private val Muted = Color(0xFF5F584E)
private val Line = Color(0xFFDDD4C6)
private val Danger = Color(0xFF9C2F2F)
private val Night = Color(0xFF141210)
private val NightCard = Color(0xFF1C1916)
private val NightInk = Color(0xFFF6F1E7)
private val NightMuted = Color(0xFFB7A99A)

@Composable
fun LocalPasswordApp(model: PasswordModel = viewModel()) {
    val context = LocalContext.current
    val dark = model.dark
    val page = if (dark) Night else Cream
    val card = if (dark) NightCard else Card
    val ink = if (dark) NightInk else Ink
    val muted = if (dark) NightMuted else Muted
    val importVault = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return@rememberLauncherForActivityResult
        model.import(bytes)
    }
    val exportVault = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        val bytes = model.exportBytes() ?: return@rememberLauncherForActivityResult
        context.contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
        model.status = "Vault file written. Copy it back to the computer the same way."
    }

    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = page) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 20.dp, vertical = 28.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("ON THIS PHONE", color = Green, fontWeight = FontWeight.Bold, fontSize = 11.sp, letterSpacing = 1.5.sp)
                        Text("Local Password", color = ink, fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold, fontSize = 32.sp)
                    }
                    TextButton(onClick = { model.toggleDark() }) {
                        Text(if (dark) "Dark    On" else "Dark    Off", color = if (dark) Green else muted)
                    }
                }
                Text(
                    "Create a password here, or open Saved to use the ones you already kept. A passphrase or a recovery key opens all of them.",
                    color = muted,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Pill("Create", model.section == "create", dark) { model.section = "create" }
                    Pill("Saved", model.section == "saved", dark) { model.section = "saved" }
                }
                if (model.section == "create") {
                    CreatePane(model, card, ink, muted, dark)
                } else {
                    SavedPane(model, card, ink, muted, dark)
                }
                Text(
                    "Send vault shares the encrypted file with another device on the same Wi-Fi. The passphrase stays here.",
                    color = muted,
                    fontSize = 13.sp,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(
                        onClick = { model.sendVault() },
                        enabled = !model.busy && model.offerCode == null,
                    ) {
                        Text("Send vault", color = Green)
                    }
                    TextButton(
                        onClick = { model.askReceive = true },
                        enabled = !model.busy,
                    ) {
                        Text("Receive vault", color = Green)
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { importVault.launch(arrayOf("*/*")) }) {
                        Text("Import vault", color = Green)
                    }
                    TextButton(onClick = { exportVault.launch("saved.vault") }) {
                        Text("Export vault", color = Green)
                    }
                }
                if (model.error.isNotEmpty()) {
                    Text(model.error, color = Danger)
                }
                Text(model.status, color = muted)
                Text(
                    "Passphrases use the EFF large wordlist, created by Joseph Bonneau and the Electronic Frontier Foundation, under CC BY 3.0 US. The EFF does not endorse this project.",
                    color = muted,
                    fontSize = 12.sp,
                )
            }
        }
    }

    if (model.askNewPassphrase) {
        PassphraseDialog(
            title = "Choose a passphrase",
            body = "Choose a passphrase to lock saved passwords. It is not stored. If you lose both this passphrase and the recovery key, your saved passwords cannot be recovered.",
            confirm = true,
            busy = model.busy,
            onDismiss = { model.askNewPassphrase = false },
        ) { phrase, again -> model.createVault(phrase, again) }
    }
    if (model.askUnlock) {
        PassphraseDialog(
            title = "Unlock",
            body = "Enter the passphrase or the recovery key.",
            confirm = false,
            busy = model.busy,
            onDismiss = { model.askUnlock = false },
        ) { phrase, _ -> model.unlock(phrase, thenSave = model.section == "create" && model.current.isNotEmpty()) }
    }
    val offerCode = model.offerCode
    if (offerCode != null) {
        AlertDialog(
            onDismissRequest = { model.cancelOffer() },
            title = { Text("Send vault") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("On the other device, choose Receive vault and enter this code. Both devices need the same Wi-Fi. The passphrase stays on this phone.")
                    Text(offerCode, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 32.sp, color = Green)
                    if (model.offerWhere.isNotEmpty()) {
                        Text("If the code is not found, enter this address: ${model.offerWhere}")
                    }
                    Text("The offer lasts two minutes.")
                }
            },
            confirmButton = {
                TextButton(onClick = { model.cancelOffer() }) { Text("Cancel") }
            },
        )
    }
    if (model.askReceive) {
        ReceiveDialog(model)
    }
    if (model.askIncomingPassphrase) {
        PassphraseDialog(
            title = "Other vault",
            body = "This vault uses a different passphrase. Enter it to merge the passwords. It is not sent.",
            confirm = false,
            busy = model.busy,
            onDismiss = { model.dismissIncoming() },
        ) { phrase, _ -> model.mergeWithIncomingPassphrase(phrase) }
    }
    val recovery = model.recoveryKey
    if (recovery != null) {
        AlertDialog(
            onDismissRequest = {},
            title = { Text("Write down this recovery key") },
            text = {
                Text(
                    "$recovery\n\nIt opens your saved passwords if you forget the passphrase. It is shown once and is not stored.",
                    fontFamily = FontFamily.Monospace,
                )
            },
            confirmButton = {
                TextButton(onClick = { model.recoveryKey = null }) { Text("I wrote it down") }
            },
        )
    }
}

@Composable
private fun CreatePane(model: PasswordModel, card: Color, ink: Color, muted: Color, dark: Boolean) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(card, RoundedCornerShape(18.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Pill("Characters", !model.wordsMode, dark) { model.wordsMode = false }
            Pill("Words", model.wordsMode, dark) { model.wordsMode = true }
        }
        if (model.wordsMode) {
            Stepper("Words", model.wordCount, 1, 20, ink, muted) { model.wordCount = it }
        } else {
            Stepper("Length", model.length, 1, 128, ink, muted) { model.length = it }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill(if (model.digits) "Digits    On" else "Digits    Off", model.digits, dark) { model.digits = !model.digits }
                Pill(if (model.letters) "Letters    On" else "Letters    Off", model.letters, dark) { model.letters = !model.letters }
                Pill(if (model.symbols) "Symbols    On" else "Symbols    Off", model.symbols, dark) { model.symbols = !model.symbols }
            }
            Text("Symbols include quotes, backticks, and backslashes.", color = muted, fontSize = 13.sp)
        }
        GreenButton("Generate", model.busy, onClick = { model.generate() })
        Text("Result", color = ink, fontWeight = FontWeight.Bold)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(model.strength.ifEmpty { "Waiting to generate" }, color = if (model.strength == "Strong") Green else muted, modifier = Modifier.weight(1f))
            Text(model.bitsLabel, color = muted, fontSize = 13.sp)
        }
        LinearProgressIndicator(
            progress = { model.fraction },
            modifier = Modifier.fillMaxWidth().height(8.dp),
            color = if (model.strength == "Weak") Color(0xFFC47B2B) else Green,
            trackColor = Line,
        )
        Text(model.note, color = muted, fontSize = 13.sp)
        Text(
            model.current.ifEmpty { "Generate a password." },
            color = Color(0xFFF7F3EC),
            fontFamily = FontFamily.Monospace,
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF1C1915), RoundedCornerShape(12.dp))
                .padding(12.dp),
            fontSize = 16.sp,
        )
        TextField(
            value = model.name,
            onValueChange = { model.name = it },
            label = { Text("Name") },
            placeholder = { Text("Email, bank, router") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Text("What this password is for.", color = muted, fontSize = 13.sp)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            GreenButton("Copy", enabled = model.current.isNotEmpty()) { model.copy(model.current) }
            TextButton(onClick = { model.requestSave() }, enabled = !model.busy) {
                Text("Save", color = Green)
            }
        }
        Text(
            "If you lose both this passphrase and the recovery key, your saved passwords cannot be recovered.",
            color = Danger,
            fontSize = 13.sp,
        )
    }
}

@Composable
private fun SavedPane(model: PasswordModel, card: Color, ink: Color, muted: Color, dark: Boolean) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(card, RoundedCornerShape(18.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("Saved", color = ink, fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold, fontSize = 24.sp)
        if (!model.hasVault()) {
            Text("No passwords are saved on this phone yet. Generate one, name it, then save it. Or import the vault file from a computer.", color = muted)
        } else if (!model.unlocked) {
            Text("Saved passwords are locked. The passphrase or the recovery key opens all of them.", color = muted)
            GreenButton("Unlock", model.busy) { model.askUnlock = true }
        } else if (model.saved.isEmpty()) {
            Text("The vault is empty.", color = muted)
        } else {
            model.saved.forEach { item ->
                Column(modifier = Modifier.fillMaxWidth().background(if (dark) Night else Cream, RoundedCornerShape(12.dp)).padding(12.dp)) {
                    Text(item.name, color = ink, fontWeight = FontWeight.Bold)
                    if (model.revealed == item.name) {
                        Text(item.password, color = ink, fontFamily = FontFamily.Monospace)
                    }
                    Row {
                        TextButton(onClick = { model.revealed = if (model.revealed == item.name) null else item.name }) {
                            Text(if (model.revealed == item.name) "Hide" else "Show", color = Green)
                        }
                        TextButton(onClick = { model.copy(item.password) }) { Text("Copy", color = Green) }
                        TextButton(onClick = { model.remove(item) }) { Text("Remove", color = Danger) }
                    }
                }
            }
        }
    }
}

@Composable
private fun Pill(label: String, selected: Boolean, dark: Boolean, onClick: () -> Unit) {
    TextButton(
        onClick = onClick,
        modifier = Modifier.background(if (selected) Green else if (dark) Color(0xFF2C2823) else Color(0xFFF3EFE6), RoundedCornerShape(24.dp)),
    ) {
        Text(label, color = if (selected) Color.White else if (dark) NightInk else Ink, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun GreenButton(label: String, busy: Boolean = false, enabled: Boolean = true, onClick: () -> Unit) {
    TextButton(
        onClick = onClick,
        enabled = enabled && !busy,
        modifier = Modifier.background(Green, RoundedCornerShape(24.dp)),
    ) {
        Text(label, color = Color.White, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun Stepper(label: String, value: Int, min: Int, max: Int, ink: Color, muted: Color, onChange: (Int) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
        Text(label, color = ink)
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { if (value > min) onChange(value - 1) }) { Text("−", color = Green, fontSize = 20.sp) }
            Text(value.toString(), color = ink, fontWeight = FontWeight.Bold)
            TextButton(onClick = { if (value < max) onChange(value + 1) }) { Text("+", color = Green, fontSize = 20.sp) }
        }
    }
}

@Composable
private fun ReceiveDialog(model: PasswordModel) {
    var code by remember { mutableStateOf("") }
    var address by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = { model.askReceive = false },
        title = { Text("Receive vault") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Enter the 6-digit code from the other device. Both devices need the same Wi-Fi. The passphrase is not sent.")
                OutlinedTextField(
                    value = code,
                    onValueChange = { if (it.length <= 6) code = it },
                    label = { Text("6-digit code") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                )
                OutlinedTextField(
                    value = address,
                    onValueChange = { address = it },
                    label = { Text("Optional address") },
                    placeholder = { Text("192.168.1.20:12345") },
                    singleLine = true,
                )
                if (model.error.isNotEmpty()) {
                    Text(model.error, color = Danger)
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { model.receiveVault(code, address) }, enabled = !model.busy) { Text("Receive") }
        },
        dismissButton = {
            TextButton(onClick = { model.askReceive = false }) { Text("Cancel") }
        },
    )
}

@Composable
private fun PassphraseDialog(
    title: String,
    body: String,
    confirm: Boolean,
    busy: Boolean,
    onDismiss: () -> Unit,
    onSubmit: (String, String) -> Unit,
) {
    var phrase by remember { mutableStateOf("") }
    var again by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(body)
                OutlinedTextField(
                    value = phrase,
                    onValueChange = { phrase = it },
                    label = { Text(if (confirm) "Passphrase" else "Passphrase or recovery key") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                )
                if (confirm) {
                    OutlinedTextField(
                        value = again,
                        onValueChange = { again = it },
                        label = { Text("Repeat the passphrase") },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onSubmit(phrase, again) }, enabled = !busy) { Text("Continue") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}
