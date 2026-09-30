package app.localpassword

import org.bouncycastle.crypto.generators.SCrypt
import org.json.JSONArray
import org.json.JSONObject
import java.security.GeneralSecurityException
import java.security.SecureRandom
import java.time.Instant
import java.util.Locale
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec
import kotlin.math.roundToInt

/**
 * The same saved.vault file the computer app writes.
 * LPV2 is AES-GCM with a scrypt-wrapped key. The passphrase is not stored.
 */
class VaultException(message: String) : Exception(message)

data class SavedPassword(
    val name: String,
    val password: String,
    val username: String = "",
    val url: String = "",
    val notes: String = "",
    val category: String = "",
    val favorite: Boolean = false,
    val created: String = "",
    val modified: String = "",
    val extras: Map<String, Any?> = emptyMap(),
)

data class OpenVault(
    val items: List<SavedPassword>,
    val dek: ByteArray,
    val n: Int,
    val r: Int,
    val p: Int,
    val passphraseSalt: ByteArray,
    val recoverySalt: ByteArray,
    val passphraseWrap: ByteArray,
    val recoveryWrap: ByteArray,
)

object Vault {
    const val MIN_PASSPHRASE_LENGTH = 8
    const val RECOVERY_WORD_COUNT = 8
    const val SCRYPT_N = 1 shl 15
    const val SCRYPT_R = 8
    const val SCRYPT_P = 1
    private const val WRAP_LEN = 60
    private val MAGIC_V1 = "LPV1".toByteArray(Charsets.US_ASCII)
    private val MAGIC_V2 = "LPV2".toByteArray(Charsets.US_ASCII)
    private val random = SecureRandom()

    fun requirePassphrase(passphrase: String): String {
        if (passphrase.length < MIN_PASSPHRASE_LENGTH) {
            throw VaultException("Use at least $MIN_PASSPHRASE_LENGTH characters for the passphrase.")
        }
        return passphrase
    }

    fun normalizeRecoveryKey(recoveryKey: String): String {
        return recoveryKey.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
            .joinToString(" ") { it.lowercase(Locale.ROOT) }
    }

    fun create(passphrase: String, recoveryKey: String, items: List<SavedPassword>): Pair<ByteArray, OpenVault> {
        requirePassphrase(passphrase)
        val normalized = requireRecoveryKey(recoveryKey)
        val n = SCRYPT_N
        val salt = randomBytes(16)
        val recoverySalt = randomBytes(16)
        val header = headerV2(n, SCRYPT_R, SCRYPT_P, salt, recoverySalt)
        val dek = randomBytes(32)
        val passphraseWrap = wrap(derive(passphrase, salt, n, SCRYPT_R, SCRYPT_P), dek, header)
        val recoveryWrap = wrap(derive(normalized, recoverySalt, n, SCRYPT_R, SCRYPT_P), dek, header)
        val opened = OpenVault(items, dek, n, SCRYPT_R, SCRYPT_P, salt, recoverySalt, passphraseWrap, recoveryWrap)
        return seal(opened, items) to opened.copy(items = items)
    }

    fun open(secret: String, blob: ByteArray): OpenVault {
        if (secret.length < MIN_PASSPHRASE_LENGTH) {
            throw VaultException("That passphrase or recovery key did not unlock the saved passwords.")
        }
        if (blob.startsWith(MAGIC_V2)) {
            return openV2(secret, blob)
        }
        if (blob.startsWith(MAGIC_V1)) {
            return openV1(secret, blob)
        }
        throw VaultException("The saved password file is damaged.")
    }

    fun itemsFromSameVault(blob: ByteArray, opened: OpenVault): List<SavedPassword>? {
        if (opened.recoveryWrap.isEmpty() || !blob.startsWith(MAGIC_V2)) return null
        val header = headerV2(opened.n, opened.r, opened.p, opened.passphraseSalt, opened.recoverySalt)
        val prefix = header + opened.passphraseWrap + opened.recoveryWrap
        if (blob.size < prefix.size + 12 + 16 || !blob.startsWith(prefix)) return null
        val nonce = blob.copyOfRange(prefix.size, prefix.size + 12)
        val ciphertext = blob.copyOfRange(prefix.size + 12, blob.size)
        return try {
            decodeSaved(decrypt(opened.dek, nonce, ciphertext, prefix))
        } catch (_: VaultException) {
            null
        }
    }

