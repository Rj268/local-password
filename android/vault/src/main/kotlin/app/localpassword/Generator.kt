package app.localpassword

import java.security.SecureRandom
import kotlin.math.log2
import kotlin.math.min
import kotlin.math.roundToInt

object Generator {
    const val STRONG_ENTROPY_BITS = 75.0
    const val VERY_WEAK_ENTROPY_BITS = 28.0
    const val WEAK_ENTROPY_BITS = 50.0
    const val VERY_STRONG_ENTROPY_BITS = 100.0
    const val METER_CAP_BITS = 256.0
    private const val PUNCTUATION = "!\"#\$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
    private const val DIGITS = "0123456789"
    private const val LOWER = "abcdefghijklmnopqrstuvwxyz"
    private const val UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    private val random = SecureRandom()

    fun characterPool(digits: Boolean, letters: Boolean, symbols: Boolean): String {
        if (!digits && !letters && !symbols) {
            throw VaultException("Choose at least one character type.")
        }
        val parts = StringBuilder()
        if (digits) parts.append("0123456789")
        if (letters) parts.append("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
        if (symbols) parts.append(PUNCTUATION)
        return parts.toString()
    }

    fun password(length: Int, pool: String): String {
        if (length < 1 || length > 1024) {
            throw VaultException("Password length must be between 1 and 1024.")
        }
        val unique = unique(pool)
        if (unique.isEmpty()) throw VaultException("Choose at least one character type.")
        val groups = groups(unique)
        val chars = ArrayList<Char>(length)
        if (length >= groups.size) {
            for (group in groups) chars.add(pick(group))
        }
        while (chars.size < length) chars.add(pick(unique))
        shuffle(chars)
        return chars.joinToString("")
    }

    fun passphrase(wordCount: Int, words: List<String>): String {
        if (wordCount < 1 || wordCount > 20) {
            throw VaultException("Word count must be between 1 and 20.")
        }
        if (words.isEmpty()) throw VaultException("The passphrase word list is empty.")
        return List(wordCount) { words[random.nextInt(words.size)] }.joinToString(" ")
    }

    fun recoveryKey(words: List<String>): String = passphrase(Vault.RECOVERY_WORD_COUNT, words)

    fun characterBits(length: Int, pool: String): Double = entropy(length, unique(pool).length)

    fun passphraseBits(wordCount: Int, wordlistSize: Int): Double = entropy(wordCount, wordlistSize)

    fun entropy(length: Int, poolSize: Int): Double {
        if (length <= 0 || poolSize <= 1) return 0.0
        return length * log2(poolSize.toDouble())
    }

    fun meterFraction(bits: Double): Float = min(bits / METER_CAP_BITS, 1.0).toFloat()

    fun bitsLabel(bits: Double): String = "about ${bits.roundToInt()} bits"

    fun isStrong(bits: Double): Boolean = bits >= STRONG_ENTROPY_BITS

    fun estimatedPoolSize(password: String): Int {
        var size = 0
        if (password.any { it in LOWER }) size += LOWER.length
        if (password.any { it in UPPER }) size += UPPER.length
        if (password.any { it in DIGITS }) size += DIGITS.length
        if (password.any { it in PUNCTUATION }) size += PUNCTUATION.length
        val extras = password.filter {
            it !in LOWER && it !in UPPER && it !in DIGITS && it !in PUNCTUATION
        }.toSet()
        return size + extras.size
    }

    fun passwordStrengthBits(password: String): Double =
        entropy(password.length, estimatedPoolSize(password))

    fun strengthTier(entropyBits: Double): String = when {
        entropyBits < VERY_WEAK_ENTROPY_BITS -> "Very weak"
        entropyBits < WEAK_ENTROPY_BITS -> "Weak"
        entropyBits < STRONG_ENTROPY_BITS -> "Fair"
        entropyBits < VERY_STRONG_ENTROPY_BITS -> "Strong"
        else -> "Very strong"
    }

    fun isWeakPassword(password: String): Boolean = !isStrong(passwordStrengthBits(password))

    private fun unique(value: String): String {
        val seen = LinkedHashSet<Char>()
        value.forEach { seen.add(it) }
        return seen.joinToString("")
    }

    private fun groups(pool: String): List<String> {
        val present = pool.toSet()
        val buckets = listOf(
            "0123456789".filter { it in present },
            "abcdefghijklmnopqrstuvwxyz".filter { it in present },
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ".filter { it in present },
            PUNCTUATION.filter { it in present },
        )
        val known = buckets.joinToString("").toSet()
        val extra = pool.filter { it !in known }
        return (buckets + extra).filter { it.isNotEmpty() }
    }

    private fun pick(pool: String): Char = pool[random.nextInt(pool.length)]

    private fun shuffle(items: MutableList<Char>) {
        for (index in items.lastIndex downTo 1) {
            val swapWith = random.nextInt(index + 1)
            val tmp = items[index]
            items[index] = items[swapWith]
            items[swapWith] = tmp
        }
    }
}
