package app.localpassword

import android.app.Activity
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
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
import androidx.compose.runtime.DisposableEffect
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
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
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
    val lifecycleOwner = LocalLifecycleOwner.current
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

    DisposableEffect(lifecycleOwner, context) {
        val activity = context as? Activity
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP && activity?.isChangingConfigurations != true) {
                model.lockApp()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = page) {
            if (model.appLocked) {
                AppLockPane(model, card, ink, muted, dark)
            } else {
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
                        "Generate a password, open Saved, or change appearance and vault transfer in Settings.",
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
                        "Passphrases use the EFF large wordlist (CC BY 3.0 US). The EFF does not endorse this project.",
                        color = muted,
                        fontSize = 12.sp,
                    )
                }
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
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(
                        recovery,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp,
                    )
                    Text(
                        "It opens your saved passwords if you forget the passphrase. It is shown once and is not stored.",
                        color = Muted,
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = { model.recoveryKey = null }) { Text("I wrote it down") }
            },
            dismissButton = {
                TextButton(onClick = { model.copy(recovery) }) { Text("Copy", color = Green) }
            },
        )
    }
    if (model.askEnableBiometric) {
        PassphraseDialog(
            title = "Enable biometric unlock",
            body = "Enter your passphrase or recovery key so fingerprint or face unlock can open the app.",
            confirm = false,
            busy = model.busy,
            onDismiss = { model.askEnableBiometric = false },
        ) { phrase, _ -> model.confirmEnableBiometric(phrase) }
    }
}