    fun mergeSaved(local: List<SavedPassword>, incoming: List<SavedPassword>): Pair<List<SavedPassword>, Int> {
        val merged = mutableListOf<SavedPassword>()
        val taken = mutableMapOf<String, Int>()
        var splits = 0
        for (item in local) {
            taken[item.name] = merged.size
            merged.add(item)
        }
        for (item in incoming) {
            val slot = taken[item.name]
            if (slot == null) {
                taken[item.name] = merged.size
                merged.add(item)
                continue
            }
            if (merged[slot].password == item.password) {
                merged[slot] = mergeMatching(merged[slot], item)
                continue
            }
            splits += 1
            val name = otherDeviceName(item.name, taken)
            taken[name] = merged.size
            merged.add(item.copy(name = name))
        }
        return merged to splits
    }

    private fun mergeMatching(local: SavedPassword, incoming: SavedPassword): SavedPassword {
        val extras = local.extras.toMutableMap()
        for ((key, value) in incoming.extras) {
            extras.putIfAbsent(key, value)
        }
        val modified = when {
            local.modified.isNotEmpty() && incoming.modified.isNotEmpty() ->
                maxOf(local.modified, incoming.modified)
            else -> local.modified.ifEmpty { incoming.modified }
        }
        return local.copy(
            username = local.username.ifBlank { incoming.username },
            url = local.url.ifBlank { incoming.url },
            notes = local.notes.ifBlank { incoming.notes },
            category = local.category.ifBlank { incoming.category },
            favorite = local.favorite || incoming.favorite,
            created = local.created.ifEmpty { incoming.created },
            modified = modified,
            extras = extras,
        )
    }

    private fun otherDeviceName(name: String, taken: Map<String, Int>): String {
        val suffix = " (other device)"
        val limit = 80
        var room = limit - suffix.length
        val base = if (name.length + suffix.length > limit) name.take(room).trimEnd() else name
        var candidate = base + suffix
        var number = 2
        while (candidate in taken) {
            val extra = " $number"
            room = limit - suffix.length - extra.length
            candidate = name.take(room).trimEnd() + suffix + extra
            number += 1
        }
        return candidate
    }

    fun seal(opened: OpenVault, items: List<SavedPassword>): ByteArray {
        val checked = items.map { normalizeEntry(it) }
        if (opened.recoveryWrap.isNotEmpty()) {
            val header = headerV2(opened.n, opened.r, opened.p, opened.passphraseSalt, opened.recoverySalt)
            val associated = header + opened.passphraseWrap + opened.recoveryWrap
            val (nonce, ciphertext) = encrypt(opened.dek, encodeSaved(checked), associated)
            return header + opened.passphraseWrap + opened.recoveryWrap + nonce + ciphertext
        }
        val header = headerV1(opened.n, opened.r, opened.p, opened.passphraseSalt)
        val (nonce, ciphertext) = encrypt(opened.dek, encodeSaved(checked), header)
        return header + nonce + ciphertext
    }

    fun utcNow(): String = Instant.now().truncatedTo(java.time.temporal.ChronoUnit.SECONDS).toString()

    fun reusedPasswordGroups(items: List<SavedPassword>): Map<String, List<String>> {
        val groups = linkedMapOf<String, MutableList<String>>()
        for (item in items) {
            groups.getOrPut(item.password) { mutableListOf() }.add(item.name)
        }
        return groups.filterValues { it.size > 1 }
    }

    fun reuseWarningFor(item: SavedPassword, items: List<SavedPassword>): String {
        val names = reusedPasswordGroups(items)[item.password] ?: return ""
        val others = names.filter { it != item.name }
        return when {
            others.isEmpty() -> ""
            others.size == 1 -> "Same password as ${others[0]}."
            others.size == 2 -> "Same password as ${others[0]} and ${others[1]}."
            else -> "Same password as ${others.size} other saved entries."
        }
    }

