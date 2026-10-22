@file:OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package app.localpassword

import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.imePadding
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.LocalActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
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

private val Green: Color @Composable get() = MaterialTheme.colorScheme.primary
private val Muted: Color @Composable get() = MaterialTheme.colorScheme.onSurfaceVariant
private val Line: Color @Composable get() = MaterialTheme.colorScheme.outlineVariant
private val Danger: Color @Composable get() = MaterialTheme.colorScheme.error

@Composable
fun LocalPasswordApp(model: PasswordModel = viewModel()) {
    LocalPasswordTheme(model.appearance) { LocalPasswordContent(model) }
}

@Composable
private fun LocalPasswordContent(model: PasswordModel) {
    val context = LocalContext.current
    val activity = LocalActivity.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val page = MaterialTheme.colorScheme.background
    val ink = MaterialTheme.colorScheme.onSurface
    val muted = MaterialTheme.colorScheme.onSurfaceVariant
    val enrollmentCipher = model.biometricEnrollmentCipher
    DisposableEffect(enrollmentCipher, activity) {
        val host = activity as? FragmentActivity
        val prompt = if (enrollmentCipher != null && host != null) {
            BiometricPrompt(host, ContextCompat.getMainExecutor(host),
                object : BiometricPrompt.AuthenticationCallback() {
                    override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                        model.completeBiometricEnrollment(result.cryptoObject?.cipher)
                    }
                    override fun onAuthenticationError(code: Int, message: CharSequence) {
                        if (model.biometricEnrollmentCipher !== enrollmentCipher) return
                        model.cancelBiometricEnrollment()
                        model.error = "Biometric setup cancelled. Your passphrase still works."
                    }
                }).also {
                try {
                    it.authenticate(
                        BiometricPrompt.PromptInfo.Builder()
                            .setTitle("Enable biometric unlock")
                            .setSubtitle("Authorize protection of your vault unlock secret")
                            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
                            .setNegativeButtonText("Cancel")
                            .build(),
                        BiometricPrompt.CryptoObject(enrollmentCipher),
                    )
                } catch (_: Exception) {
                    model.cancelBiometricEnrollment()
                    model.error = "Biometric setup could not start. Your passphrase still works."
                }
            }
        } else null
        onDispose { prompt?.cancelAuthentication() }
    }
    val importVault = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        try {
            val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                ?: throw java.io.IOException("Could not open that backup file.")
            model.beginVaultImport(bytes)
            bytes.fill(0)
        } catch (exc: Exception) {
            model.error = exc.message ?: "Could not read that backup file. Your vault was not changed."
        }
    }
    val importCsv = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        try {
            val text = context.contentResolver.openInputStream(uri)?.use { stream ->
                stream.bufferedReader().readText()
            } ?: throw java.io.IOException("Could not open that CSV file.")
            model.importCsv(text)
        } catch (exc: Exception) {
            model.error = exc.message ?: "Could not read that CSV file. Your vault was not changed."
        }
    }
    val exportVault = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        val bytes = model.exportBytes() ?: return@rememberLauncherForActivityResult
        try {
            val output = context.contentResolver.openOutputStream(uri)
                ?: throw java.io.IOException("Could not open the selected destination.")
            output.use { it.write(bytes); it.flush() }
            model.status = "Encrypted vault backup written. Keep it somewhere private."
            model.error = ""
        } catch (exc: Exception) {
            model.error = exc.message ?: "Could not write the encrypted vault backup."
        } finally {
            bytes.fill(0)
        }
    }
    val exportCsv = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        val text = model.exportCsvText() ?: return@rememberLauncherForActivityResult
        val bytes = text.toByteArray(Charsets.UTF_8)
        try {
            val output = context.contentResolver.openOutputStream(uri)
                ?: throw java.io.IOException("Could not open the selected destination.")
            output.use { it.write(bytes); it.flush() }
            model.status = "Plaintext CSV exported. Protect the file and delete it when you are done."
            model.error = ""
        } catch (exc: Exception) {
            model.error = exc.message ?: "Could not write the plaintext CSV export."
        } finally {
            bytes.fill(0)
        }
    }

    DisposableEffect(lifecycleOwner, activity) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_STOP -> {
                    if (activity?.isChangingConfigurations != true) {
                        model.scheduleBackgroundLock()
                    }
                }
                Lifecycle.Event.ON_START -> model.cancelBackgroundLock()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

        Surface(modifier = Modifier.fillMaxSize(), color = page) {
            if (model.appLocked) {
                AppLockPane(model, ink, muted)
            } else {
                AppShell(model.section, onSectionChange = { model.closeEntry(); model.section = it }, detailKey = model.selectedEntryName) {
                    if (model.section == "create") {
                        CreatePane(model)
                    } else if (model.section == "saved") {
                        SavedPane(model)
                    } else {
                        SettingsPane(
                            model,
                            muted,
                            onImport = { importVault.launch(arrayOf("*/*")) },
                            onImportCsv = { importCsv.launch(arrayOf("text/*", "text/csv", "*/*")) },
                            onExportCsv = { exportCsv.launch("local-password.csv") },
                            onExport = { exportVault.launch("saved.vault") },
                        )
                    }
                    if (model.error.isNotEmpty()) {
                        Text(model.error, color = Danger, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                    }
                    Text(model.status, color = muted, style = MaterialTheme.typography.bodySmall, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                }
            }
        }

    if (model.askNewPassphrase) {
        PassphraseDialog(
            title = "Choose a passphrase",
            body = "Choose a passphrase to lock saved passwords. If you enable biometric unlock later, an encrypted unlock secret is protected by Android Keystore. If you lose both this passphrase and the recovery key, your saved passwords cannot be recovered.",
            confirm = true,
            busy = model.busy,
            error = model.error,
            onDismiss = { model.askNewPassphrase = false },
        ) { phrase, again -> model.createVault(phrase, again) }
    }
    if (model.askUnlock) {
        PassphraseDialog(
            title = "Unlock",
            body = "Enter the passphrase or the recovery key.",
            confirm = false,
            busy = model.busy,
            error = model.error,
            onDismiss = { model.askUnlock = false },
        ) { phrase, _ -> model.unlock(phrase, thenSave = model.section == "create" && model.current.isNotEmpty()) }
    }
    if (model.askChangeCurrent) {
        PassphraseDialog(
            title = "Current passphrase",
            body = "Enter the current passphrase or recovery key.",
            confirm = false,
            busy = model.busy,
            error = model.error,
            onDismiss = { model.cancelChangePassphrase() },
        ) { phrase, _ -> model.confirmChangeCurrent(phrase) }
    }
    if (model.askChangeNew) {
        PassphraseDialog(
            title = "New passphrase",
            body = "Choose a new passphrase. A new recovery key will be shown once. The old passphrase and recovery key will stop working.",
            confirm = true,
            busy = model.busy,
            error = model.error,
            onDismiss = { model.cancelChangePassphrase() },
        ) { phrase, again -> model.confirmChangeNew(phrase, again) }
    }
    val offerCode = model.offerCode
    if (offerCode != null) {
        AlertDialog(
            onDismissRequest = { model.cancelOffer() },
            title = { Text("Send vault") },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
    if (model.askImportOverwrite) {
        AlertDialog(
            onDismissRequest = { model.cancelVaultImport() },
            title = { Text("Replace this vault?") },
            text = {
                Text("Your current vault will be replaced only after the selected backup is successfully unlocked. If verification fails or you cancel, the current vault stays unchanged.")
            },
            confirmButton = {
                TextButton(onClick = model::confirmVaultImportReplacement) { Text("Continue") }
            },
            dismissButton = {
                TextButton(onClick = model::cancelVaultImport) { Text("Cancel") }
            },
        )
    }
    if (model.askImportPassphrase) {
        PassphraseDialog(
            title = if (model.pendingImportSource == "Wi-Fi transfer") "Verify received vault" else "Verify backup",
            body = "Enter the passphrase or recovery key for this vault. It is checked before this phone’s vault is changed.",
            confirm = false,
            busy = model.busy,
            error = model.error,
            onDismiss = { if (!model.busy) model.cancelVaultImport() },
        ) { phrase, _ -> model.unlockImportedVault(phrase) }
    }
    if (model.askIncomingPassphrase) {
        PassphraseDialog(
            title = "Other vault",
            body = "This vault uses a different passphrase. Enter it to merge the passwords. It is not sent.",
            confirm = false,
            busy = model.busy,
            error = model.error,
            onDismiss = { model.dismissIncoming() },
        ) { phrase, _ -> model.mergeWithIncomingPassphrase(phrase) }
    }
    val recovery = model.recoveryKey
    if (recovery != null) {
        AlertDialog(
            onDismissRequest = {},
            title = { Text("Write down this recovery key") },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
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
                TextButton(onClick = { model.copy(recovery) }) { Text("Copy") }
            },
        )
    }
    if (model.askEnableBiometric) {
        PassphraseDialog(
            title = "Enable biometric unlock",
            body = "Enter your passphrase or recovery key so fingerprint or face unlock can open the app.",
            confirm = false,
            busy = model.busy,
            error = model.error,
            onDismiss = { model.askEnableBiometric = false },
        ) { phrase, _ -> model.confirmEnableBiometric(phrase) }
    }
    if (model.askEnableAppLock) {
        PassphraseDialog(
            title = "Turn on app lock",
            body = "Enter your vault passphrase or recovery key. Closing the app will ask for it again.",
            confirm = false,
            busy = model.busy,
            error = model.error,
            onDismiss = { model.askEnableAppLock = false },
        ) { phrase, _ -> model.confirmEnableAppLock(phrase) }
    }
}

@Composable
private fun AppLockPane(model: PasswordModel, ink: Color, muted: Color) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val activity = LocalActivity.current as? FragmentActivity
    val canBiometric = remember(context) {
        val manager = BiometricManager.from(context)
        manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG) == BiometricManager.BIOMETRIC_SUCCESS
    }
    val biometricReady = canBiometric && model.hasBiometricSecret()
    val windowFocused = LocalWindowInfo.current.isWindowFocused
    var resumed by remember(lifecycleOwner) {
        mutableStateOf(lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED))
    }
    var phrase by remember { mutableStateOf("") }
    var showPassphrase by remember { mutableStateOf(!biometricReady) }
    var biometricPrompted by remember { mutableStateOf(false) }
    var activePrompt by remember { mutableStateOf<BiometricPrompt?>(null) }
    var promptGeneration by remember { mutableIntStateOf(0) }

    fun promptBiometric() {
        if (!lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED) ||
            activePrompt != null || model.busy) return
        val host = activity ?: return
        biometricPrompted = true
        val generation = ++promptGeneration
        val cipher = model.prepareBiometricUnlock()
        if (cipher == null) {
            showPassphrase = true
            return
        }
        val executor = ContextCompat.getMainExecutor(host)
        val prompt = BiometricPrompt(
            host,
            executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    if (generation != promptGeneration) return
                    activePrompt = null
                    if (!model.unlockWithBiometricSecret(result.cryptoObject?.cipher)) showPassphrase = true
                }

                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    if (generation != promptGeneration) return
                    activePrompt = null
                    if (errorCode == BiometricPrompt.ERROR_NEGATIVE_BUTTON ||
                        errorCode == BiometricPrompt.ERROR_USER_CANCELED ||
                        errorCode == BiometricPrompt.ERROR_CANCELED
                    ) {
                        showPassphrase = true
                        return
                    }
                    model.error = errString.toString()
                    showPassphrase = true
                }
            },
        )
        activePrompt = prompt
        try {
        prompt.authenticate(
            BiometricPrompt.PromptInfo.Builder()
                .setTitle("Unlock Local Password")
                .setSubtitle("Confirm fingerprint or face")
                .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
                .setNegativeButtonText("Use passphrase")
                .build(),
            BiometricPrompt.CryptoObject(cipher),
        )
        } catch (_: Exception) {
            activePrompt = null
            showPassphrase = true
            model.error = "Biometric unlock could not start. Use your passphrase or try again."
        }
    }

    DisposableEffect(lifecycleOwner, biometricReady) {
        // Recents can pause the Activity without stopping it. Reset the attempt
        // on pause as well, but launch only after resume and window focus settle.
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> {
                    resumed = true
                }
                Lifecycle.Event.ON_PAUSE, Lifecycle.Event.ON_STOP -> {
                    resumed = false
                    promptGeneration++
                    activePrompt?.cancelAuthentication()
                    activePrompt = null
                    biometricPrompted = false
                }
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            promptGeneration++
            activePrompt?.cancelAuthentication()
            activePrompt = null
        }
    }

    LaunchedEffect(resumed, windowFocused, biometricReady, model.busy, biometricPrompted) {
        if (resumed && windowFocused && biometricReady && !model.busy && !biometricPrompted) {
            // The Recents transition may resume us before the app owns the window.
            // Losing focus cancels this pending launch, not an active system prompt.
            kotlinx.coroutines.delay(200)
            promptBiometric()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .safeDrawingPadding()
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 40.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("ON THIS PHONE", color = Green, fontWeight = FontWeight.Bold, fontSize = 11.sp, letterSpacing = 1.5.sp)
            Text("Local Password", color = ink, fontWeight = FontWeight.Bold, fontSize = 32.sp)
        }
        ScreenSurface {
            Text("Unlock", color = ink, fontWeight = FontWeight.Bold, fontSize = 24.sp)
            if (biometricReady) {
                Text("Use biometrics to open. Passphrase is backup.", color = muted)
                PrimaryActionButton("Unlock with biometrics", model.busy, fillMaxWidth = true) {
                    promptBiometric()
                }
                TextButton(
                    onClick = { showPassphrase = !showPassphrase },
                    enabled = !model.busy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        if (showPassphrase) "Hide passphrase" else "Use passphrase instead",
                        color = Green,
                        fontWeight = FontWeight.Bold,
                    )
                }
            } else {
                Text("Enter your passphrase or recovery key to open the vault on this phone.", color = muted)
            }
            if (showPassphrase || !biometricReady) {
                OutlinedTextField(
                    value = phrase,
                    onValueChange = { phrase = it },
                    label = { Text("Passphrase or recovery key") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier.fillMaxWidth(),
                )
                PrimaryActionButton(
                    if (biometricReady) "Unlock with passphrase" else "Unlock",
                    model.busy,
                    fillMaxWidth = true,
                ) {
                    model.unlock(phrase, thenSave = false)
                }
            }
            if (model.error.isNotEmpty()) {
                Text(model.error, color = Danger, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            }
            Text(model.status, color = muted, fontSize = 13.sp)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CredentialDetailsContent(
    model: PasswordModel,
    item: SavedPassword,
    ink: Color,
    muted: Color,
) {
    var more by remember(item.name) { mutableStateOf(false) }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surfaceContainerLow, MaterialTheme.shapes.medium)
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
        if (item.url.isNotBlank()) Text(item.url, color = muted)
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
                Text("Copy")
            }
            TextButton(onClick = { model.beginEdit(item) }) {
                Text("Edit")
            }

            TextButton(onClick = { more = !more }) {
                Text(if (more) "Hide management actions" else "Manage entry", color = muted)
            }
        }
        if (more) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalArrangement = Arrangement.spacedBy(0.dp),
            ) {
                TextButton(onClick = { model.requestRemove(item) }, enabled = !model.busy) {
                    Text("Remove entry", color = Danger)
                }
                val loginText = Vault.loginCopyText(item)
                if (loginText.isNotEmpty()) {
                    TextButton(onClick = { model.copySavedSecret(item, loginText) }) {
                        Text("Copy login")
                    }
                    TextButton(onClick = { model.copySavedSecret(item, item.username) }) {
                        Text("Copy username")
                    }
                }
                Vault.optionalCopyFields(item).forEach { (label, value) ->
                    TextButton(onClick = { model.copySavedSecret(item, value) }) {
                        Text(label, color = Green)
                    }
                    if (label == "Copy URL" && Vault.browseableUrl(item.url) != null) {
                        TextButton(onClick = { model.openUrl(item.url) }) {
                            Text("Open URL")
                        }
                    }
                }
                TextButton(onClick = { model.requestReplace(item) }) {
                    Text("Replace")
                }
                if (item.history.isNotEmpty()) {
                    TextButton(onClick = { model.showHistory(item) }) {
                        Text("Previous (${item.history.size})")
                    }
                }
                TextButton(onClick = { model.toggleFavorite(item) }, enabled = !model.busy) {
                    Text(if (item.favorite) "Unfavorite" else "Favorite", color = Green)
                }
                TextButton(onClick = { model.toggleArchived(item) }, enabled = !model.busy) {
                    Text(if (item.archived) "Unarchive" else "Archive", color = Green)
                }
                TextButton(onClick = { model.duplicateEntry(item) }, enabled = !model.busy) {
                    Text("Duplicate")
                }
                TextButton(onClick = { model.beginRename(item) }, enabled = !model.busy) {
                    Text("Rename")
                }
                TextButton(onClick = { model.beginCategory(item) }, enabled = !model.busy) {
                    Text("Category")
                }
                TextButton(onClick = { model.beginUsername(item) }, enabled = !model.busy) {
                    Text("Username")
                }
                TextButton(onClick = { model.beginUrl(item) }, enabled = !model.busy) {
                    Text("URL")
                }
                TextButton(onClick = { model.beginNotes(item) }, enabled = !model.busy) {
                    Text("Notes")
                }
            }
        }
    }
}

