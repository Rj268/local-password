package app.localpassword

import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit
import javax.crypto.Cipher

/** Interactive test: the owner supplies two real biometric confirmations. */
@RunWith(AndroidJUnit4::class)
class BiometricDeviceTest {
    @Test fun realBiometricAuthorizationProtectsBothOperations() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        check(context.packageName == "app.localpassword.reviewtest")
        val store = BiometricSecretStore(context)
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            fun authorize(cipher: Cipher, title: String): Cipher {
                val result = CompletableFuture<Cipher>()
                scenario.onActivity { activity ->
                    val prompt = BiometricPrompt(activity, ContextCompat.getMainExecutor(activity),
                        object : BiometricPrompt.AuthenticationCallback() {
                            override fun onAuthenticationSucceeded(auth: BiometricPrompt.AuthenticationResult) {
                                val authorized = auth.cryptoObject?.cipher
                                if (authorized == null) result.completeExceptionally(IllegalStateException("Missing cipher"))
                                else result.complete(authorized)
                            }
                            override fun onAuthenticationError(code: Int, message: CharSequence) {
                                result.completeExceptionally(IllegalStateException("Biometric test cancelled or unavailable: $code"))
                            }
                        })
                    prompt.authenticate(BiometricPrompt.PromptInfo.Builder()
                        .setTitle(title)
                        .setSubtitle("Dummy credentials in isolated Local Password test")
                        .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
                        .setNegativeButtonText("Cancel test")
                        .build(), BiometricPrompt.CryptoObject(cipher))
                }
                return result.get(90, TimeUnit.SECONDS)
            }
            try {
                val encrypt = authorize(store.encryptionCipher(), "Test 1 of 2: protect dummy secret")
                store.save(encrypt, "biometric-round-trip-only")
                assertTrue(store.isEnrolled())
                assertTrue("Unlock must require a new biometric operation",
                    runCatching { store.decrypt(store.decryptionCipher()) }.isFailure)
                val decrypt = authorize(store.decryptionCipher(), "Test 2 of 2: unlock dummy secret")
                assertEquals("biometric-round-trip-only", store.decrypt(decrypt))
            } finally { store.clear() }
        }
    }
}
