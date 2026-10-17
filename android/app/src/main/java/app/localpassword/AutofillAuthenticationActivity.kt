package app.localpassword

import android.app.assist.AssistStructure
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import android.view.autofill.AutofillManager
import android.view.autofill.AutofillValue
import android.net.Uri
import androidx.activity.compose.setContent
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import kotlinx.coroutines.CancellationException
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.RadioButton
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

/** Authentication UI shown only after Android's Autofill UI launches our protected dataset. */
class AutofillAuthenticationActivity : FragmentActivity() {
    private lateinit var target: AutofillTargetFields
    private var enteredSecret by mutableStateOf("")
    private var error by mutableStateOf("")
    private var status by mutableStateOf("")
    private var busy by mutableStateOf(false)
    private var accounts by mutableStateOf<List<SavedPassword>?>(null)
    private var allAccounts = emptyList<SavedPassword>()
    private var showAllAccounts by mutableStateOf(false)
    private var siteName: String? = null
    private var requestingAppName by mutableStateOf("the requesting app")
    private var showAccountFallback by mutableStateOf(false)
    private var authenticationGeneration = 0
    private val biometricStore by lazy { BiometricSecretStore(this) }
    private var biometricAvailable by mutableStateOf(false)
    private var biometricAttempted = false
    private var activePrompt: BiometricPrompt? = null

