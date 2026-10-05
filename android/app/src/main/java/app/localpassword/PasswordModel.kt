package app.localpassword

import android.app.Application
import android.content.ClipData
import android.content.ClipboardManager
import android.content.SharedPreferences
import android.net.wifi.WifiManager
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.util.Locale

class PasswordModel(app: Application) : AndroidViewModel(app) {
    var section by mutableStateOf("create")
    var wordsMode by mutableStateOf(false)
    var length by mutableStateOf(16)
    var wordCount by mutableStateOf(6)
    var digits by mutableStateOf(true)
    var letters by mutableStateOf(true)
    var symbols by mutableStateOf(true)
    var current by mutableStateOf("")
    var bitsLabel by mutableStateOf("")
    var strength by mutableStateOf("")
    var fraction by mutableStateOf(0f)
    var note by mutableStateOf("The bar fills toward 256 bits. Strong starts at 75.")
    var name by mutableStateOf("")
    var status by mutableStateOf("Generate a password. Name it, then save it.")
    var busy by mutableStateOf(false)
    var unlocked by mutableStateOf(false)
    var appLocked by mutableStateOf(false)
    var appLockEnabled by mutableStateOf(false)
    var biometricEnabled by mutableStateOf(false)
    var askEnableBiometric by mutableStateOf(false)
    var askEnableAppLock by mutableStateOf(false)
    var saved by mutableStateOf<List<SavedPassword>>(emptyList())
    var revealed by mutableStateOf<String?>(null)
    var askNewPassphrase by mutableStateOf(false)
    var askUnlock by mutableStateOf(false)
    var askChangeCurrent by mutableStateOf(false)
    var askChangeNew by mutableStateOf(false)
    var recoveryKey by mutableStateOf<String?>(null)
    var error by mutableStateOf("")
    var dark by mutableStateOf(loadDark())
    var offerCode by mutableStateOf<String?>(null)
    var offerWhere by mutableStateOf("")
    var askReceive by mutableStateOf(false)
    var askIncomingPassphrase by mutableStateOf(false)
    var savedQuery by mutableStateOf("")
    var favoritesOnly by mutableStateOf(false)
    var archivedOnly by mutableStateOf(false)
    var needsAttentionOnly by mutableStateOf(false)
    var categoryFilter by mutableStateOf("all")
    var savedSortMode by mutableStateOf(Vault.SAVED_SORT_NAME)
    var pendingRemove by mutableStateOf<SavedPassword?>(null)
    var lastRemoved by mutableStateOf<SavedPassword?>(null)
    var pendingReplace by mutableStateOf<SavedPassword?>(null)
    var historyFor by mutableStateOf<SavedPassword?>(null)
    var editing by mutableStateOf<SavedPassword?>(null)
    var renaming by mutableStateOf<SavedPassword?>(null)
    var categorizing by mutableStateOf<SavedPassword?>(null)
    var editingUsername by mutableStateOf<SavedPassword?>(null)
    var editingUrl by mutableStateOf<SavedPassword?>(null)
    var editingNotes by mutableStateOf<SavedPassword?>(null)

    private var opened: OpenVault? = null
    private var offer: VaultSync.Offer? = null
    private var incomingBlob: ByteArray? = null
    private var changeItems: List<SavedPassword>? = null
    private var clipboardGeneration = 0
    private var lastUnlockSecret: String? = null
    private val words: List<String> by lazy { loadWords() }

    init {
        appLockEnabled = loadAppLockEnabled()
        biometricEnabled = loadBiometricEnabled() && hasStoredUnlockSecret()
        // App lock is opt-in. A vault passphrase alone does not lock the whole app.
        if (hasVault() && appLockEnabled) {
            appLocked = true
            status = "Unlock to open Local Password."
        }
    }

    fun vaultFile(): File = File(getApplication<Application>().filesDir, "saved.vault")

    fun hasVault(): Boolean = vaultFile().isFile

    fun toggleDark() {
        dark = !dark
        getApplication<Application>().getSharedPreferences("local-password", 0)
            .edit()
            .putString("appearance", if (dark) "dark" else "light")
            .apply()
    }

    fun generate() {
        viewModelScope.launch {
            try {
                val wordlist = words
                val made = withContext(Dispatchers.Default) {
                    if (wordsMode) {
                        val text = Generator.passphrase(wordCount, wordlist)
                        val bits = Generator.passphraseBits(wordCount, wordlist.size)
                        Made(text, bits, if (Generator.isStrong(bits)) "" else "Add words to reach a strong passphrase.")
                    } else {
                        val pool = Generator.characterPool(digits, letters, symbols)
                        val text = Generator.password(length, pool)
                        val bits = Generator.characterBits(length, pool)
                        Made(
                            text,
                            bits,
                            if (Generator.isStrong(bits)) {
                                ""
                            } else {
                                "These options stay under 75 bits. Add length or more character types to reach a strong password."
                            },
                        )
                    }
                }
                current = made.text
                bitsLabel = Generator.bitsLabel(made.bits)
                strength = if (Generator.isStrong(made.bits)) "Strong" else "Weak"
                fraction = Generator.meterFraction(made.bits)
                note = made.note.ifEmpty { "The bar fills toward 256 bits. Strong starts at 75." }
                status = "Name it, then save it."
                error = ""
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not generate a password."
            }
        }
    }

