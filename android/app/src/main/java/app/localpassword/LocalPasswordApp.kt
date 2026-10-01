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
    val importCsv = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        val text = context.contentResolver.openInputStream(uri)?.use { stream ->
            stream.bufferedReader().readText()
        } ?: return@rememberLauncherForActivityResult
        model.importCsv(text)
    }
    val exportVault = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        val bytes = model.exportBytes() ?: return@rememberLauncherForActivityResult
        context.contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
        model.status = "Vault file written. Copy it back to the computer the same way."
    }
    val exportCsv = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        val text = model.exportCsvText() ?: return@rememberLauncherForActivityResult
        context.contentResolver.openOutputStream(uri)?.use { stream ->
            stream.write(text.toByteArray(Charsets.UTF_8))
        }
        model.status = "Exported plaintext CSV. Delete that file when you are done."
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
                Column {
                    Text("ON THIS PHONE", color = Green, fontWeight = FontWeight.Bold, fontSize = 11.sp, letterSpacing = 1.5.sp)
                    Text("Local Password", color = ink, fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold, fontSize = 32.sp)
                }
                Text(
                    "Create a password here, or open Saved to use the ones you already kept. Dark mode and sending the vault are in Settings. A passphrase or a recovery key opens all of them.",
                    color = muted,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Pill("Create", model.section == "create", dark) { model.section = "create" }
                    Pill("Saved", model.section == "saved", dark) { model.section = "saved" }
                    Pill("Settings", model.section == "settings", dark) { model.section = "settings" }
                }
                if (model.section == "create") {
                    CreatePane(model, card, ink, muted, dark)
                } else if (model.section == "saved") {
                    SavedPane(model, card, ink, muted, dark)
                } else {
                    SettingsPane(
                        model,
                        card,
                        ink,
                        muted,
                        dark,
                        onImport = { importVault.launch(arrayOf("*/*")) },
                        onImportCsv = { importCsv.launch(arrayOf("text/*", "text/csv", "*/*")) },
                        onExportCsv = { exportCsv.launch("local-password.csv") },
                        onExport = { exportVault.launch("saved.vault") },
                    )
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
    if (model.askChangeCurrent) {
        PassphraseDialog(
            title = "Current passphrase",
            body = "Enter the current passphrase or recovery key.",
            confirm = false,
            busy = model.busy,
            onDismiss = { model.cancelChangePassphrase() },
        ) { phrase, _ -> model.confirmChangeCurrent(phrase) }
    }
    if (model.askChangeNew) {
        PassphraseDialog(
            title = "New passphrase",
            body = "Choose a new passphrase to lock saved passwords. It is not stored. A new recovery key will be shown once. The old passphrase and recovery key will stop working.",
            confirm = true,
            busy = model.busy,
            onDismiss = { model.cancelChangePassphrase() },
        ) { phrase, again -> model.confirmChangeNew(phrase, again) }
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
            val (weakCount, reuseCount, _) = model.passwordHealthSummary()
            val healthBits = buildList {
                if (weakCount > 0) add("$weakCount weak")
                if (reuseCount > 0) add("$reuseCount reused")
            }
            Text(
                if (healthBits.isNotEmpty()) {
                    "Passwords stay masked until you show one. Weak or reused passwords are called out. ${healthBits.joinToString(" · ")}. Sort by Name, Recent, or Changed. Copying a saved password marks it Recent and shows Last used. Favorite stars or clears a row without opening Edit."
                } else {
                    "Passwords stay masked until you show one. Weak or reused passwords are called out. Needs attention filters those rows. Sort by Name, Recent, or Changed. Copying a saved password marks it Recent and shows Last used. Favorite stars or clears a row without opening Edit."
                },
                color = muted,
                fontSize = 13.sp,
            )
            OutlinedTextField(
                value = model.savedQuery,
                onValueChange = { model.savedQuery = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                label = { Text("Search") },
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = { model.favoritesOnly = !model.favoritesOnly }) {
                    Text(if (model.favoritesOnly) "Favorites On" else "Favorites", color = if (model.favoritesOnly) Green else muted)
                }
                TextButton(onClick = { model.needsAttentionOnly = !model.needsAttentionOnly }) {
                    Text(
                        if (model.needsAttentionOnly) "Needs attention On" else "Needs attention",
                        color = if (model.needsAttentionOnly) Green else muted,
                    )
                }
                TextButton(onClick = { model.categoryFilter = "all" }) {
                    Text(if (model.categoryFilter == "all") "All categories" else "Clear category", color = muted)
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Sort", color = muted, fontSize = 13.sp)
                listOf(
                    Vault.SAVED_SORT_NAME to "Name",
                    Vault.SAVED_SORT_RECENT to "Recent",
                    Vault.SAVED_SORT_CHANGED to "Changed",
                ).forEach { (mode, label) ->
                    TextButton(onClick = { model.savedSortMode = mode }) {
                        Text(label, color = if (model.savedSortMode == mode) Green else muted)
                    }
                }
            }
            val categories = model.categories()
            if (categories.isNotEmpty()) {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    categories.forEach { category ->
                        TextButton(onClick = { model.categoryFilter = category }) {
                            Text(category, color = if (model.categoryFilter == category) Green else muted)
                        }
                    }
                }
            }
            val matches = model.filteredSaved()
            if (matches.isEmpty()) {
                Text("No saved password matches that search.", color = muted)
            } else {
                matches.forEach { item ->
                    Column(modifier = Modifier.fillMaxWidth().background(if (dark) Night else Cream, RoundedCornerShape(12.dp)).padding(12.dp)) {
                        Text(if (item.favorite) "★ ${item.name}" else item.name, color = ink, fontWeight = FontWeight.Bold)
                        val meta = listOf(item.username, item.category, item.url).filter { it.isNotEmpty() }
                        if (meta.isNotEmpty()) {
                            Text(meta.joinToString(" · "), color = muted, fontSize = 13.sp)
                        }
                        Text(Vault.lastUsedLabel(item), color = muted, fontSize = 13.sp)
                        val strength = model.strengthWarning(item)
                        if (strength.isNotEmpty()) {
                            Text(strength, color = Danger, fontSize = 13.sp)
                        }
                        val warning = model.reuseWarning(item)
                        if (warning.isNotEmpty()) {
                            Text(warning, color = Danger, fontSize = 13.sp)
                        }
                        if (model.revealed == item.name) {
                            Text(item.password, color = ink, fontFamily = FontFamily.Monospace)
                            if (item.notes.isNotEmpty()) {
                                Text(item.notes, color = muted, fontSize = 13.sp)
                            }
                        } else {
                            Text("••••••••••••", color = muted)
                        }
                        Row {
                            TextButton(onClick = { model.revealed = if (model.revealed == item.name) null else item.name }) {
                                Text(if (model.revealed == item.name) "Hide" else "Show", color = Green)
                            }
                            TextButton(onClick = { model.copySavedSecret(item, item.password) }) {
                                Text("Copy password", color = Green)
                            }
                            if (item.username.isNotEmpty()) {
                                TextButton(onClick = { model.copySavedSecret(item, item.username) }) {
                                    Text("Copy username", color = Green)
                                }
                            }
                            if (Vault.browseableUrl(item.url) != null) {
                                TextButton(onClick = { model.openUrl(item.url) }) { Text("Open URL", color = Green) }
                            }
                            TextButton(onClick = { model.requestReplace(item) }) {
                                Text("Replace password", color = Green)
                            }
                            if (item.history.isNotEmpty()) {
                                TextButton(onClick = { model.showHistory(item) }) {
                                    Text("Previous (${item.history.size})", color = Green)
                                }
                            }
                            TextButton(onClick = { model.toggleFavorite(item) }, enabled = !model.busy) {
                                Text(if (item.favorite) "Unfavorite" else "Favorite", color = Green)
                            }
                            TextButton(onClick = { model.beginEdit(item) }) { Text("Edit", color = Green) }
                            TextButton(onClick = { model.requestRemove(item) }) { Text("Remove", color = Danger) }
                        }
                    }
                }
            }
        }
    }
    model.historyFor?.let { item ->
        AlertDialog(
            onDismissRequest = { model.cancelHistory() },
            title = { Text("Previous passwords") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "Earlier passwords for \"${item.name}\". Copy one, or Restore to make it current again. Up to ${Vault.MAX_PASSWORD_HISTORY} are kept.",
                        color = muted,
                    )
                    item.history.forEachIndexed { index, revision ->
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(
                                if (revision.replacedAt.isNotEmpty()) {
                                    "Replaced ${revision.replacedAt}"
                                } else {
                                    "Previous ${index + 1}"
                                },
                                color = ink,
                                modifier = Modifier.weight(1f),
                                fontSize = 13.sp,
                            )
                            TextButton(onClick = { model.copyPrevious(revision.password) }) {
                                Text("Copy", color = Green)
                            }
                            TextButton(onClick = { model.restorePrevious(index) }, enabled = !model.busy) {
                                Text("Restore", color = Green)
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { model.cancelHistory() }) { Text("Close") }
            },
        )
    }
    model.pendingRemove?.let { item ->
        AlertDialog(
            onDismissRequest = { model.cancelRemove() },
            title = { Text("Remove saved password") },
            text = { Text("Remove \"${item.name}\" from this phone? This cannot be undone.") },
            confirmButton = {
                TextButton(onClick = { model.confirmRemove() }) { Text("Remove", color = Danger) }
            },
            dismissButton = {
                TextButton(onClick = { model.cancelRemove() }) { Text("Cancel") }
            },
        )
    }
    model.pendingReplace?.let { item ->
        val strength = model.strengthWarning(item)
        val reuse = model.reuseWarning(item)
        val reason = listOf(strength, reuse).filter { it.isNotEmpty() }.joinToString(" ")
        AlertDialog(
            onDismissRequest = { model.cancelReplace() },
            title = { Text("Replace password") },
            text = {
                Text(
                    "Replace the password for \"${item.name}\" with a new strong password?" +
                        (if (reason.isNotEmpty()) " $reason" else "") +
                        " The new password is saved and copied. The old one stays under Previous. Update the site next.",
                )
            },
            confirmButton = {
                TextButton(onClick = { model.confirmReplace() }, enabled = !model.busy) {
                    Text("Replace", color = Green)
                }
            },
            dismissButton = {
                TextButton(onClick = { model.cancelReplace() }) { Text("Cancel") }
            },
        )
    }
    model.editing?.let { item ->
        EditEntryDialog(item = item, busy = model.busy, error = model.error, onCancel = { model.cancelEdit() }, onSave = { model.saveEdit(it) })
    }
}

