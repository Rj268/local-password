package app.localpassword

import org.bouncycastle.crypto.generators.SCrypt
import org.json.JSONArray
import org.json.JSONObject
import java.security.GeneralSecurityException
import java.security.SecureRandom
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit
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

data class PasswordRevision(
    val password: String,
    val replacedAt: String = "",
)

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
    val lastUsed: String = "",
    val history: List<PasswordRevision> = emptyList(),
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

data class PasswordHealth(
    val weakCount: Int,
    val reuseCount: Int,
    val staleCount: Int,
    val attentionCount: Int,
)

object Vault {
    const val MIN_PASSPHRASE_LENGTH = 8
    const val RECOVERY_WORD_COUNT = 8
    const val MAX_PASSWORD_HISTORY = 5
    const val STALE_PASSWORD_DAYS = 180
    const val SAVED_SORT_NAME = "name"
    const val SAVED_SORT_RECENT = "recent"
    const val SAVED_SORT_CHANGED = "changed"
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
        return mergeEntries(local, incoming, conflictSuffix = " (other device)")
    }

    fun mergeEntries(
        local: List<SavedPassword>,
        incoming: List<SavedPassword>,
        conflictSuffix: String = " (imported)",
    ): Pair<List<SavedPassword>, Int> {
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
            val name = uniqueEntryName(item.name, taken, conflictSuffix)
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
            lastUsed = when {
                local.lastUsed.isNotEmpty() && incoming.lastUsed.isNotEmpty() ->
                    maxOf(local.lastUsed, incoming.lastUsed)
                else -> local.lastUsed.ifEmpty { incoming.lastUsed }
            },
            history = mergeHistories(local.history, incoming.history, local.password),
            extras = extras,
        )
    }

    fun sortedSavedEntries(
        items: List<SavedPassword>,
        mode: String,
        allItems: List<SavedPassword> = items,
    ): List<SavedPassword> {
        return when (mode) {
            SAVED_SORT_RECENT -> {
                val used = items.filter { it.lastUsed.isNotEmpty() }
                    .sortedWith(compareByDescending<SavedPassword> { it.lastUsed }.thenBy { it.name.lowercase(Locale.ROOT) })
                val unused = items.filter { it.lastUsed.isEmpty() }
                    .sortedBy { it.name.lowercase(Locale.ROOT) }
                used + unused
            }
            SAVED_SORT_CHANGED -> {
                val stamped = items.filter { it.modified.isNotEmpty() }
                    .sortedWith(compareByDescending<SavedPassword> { it.modified }.thenBy { it.name.lowercase(Locale.ROOT) })
                val plain = items.filter { it.modified.isEmpty() }
                    .sortedBy { it.name.lowercase(Locale.ROOT) }
                stamped + plain
            }
            else -> items.sortedWith(
                compareBy(
                    { !entryNeedsAttention(it, allItems) },
                    { !it.favorite },
                    { it.name.lowercase(Locale.ROOT) },
                ),
            )
        }
    }

    fun touchLastUsed(items: List<SavedPassword>, item: SavedPassword, whenStamp: String = utcNow()): List<SavedPassword> {
        return items.map { entry ->
            if (entry.name == item.name) entry.copy(lastUsed = whenStamp) else entry
        }
    }

    fun stampDate(stamp: String): String {
        val text = stamp.trim()
        return if (text.length < 10) "" else text.take(10)
    }

    fun lastUsedLabel(item: SavedPassword): String {
        val day = stampDate(item.lastUsed)
        return if (day.isNotEmpty()) "Last used $day" else "Not used yet"
    }

    fun entryDatesLabel(item: SavedPassword): String {
        val bits = mutableListOf<String>()
        val created = stampDate(item.created)
        val changed = stampDate(item.modified)
        if (created.isNotEmpty()) bits.add("Created $created")
        if (changed.isNotEmpty()) bits.add("Changed $changed")
        return bits.joinToString(" · ")
    }

    fun recentlyUsedEntries(items: List<SavedPassword>, limit: Int = 5): List<SavedPassword> {
        if (limit <= 0) return emptyList()
        val used = items.filter { it.lastUsed.isNotEmpty() }
        if (used.isNotEmpty()) {
            return used
                .sortedWith(compareByDescending<SavedPassword> { it.lastUsed }.thenBy { it.name.lowercase(Locale.ROOT) })
                .take(limit)
        }
        val stamped = items.filter { it.modified.isNotEmpty() }
            .sortedWith(compareByDescending<SavedPassword> { it.modified }.thenBy { it.name.lowercase(Locale.ROOT) })
        val plain = items.filter { it.modified.isEmpty() }
            .sortedBy { it.name.lowercase(Locale.ROOT) }
        return (stamped + plain).take(limit)
    }

    fun setEntryFavorite(items: List<SavedPassword>, item: SavedPassword, favorite: Boolean): List<SavedPassword> {
        return items.map { entry ->
            if (entry.name == item.name) entry.copy(favorite = favorite) else entry
        }
    }

    fun toggleEntryFavorite(items: List<SavedPassword>, item: SavedPassword): List<SavedPassword> {
        return setEntryFavorite(items, item, !item.favorite)
    }

    fun duplicateEntry(items: List<SavedPassword>, item: SavedPassword, whenStamp: String = utcNow()): List<SavedPassword> {
        if (items.none { it.name == item.name }) {
            throw VaultException("That saved password is gone.")
        }
        val taken = items.mapIndexed { index, entry -> entry.name to index }.toMap().toMutableMap()
        val label = uniqueEntryName(item.name, taken, " (copy)")
        val fresh = SavedPassword(
            name = label,
            password = item.password,
            username = item.username,
            url = item.url,
            notes = item.notes,
            category = item.category,
            favorite = item.favorite,
            created = whenStamp,
            modified = whenStamp,
            lastUsed = "",
            history = emptyList(),
            extras = item.extras,
        )
        return listOf(fresh) + items
    }

    fun removeEntry(items: List<SavedPassword>, item: SavedPassword): List<SavedPassword> {
        if (items.none { it.name == item.name }) {
            throw VaultException("That saved password is gone.")
        }
        return items.filter { it.name != item.name }
    }

    fun restoreRemovedEntry(items: List<SavedPassword>, item: SavedPassword): List<SavedPassword> {
        val taken = items.mapIndexed { index, entry -> entry.name to index }.toMap().toMutableMap()
        val restored = if (item.name in taken) {
            item.copy(name = uniqueEntryName(item.name, taken, " (restored)"))
        } else {
            item
        }
        return listOf(restored) + items
    }

    private fun mergeHistories(
        left: List<PasswordRevision>,
        right: List<PasswordRevision>,
        currentPassword: String,
    ): List<PasswordRevision> {
        val merged = mutableListOf<PasswordRevision>()
        for (revision in left + right) {
            val secret = try {
                passwordLine(revision.password)
            } catch (_: VaultException) {
                continue
            }
            if (secret == currentPassword) continue
            if (merged.any { it.password == secret }) continue
            merged.add(PasswordRevision(secret, revision.replacedAt))
            if (merged.size >= MAX_PASSWORD_HISTORY) break
        }
        return merged
    }

    private fun uniqueEntryName(name: String, taken: Map<String, Int>, suffix: String): String {
        val limit = 80
        var room = limit - suffix.length
        val base = if (name.length + suffix.length > limit) name.take(room).trimEnd() else name
        var candidate = base + suffix
        var number = 2
        while (candidate in taken) {
            val numbered = if (suffix.endsWith(")")) {
                "${suffix.dropLast(1)} $number)"
            } else {
                "$suffix $number"
            }
            room = limit - numbered.length
            candidate = name.take(room).trimEnd() + numbered
            number += 1
        }
        return candidate
    }

    fun parsePasswordCsv(text: String): List<SavedPassword> {
        val raw = text.trimStart('\uFEFF')
        if (raw.isBlank()) throw VaultException("That CSV file is empty.")
        val rows = readCsv(raw)
        if (rows.isEmpty()) throw VaultException("That CSV file has no header row.")
        val headers = rows.first().map { it.trim().lowercase(Locale.ROOT) }
        if (headers.none { it in CSV_PASSWORD_KEYS }) {
            throw VaultException("That CSV file needs a password column.")
        }
        val now = utcNow()
        val items = mutableListOf<SavedPassword>()
        val used = linkedMapOf<String, Int>()
        var unnamed = 0
        for (cells in rows.drop(1)) {
            val row = linkedMapOf<String, String>()
            for (index in headers.indices) {
                val key = headers[index]
                if (key.isEmpty()) continue
                row[key] = cells.getOrElse(index) { "" }
            }
            val password = csvCell(row, CSV_PASSWORD_KEYS)
            if (password.isEmpty() || '\n' in password || '\r' in password) continue
            var name = csvCell(row, CSV_NAME_KEYS)
            if (name.isEmpty()) {
                val url = csvCell(row, CSV_URL_KEYS)
                unnamed += 1
                name = url.ifEmpty { "Imported $unnamed" }
            }
            val label = try {
                cleanName(name)
            } catch (_: VaultException) {
                unnamed += 1
                cleanName("Imported $unnamed")
            }
            val finalName = if (label in used) uniqueEntryName(label, used, " (imported)") else label
            used[finalName] = 0
            try {
                items.add(
                    normalizeEntry(
                        SavedPassword(
                            name = finalName,
                            password = password,
                            username = csvCell(row, CSV_USERNAME_KEYS),
                            url = csvCell(row, CSV_URL_KEYS),
                            notes = csvCell(row, CSV_NOTES_KEYS),
                            category = csvCell(row, CSV_CATEGORY_KEYS),
                            created = now,
                            modified = now,
                        ),
                    ),
                )
            } catch (_: VaultException) {
                continue
            }
        }
        if (items.isEmpty()) throw VaultException("No password rows were found in that CSV file.")
        return items
    }

    fun formatPasswordCsv(items: List<SavedPassword>): String {
        if (items.isEmpty()) throw VaultException("There are no saved passwords to export.")
        val out = StringBuilder()
        out.append(csvRow(listOf("name", "username", "password", "url", "notes", "category")))
        for (item in items) {
            out.append(
                csvRow(
                    listOf(
                        item.name,
                        item.username,
                        item.password,
                        item.url,
                        item.notes,
                        item.category,
                    ),
                ),
            )
        }
        return out.toString()
    }

    private fun csvRow(fields: List<String>): String {
        return fields.joinToString(",") { csvEscape(it) } + "\n"
    }

    private fun csvEscape(value: String): String {
        return if (value.any { it == ',' || it == '"' || it == '\n' || it == '\r' }) {
            "\"" + value.replace("\"", "\"\"") + "\""
        } else {
            value
        }
    }

    private fun csvCell(row: Map<String, String>, keys: Set<String>): String {
        for (key in keys) {
            val value = row[key]?.trim().orEmpty()
            if (value.isNotEmpty()) return value
        }
        return ""
    }

    private fun readCsv(text: String): List<List<String>> {
        val rows = mutableListOf<List<String>>()
        val field = StringBuilder()
        val row = mutableListOf<String>()
        var inQuotes = false
        var index = 0
        while (index < text.length) {
            val ch = text[index]
            when {
                inQuotes && ch == '"' -> {
                    if (index + 1 < text.length && text[index + 1] == '"') {
                        field.append('"')
                        index += 1
                    } else {
                        inQuotes = false
                    }
                }
                !inQuotes && ch == '"' -> inQuotes = true
                !inQuotes && ch == ',' -> {
                    row.add(field.toString())
                    field.clear()
                }
                !inQuotes && (ch == '\n' || ch == '\r') -> {
                    row.add(field.toString())
                    field.clear()
                    if (row.any { it.isNotEmpty() } || rows.isEmpty()) {
                        rows.add(row.toList())
                    }
                    row.clear()
                    if (ch == '\r' && index + 1 < text.length && text[index + 1] == '\n') {
                        index += 1
                    }
                }
                else -> field.append(ch)
            }
            index += 1
        }
        if (field.isNotEmpty() || row.isNotEmpty()) {
            row.add(field.toString())
            rows.add(row.toList())
        }
        return rows
    }

    private val CSV_NAME_KEYS = setOf("name", "title", "account", "entry")
    private val CSV_USERNAME_KEYS = setOf("username", "user", "login", "login_username", "email")
    private val CSV_PASSWORD_KEYS = setOf("password", "pass", "passwd", "login_password")
    private val CSV_URL_KEYS = setOf("url", "website", "web site", "login_uri", "uri", "href")
    private val CSV_NOTES_KEYS = setOf("notes", "note", "comments", "extra")
    private val CSV_CATEGORY_KEYS = setOf("category", "folder", "group", "grouping")

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

    fun entryChangedDay(item: SavedPassword): LocalDate? {
        val day = stampDate(item.modified).ifEmpty { stampDate(item.created) }
        if (day.isEmpty()) return null
        return try {
            LocalDate.parse(day)
        } catch (_: Exception) {
            null
        }
    }

    fun entryIsStale(
        item: SavedPassword,
        days: Int = STALE_PASSWORD_DAYS,
        today: LocalDate? = null,
    ): Boolean {
        val changed = entryChangedDay(item) ?: return false
        val ref = today ?: LocalDate.now(ZoneOffset.UTC)
        return ChronoUnit.DAYS.between(changed, ref) >= days
    }

    fun staleWarningFor(
        item: SavedPassword,
        days: Int = STALE_PASSWORD_DAYS,
        today: LocalDate? = null,
    ): String {
        if (!entryIsStale(item, days, today)) return ""
        val day = stampDate(item.modified).ifEmpty { stampDate(item.created) }
        return "Not changed since $day."
    }

    fun stalePasswordNames(
        items: List<SavedPassword>,
        days: Int = STALE_PASSWORD_DAYS,
        today: LocalDate? = null,
    ): List<String> =
        items.filter { entryIsStale(it, days, today) }.map { it.name }

    fun entryNeedsAttention(
        item: SavedPassword,
        items: List<SavedPassword>,
        today: LocalDate? = null,
    ): Boolean =
        Generator.isWeakPassword(item.password) ||
            reuseWarningFor(item, items).isNotEmpty() ||
            entryIsStale(item, today = today)

    fun passwordHealthSummary(items: List<SavedPassword>, today: LocalDate? = null): PasswordHealth {
        val weakCount = weakPasswordNames(items).size
        val reuseCount = reusedPasswordGroups(items).size
        val staleCount = stalePasswordNames(items, today = today).size
        val attentionCount = items.count { entryNeedsAttention(it, items, today = today) }
        return PasswordHealth(weakCount, reuseCount, staleCount, attentionCount)
    }

    fun historyAfterChange(
        oldPassword: String,
        history: List<PasswordRevision>,
        replacedAt: String = utcNow(),
    ): List<PasswordRevision> {
        val secret = passwordLine(oldPassword)
        val revisions = mutableListOf(PasswordRevision(secret, replacedAt))
        for (item in history) {
            val previous = try {
                passwordLine(item.password)
            } catch (_: VaultException) {
                continue
            }
            if (previous == secret) continue
            if (revisions.any { it.password == previous }) continue
            revisions.add(PasswordRevision(previous, item.replacedAt))
            if (revisions.size >= MAX_PASSWORD_HISTORY) break
        }
        return revisions.take(MAX_PASSWORD_HISTORY)
    }

    fun withChangedPassword(item: SavedPassword, newPassword: String): SavedPassword {
        val secret = passwordLine(newPassword)
        if (secret == item.password) return item
        return normalizeEntry(
            item.copy(
                password = secret,
                modified = utcNow(),
                history = historyAfterChange(item.password, item.history),
            ),
        )
    }

    fun replaceEntryPassword(items: List<SavedPassword>, item: SavedPassword, newPassword: String): List<SavedPassword> {
        val stamped = withChangedPassword(item, newPassword)
        return listOf(stamped) + items.filter { it.name != item.name }
    }

    fun restoreEntryPassword(items: List<SavedPassword>, item: SavedPassword, index: Int): List<SavedPassword> {
        if (index !in item.history.indices) {
            throw VaultException("That previous password is gone.")
        }
        val revision = item.history[index]
        val secret = passwordLine(revision.password)
        if (secret == item.password) {
            throw VaultException("That is already the current password.")
        }
        val stamped = withChangedPassword(item, secret).let { next ->
            next.copy(history = next.history.filter { it.password != secret })
        }
        return listOf(normalizeEntry(stamped)) + items.filter { it.name != item.name }
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
            lastUsed = item.lastUsed.trim(),
            history = item.history.mapNotNull { revision ->
                try {
                    PasswordRevision(passwordLine(revision.password), revision.replacedAt.trim())
                } catch (_: VaultException) {
                    null
                }
            }.distinctBy { it.password }.take(MAX_PASSWORD_HISTORY),
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
        if (item.lastUsed.isNotEmpty()) obj.put("last_used", item.lastUsed)
        if (item.history.isNotEmpty()) {
            val history = JSONArray()
            for (revision in item.history) {
                val row = JSONObject()
                row.put("password", revision.password)
                if (revision.replacedAt.isNotEmpty()) row.put("replaced_at", revision.replacedAt)
                history.put(row)
            }
            obj.put("history", history)
        }
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
                lastUsed = obj.optString("last_used", ""),
                history = historyFromJson(obj.optJSONArray("history")),
                extras = extras,
            ),
        )
    }

    private fun historyFromJson(array: JSONArray?): List<PasswordRevision> {
        if (array == null) return emptyList()
        val revisions = mutableListOf<PasswordRevision>()
        for (index in 0 until array.length()) {
            val row = array.optJSONObject(index) ?: continue
            val password = row.optString("password", "")
            if (password.isEmpty()) continue
            val secret = try {
                passwordLine(password)
            } catch (_: VaultException) {
                continue
            }
            if (revisions.any { it.password == secret }) continue
            revisions.add(PasswordRevision(secret, row.optString("replaced_at", "").trim()))
            if (revisions.size >= MAX_PASSWORD_HISTORY) break
        }
        return revisions
    }

    private val KNOWN_ENTRY_KEYS = setOf(
        "name", "password", "username", "url", "notes", "category", "favorite", "created", "modified", "history", "last_used",
    )
}

private fun ByteArray.startsWith(prefix: ByteArray): Boolean {
    if (size < prefix.size) return false
    return prefix.indices.all { this[it] == prefix[it] }
}