@Composable
private fun AppLockPane(model: PasswordModel, card: Color, ink: Color, muted: Color, dark: Boolean) {
    val context = LocalContext.current
    val activity = context as? FragmentActivity
    val canBiometric = remember(context) {
        val manager = BiometricManager.from(context)
        manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG) == BiometricManager.BIOMETRIC_SUCCESS ||
            manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_WEAK) == BiometricManager.BIOMETRIC_SUCCESS
    }
    var phrase by remember { mutableStateOf("") }

    fun promptBiometric() {
        val host = activity ?: return
        val executor = ContextCompat.getMainExecutor(host)
        val prompt = BiometricPrompt(
            host,
            executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    model.unlockWithBiometricSecret()
                }

                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    if (errorCode != BiometricPrompt.ERROR_USER_CANCELED &&
                        errorCode != BiometricPrompt.ERROR_NEGATIVE_BUTTON &&
                        errorCode != BiometricPrompt.ERROR_CANCELED
                    ) {
                        model.error = errString.toString()
                    }
                }
            },
        )
        prompt.authenticate(
            BiometricPrompt.PromptInfo.Builder()
                .setTitle("Unlock Local Password")
                .setSubtitle("Confirm fingerprint or face")
                .setNegativeButtonText("Use passphrase")
                .build(),
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 40.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("ON THIS PHONE", color = Green, fontWeight = FontWeight.Bold, fontSize = 11.sp, letterSpacing = 1.5.sp)
            Text("Local Password", color = ink, fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold, fontSize = 32.sp)
        }
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(card, RoundedCornerShape(18.dp))
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Unlock", color = ink, fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold, fontSize = 24.sp)
            Text("Enter your passphrase or recovery key to open the vault on this phone.", color = muted)
            OutlinedTextField(
                value = phrase,
                onValueChange = { phrase = it },
                label = { Text("Passphrase or recovery key") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                modifier = Modifier.fillMaxWidth(),
            )
            GreenButton("Unlock", model.busy, fillMaxWidth = true) {
                model.unlock(phrase, thenSave = false)
            }
            if (canBiometric && model.hasBiometricSecret()) {
                TextButton(
                    onClick = { promptBiometric() },
                    enabled = !model.busy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Use biometrics", color = Green, fontWeight = FontWeight.Bold)
                }
            }
            if (model.error.isNotEmpty()) {
                Text(model.error, color = Danger)
            }
            Text(model.status, color = muted, fontSize = 13.sp)
        }
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
        Spacer(modifier = Modifier.height(4.dp))
        GreenButton("Generate", model.busy, fillMaxWidth = true, onClick = { model.generate() })
        Spacer(modifier = Modifier.height(4.dp))
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

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SavedPane(model: PasswordModel, card: Color, ink: Color, muted: Color, dark: Boolean) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(card, RoundedCornerShape(18.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Saved", color = ink, fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold, fontSize = 24.sp)
        if (!model.hasVault()) {
            Text("Nothing saved yet. Generate one, name it, then save — or import a vault file.", color = muted)
        } else if (!model.unlocked) {
            Text("Locked. Unlock with your passphrase or recovery key.", color = muted)
            GreenButton("Unlock", model.busy, fillMaxWidth = true) { model.askUnlock = true }
        } else if (model.saved.isEmpty()) {
            Text("The vault is empty.", color = muted)
        } else {
            val health = model.passwordHealthSummary()
            val healthBits = buildList {
                if (health.weakCount > 0) add("${health.weakCount} weak")
                if (health.reuseCount > 0) add("${health.reuseCount} reused")
                if (health.staleCount > 0) add("${health.staleCount} stale")
            }
            Text(
                if (healthBits.isNotEmpty()) {
                    "Masked until shown. ${healthBits.joinToString(" · ")} need attention."
                } else {
                    "Masked until shown. Use filters and sort below."
                },
                color = muted,
                fontSize = 13.sp,
            )
            if (model.lastRemoved != null) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(model.status.ifEmpty { "Removed. Undo to put it back." }, color = muted, fontSize = 13.sp, modifier = Modifier.weight(1f))
                    TextButton(onClick = { model.undoRemove() }, enabled = !model.busy) {
                        Text("Undo", color = Green)
                    }
                }
            }
            OutlinedTextField(
                value = model.savedQuery,
                onValueChange = { model.savedQuery = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                label = { Text("Search") },
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalArrangement = Arrangement.spacedBy(0.dp),
            ) {
                TextButton(onClick = { model.favoritesOnly = !model.favoritesOnly }) {
                    Text(if (model.favoritesOnly) "Favorites On" else "Favorites", color = if (model.favoritesOnly) Green else muted)
                }
                TextButton(onClick = { model.archivedOnly = !model.archivedOnly }) {
                    Text(if (model.archivedOnly) "Archived On" else "Archived", color = if (model.archivedOnly) Green else muted)
                }
                TextButton(onClick = { model.needsAttentionOnly = !model.needsAttentionOnly }) {
                    Text(
                        if (model.needsAttentionOnly) "Needs attention On" else "Needs attention",
                        color = if (model.needsAttentionOnly) Green else muted,
                    )
                }
                if (model.categoryFilter != "all") {
                    TextButton(onClick = { model.categoryFilter = "all" }) {
                        Text("Clear category", color = muted)
                    }
                }
            }
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalArrangement = Arrangement.spacedBy(0.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Sort", color = muted, fontSize = 13.sp, modifier = Modifier.align(Alignment.CenterVertically))
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
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    verticalArrangement = Arrangement.spacedBy(0.dp),
                ) {
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
                    SavedEntryCard(model, item, ink, muted, dark)
                }
            }
        }
    }
    SavedPaneDialogs(model, muted, ink)
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SavedEntryCard(
    model: PasswordModel,
    item: SavedPassword,
    ink: Color,
    muted: Color,
    dark: Boolean,
) {
    var more by remember(item.name) { mutableStateOf(false) }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(if (dark) Night else Cream, RoundedCornerShape(12.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            buildString {
                if (item.favorite) append("★ ")
                append(item.name)
                if (item.archived) append(" (archived)")
            },
            color = ink,
            fontWeight = FontWeight.Bold,
            fontSize = 17.sp,
        )
        val meta = listOf(item.username, item.category).filter { it.isNotEmpty() }
        if (meta.isNotEmpty()) {
            Text(meta.joinToString(" · "), color = muted, fontSize = 13.sp)
        }
        val dates = Vault.entryDatesLabel(item)
        if (dates.isNotEmpty()) {
            Text(dates, color = muted, fontSize = 12.sp)
        }
        Text(Vault.lastUsedLabel(item), color = muted, fontSize = 12.sp)
        val strength = model.strengthWarning(item)
        if (strength.isNotEmpty()) {
            Text(strength, color = Danger, fontSize = 13.sp)
        }
        val warning = model.reuseWarning(item)
        if (warning.isNotEmpty()) {
            Text(warning, color = Danger, fontSize = 13.sp)
        }
        val stale = model.staleWarning(item)
        if (stale.isNotEmpty()) {
            Text(stale, color = Danger, fontSize = 13.sp)
        }
        if (model.revealed == item.name) {
            Text(item.password, color = ink, fontFamily = FontFamily.Monospace)
        } else {
            Text("••••••••••••", color = muted, fontFamily = FontFamily.Monospace)
        }
        if (item.notes.isNotBlank()) {
            Text(item.notes, color = muted, fontSize = 13.sp)
        }
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalArrangement = Arrangement.spacedBy(0.dp),
        ) {
            TextButton(onClick = { model.revealed = if (model.revealed == item.name) null else item.name }) {
                Text(if (model.revealed == item.name) "Hide" else "Show", color = Green)
            }
            TextButton(onClick = { model.copySavedSecret(item, item.password) }) {
                Text("Copy", color = Green)
            }
            TextButton(onClick = { model.beginEdit(item) }) {
                Text("Edit", color = Green)
            }
            TextButton(onClick = { model.requestRemove(item) }) {
                Text("Remove", color = Danger)
            }
            TextButton(onClick = { more = !more }) {
                Text(if (more) "Less" else "More", color = muted)
            }
        }
        if (more) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalArrangement = Arrangement.spacedBy(0.dp),
            ) {
                val loginText = Vault.loginCopyText(item)
                if (loginText.isNotEmpty()) {
                    TextButton(onClick = { model.copySavedSecret(item, loginText) }) {
                        Text("Copy login", color = Green)
                    }
                    TextButton(onClick = { model.copySavedSecret(item, item.username) }) {
                        Text("Copy username", color = Green)
                    }
                }
                Vault.optionalCopyFields(item).forEach { (label, value) ->
                    TextButton(onClick = { model.copySavedSecret(item, value) }) {
                        Text(label, color = Green)
                    }
                    if (label == "Copy URL" && Vault.browseableUrl(item.url) != null) {
                        TextButton(onClick = { model.openUrl(item.url) }) {
                            Text("Open URL", color = Green)
                        }
                    }
                }
                TextButton(onClick = { model.requestReplace(item) }) {
                    Text("Replace", color = Green)
                }
                if (item.history.isNotEmpty()) {
                    TextButton(onClick = { model.showHistory(item) }) {
                        Text("Previous (${item.history.size})", color = Green)
                    }
                }
                TextButton(onClick = { model.toggleFavorite(item) }, enabled = !model.busy) {
                    Text(if (item.favorite) "Unfavorite" else "Favorite", color = Green)
                }
                TextButton(onClick = { model.toggleArchived(item) }, enabled = !model.busy) {
                    Text(if (item.archived) "Unarchive" else "Archive", color = Green)
                }
                TextButton(onClick = { model.duplicateEntry(item) }, enabled = !model.busy) {
                    Text("Duplicate", color = Green)
                }
                TextButton(onClick = { model.beginRename(item) }, enabled = !model.busy) {
                    Text("Rename", color = Green)
                }
                TextButton(onClick = { model.beginCategory(item) }, enabled = !model.busy) {
                    Text("Category", color = Green)
                }
                TextButton(onClick = { model.beginUsername(item) }, enabled = !model.busy) {
                    Text("Username", color = Green)
                }
                TextButton(onClick = { model.beginUrl(item) }, enabled = !model.busy) {
                    Text("URL", color = Green)
                }
                TextButton(onClick = { model.beginNotes(item) }, enabled = !model.busy) {
                    Text("Notes", color = Green)
                }
            }
        }
    }
}