    fun browseableUrl(url: String): String? {
        val text = url.trim()
        if (text.isEmpty()) return null
        val lowered = text.lowercase(Locale.ROOT)
        if (lowered.startsWith("https://") || lowered.startsWith("http://")) return text
        // Reject other schemes (javascript:, file:, data:). Allow host:port.
        if (Regex("^[a-z][a-z0-9+.-]*:(?!\\d)").containsMatchIn(lowered)) return null
        return "https://$text"
    }

    fun strengthWarningFor(item: SavedPassword): String {
        if (!Generator.isWeakPassword(item.password)) return ""
        val bits = Generator.passwordStrengthBits(item.password)
        val tier = Generator.strengthTier(bits)
        return "$tier password (about ${bits.roundToInt()} bits)."
    }

    fun weakPasswordNames(items: List<SavedPassword>): List<String> =
        items.filter { Generator.isWeakPassword(it.password) }.map { it.name }

    fun entryNeedsAttention(item: SavedPassword, items: List<SavedPassword>): Boolean =
        Generator.isWeakPassword(item.password) || reuseWarningFor(item, items).isNotEmpty()

    fun passwordHealthSummary(items: List<SavedPassword>): Triple<Int, Int, Int> {
        val weakCount = weakPasswordNames(items).size
        val reuseCount = reusedPasswordGroups(items).size
        val attentionCount = items.count { entryNeedsAttention(it, items) }
        return Triple(weakCount, reuseCount, attentionCount)
    }

    fun normalizeEntry(item: SavedPassword): SavedPassword {
        return item.copy(
            name = cleanName(item.name),
            password = passwordLine(item.password),
            username = cleanUsername(item.username),
            url = cleanUrl(item.url),
            notes = cleanNotes(item.notes),
            category = cleanCategory(item.category),
            created = item.created.trim(),
            modified = item.modified.trim(),
            extras = item.extras.filterKeys { it !in KNOWN_ENTRY_KEYS },
        )
    }

    fun cleanUsername(value: String): String {
        val text = value.trim()
        if (text.length > 200) throw VaultException("The username must be 200 characters or fewer.")
        return text
    }

    fun cleanUrl(value: String): String {
        val text = value.trim()
        if (text.length > 500) throw VaultException("The URL must be 500 characters or fewer.")
        return text
    }

    fun cleanNotes(value: String): String {
        val text = value.replace("\r\n", "\n").replace("\r", "\n").trim()
        if (text.length > 2000) throw VaultException("Notes must be 2000 characters or fewer.")
        return text
    }

    fun cleanCategory(value: String): String {
        val text = value.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")
        if (text.length > 40) throw VaultException("The category must be 40 characters or fewer.")
        return text
    }

    private fun openV2(secret: String, blob: ByteArray): OpenVault {
        val fixed = 48 + WRAP_LEN + WRAP_LEN + 12
        if (blob.size < fixed + 16) {
            throw VaultException("The saved password file is damaged.")
        }
        val n = intBe(blob, 4)
        val r = intBe(blob, 8)
        val p = intBe(blob, 12)
        val passphraseSalt = blob.copyOfRange(16, 32)
        val recoverySalt = blob.copyOfRange(32, 48)
        val passphraseWrap = blob.copyOfRange(48, 48 + WRAP_LEN)
        val recoveryWrap = blob.copyOfRange(48 + WRAP_LEN, 48 + WRAP_LEN + WRAP_LEN)
        val nonce = blob.copyOfRange(48 + WRAP_LEN * 2, 48 + WRAP_LEN * 2 + 12)
        val ciphertext = blob.copyOfRange(48 + WRAP_LEN * 2 + 12, blob.size)
        val header = blob.copyOfRange(0, 48)
        val associated = header + passphraseWrap + recoveryWrap
        val dek = unlockDek(secret, passphraseSalt, passphraseWrap, n, r, p, header)
            ?: unlockDek(normalizeRecoveryKey(secret), recoverySalt, recoveryWrap, n, r, p, header)
            ?: throw VaultException("That passphrase or recovery key did not unlock the saved passwords.")
        val raw = try {
            decrypt(dek, nonce, ciphertext, associated)
        } catch (exc: VaultException) {
            throw VaultException("The saved password file is damaged.")
        }
        return OpenVault(
            decodeSaved(raw),
            dek,
            n,
            r,
            p,
            passphraseSalt,
            recoverySalt,
            passphraseWrap,
            recoveryWrap,
        )
    }