    override fun onResume() {
        super.onResume()
        biometricAvailable = getSharedPreferences("local-password", MODE_PRIVATE)
            .getBoolean("biometric_unlock", false) && biometricStore.isEnrolled() &&
            BiometricManager.from(this).canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG) ==
            BiometricManager.BIOMETRIC_SUCCESS
        maybePromptBiometric()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) maybePromptBiometric()
    }

    private fun maybePromptBiometric() {
        if (!biometricAttempted && window.decorView.hasWindowFocus()) promptBiometric()
    }

    private fun promptBiometric() {
        if (busy || activePrompt != null || accounts != null || !biometricAvailable || isFinishing ||
            !lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) return
        biometricAttempted = true
        authenticationGeneration++
        val generation = authenticationGeneration
        try {
            val cipher = biometricStore.decryptionCipher()
            val prompt = BiometricPrompt(this, ContextCompat.getMainExecutor(this),
                object : BiometricPrompt.AuthenticationCallback() {
                    override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                        if (generation != authenticationGeneration || activePrompt == null || isFinishing) return
                        activePrompt = null
                        try {
                            check(result.cryptoObject?.cipher === cipher)
                            unlockAndLoad(biometricStore.decrypt(cipher))
                        } catch (_: Exception) {
                            error = "Biometric unlock is unavailable. Use your passphrase or recovery key."
                        }
                    }

                    override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                        if (generation != authenticationGeneration || activePrompt == null) return
                        activePrompt = null
                        status = "Use your passphrase or recovery key, or try biometrics again."
                    }
                })
            activePrompt = prompt
            error = ""
            prompt.authenticate(BiometricPrompt.PromptInfo.Builder()
                .setTitle("Unlock Local Password")
                .setSubtitle(siteName?.let { "Use a saved password for $it" } ?: "Choose a saved login")
                .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
                .setNegativeButtonText("Use passphrase")
                .build(), BiometricPrompt.CryptoObject(cipher))
        } catch (_: Exception) {
            activePrompt = null
            error = "Biometric unlock is unavailable. Use your passphrase or recovery key."
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        val structure = if (Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableExtra(AutofillManager.EXTRA_ASSIST_STRUCTURE, AssistStructure::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(AutofillManager.EXTRA_ASSIST_STRUCTURE)
        }
        if (structure == null) {
            finishCancelled("Android did not provide the sign-in form.")
            return
        }
        target = AutofillTargetFields.from(structure)
        if (target.passwordId == null) {
            finishCancelled("This screen does not have a supported password field.")
            return
        }
        siteName = target.webDomain
        requestingAppName = structure.activityComponent?.packageName?.let { packageName ->
            try {
                @Suppress("DEPRECATION")
                "${packageManager.getApplicationLabel(packageManager.getApplicationInfo(packageName, 0))} ($packageName)"
            } catch (_: Exception) {
                packageName
            }
        } ?: "the requesting app"
        val appearance = getSharedPreferences("local-password", MODE_PRIVATE)
            .getString("appearance", "light") ?: "light"
        setContent {
            LocalPasswordTheme(appearance) {
                BoxWithConstraints(modifier = Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.55f)).safeDrawingPadding().imePadding(), contentAlignment = Alignment.BottomCenter) {
                val panelMaxHeight = maxHeight
                Surface(modifier = Modifier.fillMaxWidth().heightIn(max = panelMaxHeight),
                    shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
                    color = MaterialTheme.colorScheme.surface) {
                AutofillAuthenticationScreen(
                    siteName = siteName,
                    requestingAppName = requestingAppName,
                    accounts = accounts,
                    showAllAccounts = showAllAccounts,
                    showAccountFallback = showAccountFallback,
                    secret = enteredSecret,
                    error = error,
                    status = status,
                    busy = busy,
                    onSecretChange = { enteredSecret = it },
                    onUnlock = { unlockAndLoad(enteredSecret) },
                    biometricAvailable = biometricAvailable,
                    onBiometricUnlock = ::promptBiometric,
                    onShowAll = { showAllAccounts = true; accounts = allAccounts },
                    onSelect = ::fill,
                    onCancel = { finishCancelled(null) },
                )
                }
                }
            }
        }
    }

    override fun onStop() {
        authenticationGeneration++
        val prompt = activePrompt
        activePrompt = null
        prompt?.cancelAuthentication()
        biometricAttempted = false
        enteredSecret = ""
        accounts = null
        allAccounts = emptyList()
        showAllAccounts = false
        showAccountFallback = false
        status = ""
        super.onStop()
    }

    private fun unlockAndLoad(secret: String) {
        if (busy || secret.isBlank()) return
        val generation = authenticationGeneration
        lifecycleScope.launch {
            busy = true
            error = ""
            status = "Unlocking vault…"
            var encryptedBlob: ByteArray? = null
            try {
                encryptedBlob = withContext(Dispatchers.IO) { VaultFileStore.read(this@AutofillAuthenticationActivity) }
                val active = withContext(Dispatchers.Default) {
                    val opened = Vault.open(secret, encryptedBlob!!)
                    try {
                        opened.items.filter { !it.archived && it.password.isNotEmpty() }
                    } finally {
                        opened.dek.fill(0)
                    }
                }
                if (generation != authenticationGeneration) return@launch
                val matches = siteName?.let { domain ->
                    active.filter { entry -> sameSite(entry.url, domain) }
                }
                allAccounts = active
                accounts = if (matches == null) active else matches
                showAccountFallback = matches != null && matches.isEmpty() && active.isNotEmpty()
                enteredSecret = ""
                status = if (accounts.isNullOrEmpty()) {
                    if (active.isEmpty()) "No saved passwords are available to fill."
                    else "No saved login matches $siteName."
                } else {
                    "Choose a saved login to fill."
                }
            } catch (exc: CancellationException) {
                throw exc
            } catch (exc: Exception) {
                if (generation != authenticationGeneration) return@launch
                error = if (exc is VaultException) exc.message ?: "Could not unlock the vault."
                    else "Could not open the vault. Try your passphrase or recovery key."
                status = ""
            } finally {
                encryptedBlob?.fill(0)
                busy = false
            }
        }
    }

    private fun sameSite(savedUrl: String, requestedDomain: String): Boolean {
        val savedHost = host(savedUrl) ?: return false
        val targetHost = host(requestedDomain) ?: return false
        return savedHost == targetHost
    }

    private fun host(value: String): String? {
        val candidate = value.trim().let { if (it.contains("://")) it else "https://$it" }
        return Uri.parse(candidate).host?.lowercase(Locale.ROOT)?.trimEnd('.')
    }

    @Suppress("DEPRECATION") // The RemoteViews dataset presentation is required on API 26+.
    private fun fill(item: SavedPassword) {
        val passwordId = target.passwordId ?: return finishCancelled("Password field is unavailable.")
        val presentation = android.widget.RemoteViews(packageName, R.layout.autofill_suggestion).apply {
            setTextViewText(R.id.autofill_label, "${item.name} · Local Password")
        }
        try {
            val dataset = android.service.autofill.Dataset.Builder(presentation).apply {
                target.usernameId?.takeIf { item.username.isNotBlank() }?.let { id ->
                    setValue(id, AutofillValue.forText(item.username), presentation)
                }
                setValue(passwordId, AutofillValue.forText(item.password), presentation)
            }.build()
            setResult(RESULT_OK, Intent().putExtra(AutofillManager.EXTRA_AUTHENTICATION_RESULT, dataset))
            accounts = null
            allAccounts = emptyList()
            finish()
        } catch (_: Exception) {
            error = "Android could not fill this sign-in form."
        }
    }

    private fun finishCancelled(message: String?) {
        if (message != null) status = message
        setResult(RESULT_CANCELED)
        finish()
    }
}

