package app.localpassword

import android.app.Application
import android.content.ClipData
import android.content.ClipboardManager
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

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
    var saved by mutableStateOf<List<SavedPassword>>(emptyList())
    var revealed by mutableStateOf<String?>(null)
    var askNewPassphrase by mutableStateOf(false)
    var askUnlock by mutableStateOf(false)
    var recoveryKey by mutableStateOf<String?>(null)
    var error by mutableStateOf("")
    var dark by mutableStateOf(loadDark())

    private var opened: OpenVault? = null
    private val words: List<String> by lazy { loadWords() }

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
        status = "Copied."
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
                val item = SavedPassword(Vault.cleanName(name), current)
                val recovery = Generator.recoveryKey(words)
                val (blob, fresh) = withContext(Dispatchers.Default) {
                    Vault.create(passphrase, recovery, listOf(item))
                }
                writeAtomically(blob)
                opened = fresh
                saved = fresh.items
                unlocked = true
                askNewPassphrase = false
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
                askUnlock = false
                status = "Unlocked."
                if (thenSave) persist(fresh)
            } catch (exc: VaultException) {
                error = exc.message ?: "That passphrase or recovery key did not unlock the saved passwords."
            } finally {
                busy = false
            }
        }
    }

    fun remove(item: SavedPassword) {
        val currentOpen = opened ?: return
        replace(currentOpen, currentOpen.items.filter { it.name != item.name }, "Removed.")
        if (revealed == item.name) revealed = null
    }

    fun import(bytes: ByteArray) {
        if (bytes.size < 48 || (!bytes.startsWithMagic("LPV2") && !bytes.startsWithMagic("LPV1"))) {
            error = "That file is not a Local Password vault."
            return
        }
        writeAtomically(bytes)
        opened = null
        unlocked = false
        saved = emptyList()
        revealed = null
        section = "saved"
        askUnlock = true
        status = "Vault copied onto this phone. The same passphrase opens it."
        error = ""
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
        val item = SavedPassword(Vault.cleanName(name), current)
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

    private fun loadDark(): Boolean {
        return getApplication<Application>().getSharedPreferences("local-password", 0)
            .getString("appearance", "light") == "dark"
    }

    private fun loadWords(): List<String> {
        return getApplication<Application>().assets.open("eff_large_wordlist.txt").bufferedReader().useLines { lines ->
            lines.mapNotNull { line -> line.trim().split(Regex("\\s+")).lastOrNull()?.takeIf { it.isNotEmpty() } }
                .toList()
        }
    }

    private data class Made(val text: String, val bits: Double, val note: String)
}

private fun ByteArray.startsWithMagic(magic: String): Boolean {
    val bytes = magic.toByteArray(Charsets.US_ASCII)
    if (size < bytes.size) return false
    return bytes.indices.all { this[it] == bytes[it] }
}