    private fun openV1(passphrase: String, blob: ByteArray): OpenVault {
        if (blob.size < 44 + 16) {
            throw VaultException("The saved password file is damaged.")
        }
        val n = intBe(blob, 4)
        val r = intBe(blob, 8)
        val p = intBe(blob, 12)
        val salt = blob.copyOfRange(16, 32)
        val nonce = blob.copyOfRange(32, 44)
        val ciphertext = blob.copyOfRange(44, blob.size)
        val header = blob.copyOfRange(0, 32)
        val dek = try {
            val key = derive(passphrase, salt, n, r, p)
            decrypt(key, nonce, ciphertext, header)
            key
        } catch (exc: VaultException) {
            throw VaultException("That passphrase did not unlock the saved passwords.")
        }
        val raw = decrypt(dek, nonce, ciphertext, header)
        return OpenVault(decodeSaved(raw), dek, n, r, p, salt, ByteArray(0), ByteArray(0), ByteArray(0))
    }

    private fun unlockDek(
        secret: String,
        salt: ByteArray,
        wrapped: ByteArray,
        n: Int,
        r: Int,
        p: Int,
        header: ByteArray,
    ): ByteArray? {
        return try {
            val kek = derive(secret, salt, n, r, p)
            unwrap(kek, wrapped, header)
        } catch (_: VaultException) {
            null
        }
    }

    private fun derive(secret: String, salt: ByteArray, n: Int, r: Int, p: Int): ByteArray {
        if (r != SCRYPT_R || p != SCRYPT_P || n < (1 shl 14) || n > (1 shl 16) || n and (n - 1) != 0) {
            throw VaultException("The saved password file is damaged.")
        }
        return SCrypt.generate(secret.toByteArray(Charsets.UTF_8), salt, n, r, p, 32)
    }

    private fun wrap(kek: ByteArray, dek: ByteArray, header: ByteArray): ByteArray {
        val (nonce, ciphertext) = encrypt(kek, dek, header)
        return nonce + ciphertext
    }

    private fun unwrap(kek: ByteArray, wrapped: ByteArray, header: ByteArray): ByteArray {
        if (wrapped.size != WRAP_LEN) {
            throw VaultException("The saved password file is damaged.")
        }
        return decrypt(kek, wrapped.copyOfRange(0, 12), wrapped.copyOfRange(12, wrapped.size), header)
    }

    private fun encrypt(key: ByteArray, plain: ByteArray, aad: ByteArray): Pair<ByteArray, ByteArray> {
        val nonce = randomBytes(12)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
        cipher.updateAAD(aad)
        return nonce to cipher.doFinal(plain)
    }

    private fun decrypt(key: ByteArray, nonce: ByteArray, ciphertext: ByteArray, aad: ByteArray): ByteArray {
        try {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
            cipher.updateAAD(aad)
            return cipher.doFinal(ciphertext)
        } catch (exc: GeneralSecurityException) {
            throw VaultException("That passphrase or recovery key did not unlock the saved passwords.")
        }
    }

    private fun headerV2(n: Int, r: Int, p: Int, passphraseSalt: ByteArray, recoverySalt: ByteArray): ByteArray {
        return MAGIC_V2 + intBytes(n) + intBytes(r) + intBytes(p) + passphraseSalt + recoverySalt
    }

    private fun headerV1(n: Int, r: Int, p: Int, salt: ByteArray): ByteArray {
        return MAGIC_V1 + intBytes(n) + intBytes(r) + intBytes(p) + salt
    }

    private fun randomBytes(size: Int): ByteArray = ByteArray(size).also { random.nextBytes(it) }

    private fun intBe(blob: ByteArray, offset: Int): Int {
        return ((blob[offset].toInt() and 0xff) shl 24) or
            ((blob[offset + 1].toInt() and 0xff) shl 16) or
            ((blob[offset + 2].toInt() and 0xff) shl 8) or
            (blob[offset + 3].toInt() and 0xff)
    }