@Composable
private fun SavedPaneDialogs(model: PasswordModel, muted: Color, ink: Color) {
    model.renaming?.let { item ->
        RenameEntryDialog(
            item = item,
            busy = model.busy,
            error = model.error,
            onCancel = { model.cancelRename() },
            onRename = { model.confirmRename(it) },
        )
    }
    model.categorizing?.let { item ->
        CategoryEntryDialog(
            item = item,
            busy = model.busy,
            error = model.error,
            onCancel = { model.cancelCategory() },
            onSave = { model.confirmCategory(it) },
        )
    }
    model.editingUsername?.let { item ->
        UsernameEntryDialog(
            item = item,
            busy = model.busy,
            error = model.error,
            onCancel = { model.cancelUsername() },
            onSave = { model.confirmUsername(it) },
        )
    }
    model.editingUrl?.let { item ->
        UrlEntryDialog(
            item = item,
            busy = model.busy,
            error = model.error,
            onCancel = { model.cancelUrl() },
            onSave = { model.confirmUrl(it) },
        )
    }
    model.editingNotes?.let { item ->
        NotesEntryDialog(
            item = item,
            busy = model.busy,
            error = model.error,
            onCancel = { model.cancelNotes() },
            onSave = { model.confirmNotes(it) },
        )
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
            text = { Text("Remove \"${item.name}\" from this phone? You can Undo afterward.") },
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
private fun RenameEntryDialog(
    item: SavedPassword,
    busy: Boolean,
    error: String,
    onCancel: () -> Unit,
    onRename: (String) -> Unit,
) {
    var name by remember(item) { mutableStateOf(item.name) }
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Rename saved password") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Rename \"${item.name}\". Other fields stay the same.", color = Muted)
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Name") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (error.isNotEmpty()) {
                    Text(error, color = Danger)
                }
            }
        },
        confirmButton = {
            TextButton(enabled = !busy, onClick = { onRename(name) }) {
                Text("Rename", color = Green)
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel, enabled = !busy) { Text("Cancel") }
        },
    )
}