    fun copy(text: String) {
        val clipboard = getApplication<Application>().getSystemService(ClipboardManager::class.java)
        clipboard.setPrimaryClip(ClipData.newPlainText("password", text))
        status = "Copied. Clipboard clears in 30 seconds."
        val generation = ++clipboardGeneration
        viewModelScope.launch {
            delay(30_000)
            if (generation != clipboardGeneration) return@launch
            val currentClip = clipboard.primaryClip
            val stillOurs = currentClip != null &&
                currentClip.itemCount > 0 &&
                currentClip.getItemAt(0).coerceToText(getApplication()).toString() == text
            if (stillOurs) {
                clipboard.setPrimaryClip(ClipData.newPlainText("", ""))
            }
        }
    }

    fun copySavedSecret(item: SavedPassword, text: String) {
        copy(text)
        if (text.isEmpty()) return
        val currentOpen = opened ?: return
        val current = currentOpen.items.firstOrNull { it.name == item.name } ?: return
        viewModelScope.launch {
            try {
                val next = withContext(Dispatchers.Default) {
                    Vault.touchLastUsed(currentOpen.items, current)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
            } catch (_: VaultException) {
                // Copy already succeeded; leave last-used alone if sealing fails.
            }
        }
    }

    fun requestSave() {
        error = ""
        if (current.isEmpty()) {
            status = "Generate a password first."
            return
        }
        try {
            Vault.cleanName(name)
        } catch (exc: VaultException) {
            error = exc.message ?: "Name this password."
            return
        }
        if (!hasVault()) {
            askNewPassphrase = true
            return
        }
        if (opened == null) {
            askUnlock = true
            return
        }
        persist(opened!!)
    }

    fun createVault(passphrase: String, confirm: String) {
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                if (passphrase != confirm) {
                    error = "Those passphrases do not match."
                    return@launch
                }
                val now = Vault.utcNow()
                val item = SavedPassword(
                    name = Vault.cleanName(name),
                    password = current,
                    created = now,
                    modified = now,
                )
                val recovery = Generator.recoveryKey(words)
                val (blob, fresh) = withContext(Dispatchers.Default) {
                    Vault.create(passphrase, recovery, listOf(item))
                }
                writeAtomically(blob)
                opened = fresh
                saved = fresh.items
                unlocked = true
                appLocked = false
                askNewPassphrase = false
                rememberUnlockSecret(passphrase)
                recoveryKey = recovery
                status = "Saved."
            } catch (exc: VaultException) {
                error = exc.message ?: "Not saved."
            } finally {
                busy = false
            }
        }
    }

    fun unlock(secret: String, thenSave: Boolean) {
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val blob = vaultFile().readBytes()
                val fresh = withContext(Dispatchers.Default) { Vault.open(secret, blob) }
                opened = fresh
                saved = fresh.items
                unlocked = true
                appLocked = false
                askUnlock = false
                rememberUnlockSecret(secret)
                val waiting = incomingBlob
                if (waiting != null) {
                    status = "Unlocked."
                    mergeInto(fresh, waiting)
                } else {
                    status = "Unlocked."
                    if (thenSave) persist(fresh)
                }
            } catch (exc: VaultException) {
                error = exc.message ?: "That passphrase or recovery key did not unlock the saved passwords."
            } finally {
                busy = false
            }
        }
    }

    fun lockApp() {
        if (!hasVault()) {
            appLocked = false
            return
        }
        if (appLocked) return
        // Keep the recovery-key dialog up until the user acknowledges it.
        if (recoveryKey != null) return
        opened = null
        unlocked = false
        saved = emptyList()
        revealed = null
        lastRemoved = null
        pendingRemove = null
        pendingReplace = null
        historyFor = null
        editing = null
        renaming = null
        categorizing = null
        editingUsername = null
        editingUrl = null
        editingNotes = null
        askUnlock = false
        askNewPassphrase = false
        askChangeCurrent = false
        askChangeNew = false
        askEnableBiometric = false
        askEnableAppLock = false
        appLocked = true
        status = "Locked."
        error = ""
    }

    fun requestEnableAppLock() {
        error = ""
        if (!hasVault()) {
            error = "Save a password first. App lock needs a vault passphrase."
            return
        }
        if (unlocked && !lastUnlockSecret.isNullOrEmpty()) {
            prefs().edit().putBoolean(PREF_APP_LOCK, true).apply()
            appLockEnabled = true
            status = "App lock is on. Closing the app asks for your passphrase."
            return
        }
        askEnableAppLock = true
    }

    fun confirmEnableAppLock(secret: String) {
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val blob = vaultFile().readBytes()
                val fresh = withContext(Dispatchers.Default) { Vault.open(secret, blob) }
                opened = fresh
                saved = fresh.items
                unlocked = true
                rememberUnlockSecret(secret)
                prefs().edit().putBoolean(PREF_APP_LOCK, true).apply()
                appLockEnabled = true
                askEnableAppLock = false
                status = "App lock is on. Closing the app asks for your passphrase."
            } catch (exc: VaultException) {
                error = exc.message ?: "That passphrase or recovery key did not unlock the saved passwords."
            } finally {
                busy = false
            }
        }
    }

    fun disableAppLock() {
        prefs().edit().putBoolean(PREF_APP_LOCK, false).apply()
        appLockEnabled = false
        disableBiometric(announce = false)
        appLocked = false
        status = "App lock is off. Saved passwords still need the passphrase when you open them."
    }

    fun unlockWithBiometricSecret() {
        val secret = readStoredUnlockSecret()
        if (secret.isNullOrEmpty()) {
            error = "Biometric unlock is not set up. Enter your passphrase."
            biometricEnabled = false
            return
        }
        unlock(secret, thenSave = false)
    }

    fun requestEnableBiometric() {
        error = ""
        if (!appLockEnabled) {
            error = "Turn on App lock first."
            return
        }
        if (!unlocked || lastUnlockSecret.isNullOrEmpty()) {
            askEnableBiometric = true
            return
        }
        storeUnlockSecret(lastUnlockSecret!!)
        biometricEnabled = true
        prefs().edit().putBoolean(PREF_BIOMETRIC, true).apply()
        status = "Biometric unlock is on."
    }

    fun confirmEnableBiometric(secret: String) {
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val blob = vaultFile().readBytes()
                withContext(Dispatchers.Default) { Vault.open(secret, blob) }
                storeUnlockSecret(secret)
                rememberUnlockSecret(secret)
                biometricEnabled = true
                prefs().edit().putBoolean(PREF_BIOMETRIC, true).apply()
                askEnableBiometric = false
                status = "Biometric unlock is on."
            } catch (exc: VaultException) {
                error = exc.message ?: "That passphrase or recovery key did not unlock the saved passwords."
            } finally {
                busy = false
            }
        }
    }

    fun disableBiometric(announce: Boolean = true) {
        clearStoredUnlockSecret()
        biometricEnabled = false
        prefs().edit().putBoolean(PREF_BIOMETRIC, false).apply()
        if (announce) {
            status = "Biometric unlock is off."
        }
    }

    fun hasBiometricSecret(): Boolean = biometricEnabled && hasStoredUnlockSecret()

    fun requestChangePassphrase() {
        error = ""
        if (!hasVault()) {
            error = "Save a password first. There is no vault to re-lock yet."
            return
        }
        askChangeCurrent = true
    }

    fun confirmChangeCurrent(secret: String) {
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val blob = vaultFile().readBytes()
                val fresh = withContext(Dispatchers.Default) { Vault.open(secret, blob) }
                opened = fresh
                saved = fresh.items
                unlocked = true
                changeItems = fresh.items
                askChangeCurrent = false
                askChangeNew = true
            } catch (exc: VaultException) {
                error = exc.message ?: "That passphrase or recovery key did not unlock the saved passwords."
            } finally {
                busy = false
            }
        }
    }

    fun cancelChangePassphrase() {
        askChangeCurrent = false
        askChangeNew = false
        changeItems = null
    }

    fun confirmChangeNew(passphrase: String, confirm: String) {
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                if (passphrase != confirm) {
                    error = "Those passphrases do not match."
                    return@launch
                }
                val items = changeItems ?: opened?.items
                if (items == null) {
                    error = "Unlock the vault before changing the passphrase."
                    return@launch
                }
                val recovery = Generator.recoveryKey(words)
                val (blob, fresh) = withContext(Dispatchers.Default) {
                    Vault.create(passphrase, recovery, items)
                }
                writeAtomically(blob)
                opened = fresh
                saved = fresh.items
                unlocked = true
                appLocked = false
                askChangeNew = false
                changeItems = null
                rememberUnlockSecret(passphrase)
                recoveryKey = recovery
                status = "Passphrase changed. The old passphrase and recovery key no longer open this vault."
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not rewrite the vault with the new passphrase."
            } finally {
                busy = false
            }
        }
    }

    fun requestRemove(item: SavedPassword) {
        pendingRemove = item
    }

    fun confirmRemove() {
        val item = pendingRemove ?: return
        val currentOpen = opened ?: return
        pendingRemove = null
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val next = withContext(Dispatchers.Default) {
                    Vault.removeEntry(currentOpen.items, item)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                lastRemoved = item
                if (revealed == item.name) revealed = null
                status = "Removed \"${item.name}\". Undo to put it back."
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not remove the saved password."
            } finally {
                busy = false
            }
        }
    }

    fun cancelRemove() {
        pendingRemove = null
    }

    fun undoRemove() {
        val item = lastRemoved ?: return
        val currentOpen = opened ?: return
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val next = withContext(Dispatchers.Default) {
                    Vault.restoreRemovedEntry(currentOpen.items, item)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                lastRemoved = null
                status = "Restored \"${next.first().name}\"."
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not restore that entry."
            } finally {
                busy = false
            }
        }
    }

    fun requestReplace(item: SavedPassword) {
        pendingReplace = item
    }

    fun cancelReplace() {
        pendingReplace = null
    }

    fun confirmReplace() {
        val item = pendingReplace ?: return
        val currentOpen = opened ?: return
        pendingReplace = null
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val fresh = withContext(Dispatchers.Default) { Generator.strongReplacementPassword() }
                val next = Vault.replaceEntryPassword(currentOpen.items, item, fresh)
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                revealed = item.name
                copy(fresh)
                status = "Replaced the password for ${item.name} and copied it. The old one is under Previous."
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not save the new password."
            } finally {
                busy = false
            }
        }
    }

    fun showHistory(item: SavedPassword) {
        historyFor = item
    }

    fun cancelHistory() {
        historyFor = null
    }

    fun copyPrevious(secret: String) {
        historyFor = null
        copy(secret)
        status = "Copied a previous password."
    }

    fun restorePrevious(index: Int) {
        val item = historyFor ?: return
        val currentOpen = opened ?: return
        val current = currentOpen.items.firstOrNull { it.name == item.name } ?: run {
            error = "That saved password is gone."
            historyFor = null
            return
        }
        historyFor = null
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val next = withContext(Dispatchers.Default) {
                    Vault.restoreEntryPassword(currentOpen.items, current, index)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                val restored = next.first { it.name == current.name }
                revealed = restored.name
                copy(restored.password)
                status = "Restored the previous password for ${restored.name} and copied it."
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not restore that password."
            } finally {
                busy = false
            }
        }
    }

    fun toggleFavorite(item: SavedPassword) {
        val currentOpen = opened ?: return
        val current = currentOpen.items.firstOrNull { it.name == item.name } ?: run {
            error = "That saved password is gone."
            return
        }
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val next = withContext(Dispatchers.Default) {
                    Vault.toggleEntryFavorite(currentOpen.items, current)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                val stamped = next.first { it.name == current.name }
                status = if (stamped.favorite) {
                    "Favorited ${stamped.name}."
                } else {
                    "Cleared favorite on ${stamped.name}."
                }
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not update Favorite."
            } finally {
                busy = false
            }
        }
    }

    fun duplicateEntry(item: SavedPassword) {
        val currentOpen = opened ?: return
        val current = currentOpen.items.firstOrNull { it.name == item.name } ?: run {
            error = "That saved password is gone."
            return
        }
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val next = withContext(Dispatchers.Default) {
                    Vault.duplicateEntry(currentOpen.items, current)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                status = "Duplicated as ${next.first().name}."
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not duplicate that entry."
            } finally {
                busy = false
            }
        }
    }

    fun beginEdit(item: SavedPassword) {
        editing = item
    }

    fun cancelEdit() {
        editing = null
    }

    fun beginRename(item: SavedPassword) {
        error = ""
        renaming = item
    }

    fun cancelRename() {
        renaming = null
        error = ""
    }

    fun confirmRename(newName: String) {
        val currentOpen = opened ?: return
        val current = renaming ?: return
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val label = withContext(Dispatchers.Default) { Vault.cleanName(newName) }
                if (label == current.name) {
                    status = "${current.name} already uses that name."
                    renaming = null
                    return@launch
                }
                val next = withContext(Dispatchers.Default) {
                    Vault.renameEntry(currentOpen.items, current, label)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                if (revealed == current.name) revealed = label
                renaming = null
                status = "Renamed to $label."
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not rename that entry."
            } finally {
                busy = false
            }
        }
    }

    fun beginCategory(item: SavedPassword) {
        error = ""
        categorizing = item
    }

    fun cancelCategory() {
        categorizing = null
        error = ""
    }

    fun confirmCategory(category: String) {
        val currentOpen = opened ?: return
        val current = categorizing ?: return
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val label = withContext(Dispatchers.Default) { Vault.cleanCategory(category) }
                if (label == current.category) {
                    status = if (current.category.isNotEmpty()) {
                        "${current.name} already uses that category."
                    } else {
                        "${current.name} has no category."
                    }
                    categorizing = null
                    return@launch
                }
                val next = withContext(Dispatchers.Default) {
                    Vault.setEntryCategory(currentOpen.items, current, label)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                categorizing = null
                val stamped = next.first { it.name == current.name }
                status = if (stamped.category.isNotEmpty()) {
                    "Set category on ${stamped.name} to ${stamped.category}."
                } else {
                    "Cleared category on ${stamped.name}."
                }
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not update that category."
            } finally {
                busy = false
            }
        }
    }

    fun beginUsername(item: SavedPassword) {
        error = ""
        editingUsername = item
    }

    fun cancelUsername() {
        editingUsername = null
        error = ""
    }

    fun confirmUsername(username: String) {
        val currentOpen = opened ?: return
        val current = editingUsername ?: return
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val label = withContext(Dispatchers.Default) { Vault.cleanUsername(username) }
                if (label == current.username) {
                    status = if (current.username.isNotEmpty()) {
                        "${current.name} already uses that username."
                    } else {
                        "${current.name} has no username."
                    }
                    editingUsername = null
                    return@launch
                }
                val next = withContext(Dispatchers.Default) {
                    Vault.setEntryUsername(currentOpen.items, current, label)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                editingUsername = null
                val stamped = next.first { it.name == current.name }
                status = if (stamped.username.isNotEmpty()) {
                    "Set username on ${stamped.name} to ${stamped.username}."
                } else {
                    "Cleared username on ${stamped.name}."
                }
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not update that username."
            } finally {
                busy = false
            }
        }
    }

    fun beginUrl(item: SavedPassword) {
        error = ""
        editingUrl = item
    }

    fun cancelUrl() {
        editingUrl = null
        error = ""
    }

    fun confirmUrl(url: String) {
        val currentOpen = opened ?: return
        val current = editingUrl ?: return
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val label = withContext(Dispatchers.Default) { Vault.cleanUrl(url) }
                if (label == current.url) {
                    status = if (current.url.isNotEmpty()) {
                        "${current.name} already uses that URL."
                    } else {
                        "${current.name} has no URL."
                    }
                    editingUrl = null
                    return@launch
                }
                val next = withContext(Dispatchers.Default) {
                    Vault.setEntryUrl(currentOpen.items, current, label)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                editingUrl = null
                val stamped = next.first { it.name == current.name }
                status = if (stamped.url.isNotEmpty()) {
                    "Set URL on ${stamped.name}."
                } else {
                    "Cleared URL on ${stamped.name}."
                }
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not update that URL."
            } finally {
                busy = false
            }
        }
    }

    fun beginNotes(item: SavedPassword) {
        error = ""
        editingNotes = item
    }

    fun cancelNotes() {
        editingNotes = null
        error = ""
    }

    fun confirmNotes(notes: String) {
        val currentOpen = opened ?: return
        val current = editingNotes ?: return
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val label = withContext(Dispatchers.Default) { Vault.cleanNotes(notes) }
                if (label == current.notes) {
                    status = if (current.notes.isNotEmpty()) {
                        "${current.name} already uses those notes."
                    } else {
                        "${current.name} has no notes."
                    }
                    editingNotes = null
                    return@launch
                }
                val next = withContext(Dispatchers.Default) {
                    Vault.setEntryNotes(currentOpen.items, current, label)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                editingNotes = null
                val stamped = next.first { it.name == current.name }
                status = if (stamped.notes.isNotEmpty()) {
                    "Updated notes on ${stamped.name}."
                } else {
                    "Cleared notes on ${stamped.name}."
                }
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not update those notes."
            } finally {
                busy = false
            }
        }
    }

    fun saveEdit(updated: SavedPassword) {
        val currentOpen = opened ?: return
        val previous = editing ?: return
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val now = Vault.utcNow()
                val base = previous.copy(
                    name = updated.name,
                    username = updated.username,
                    url = updated.url,
                    notes = updated.notes,
                    category = updated.category,
                    favorite = updated.favorite,
                    archived = updated.archived,
                    created = previous.created.ifEmpty { now },
                    lastUsed = previous.lastUsed,
                    extras = previous.extras,
                    history = previous.history,
                )
                val stamped = if (updated.password != previous.password) {
                    Vault.withChangedPassword(base, updated.password)
                } else {
                    Vault.normalizeEntry(base.copy(password = previous.password, modified = now))
                }
                if (stamped.name != previous.name && currentOpen.items.any { it.name == stamped.name }) {
                    error = "Another saved password already uses that name."
                    return@launch
                }
                val next = listOf(stamped) + currentOpen.items.filter { it.name != previous.name }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                if (revealed == previous.name) revealed = stamped.name
                editing = null
                status = "Updated ${stamped.name}."
            } catch (exc: VaultException) {
                error = exc.message ?: "Not saved."
            } finally {
                busy = false
            }
        }
    }

    fun filteredSaved(): List<SavedPassword> {
        val needle = savedQuery.trim().lowercase(Locale.getDefault())
        val pool = if (archivedOnly) saved.filter { it.archived } else Vault.activeSavedEntries(saved)
        val matches = pool.filter { item ->
            val matchesQuery = needle.isEmpty() || listOf(
                item.name, item.username, item.url, item.notes, item.category,
            ).any { it.lowercase(Locale.getDefault()).contains(needle) }
            val matchesFavorite = !favoritesOnly || item.favorite
            val matchesAttention = !needsAttentionOnly || Vault.entryNeedsAttention(item, pool)
            val matchesCategory = categoryFilter == "all" || item.category == categoryFilter
            matchesQuery && matchesFavorite && matchesAttention && matchesCategory
        }
        return Vault.sortedSavedEntries(matches, savedSortMode, allItems = pool)
    }

    fun toggleArchived(item: SavedPassword) {
        val currentOpen = opened ?: return
        val current = currentOpen.items.firstOrNull { it.name == item.name } ?: run {
            error = "That saved password is gone."
            return
        }
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val next = withContext(Dispatchers.Default) {
                    Vault.toggleEntryArchived(currentOpen.items, current)
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                val stamped = next.first { it.name == current.name }
                status = if (stamped.archived) {
                    "Archived ${stamped.name}."
                } else {
                    "Unarchived ${stamped.name}."
                }
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not update Archive."
            } finally {
                busy = false
            }
        }
    }

    fun reuseWarning(item: SavedPassword): String = Vault.reuseWarningFor(item, saved)

    fun strengthWarning(item: SavedPassword): String = Vault.strengthWarningFor(item)

    fun reusedPasswordCount(): Int = Vault.reusedPasswordGroups(saved).size

    fun weakPasswordCount(): Int = Vault.weakPasswordNames(saved).size

    fun passwordHealthSummary(): PasswordHealth = Vault.passwordHealthSummary(saved)

    fun staleWarning(item: SavedPassword): String = Vault.staleWarningFor(item)

    fun openUrl(url: String) {
        val target = Vault.browseableUrl(url) ?: run {
            error = "That URL could not be opened."
            return
        }
        try {
            val intent = android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(target))
            intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
            getApplication<Application>().startActivity(intent)
            status = "Opening $target."
            error = ""
        } catch (_: Exception) {
            error = "That URL could not be opened."
        }
    }

    fun categories(): List<String> =
        saved.map { it.category }.filter { it.isNotEmpty() }.distinct().sortedBy { it.lowercase(Locale.getDefault()) }

    fun import(bytes: ByteArray) {
        if (bytes.size < 48 || (!bytes.startsWithMagic("LPV2") && !bytes.startsWithMagic("LPV1"))) {
            error = "That file is not a Local Password vault."
            return
        }
        writeAtomically(bytes)
        opened = null
        unlocked = false
        saved = emptyList()
        lastRemoved = null
        revealed = null
        section = "saved"
        disableBiometric(announce = false)
        if (appLockEnabled) {
            appLocked = true
        } else {
            appLocked = false
            askUnlock = true
        }
        status = "Vault copied onto this phone. Unlock with the same passphrase."
        error = ""
    }

    fun importCsv(text: String) {
        val currentOpen = opened
        if (currentOpen == null || !unlocked) {
            error = "Unlock the vault before importing a CSV."
            askUnlock = true
            return
        }
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val incoming = withContext(Dispatchers.Default) { Vault.parsePasswordCsv(text) }
                val before = currentOpen.items.size
                val (next, splits) = withContext(Dispatchers.Default) {
                    Vault.mergeEntries(currentOpen.items, incoming, conflictSuffix = " (imported)")
                }
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                section = "saved"
                val added = next.size - before
                status = if (splits > 0) {
                    "Imported $added new entr${if (added == 1) "y" else "ies"} ($splits renamed to avoid clashes)."
                } else {
                    "Imported $added new entr${if (added == 1) "y" else "ies"} from the CSV."
                }
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not import that CSV file."
            } finally {
                busy = false
            }
        }
    }

    fun exportCsvText(): String? {
        val currentOpen = opened
        if (currentOpen == null || !unlocked) {
            error = "Unlock the vault before exporting a CSV."
            askUnlock = true
            return null
        }
        return try {
            Vault.formatPasswordCsv(currentOpen.items).also {
                status = "CSV is ready. The file is plaintext — delete it when you are done."
                error = ""
            }
        } catch (exc: VaultException) {
            error = exc.message ?: "Could not export a CSV."
            null
        }
    }

    fun sendVault() {
        if (busy || offerCode != null) return
        if (!hasVault()) {
            error = "Save a password on this phone first."
            return
        }
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val bytes = withContext(Dispatchers.IO) { vaultFile().readBytes() }
                val started = withContext(Dispatchers.IO) {
                    VaultSync.Offer(bytes).also { it.start() }
                }
                if (started.error.isNotEmpty() || started.port == 0) {
                    started.stop()
                    error = started.error.ifEmpty { "Could not offer the vault on this network." }
                    return@launch
                }
                offer?.stop()
                offer = started
                offerCode = started.code
                offerWhere = started.where()
                watchOffer(started)
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not offer the vault on this network."
            } finally {
                busy = false
            }
        }
    }

    fun cancelOffer() {
        val current = offer
        val sent = current?.sent == true
        current?.stop()
        offer = null
        offerCode = null
        offerWhere = ""
        status = if (sent) {
            "The encrypted vault was sent. The passphrase stayed on this phone."
        } else {
            "The offer was cancelled. Nothing was sent."
        }
    }

    fun receiveVault(code: String, address: String) {
        if (busy) return
        try {
            VaultSync.normalizeCode(code)
        } catch (exc: VaultException) {
            error = exc.message ?: "The pairing code is 6 digits."
            return
        }
        askReceive = false
        error = ""
        viewModelScope.launch {
            busy = true
            status = "Looking for the other device."
            try {
                val blob = withContext(Dispatchers.IO) {
                    withMulticastLock {
                        VaultSync.receiveVault(code, address.trim().ifEmpty { null })
                    }
                }
                applyReceived(blob)
            } catch (exc: VaultException) {
                error = exc.message ?: "Could not receive the vault."
            } finally {
                busy = false
            }
        }
    }

    fun mergeWithIncomingPassphrase(secret: String) {
        val blob = incomingBlob ?: return
        val current = opened ?: return
        viewModelScope.launch {
            busy = true
            error = ""
            try {
                val foreign = withContext(Dispatchers.Default) { Vault.open(secret, blob) }
                incomingBlob = null
                askIncomingPassphrase = false
                finishMerge(current, foreign.items)
            } catch (exc: VaultException) {
                error = exc.message ?: "That passphrase or recovery key did not unlock the saved passwords."
            } finally {
                busy = false
            }
        }
    }

    fun dismissIncoming() {
        askIncomingPassphrase = false
        incomingBlob = null
        status = "Nothing was merged."
    }

    override fun onCleared() {
        offer?.stop()
        super.onCleared()
    }

    private fun watchOffer(started: VaultSync.Offer) {
        viewModelScope.launch {
            while (offer === started && !started.sent && started.error.isEmpty()) {
                delay(400)
            }
            if (offer !== started) return@launch
            if (started.sent) {
                status = "The encrypted vault was sent. The passphrase stayed on this phone."
            } else if (started.error.isNotEmpty()) {
                error = started.error
            } else {
                status = "The offer ended. Nothing was sent."
            }
            offerCode = null
            offerWhere = ""
            started.stop()
            if (offer === started) offer = null
        }
    }

    private suspend fun applyReceived(blob: ByteArray) {
        if (!hasVault()) {
            withContext(Dispatchers.IO) { writeAtomically(blob) }
            opened = null
            unlocked = false
            saved = emptyList()
            revealed = null
            section = "saved"
            askUnlock = true
            status = "Vault received. The passphrase was not sent. Unlock with the same passphrase."
            error = ""
            return
        }
        val current = opened
        if (current == null) {
            incomingBlob = blob
            askUnlock = true
            section = "saved"
            status = "Unlock this phone's vault to merge. The passphrase is not sent."
            return
        }
        mergeInto(current, blob)
    }

    private suspend fun mergeInto(current: OpenVault, blob: ByteArray) {
        val same = withContext(Dispatchers.Default) { Vault.itemsFromSameVault(blob, current) }
        if (same != null) {
            incomingBlob = null
            finishMerge(current, same)
            return
        }
        incomingBlob = blob
        askIncomingPassphrase = true
        status = "This vault uses a different passphrase. Enter it to merge. It is not sent."
    }

    private fun finishMerge(current: OpenVault, incoming: List<SavedPassword>) {
        val (merged, splits) = Vault.mergeSaved(current.items, incoming)
        val extra = when (splits) {
            0 -> ""
            1 -> " One name differed, so both copies were kept."
            else -> " $splits names differed, so both copies were kept."
        }
        replace(current, merged, "Passwords arrived. The passphrase was not sent.$extra")
        section = "saved"
    }

    private inline fun <T> withMulticastLock(block: () -> T): T {
        val lock = try {
            val wifi = getApplication<Application>().applicationContext.getSystemService(WifiManager::class.java)
            wifi?.createMulticastLock("local-password")?.also {
                it.setReferenceCounted(false)
                it.acquire()
            }
        } catch (_: SecurityException) {
            null
        }
        try {
            return block()
        } finally {
            try {
                if (lock?.isHeld == true) lock.release()
            } catch (_: RuntimeException) {
            }
        }
    }

    fun exportBytes(): ByteArray? {
        val file = vaultFile()
        if (!file.isFile) {
            error = "Save a password on this phone first."
            return null
        }
        return file.readBytes()
    }

    private fun persist(currentOpen: OpenVault) {
        val now = Vault.utcNow()
        val label = Vault.cleanName(name)
        val previous = currentOpen.items.firstOrNull { it.name == label }
        val item = if (previous == null) {
            SavedPassword(
                name = label,
                password = current,
                created = now,
                modified = now,
            )
        } else if (previous.password == current) {
            previous.copy(modified = now)
        } else {
            Vault.withChangedPassword(
                previous.copy(
                    username = previous.username,
                    url = previous.url,
                    notes = previous.notes,
                    category = previous.category,
                    favorite = previous.favorite,
                    created = previous.created.ifEmpty { now },
                    extras = previous.extras,
                ),
                current,
            )
        }
        replace(currentOpen, currentOpen.items.filter { it.name != item.name } + item, "Saved.")
    }

    private fun replace(currentOpen: OpenVault, next: List<SavedPassword>, done: String) {
        viewModelScope.launch {
            busy = true
            try {
                val blob = withContext(Dispatchers.Default) { Vault.seal(currentOpen, next) }
                writeAtomically(blob)
                opened = currentOpen.copy(items = next)
                saved = next
                unlocked = true
                status = done
                error = ""
            } catch (exc: VaultException) {
                error = exc.message ?: "Not saved."
            } finally {
                busy = false
            }
        }
    }

    private fun writeAtomically(bytes: ByteArray) {
        val file = vaultFile()
        val temporary = File(file.parentFile, "saved.vault.tmp")
        temporary.writeBytes(bytes)
        if (!temporary.renameTo(file)) {
            file.writeBytes(bytes)
            temporary.delete()
        }
    }

    private fun rememberUnlockSecret(secret: String) {
        lastUnlockSecret = secret
        if (biometricEnabled) {
            storeUnlockSecret(secret)
        }
    }

    private fun loadDark(): Boolean {
        return prefs().getString("appearance", "light") == "dark"
    }

    private fun loadAppLockEnabled(): Boolean = prefs().getBoolean(PREF_APP_LOCK, false)

    private fun loadBiometricEnabled(): Boolean = prefs().getBoolean(PREF_BIOMETRIC, false)

    private fun prefs(): SharedPreferences =
        getApplication<Application>().getSharedPreferences("local-password", 0)

    private fun encryptedPrefs(): SharedPreferences {
        val app = getApplication<Application>()
        val masterKey = MasterKey.Builder(app)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        return EncryptedSharedPreferences.create(
            app,
            "local-password-secure",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    private fun hasStoredUnlockSecret(): Boolean =
        try {
            !encryptedPrefs().getString(PREF_UNLOCK_SECRET, null).isNullOrEmpty()
        } catch (_: Exception) {
            false
        }

    private fun readStoredUnlockSecret(): String? =
        try {
            encryptedPrefs().getString(PREF_UNLOCK_SECRET, null)
        } catch (_: Exception) {
            null
        }

    private fun storeUnlockSecret(secret: String) {
        encryptedPrefs().edit().putString(PREF_UNLOCK_SECRET, secret).apply()
    }

    private fun clearStoredUnlockSecret() {
        try {
            encryptedPrefs().edit().remove(PREF_UNLOCK_SECRET).apply()
        } catch (_: Exception) {
            // Ignore wipe failures; biometric toggle is already cleared.
        }
    }

    private fun loadWords(): List<String> {
        return getApplication<Application>().assets.open("eff_large_wordlist.txt").bufferedReader().useLines { lines ->
            lines.mapNotNull { line -> line.trim().split(Regex("\\s+")).lastOrNull()?.takeIf { it.isNotEmpty() } }
                .toList()
        }
    }

    private data class Made(val text: String, val bits: Double, val note: String)

    companion object {
        private const val PREF_APP_LOCK = "app_lock"
        private const val PREF_BIOMETRIC = "biometric_unlock"
        private const val PREF_UNLOCK_SECRET = "unlock_secret"
    }
}

private fun ByteArray.startsWithMagic(magic: String): Boolean {
    val bytes = magic.toByteArray(Charsets.US_ASCII)
    if (size < bytes.size) return false
    return bytes.indices.all { this[it] == bytes[it] }
}