@Composable
private fun EditEntryDialog(
    item: SavedPassword,
    busy: Boolean,
    error: String,
    onCancel: () -> Unit,
    onSave: (SavedPassword) -> Unit,
) {
    var name by remember(item) { mutableStateOf(item.name) }
    var username by remember(item) { mutableStateOf(item.username) }
    var url by remember(item) { mutableStateOf(item.url) }
    var password by remember(item) { mutableStateOf(item.password) }
    var category by remember(item) { mutableStateOf(item.category) }
    var notes by remember(item) { mutableStateOf(item.notes) }
    var favorite by remember(item) { mutableStateOf(item.favorite) }
    val history = item.history
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Edit saved password") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = username, onValueChange = { username = it }, label = { Text("Username") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = url, onValueChange = { url = it }, label = { Text("URL") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Password") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(value = category, onValueChange = { category = it }, label = { Text("Category") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = notes, onValueChange = { notes = it }, label = { Text("Notes") }, modifier = Modifier.fillMaxWidth())
                TextButton(onClick = { favorite = !favorite }) {
                    Text(if (favorite) "Favorite On" else "Favorite Off", color = if (favorite) Green else Muted)
                }
                if (error.isNotEmpty()) {
                    Text(error, color = Danger)
                }
            }
        },
        confirmButton = {
            TextButton(
                enabled = !busy,
                onClick = {
                    onSave(
                        item.copy(
                            name = name,
                            username = username,
                            url = url,
                            password = password,
                            category = category,
                            notes = notes,
                            favorite = favorite,
                            history = history,
                        ),
                    )
                },
            ) { Text("Save", color = Green) }
        },
        dismissButton = {
            TextButton(onClick = onCancel, enabled = !busy) { Text("Cancel") }
        },
    )
}

