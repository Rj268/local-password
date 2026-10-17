package app.localpassword

import android.content.Intent
import android.content.ComponentName
import android.os.ParcelFileDescriptor
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class SecurityDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private fun requireIsolatedInstall() {
        check(context.packageName == "app.localpassword.reviewtest") {
            "Device tests require the isolated reviewtest installation; never seed a real vault."
        }
    }
    private fun shell(command: String): String =
        ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand(command))
            .bufferedReader().use { it.readText().trim() }

    @Test fun encryptionRequiresFreshBiometricAuthorization() {
        requireIsolatedInstall()
        val store = BiometricSecretStore(context)
        try {
            val cipher = store.encryptionCipher()
            val failed = runCatching { store.save(cipher, "synthetic-test-secret") }.isFailure
            assertTrue("Unapproved encryption must fail", failed)
            assertFalse(store.isEnrolled())
        } finally { store.clear() }
    }

    @Test fun unfinishedWriteRetainsPreviousVault() {
        requireIsolatedInstall()
        val original = "synthetic-original-vault".toByteArray()
        VaultFileStore.write(context, original)
        val file = android.util.AtomicFile(VaultFileStore.file(context))
        file.startWrite().use { it.write("incomplete-replacement".toByteArray()) }
        assertArrayEquals(original, VaultFileStore.read(context))
    }

    @Test fun fillsSyntheticLoginAfterVaultAuthentication() {
        requireIsolatedInstall()
        val previous = shell("settings get secure autofill_service")
        val device = UiDevice.getInstance(instrumentation)
        val secret = "review-test-passphrase"
        val (blob, opened) = Vault.create(secret, "one two three four five six seven eight",
            listOf(SavedPassword("Fixture login", "Synthetic-Password-42!", username = "fixture@example.test")))
        opened.dek.fill(0)
        VaultFileStore.write(context, blob)
        blob.fill(0)
        try {
            shell("settings put secure autofill_service ${context.packageName}/app.localpassword.PasswordAutofillService")
            shell("am start -W -n ${instrumentation.context.packageName}/${AutofillFixtureActivity::class.java.name}")
            assertTrue(device.wait(Until.hasObject(By.text("Request Autofill")), 15000))
            device.findObject(By.text("Request Autofill")).click()
            assertTrue("Autofill suggestion", device.wait(Until.hasObject(By.text("Unlock Local Password")), 15000))
            device.findObject(By.text("Unlock Local Password")).click()
            assertTrue("Authentication activity", device.wait(Until.hasObject(By.text("Unlock and choose login")), 15000))
            device.findObject(By.clazz("android.widget.EditText")).text = secret
            device.findObject(By.text("Unlock and choose login")).click()
            assertTrue("Account chooser", device.wait(Until.hasObject(By.text("Fixture login")), 20000))
            device.findObject(By.text("Fixture login")).click()
            assertTrue("Username filled", device.wait(Until.hasObject(By.text("fixture@example.test")), 15000))
            assertTrue("Password filled", device.wait(Until.hasObject(By.text("Synthetic-Password-42!")), 15000))
        } finally {
            if (previous == "null" || previous.isBlank()) shell("settings delete secure autofill_service")
            else shell("settings put secure autofill_service $previous")
            device.pressHome()
        }
    }
}