@Composable
fun SavedPaneDialogs(model: PasswordModel, muted: Color, ink: Color) {
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
        var restoreIndex by remember(item) { mutableStateOf<Int?>(null) }
        if (restoreIndex != null) {
            AlertDialog(
                onDismissRequest = { restoreIndex = null },
                title = { Text("Restore previous password?") },
                text = { Text("This changes the saved password for ${item.name} in this vault only. It does not change the password on the website or app. The current password will move into history.") },
                confirmButton = { TextButton(enabled = !model.busy, onClick = {
                    restoreIndex?.let(model::restorePrevious)
                    restoreIndex = null
                }) { Text("Restore in vault") } },
                dismissButton = { TextButton(onClick = { restoreIndex = null }) { Text("Cancel") } },
            )
        } else {
        AlertDialog(
            onDismissRequest = { model.cancelHistory() },
            title = { Text("Previous passwords") },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "Earlier passwords for \"${item.name}\". Copy one, or Restore to make it current again. Up to ${Vault.MAX_PASSWORD_HISTORY} are kept.",
                        color = muted,
                    )
                    item.history.forEachIndexed { index, revision ->
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
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
                                Text("Copy")
                            }
                            TextButton(onClick = { restoreIndex = index }, enabled = !model.busy) {
                                Text("Restore")
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
    model.pendingSaveReplacement?.let { pending ->
        AlertDialog(
            onDismissRequest = { model.cancelSaveReplacement() },
            title = { Text("Replace existing password?") },
            text = { Text("Already saved: ${pending.first.name}\n\nReplace only the password with the generated value? Account details stay unchanged. The old password stays under Previous. Update the website separately.") },
            confirmButton = { TextButton(onClick = { model.confirmSaveReplacement() }, enabled = !model.busy) { Text("Replace password") } },
            dismissButton = { TextButton(onClick = { model.cancelSaveReplacement() }) { Text("Cancel") } },
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
                    Text("Replace")
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
            Column(modifier = Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
                Text("Rename")
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
            Column(modifier = Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
                FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    Vault.DEFAULT_CATEGORIES.take(4).forEach { label ->
                        TextButton(onClick = { category = label }, enabled = !busy) {
                            Text(label, color = Green, fontSize = 12.sp)
                        }
                    }
                }
                FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
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
                Text("Save")
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
            Column(modifier = Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
                Text("Save")
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
            Column(modifier = Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
                Text("Save")
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
            Column(modifier = Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "Notes for \"${item.name}\" are stored inside the encrypted vault. Leave blank to clear. Plaintext CSV exports include these notes.",
                    color = Muted,
                )
                OutlinedTextField(
                    value = notes,
                    onValueChange = { notes = it },
                    label = { Text("Notes") },
                    supportingText = { Text("${notes.length} / 2000 characters") },
                    isError = notes.length > 2000,
                    minLines = 3,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (error.isNotEmpty()) {
                    Text(error, color = Danger)
                }
            }
        },
        confirmButton = {
            TextButton(enabled = !busy && notes.length <= 2000, onClick = { onSave(notes) }) {
                Text("Save")
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
    var showPassword by remember(item) { mutableStateOf(false) }
    val history = item.history
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Edit saved password") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = username, onValueChange = { username = it }, label = { Text("Username") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = url, onValueChange = { url = it }, label = { Text("URL") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Password") },
                    singleLine = true,
                    visualTransformation = if (showPassword) androidx.compose.ui.text.input.VisualTransformation.None else PasswordVisualTransformation(),
                    modifier = Modifier.fillMaxWidth(),
                )
                TextButton(onClick = { showPassword = !showPassword }) { Text(if (showPassword) "Hide password" else "Show password") }
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
            ) { Text("Save") }
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
    muted: Color,
    onImport: () -> Unit,
    onImportCsv: () -> Unit,
    onExportCsv: () -> Unit,
    onExport: () -> Unit,
) {
    val context = LocalContext.current
    var showPrivacy by remember { mutableStateOf(false) }
    if (showPrivacy) {
        val policy = remember { context.assets.open("privacy-android.txt").bufferedReader().use { it.readText() } }
        AlertDialog(onDismissRequest = { showPrivacy = false }, title = { Text("Privacy") },
            text = { Text(policy, modifier = Modifier.verticalScroll(rememberScrollState())) },
            confirmButton = { TextButton(onClick = { showPrivacy = false }) { Text("Close") } })
    }
    val canBiometric = remember(context) {
        val manager = BiometricManager.from(context)
        manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG) == BiometricManager.BIOMETRIC_SUCCESS
    }
    ScreenSurface {
        SettingsCard(
            title = "Appearance",
            description = "Choose a theme. System follows your phone’s appearance setting.",
        ) {
            listOf("light" to "Light", "dark" to "Dark", "system" to "System").forEach { (mode, label) ->
                SettingsChoiceRow(
                    label = label,
                    selected = model.appearance == mode,
                    onSelect = { model.chooseAppearance(mode) },
                )
            }
        }

        SettingsCard(
            title = "App lock",
            description = "Copied passwords clear from the clipboard after 30 seconds. App lock protects the vault when you leave.",
        ) {
            SettingsSwitchRow(
                label = "Lock the app",
                supportingText = if (model.appLockEnabled) "The app asks you to unlock when the selected delay ends." else "The generator and vault stay open when you leave the app.",
                checked = model.appLockEnabled,
                enabled = !model.busy && (model.hasVault() || model.appLockEnabled),
            ) { enabled ->
                if (enabled) model.requestEnableAppLock() else model.disableAppLock()
            }
            if (!model.hasVault()) {
                Text("Save your first password to create a vault and turn on app lock.", style = MaterialTheme.typography.bodyMedium, color = muted)
            }
        }
        if (model.appLockEnabled) {
            SettingsCard(title = "Lock delay", description = "Choose when the app locks after it leaves the screen.") {
                listOf(
                    0 to "Immediately",
                    60 to "1 min",
                    300 to "5 min",
                    900 to "15 min",
                ).forEach { (seconds, label) ->
                    SettingsChoiceRow(
                        label = label,
                        selected = model.autoLockSeconds == seconds,
                        onSelect = { model.chooseAutoLockSeconds(seconds) },
                    )
                }
                if (canBiometric && model.hasVault()) {
                    SettingsSwitchRow(
                        label = "Biometric unlock",
                        supportingText = "Use fingerprint or face first. Your passphrase remains available.",
                        checked = model.biometricEnabled,
                        enabled = !model.busy,
                    ) { enabled ->
                        if (enabled) model.requestEnableBiometric() else model.disableBiometric()
                    }
                } else if (!canBiometric) {
                    Text("Biometric unlock is not available on this device. You can still unlock with your passphrase or recovery key.", style = MaterialTheme.typography.bodyMedium, color = muted)
                }
                PrimaryActionButton("Lock now", enabled = model.hasVault() && !model.appLocked, fillMaxWidth = true) {
                    model.lockApp()
                }
            }
        }

        SettingsCard(
            title = "Passphrase and recovery",
            description = "Changing the passphrase reseals the vault and shows a new recovery key once. The old passphrase and recovery key then stop working.",
        ) {
            PrimaryActionButton(
                "Change passphrase",
                enabled = !model.busy && model.hasVault(),
                fillMaxWidth = true,
            ) { model.requestChangePassphrase() }
        }

        SettingsCard(
            title = "Move vault",
            description = "Wi-Fi send keeps the passphrase on this phone. CSV export contains unencrypted text; protect or delete the file when you’re done.",
        ) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(AppSpacing.small),
                verticalArrangement = Arrangement.spacedBy(AppSpacing.small),
            ) {
                PrimaryActionButton("Send vault", enabled = !model.busy && model.offerCode == null) { model.sendVault() }
                PrimaryActionButton("Receive vault", enabled = !model.busy) { model.askReceive = true }
                PrimaryActionButton("Import vault") { onImport() }
                PrimaryActionButton("Export vault") { onExport() }
                PrimaryActionButton("Import CSV", enabled = !model.busy) { onImportCsv() }
                PrimaryActionButton("Export CSV", enabled = !model.busy) { onExportCsv() }
            }
        }

        SettingsCard(
            title = "Android Autofill",
            description = "Use Local Password to fill saved logins in other apps and websites. Android asks you to unlock and choose an entry before it fills anything. New logins are not saved by Autofill yet.",
        ) {
            PrimaryActionButton("Choose Autofill service", fillMaxWidth = true) {
                try {
                    context.startActivity(
                        android.content.Intent(
                            Settings.ACTION_REQUEST_SET_AUTOFILL_SERVICE,
                            Uri.parse("package:${context.packageName}"),
                        ),
                    )
                } catch (_: Exception) {
                    model.error = "Open Android Settings and choose Local Password under Autofill service."
                }
            }
        }

        SettingsCard(
            title = "Accessibility",
            description = "Text size follows Android’s Display size and text settings. Settings controls expose their labels and selected states to screen readers.",
        ) { }
        SettingsCard(title = "About Local Password") {
            val version = remember(context) {
                @Suppress("DEPRECATION")
                context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: "Unknown"
            }
            Text("Version $version", style = MaterialTheme.typography.bodyMedium)
            Text("Your vault is stored on this device. Backups and transfers happen when you choose them. Keep an encrypted backup and your recovery key somewhere safe.")
            Text("Passphrases use the EFF large wordlist (CC BY 3.0 US). The EFF does not endorse this project.",
                style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = { model.openUrl("https://github.com/Rj268/local-password") }) { Text("Source code and licenses") }
            TextButton(onClick = { showPrivacy = true }) { Text("Privacy information") }
        }
    }
}

@Composable
private fun SettingsCard(
    title: String,
    description: String? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            modifier = Modifier.padding(AppSpacing.large),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.small),
            content = {
                Text(title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
                if (description != null) Text(description, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                content()
            },
        )
    }
}