@androidx.compose.runtime.Composable
private fun AutofillAuthenticationScreen(
    siteName: String?,
    requestingAppName: String,
    accounts: List<SavedPassword>?,
    showAllAccounts: Boolean,
    showAccountFallback: Boolean,
    secret: String,
    error: String,
    status: String,
    busy: Boolean,
    onSecretChange: (String) -> Unit,
    onUnlock: () -> Unit,
    biometricAvailable: Boolean,
    onBiometricUnlock: () -> Unit,
    onShowAll: () -> Unit,
    onSelect: (SavedPassword) -> Unit,
    onCancel: () -> Unit,
) {
    var selectedName by remember(accounts, showAllAccounts) {
        mutableStateOf(accounts?.singleOrNull()?.takeIf { !showAllAccounts }?.name)
    }
    val selectedAccount = accounts?.firstOrNull { it.name == selectedName }
    LazyColumn(
        modifier = Modifier.fillMaxWidth().wrapContentHeight().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("Local Password", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelLarge)
            Text("Use saved password?", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text(
                if (siteName != null) "For $siteName"
                else "For $requestingAppName",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                if (siteName != null) "Site reported by $requestingAppName. Check it matches the page you opened."
                else "Check the app before choosing a login.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (accounts == null) {
            item {
                if (biometricAvailable) {
                    Button(onClick = onBiometricUnlock, enabled = !busy,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                        Text("Unlock with biometrics")
                    }
                    Text("Or use your passphrase or recovery key.", style = MaterialTheme.typography.bodyMedium)
                }
                OutlinedTextField(
                    value = secret,
                    onValueChange = onSecretChange,
                    label = { Text("Passphrase or recovery key") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
                if (status.isNotEmpty()) Text(status, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Button(onClick = onUnlock, enabled = !busy && secret.isNotBlank(), modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                    Text(if (busy) "Unlocking…" else "Unlock and choose login")
                }
            }
        } else {
            item {
                Text(status, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
                if (showAccountFallback && !showAllAccounts) {
                    TextButton(onClick = onShowAll) { Text("Show all saved logins") }
                }
            }
            if (showAllAccounts) {
                item {
                    Text("These logins do not match this site. Check the saved website before filling.",
                        color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                }
            }
            items(accounts, key = { it.name }) { account ->
                val selected = account.name == selectedName
                Card(onClick = { selectedName = account.name },
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = if (selected)
                        MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surfaceContainer)) {
                    Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(selected = selected, onClick = { selectedName = account.name })
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(account.username.ifBlank { account.name }, style = MaterialTheme.typography.titleMedium)
                            if (account.username.isNotBlank()) Text(account.name, style = MaterialTheme.typography.bodySmall)
                            Text("••••••••••••", style = MaterialTheme.typography.bodyLarge)
                            if (account.url.isNotBlank()) Text(account.url, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
            if (accounts.isNotEmpty()) {
                item {
                    Button(onClick = { selectedAccount?.let(onSelect) }, enabled = selectedAccount != null,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) {
                        Text("Fill login")
                    }
                    Text("Fills the form. You choose when to sign in.", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        item {
            TextButton(onClick = onCancel, enabled = !busy) { Text("Cancel") }
        }
    }
}
