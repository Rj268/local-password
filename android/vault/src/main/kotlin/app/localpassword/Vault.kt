package app.localpassword

import org.bouncycastle.crypto.generators.SCrypt
import java.security.GeneralSecurityException
import java.security.SecureRandom
import java.util.Locale
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * The same saved.vault file the computer app writes.
 * LPV2 is AES-GCM with a scrypt-wrapped key. The passphrase is not stored.
 */
class VaultException(message: String) : Exception(message)

data class SavedPassword(val name: String, val password: String)

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

    fun seal(opened: OpenVault, items: List<SavedPassword>): ByteArray {
        val checked = items.map { SavedPassword(cleanName(it.name), passwordLine(it.password)) }
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
        val body = items.joinToString(prefix = "[", postfix = "]") { item ->
            "{\"name\": ${jsonString(item.name)}, \"password\": ${jsonString(item.password)}}"
        }
        return body.toByteArray(Charsets.UTF_8)
    }

    private fun jsonString(value: String): String {
        val out = StringBuilder("\"")
        for (ch in value) {
            when (ch) {
                '"' -> out.append("\\\"")
                '\\' -> out.append("\\\\")
                '\b' -> out.append("\\b")
                '\u000C' -> out.append("\\f")
                '\n' -> out.append("\\n")
                '\r' -> out.append("\\r")
                '\t' -> out.append("\\t")
                else -> if (ch.code < 0x20) out.append("\\u%04x".format(ch.code)) else out.append(ch)
            }
        }
        out.append('"')
        return out.toString()
    }

    private fun decodeSaved(raw: ByteArray): List<SavedPassword> {
        val text = try {
            raw.toString(Charsets.UTF_8)
        } catch (_: Exception) {
            throw VaultException("The saved password file is damaged.")
        }
        return try {
            parseSaved(text)
        } catch (_: VaultException) {
            throw VaultException("The saved password file is damaged.")
        }
    }

    private fun parseSaved(text: String): List<SavedPassword> {
        val cursor = JsonCursor(text)
        cursor.skip()
        cursor.expect('[')
        val saved = mutableListOf<SavedPassword>()
        val used = mutableSetOf<String>()
        cursor.skip()
        if (cursor.peek() == ']') {
            cursor.expect(']')
            cursor.skip()
            if (!cursor.done()) throw VaultException("The saved password file is damaged.")
            return saved
        }
        while (true) {
            cursor.expect('{')
            var name: String? = null
            var password: String? = null
            while (true) {
                val key = cursor.string()
                cursor.expect(':')
                val value = cursor.string()
                if (key == "name") name = value
                if (key == "password") password = value
                cursor.skip()
                if (cursor.peek() == ',') {
                    cursor.expect(',')
                    continue
                }
                break
            }
            cursor.expect('}')
            if (name == null || password == null) throw VaultException("The saved password file is damaged.")
            val item = SavedPassword(cleanName(name), passwordLine(password))
            if (item.name !in used) {
                used.add(item.name)
                saved.add(item)
            }
            cursor.skip()
            if (cursor.peek() == ',') {
                cursor.expect(',')
                cursor.skip()
                continue
            }
            break
        }
        cursor.expect(']')
        cursor.skip()
        if (!cursor.done()) throw VaultException("The saved password file is damaged.")
        return saved
    }
}

private class JsonCursor(private val text: String) {
    private var index = 0

    fun done(): Boolean {
        skip()
        return index >= text.length
    }

    fun peek(): Char {
        skip()
        if (index >= text.length) throw VaultException("The saved password file is damaged.")
        return text[index]
    }

    fun expect(char: Char) {
        if (peek() != char) throw VaultException("The saved password file is damaged.")
        index += 1
    }

    fun skip() {
        while (index < text.length && text[index].isWhitespace()) index += 1
    }

    fun string(): String {
        expect('"')
        val out = StringBuilder()
        while (index < text.length) {
            val ch = text[index]
            index += 1
            if (ch == '"') return out.toString()
            if (ch != '\\') {
                out.append(ch)
                continue
            }
            if (index >= text.length) throw VaultException("The saved password file is damaged.")
            when (val escaped = text[index]) {
                '"', '\\', '/' -> out.append(escaped)
                'b' -> out.append('\b')
                'f' -> out.append('\u000C')
                'n' -> out.append('\n')
                'r' -> out.append('\r')
                't' -> out.append('\t')
                'u' -> {
                    if (index + 4 >= text.length) throw VaultException("The saved password file is damaged.")
                    val hex = text.substring(index + 1, index + 5)
                    out.append(hex.toInt(16).toChar())
                    index += 4
                }
                else -> throw VaultException("The saved password file is damaged.")
            }
            index += 1
        }
        throw VaultException("The saved password file is damaged.")
    }
}

private fun ByteArray.startsWith(prefix: ByteArray): Boolean {
    if (size < prefix.size) return false
    return prefix.indices.all { this[it] == prefix[it] }
}