@Composable
private fun SettingsPane(
    model: PasswordModel,
    card: Color,
    ink: Color,
    muted: Color,
    dark: Boolean,
    onImport: () -> Unit,
    onImportCsv: () -> Unit,
    onExportCsv: () -> Unit,
    onExport: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(card, RoundedCornerShape(18.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("Settings", color = ink, fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold, fontSize = 24.sp)
        Text(
            "Appearance, passphrase change, and moving the vault stay here. Copied passwords clear from the clipboard after 30 seconds. The passphrase is not sent.",
            color = muted,
        )
        TextButton(onClick = { model.toggleDark() }) {
            Text(if (dark) "Dark    On" else "Dark    Off", color = if (dark) Green else muted)
        }
        Text(
            "Change passphrase seals the vault under a new passphrase and shows a new recovery key once. The old passphrase and recovery key stop working.",
            color = muted,
            fontSize = 13.sp,
        )
        TextButton(
            onClick = { model.requestChangePassphrase() },
            enabled = !model.busy,
        ) {
            Text("Change passphrase", color = Green)
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
            TextButton(onClick = onImport) { Text("Import vault", color = Green) }
            TextButton(onClick = onExport) { Text("Export vault", color = Green) }
        }
        Text(
            "Import CSV adds password rows from another manager into the unlocked vault. Export CSV writes those rows as plaintext — keep that file private.",
            color = muted,
            fontSize = 13.sp,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = onImportCsv, enabled = !model.busy) {
                Text("Import CSV", color = Green)
            }
            TextButton(onClick = onExportCsv, enabled = !model.busy) {
                Text("Export CSV", color = Green)
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