@Composable
private fun CategoryEntryDialog(
    item: SavedPassword,
    busy: Boolean,
    error: String,
    onCancel: () -> Unit,
    onSave: (String) -> Unit,
) {
    var category by remember(item) { mutableStateOf(item.category) }
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Category") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "Category for \"${item.name}\". Pick a preset or type your own. Leave blank to clear. Other fields stay the same.",
                    color = Muted,
                )
                OutlinedTextField(
                    value = category,
                    onValueChange = { category = it },
                    label = { Text("Category") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    Vault.DEFAULT_CATEGORIES.take(4).forEach { label ->
                        TextButton(onClick = { category = label }, enabled = !busy) {
                            Text(label, color = Green, fontSize = 12.sp)
                        }
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    Vault.DEFAULT_CATEGORIES.drop(4).forEach { label ->
                        TextButton(onClick = { category = label }, enabled = !busy) {
                            Text(label, color = Green, fontSize = 12.sp)
                        }
                    }
                }
                if (error.isNotEmpty()) {
                    Text(error, color = Danger)
                }
            }
        },
        confirmButton = {
            TextButton(enabled = !busy, onClick = { onSave(category) }) {
                Text("Save", color = Green)
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel, enabled = !busy) { Text("Cancel") }
        },
    )
}

@Composable
private fun UsernameEntryDialog(
    item: SavedPassword,
    busy: Boolean,
    error: String,
    onCancel: () -> Unit,
    onSave: (String) -> Unit,
) {
    var username by remember(item) { mutableStateOf(item.username) }
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Username") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "Username for \"${item.name}\". Leave blank to clear. Other fields stay the same.",
                    color = Muted,
                )
                OutlinedTextField(
                    value = username,
                    onValueChange = { username = it },
                    label = { Text("Username") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (error.isNotEmpty()) {
                    Text(error, color = Danger)
                }
            }
        },
        confirmButton = {
            TextButton(enabled = !busy, onClick = { onSave(username) }) {
                Text("Save", color = Green)
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel, enabled = !busy) { Text("Cancel") }
        },
    )
}

@Composable
private fun UrlEntryDialog(
    item: SavedPassword,
    busy: Boolean,
    error: String,
    onCancel: () -> Unit,
    onSave: (String) -> Unit,
) {
    var url by remember(item) { mutableStateOf(item.url) }
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Website URL") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "Website for \"${item.name}\". Leave blank to clear. Other fields stay the same.",
                    color = Muted,
                )
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it },
                    label = { Text("URL") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (error.isNotEmpty()) {
                    Text(error, color = Danger)
                }
            }
        },
        confirmButton = {
            TextButton(enabled = !busy, onClick = { onSave(url) }) {
                Text("Save", color = Green)
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel, enabled = !busy) { Text("Cancel") }
        },
    )
}

