package app.localpassword

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class VaultTest {
    @Test
    fun opensAVaultWrittenByTheComputerApp() {
        val blob = javaClass.getResourceAsStream("/computer.vault")!!.readBytes()
        val opened = Vault.open("correct horse", blob)
        assertEquals("Email", opened.items[0].name)
        assertEquals("a\"b\\c", opened.items[0].password)
        assertEquals("Router", opened.items[1].name)
        val byRecovery = Vault.open("ONE   two three four five six seven EIGHT", blob)
        assertEquals(opened.items, byRecovery.items)
    }

    @Test
    fun aWrongPassphraseDoesNotUnlock() {
        val blob = javaClass.getResourceAsStream("/computer.vault")!!.readBytes()
        assertThrows<VaultException> {
            Vault.open("not-the-passphrase", blob)
        }
    }

    @Test
    fun aVaultWrittenHereOpensAgain() {
        val recovery = "alpha bravo charlie delta echo foxtrot golf hotel"
        val (blob, opened) = Vault.create(
            "correct horse",
            recovery,
            listOf(SavedPassword("Bank", "horse-battery")),
        )
        assertEquals("LPV2", blob.copyOfRange(0, 4).toString(Charsets.US_ASCII))
        val again = Vault.open(recovery, blob)
        assertEquals(opened.items, again.items)
        val resealed = Vault.seal(again, again.items + SavedPassword("Mail", "second"))
        assertEquals(2, Vault.open("correct horse", resealed).items.size)
    }

    @Test
    fun reusedPasswordGroupsAndBrowseableUrl() {
        val items = listOf(
            SavedPassword("Email", "shared"),
            SavedPassword("Bank", "shared"),
            SavedPassword("Unique", "solo"),
        )
        val groups = Vault.reusedPasswordGroups(items)
        assertEquals(setOf("shared"), groups.keys)
        assertEquals(listOf("Email", "Bank"), groups["shared"])
        assertEquals("Same password as Bank.", Vault.reuseWarningFor(items[0], items))
        assertEquals("", Vault.reuseWarningFor(items[2], items))
        assertEquals("https://mail.example", Vault.browseableUrl("mail.example"))
        assertEquals("https://mail.example", Vault.browseableUrl("https://mail.example"))
        assertEquals("https://localhost:8080", Vault.browseableUrl("localhost:8080"))
        assertEquals(null, Vault.browseableUrl("javascript:alert(1)"))
        assertEquals(null, Vault.browseableUrl("file:///tmp/x"))
    }

    @Test
    fun weakPasswordHealthAndNeedsAttention() {
        val weak = SavedPassword("Old", "abc123")
        val strong = SavedPassword("Bank", "correct-horse-battery-staple-extra")
        val reusedA = SavedPassword("Email", "shared-secret-value")
        val reusedB = SavedPassword("Shop", "shared-secret-value")
        val items = listOf(weak, strong, reusedA, reusedB)
        assert(Generator.isWeakPassword(weak.password))
        assert(!Generator.isWeakPassword(strong.password))
        assertEquals(listOf("Old"), Vault.weakPasswordNames(items))
        assert(Vault.strengthWarningFor(weak).startsWith("Very weak") || Vault.strengthWarningFor(weak).startsWith("Weak") || Vault.strengthWarningFor(weak).startsWith("Fair"))
        assertEquals("", Vault.strengthWarningFor(strong))
        assert(Vault.entryNeedsAttention(weak, items))
        assert(!Vault.entryNeedsAttention(strong, items))
        assert(Vault.entryNeedsAttention(reusedA, items))
        val (weakCount, reuseCount, attentionCount) = Vault.passwordHealthSummary(items)
        assertEquals(1, weakCount)
        assertEquals(1, reuseCount)
        assertEquals(3, attentionCount)
    }

    @Test
    fun changingPassphraseKeepsItemsAndRetiresOldSecrets() {
        val oldRecovery = "alpha bravo charlie delta echo foxtrot golf hotel"
        val (oldBlob, opened) = Vault.create(
            "old-passphrase",
            oldRecovery,
            listOf(SavedPassword("Bank", "horse-battery")),
        )
        val newRecovery = "one two three four five six seven eight"
        val (freshBlob, _) = Vault.create("new-passphrase", newRecovery, opened.items)
        assertEquals(opened.items, Vault.open("new-passphrase", freshBlob).items)
        assertEquals(opened.items, Vault.open(newRecovery, freshBlob).items)
        assertThrows<VaultException> { Vault.open("old-passphrase", freshBlob) }
        assertThrows<VaultException> { Vault.open(oldRecovery, freshBlob) }
        assertEquals(opened.items, Vault.open("old-passphrase", oldBlob).items)
    }

    @Test
    fun sixteenCharactersOfEverythingClearsTheStrongLine() {
        val pool = Generator.characterPool(digits = true, letters = true, symbols = true)
        val bits = Generator.characterBits(16, pool)
        assert(Generator.isStrong(bits))
    }

    @Test
    fun optionalFieldsRoundTripAndUnknownKeysSurvive() {
        val recovery = "alpha bravo charlie delta echo foxtrot golf hotel"
        val rich = SavedPassword(
            name = "Email",
            password = "secret",
            username = "me@example.com",
            url = "https://mail.example",
            notes = "work account",
            category = "Mail",
            favorite = true,
            created = "2020-01-01T00:00:00Z",
            modified = "2020-02-01T00:00:00Z",
            extras = mapOf("label_color" to "green", "priority" to 2),
        )
        val (blob, _) = Vault.create("correct horse", recovery, listOf(rich))
        val opened = Vault.open("correct horse", blob)
        assertEquals(rich, opened.items[0])
        val resealed = Vault.seal(opened, opened.items)
        assertEquals(rich, Vault.open(recovery, resealed).items[0])
    }

    @Test
    fun matchingPasswordsFillEmptyOptionalFields() {
        val local = listOf(SavedPassword("Email", "alpha", username = "me"))
        val incoming = listOf(
            SavedPassword(
                "Email",
                "alpha",
                url = "https://mail.example",
                favorite = true,
                extras = mapOf("custom" to "keep"),
            ),
        )
        val (merged, splits) = Vault.mergeSaved(local, incoming)
        assertEquals(0, splits)
        assertEquals("me", merged[0].username)
        assertEquals("https://mail.example", merged[0].url)
        assertEquals(true, merged[0].favorite)
        assertEquals("keep", merged[0].extras["custom"])
    }
}
