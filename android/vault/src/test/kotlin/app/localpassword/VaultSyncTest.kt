package app.localpassword

import org.junit.jupiter.api.Assertions.assertArrayEquals
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class VaultSyncTest {
    @Test
    fun aPairingCodePullsTheVault() {
        val payload = "LPV2".toByteArray(Charsets.US_ASCII) + ByteArray(60)
        val offer = VaultSync.Offer(payload, "123456")
        offer.start()
        try {
            assertEquals("", offer.error)
            val got = VaultSync.receiveVault("12 34 56", "127.0.0.1:${offer.port}", 5_000)
            assertArrayEquals(payload, got)
            assertTrue(offer.sent)
        } finally {
            offer.stop()
        }
    }

    @Test
    fun aWrongCodeIsRefused() {
        val payload = "LPV2".toByteArray(Charsets.US_ASCII) + ByteArray(60)
        val offer = VaultSync.Offer(payload, "123456")
        offer.start()
        try {
            val error = assertThrows<VaultException> {
                VaultSync.receiveVault("000000", "127.0.0.1:${offer.port}", 5_000)
            }
            assertEquals("That pairing code was refused.", error.message)
            assertFalse(offer.sent)
        } finally {
            offer.stop()
        }
    }

    @Test
    fun theSameVaultMergesAndADifferentVaultDoesNot() {
        val blob = javaClass.getResourceAsStream("/computer.vault")!!.readBytes()
        val opened = Vault.open("correct horse", blob)
        val resealed = Vault.seal(opened, opened.items + SavedPassword("Mail", "second"))
        val read = Vault.itemsFromSameVault(resealed, opened)
        assertEquals(listOf("Email", "Router", "Mail"), read?.map { it.name })
        val (other, _) = Vault.create(
            "another-secret",
            "alpha bravo charlie delta echo foxtrot golf hotel",
            listOf(SavedPassword("Bank", "horse")),
        )
        assertNull(Vault.itemsFromSameVault(other, opened))
    }

    @Test
    fun aDifferentPasswordForTheSameNameIsKeptBesideIt() {
        val local = listOf(SavedPassword("Email", "alpha"), SavedPassword("Bank", "one"))
        val incoming = listOf(
            SavedPassword("Email", "alpha"),
            SavedPassword("Bank", "two"),
            SavedPassword("Mail", "three"),
        )
        val (merged, splits) = Vault.mergeSaved(local, incoming)
        assertEquals(1, splits)
        assertEquals(listOf("Email", "Bank", "Bank (other device)", "Mail"), merged.map { it.name })
        assertEquals("two", merged[2].password)
    }
}
