package app.localpassword

import android.content.Context
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Only the Keystore-authorized Cipher returned by BiometricPrompt can unwrap this secret. */
internal class BiometricSecretStore(context: Context) {
    private val prefs = context.getSharedPreferences("biometric-bound-secret", Context.MODE_PRIVATE)
    private fun keyStore() = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    private fun key() = keyStore().getKey(ALIAS, null) as SecretKey

    fun isEnrolled(): Boolean = prefs.contains("iv") && prefs.contains("ciphertext") &&
        runCatching { keyStore().containsAlias(ALIAS) }.getOrDefault(false)

    fun encryptionCipher(): Cipher {
        clear()
        val spec = KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setKeySize(256)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setUserAuthenticationRequired(true)
            .setInvalidatedByBiometricEnrollment(true)
        if (Build.VERSION.SDK_INT >= 30) {
            spec.setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG)
        }
        // On API 26–29 the default validity duration is -1: authenticate each operation.
        KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(spec.build())
            generateKey()
        }
        return Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
    }

    fun save(cipher: Cipher, secret: String) {
        val raw = secret.toByteArray(Charsets.UTF_8)
        val encrypted = try { cipher.doFinal(raw) } finally { raw.fill(0) }
        try {
            check(prefs.edit()
                .putString("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
                .putString("ciphertext", Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .commit()) { "Could not save biometric setup." }
        } finally { encrypted.fill(0) }
    }

    fun decryptionCipher(): Cipher {
        check(isEnrolled()) { "Enable biometric unlock again." }
        val iv = Base64.decode(prefs.getString("iv", null)!!, Base64.NO_WRAP)
        return Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
        }
    }

    fun decrypt(cipher: Cipher): String {
        val encrypted = Base64.decode(prefs.getString("ciphertext", null)!!, Base64.NO_WRAP)
        val raw = try { cipher.doFinal(encrypted) } finally { encrypted.fill(0) }
        return try { raw.toString(Charsets.UTF_8) } finally { raw.fill(0) }
    }

    fun clear() {
        check(prefs.edit().clear().commit()) { "Could not clear biometric setup." }
        val store = keyStore()
        if (store.containsAlias(ALIAS)) store.deleteEntry(ALIAS)
    }

    private companion object { const val ALIAS = "local-password-biometric-per-use-v1" }
}