    private fun intBytes(value: Int): ByteArray {
        return byteArrayOf(
            (value ushr 24).toByte(),
            (value ushr 16).toByte(),
            (value ushr 8).toByte(),
            value.toByte(),
        )
    }

    private fun requireRecoveryKey(recoveryKey: String): String {
        val normalized = normalizeRecoveryKey(recoveryKey)
        if (normalized.split(" ").size != RECOVERY_WORD_COUNT) {
            throw VaultException("The recovery key is not complete.")
        }
        return normalized
    }

    fun cleanName(name: String): String {
        if ('\n' in name || '\r' in name) {
            throw VaultException("The name must be a single line.")
        }
        val cleaned = name.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")
        if (cleaned.isEmpty()) {
            throw VaultException("Name this password so you can recognize it later.")
        }
        if (cleaned.length > 80) {
            throw VaultException("The name must be 80 characters or fewer.")
        }
        return cleaned
    }

    private fun passwordLine(password: String): String {
        if (password.isEmpty() || '\n' in password || '\r' in password) {
            throw VaultException("A saved password must be a single line.")
        }
        return password
    }

    private fun encodeSaved(items: List<SavedPassword>): ByteArray {
        val array = JSONArray()
        for (item in items) {
            array.put(entryToJson(item))
        }
        return array.toString().toByteArray(Charsets.UTF_8)
    }

    private fun entryToJson(item: SavedPassword): JSONObject {
        val obj = JSONObject()
        obj.put("name", cleanName(item.name))
        obj.put("password", passwordLine(item.password))
        if (item.username.isNotEmpty()) obj.put("username", cleanUsername(item.username))
        if (item.url.isNotEmpty()) obj.put("url", cleanUrl(item.url))
        if (item.notes.isNotEmpty()) obj.put("notes", cleanNotes(item.notes))
        if (item.category.isNotEmpty()) obj.put("category", cleanCategory(item.category))
        if (item.favorite) obj.put("favorite", true)
        if (item.created.isNotEmpty()) obj.put("created", item.created)
        if (item.modified.isNotEmpty()) obj.put("modified", item.modified)
        for ((key, value) in item.extras) {
            if (key !in KNOWN_ENTRY_KEYS) obj.put(key, value)
        }
        return obj
    }

    private fun decodeSaved(raw: ByteArray): List<SavedPassword> {
        val text = try {
            raw.toString(Charsets.UTF_8)
        } catch (_: Exception) {
            throw VaultException("The saved password file is damaged.")
        }
        return try {
            parseSaved(text)
        } catch (_: Exception) {
            throw VaultException("The saved password file is damaged.")
        }
    }

    private fun parseSaved(text: String): List<SavedPassword> {
        val array = JSONArray(text)
        val saved = mutableListOf<SavedPassword>()
        val used = mutableSetOf<String>()
        for (index in 0 until array.length()) {
            val obj = array.getJSONObject(index)
            val item = entryFromJson(obj)
            if (item.name !in used) {
                used.add(item.name)
                saved.add(item)
            }
        }
        return saved
    }

    private fun entryFromJson(obj: JSONObject): SavedPassword {
        val name = obj.optString("name", "")
        val password = obj.optString("password", "")
        if (name.isEmpty() || !obj.has("password")) {
            throw VaultException("The saved password file is damaged.")
        }
        val extras = mutableMapOf<String, Any?>()
        val keys = obj.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            if (key !in KNOWN_ENTRY_KEYS) {
                extras[key] = obj.get(key)
            }
        }
        return normalizeEntry(
            SavedPassword(
                name = name,
                password = password,
                username = obj.optString("username", ""),
                url = obj.optString("url", ""),
                notes = obj.optString("notes", ""),
                category = obj.optString("category", ""),
                favorite = obj.optBoolean("favorite", false),
                created = obj.optString("created", ""),
                modified = obj.optString("modified", ""),
                extras = extras,
            ),
        )
    }

    private val KNOWN_ENTRY_KEYS = setOf(
        "name", "password", "username", "url", "notes", "category", "favorite", "created", "modified",
    )
}

private fun ByteArray.startsWith(prefix: ByteArray): Boolean {
    if (size < prefix.size) return false
    return prefix.indices.all { this[it] == prefix[it] }
}