@Composable
private fun SettingsChoiceRow(label: String, selected: Boolean, onSelect: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 52.dp)
            .selectable(selected = selected, role = Role.RadioButton, onClick = onSelect)
            .padding(horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null)
        Text(label, modifier = Modifier.padding(start = 8.dp), style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
private fun SettingsSwitchRow(
    label: String,
    supportingText: String,
    checked: Boolean,
    enabled: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 64.dp)
            .toggleable(value = checked, enabled = enabled, role = Role.Switch, onValueChange = onCheckedChange)
            .padding(vertical = AppSpacing.small),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium),
    ) {
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(label, style = MaterialTheme.typography.bodyLarge)
            Text(supportingText, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = checked, onCheckedChange = null, enabled = enabled)
    }
}
@Composable
private fun PrimaryActionButton(
    label: String,
    busy: Boolean = false,
    enabled: Boolean = true,
    fillMaxWidth: Boolean = false,
    onClick: () -> Unit,
) {
    Button(
        onClick = onClick,
        enabled = enabled && !busy,
        modifier = Modifier
            .then(if (fillMaxWidth) Modifier.fillMaxWidth() else Modifier)
            .heightIn(min = 48.dp),
    ) {
        Text(label, style = MaterialTheme.typography.labelLarge)
    }
}
@Composable
private fun Stepper(label: String, value: Int, min: Int, max: Int, ink: Color, muted: Color, onChange: (Int) -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.SpaceBetween, verticalArrangement = Arrangement.spacedBy(AppSpacing.small), modifier = Modifier.fillMaxWidth()) {
        Text(label, color = ink)
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { onChange(value - 1) }, enabled = value > min, modifier = Modifier.semantics { contentDescription = "Decrease $label" }) { Text("−", color = Green, fontSize = 20.sp) }
            Text(value.toString(), color = ink, fontWeight = FontWeight.Bold)
            TextButton(onClick = { onChange(value + 1) }, enabled = value < max, modifier = Modifier.semantics { contentDescription = "Increase $label" }) { Text("+", color = Green, fontSize = 20.sp) }
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
            Column(modifier = Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
                    Text(model.error, color = Danger, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
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
    error: String = "",
    onDismiss: () -> Unit,
    onSubmit: (String, String) -> Unit,
) {
    var phrase by remember { mutableStateOf("") }
    var again by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
                if (error.isNotEmpty()) {
                    Text(error, color = Danger)
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onSubmit(phrase, again) }, enabled = !busy) { Text("Continue") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !busy) { Text("Cancel") }
        },
    )
}
