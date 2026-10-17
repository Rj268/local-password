package app.localpassword

import java.time.LocalDate
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class HealthReviewTest {
    private val today = LocalDate.of(2026, 10, 16)

    @Test fun healthCountsActiveEntriesWithoutDoubleCountingFindings() {
        val items = listOf(
            SavedPassword("First", "123", modified = "2020-01-01"),
            SavedPassword("Second", "123"),
            SavedPassword("Archived", "123", archived = true),
        )
        val result = Vault.passwordHealthSummary(items, today)
        assertEquals(2, result.weakCount)
        assertEquals(1, result.reuseCount) // one group, two affected active entries
        assertEquals(1, result.staleCount)
        assertEquals(2, result.attentionCount)
    }

    @Test fun filtersIdentifyReuseAndAgeBoundaryWithoutUnknownDateWarnings() {
        val older = SavedPassword("Older", "Distinct-secret-28!", modified = today.minusDays(180).toString())
        val recent = older.copy(name = "Recent", modified = today.minusDays(179).toString())
        val unknown = older.copy(name = "Unknown", modified = "not-a-date")
        val peers = listOf(older, recent)
        assertTrue(HealthReview.REUSED.matches(older, peers, today))
        assertFalse(HealthReview.REUSED.matches(older, listOf(older), today))
        assertTrue(HealthReview.OLDER.matches(older, peers, today))
        assertFalse(HealthReview.OLDER.matches(recent, peers, today))
        assertFalse(HealthReview.OLDER.matches(unknown, peers, today))
    }

    @Test fun restoreRetainsCurrentPasswordAndDoesNotDuplicateRestoredRevision() {
        val item = SavedPassword("Login", "current", history = listOf(PasswordRevision("previous")))
        val restored = Vault.restoreEntryPassword(listOf(item), item, 0).single()
        assertEquals("previous", restored.password)
        assertEquals(listOf("current"), restored.history.map { it.password })
        assertThrows<VaultException> { Vault.restoreEntryPassword(listOf(item), item, 9) }
    }

    @Test fun notesAndHistorySurviveEncryptedBackupAndRecovery() {
        val item = SavedPassword("Login", "current", notes = "Recovery note\n第二行",
            history = listOf(PasswordRevision("previous", "2026-01-01")))
        val recovery = "one two three four five six seven eight"
        val (blob, created) = Vault.create("test passphrase", recovery, listOf(item))
        created.dek.fill(0)
        for (secret in listOf("test passphrase", recovery)) {
            val opened = Vault.open(secret, blob)
            try {
                assertEquals(item.notes, opened.items.single().notes)
                assertEquals(item.history, opened.items.single().history)
            } finally { opened.dek.fill(0) }
        }
        assertEquals(2000, Vault.cleanNotes("a".repeat(2000)).length)
        assertThrows<VaultException> { Vault.cleanNotes("a".repeat(2001)) }
    }
}