@Composable
private fun NotesEntryDialog(
    item: SavedPassword,
    busy: Boolean,
    error: String,
    onCancel: () -> Unit,
    onSave: (String) -> Unit,
) {
    var notes by remember(item) { mutableStateOf(item.notes) }
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Notes") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "Notes for \"${item.name}\". Leave blank to clear. Notes do not reveal the password.",
                    color = Muted,
                )
                OutlinedTextField(
                    value = notes,
                    onValueChange = { notes = it },
                    label = { Text("Notes") },
                    modifier = Modifier.fillMaxWidth(),
                )
                if (error.isNotEmpty()) {
                    Text(error, color = Danger)
                }
            }
        },
        confirmButton = {
            TextButton(enabled = !busy, onClick = { onSave(notes) }) {
                Text("Save", color = Green)
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel, enabled = !busy) { Text("Cancel") }
        },
    )
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
    var archived by remember(item) { mutableStateOf(item.archived) }
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
                TextButton(onClick = { archived = !archived }) {
                    Text(if (archived) "Archived On" else "Archived Off", color = if (archived) Green else Muted)
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
                            archived = archived,
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

@OptIn(ExperimentalLayoutApi::class)
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
    val context = LocalContext.current
    val canBiometric = remember(context) {
        val manager = BiometricManager.from(context)
        manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG) == BiometricManager.BIOMETRIC_SUCCESS ||
            manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_WEAK) == BiometricManager.BIOMETRIC_SUCCESS
    }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(card, RoundedCornerShape(18.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Settings", color = ink, fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold, fontSize = 24.sp)
        Text("Copied passwords clear from the clipboard after 30 seconds.", color = muted, fontSize = 13.sp)

        Text("Appearance", color = ink, fontWeight = FontWeight.Bold)
        TextButton(onClick = { model.toggleDark() }) {
            Text(if (dark) "Dark On" else "Dark Off", color = if (dark) Green else muted)
        }

        Text("App lock", color = ink, fontWeight = FontWeight.Bold)
        Text(
            "Closing the app locks the vault. Unlock with your passphrase" +
                (if (canBiometric) " or biometrics." else "."),
            color = muted,
            fontSize = 13.sp,
        )
        if (canBiometric && model.hasVault()) {
            TextButton(
                onClick = {
                    if (model.biometricEnabled) model.disableBiometric() else model.requestEnableBiometric()
                },
                enabled = !model.busy,
            ) {
                Text(
                    if (model.biometricEnabled) "Biometrics On" else "Biometrics Off",
                    color = if (model.biometricEnabled) Green else muted,
                )
            }
        }
        TextButton(
            onClick = { model.lockApp() },
            enabled = model.hasVault() && !model.appLocked,
        ) {
            Text("Lock now", color = Green)
        }

        Text("Passphrase", color = ink, fontWeight = FontWeight.Bold)
        Text("Shows a new recovery key once. The old passphrase and key stop working.", color = muted, fontSize = 13.sp)
        TextButton(
            onClick = { model.requestChangePassphrase() },
            enabled = !model.busy,
        ) {
            Text("Change passphrase", color = Green)
        }

        Text("Move vault", color = ink, fontWeight = FontWeight.Bold)
        Text("Wi-Fi send keeps the passphrase on this phone. CSV export is plaintext.", color = muted, fontSize = 13.sp)
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalArrangement = Arrangement.spacedBy(0.dp),
        ) {
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
            TextButton(onClick = onImport) { Text("Import vault", color = Green) }
            TextButton(onClick = onExport) { Text("Export vault", color = Green) }
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
private fun GreenButton(
    label: String,
    busy: Boolean = false,
    enabled: Boolean = true,
    fillMaxWidth: Boolean = false,
    onClick: () -> Unit,
) {
    TextButton(
        onClick = onClick,
        enabled = enabled && !busy,
        modifier = Modifier
            .then(if (fillMaxWidth) Modifier.fillMaxWidth() else Modifier)
            .then(if (fillMaxWidth) Modifier.height(52.dp) else Modifier)
            .background(Green, RoundedCornerShape(if (fillMaxWidth) 14.dp else 24.dp)),
    ) {
        Text(
            label,
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = if (fillMaxWidth) 18.sp else 14.sp,
        )
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
