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
    fun sixteenCharactersOfEverythingClearsTheStrongLine() {
        val pool = Generator.characterPool(digits = true, letters = true, symbols = true)
        val bits = Generator.characterBits(16, pool)
        assert(Generator.isStrong(bits))
    }
}
