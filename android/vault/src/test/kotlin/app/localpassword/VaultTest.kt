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
    fun optionalCopyFieldsForUrlAndNotes() {
        val bare = SavedPassword("Bare", "secret-value-here")
        assertEquals(emptyList<Pair<String, String>>(), Vault.optionalCopyFields(bare))
        val withUrl = SavedPassword("Mail", "secret-value-here", url = "  mail.example/login  ")
        assertEquals(listOf("Copy URL" to "mail.example/login"), Vault.optionalCopyFields(withUrl))
        val withNotes = SavedPassword(
            "Bank",
            "secret-value-here",
            notes = "recovery codes\nkeep private",
        )
        assertEquals(
            listOf("Copy notes" to "recovery codes\nkeep private"),
            Vault.optionalCopyFields(withNotes),
        )
        val both = SavedPassword(
            "Work",
            "secret-value-here",
            url = "https://work.example",
            notes = "  desk drawer  ",
        )
        assertEquals(
            listOf(
                "Copy URL" to "https://work.example",
                "Copy notes" to "  desk drawer  ",
            ),
            Vault.optionalCopyFields(both),
        )
        val whitespaceOnly = SavedPassword(
            "Empty",
            "secret-value-here",
            url = "   ",
            notes = "\n\t",
        )
        assertEquals(emptyList<Pair<String, String>>(), Vault.optionalCopyFields(whitespaceOnly))
    }

    @Test
    fun weakPasswordHealthAndNeedsAttention() {
        val today = java.time.LocalDate.of(2024, 12, 1)
        val recent = "2024-11-15T00:00:00Z"
        val weak = SavedPassword("Old", "abc123", modified = recent)
        val strong = SavedPassword("Bank", "correct-horse-battery-staple-extra", modified = recent)
        val reusedA = SavedPassword("Email", "shared-secret-value", modified = recent)
        val reusedB = SavedPassword("Shop", "shared-secret-value", modified = recent)
        val items = listOf(weak, strong, reusedA, reusedB)
        assert(Generator.isWeakPassword(weak.password))
        assert(!Generator.isWeakPassword(strong.password))
        assertEquals(listOf("Old"), Vault.weakPasswordNames(items))
        assert(Vault.strengthWarningFor(weak).startsWith("Very weak") || Vault.strengthWarningFor(weak).startsWith("Weak") || Vault.strengthWarningFor(weak).startsWith("Fair"))
        assertEquals("", Vault.strengthWarningFor(strong))
        assert(Vault.entryNeedsAttention(weak, items, today = today))
        assert(!Vault.entryNeedsAttention(strong, items, today = today))
        assert(Vault.entryNeedsAttention(reusedA, items, today = today))
        val health = Vault.passwordHealthSummary(items, today = today)
        assertEquals(1, health.weakCount)
        assertEquals(1, health.reuseCount)
        assertEquals(0, health.staleCount)
        assertEquals(3, health.attentionCount)
    }

    @Test
    fun stalePasswordFlagsOldUnchangedEntries() {
        val today = java.time.LocalDate.of(2024, 12, 1)
        val stale = SavedPassword(
            name = "Legacy",
            password = "correct-horse-battery-staple-extra",
            modified = "2024-01-01T00:00:00Z",
        )
        val fresh = SavedPassword(
            name = "Current",
            password = "correct-horse-battery-staple-fresh",
            modified = "2024-11-01T00:00:00Z",
        )
        val createdOnly = SavedPassword(
            name = "CreatedOnly",
            password = "correct-horse-battery-staple-created",
            created = "2023-01-01T00:00:00Z",
        )
        assert(Vault.entryIsStale(stale, today = today))
        assert(!Vault.entryIsStale(fresh, today = today))
        assert(Vault.entryIsStale(createdOnly, today = today))
        assertEquals("Not changed since 2024-01-01.", Vault.staleWarningFor(stale, today = today))
        assertEquals("", Vault.staleWarningFor(fresh, today = today))
        assertEquals(
            listOf("Legacy", "CreatedOnly"),
            Vault.stalePasswordNames(listOf(stale, fresh, createdOnly), today = today),
        )
        assert(Vault.entryNeedsAttention(stale, listOf(stale, fresh), today = today))
        assert(!Vault.entryNeedsAttention(fresh, listOf(stale, fresh), today = today))
        val health = Vault.passwordHealthSummary(listOf(stale, fresh, createdOnly), today = today)
        assertEquals(0, health.weakCount)
        assertEquals(0, health.reuseCount)
        assertEquals(2, health.staleCount)
        assertEquals(2, health.attentionCount)
    }

    @Test
    fun replaceEntryPasswordKeepsFieldsAndIsStrong() {
        val item = SavedPassword(
            name = "Old",
            password = "abc123",
            username = "me",
            url = "https://old.example",
            notes = "keep",
            category = "web",
            favorite = true,
            created = "2024-01-01T00:00:00Z",
        )
        val fresh = Generator.strongReplacementPassword()
        assert(Generator.isStrong(Generator.passwordStrengthBits(fresh)))
        val next = Vault.replaceEntryPassword(listOf(item), item, fresh)
        assertEquals(1, next.size)
        assertEquals("Old", next[0].name)
        assertEquals(fresh, next[0].password)
        assertEquals("me", next[0].username)
        assertEquals("https://old.example", next[0].url)
        assertEquals("keep", next[0].notes)
        assertEquals("web", next[0].category)
        assert(next[0].favorite)
        assertEquals("2024-01-01T00:00:00Z", next[0].created)
        assert(next[0].modified.isNotEmpty())
        assert(!Generator.isWeakPassword(next[0].password))
        assertEquals(1, next[0].history.size)
        assertEquals("abc123", next[0].history[0].password)
    }

    @Test
    fun archiveHidesFromActiveHealthAndRecent() {
        val today = java.time.LocalDate.of(2024, 12, 1)
        val recent = "2024-11-15T00:00:00Z"
        val active = SavedPassword(
            "Email",
            "correct-horse-battery-staple-extra",
            modified = recent,
            lastUsed = "2024-11-20T00:00:00Z",
        )
        val archived = SavedPassword(
            "Old",
            "abc123",
            archived = true,
            modified = "2020-01-01T00:00:00Z",
            lastUsed = "2024-11-21T00:00:00Z",
        )
        val items = listOf(active, archived)
        assertEquals(listOf("Email"), Vault.activeSavedEntries(items).map { it.name })
        val toggled = Vault.toggleEntryArchived(items, active)
        assert(toggled[0].archived)
        val restored = Vault.toggleEntryArchived(toggled, toggled[0])
        assert(!restored[0].archived)
        val health = Vault.passwordHealthSummary(items, today = today)
        assertEquals(0, health.weakCount)
        assertEquals(0, health.reuseCount)
        assertEquals(0, health.staleCount)
        assertEquals(0, health.attentionCount)
        assertEquals(listOf("Email"), Vault.recentlyUsedEntries(items).map { it.name })
    }

    @Test
    fun renameEntryChangesNameAndRefusesClash() {
        val email = SavedPassword(
            "Email",
            "secret-value-here",
            username = "me",
            notes = "keep",
            favorite = true,
            created = "2020-01-01T00:00:00Z",
            modified = "2020-02-01T00:00:00Z",
            lastUsed = "2020-03-01T00:00:00Z",
        )
        val bank = SavedPassword("Bank", "other-secret-value")
        val same = Vault.renameEntry(listOf(email, bank), email, "Email")
        assertEquals(listOf("Email", "Bank"), same.map { it.name })
        assertEquals("2020-02-01T00:00:00Z", same[0].modified)
        val updated = Vault.renameEntry(
            listOf(email, bank),
            email,
            "  Work email  ",
            whenStamp = "2024-05-01T00:00:00Z",
        )
        assertEquals(listOf("Work email", "Bank"), updated.map { it.name })
        assertEquals("me", updated[0].username)
        assertEquals("keep", updated[0].notes)
        assert(updated[0].favorite)
        assertEquals("2020-01-01T00:00:00Z", updated[0].created)
        assertEquals("2024-05-01T00:00:00Z", updated[0].modified)
        assertEquals("2020-03-01T00:00:00Z", updated[0].lastUsed)
        try {
            Vault.renameEntry(listOf(email, bank), email, "Bank")
            throw AssertionError("expected clash")
        } catch (exc: VaultException) {
            assert(exc.message!!.contains("already uses that name"))
        }
        try {
            Vault.renameEntry(listOf(bank), email, "Mailbox")
            throw AssertionError("expected missing entry")
        } catch (_: VaultException) {
        }
    }

    @Test
    fun duplicateEntryCopiesFieldsAndNamesUniquely() {
        val item = SavedPassword(
            name = "Bank",
            password = "secret-bank-value",
            username = "me",
            url = "https://bank.example",
            notes = "keep",
            category = "finance",
            favorite = true,
            created = "2024-01-01T00:00:00Z",
            modified = "2024-02-01T00:00:00Z",
            lastUsed = "2024-03-01T00:00:00Z",
            history = listOf(PasswordRevision("old-secret", "2024-01-15T00:00:00Z")),
        )
        val other = SavedPassword(name = "Email", password = "secret-email-value")
        val updated = Vault.duplicateEntry(listOf(item, other), item, whenStamp = "2024-04-01T00:00:00Z")
        assertEquals("Bank (copy)", updated[0].name)
        assertEquals("secret-bank-value", updated[0].password)
        assertEquals("me", updated[0].username)
        assertEquals("https://bank.example", updated[0].url)
        assertEquals("keep", updated[0].notes)
        assertEquals("finance", updated[0].category)
        assert(updated[0].favorite)
        assertEquals("2024-04-01T00:00:00Z", updated[0].created)
        assertEquals("2024-04-01T00:00:00Z", updated[0].modified)
        assertEquals("", updated[0].lastUsed)
        assert(updated[0].history.isEmpty())
        assertEquals("Bank", updated[1].name)
        assertEquals("2024-03-01T00:00:00Z", updated[1].lastUsed)
        assertEquals(1, updated[1].history.size)
        val again = Vault.duplicateEntry(updated, updated[1], whenStamp = "2024-04-02T00:00:00Z")
        assertEquals("Bank (copy 2)", again[0].name)
        val recovery = "alpha bravo charlie delta echo foxtrot golf hotel"
        val (blob, _) = Vault.create("passphrase-here", recovery, again)
        val loaded = Vault.open("passphrase-here", blob).items
        assertEquals(setOf("Bank", "Bank (copy)", "Bank (copy 2)", "Email"), loaded.map { it.name }.toSet())
    }

    @Test
    fun toggleEntryFavoriteKeepsTimestamps() {
        val item = SavedPassword(
            name = "Bank",
            password = "secret-bank-value",
            favorite = false,
            created = "2024-01-01T00:00:00Z",
            modified = "2024-02-01T00:00:00Z",
            lastUsed = "2024-03-01T00:00:00Z",
        )
        val other = SavedPassword(name = "Email", password = "secret-email-value", favorite = true)
        val updated = Vault.toggleEntryFavorite(listOf(item, other), item)
        assert(updated[0].favorite)
        assertEquals("2024-02-01T00:00:00Z", updated[0].modified)
        assertEquals("2024-03-01T00:00:00Z", updated[0].lastUsed)
        assertEquals("secret-bank-value", updated[0].password)
        assert(updated[1].favorite)
        val cleared = Vault.toggleEntryFavorite(updated, updated[0])
        assert(!cleared[0].favorite)
        val recovery = "alpha bravo charlie delta echo foxtrot golf hotel"
        val (blob, _) = Vault.create("passphrase-here", recovery, cleared)
        val loaded = Vault.open("passphrase-here", blob).items
        val loadedBank = loaded.first { it.name == "Bank" }
        assert(!loadedBank.favorite)
        assertEquals("2024-02-01T00:00:00Z", loadedBank.modified)
    }

    @Test
    fun lastUsedLabelAndRecentlyUsedEntries() {
        val alpha = SavedPassword(
            name = "Alpha",
            password = "secret-alpha-value",
            modified = "2024-01-02T00:00:00Z",
        )
        val beta = SavedPassword(
            name = "Beta",
            password = "secret-beta-value",
            modified = "2024-03-01T00:00:00Z",
            lastUsed = "2024-02-01T12:30:00Z",
        )
        val gamma = SavedPassword(
            name = "Gamma",
            password = "secret-gamma-value",
            modified = "2024-01-01T00:00:00Z",
            lastUsed = "2024-04-01T08:00:00Z",
        )
        assertEquals("Not used yet", Vault.lastUsedLabel(alpha))
        assertEquals("Last used 2024-02-01", Vault.lastUsedLabel(beta))
        assertEquals(
            listOf("Gamma", "Beta"),
            Vault.recentlyUsedEntries(listOf(alpha, beta, gamma), 2).map { it.name },
        )
        assertEquals(listOf("Alpha"), Vault.recentlyUsedEntries(listOf(alpha), 5).map { it.name })
    }

    @Test
    fun removeAndRestoreEntry() {
        val bank = SavedPassword(
            name = "Bank",
            password = "secret-bank-value",
            username = "me",
            notes = "keep",
            favorite = true,
            created = "2024-01-01T00:00:00Z",
            modified = "2024-02-01T00:00:00Z",
            lastUsed = "2024-03-01T00:00:00Z",
            history = listOf(PasswordRevision("old-secret", "2024-01-15T00:00:00Z")),
        )
        val email = SavedPassword(name = "Email", password = "secret-email-value")
        val removed = Vault.removeEntry(listOf(bank, email), bank)
        assertEquals(listOf("Email"), removed.map { it.name })
        val restored = Vault.restoreRemovedEntry(removed, bank)
        assertEquals("Bank", restored[0].name)
        assertEquals("secret-bank-value", restored[0].password)
        assertEquals("me", restored[0].username)
        assertEquals("keep", restored[0].notes)
        assert(restored[0].favorite)
        assertEquals("2024-03-01T00:00:00Z", restored[0].lastUsed)
        assertEquals(1, restored[0].history.size)
        val conflicted = Vault.restoreRemovedEntry(
            listOf(SavedPassword(name = "Bank", password = "other"), email),
            bank,
        )
        assertEquals("Bank (restored)", conflicted[0].name)
        assertEquals("secret-bank-value", conflicted[0].password)
        try {
            Vault.removeEntry(listOf(email), bank)
            throw AssertionError("expected VaultException")
        } catch (_: VaultException) {
        }
    }

    @Test
    fun entryDatesLabelShowsCreatedAndChanged() {
        val bare = SavedPassword(name = "Bare", password = "secret-bare-value")
        val createdOnly = SavedPassword(
            name = "Created",
            password = "secret-created-value",
            created = "2024-01-15T09:00:00Z",
        )
        val both = SavedPassword(
            name = "Both",
            password = "secret-both-value",
            created = "2024-01-15T09:00:00Z",
            modified = "2024-03-20T18:30:00Z",
        )
        assertEquals("", Vault.entryDatesLabel(bare))
        assertEquals("Created 2024-01-15", Vault.entryDatesLabel(createdOnly))
        assertEquals("Created 2024-01-15 · Changed 2024-03-20", Vault.entryDatesLabel(both))
    }

    @Test
    fun sortedSavedEntriesAndTouchLastUsed() {
        val alpha = SavedPassword(
            name = "Alpha",
            password = "secret-alpha-value",
            favorite = true,
            modified = "2024-01-02T00:00:00Z",
        )
        val beta = SavedPassword(
            name = "Beta",
            password = "secret-beta-value",
            modified = "2024-03-01T00:00:00Z",
            lastUsed = "2024-02-01T00:00:00Z",
        )
        val gamma = SavedPassword(
            name = "Gamma",
            password = "secret-gamma-value",
            modified = "2024-01-01T00:00:00Z",
            lastUsed = "2024-04-01T00:00:00Z",
        )
        val items = listOf(alpha, beta, gamma)
        assertEquals(
            listOf("Alpha", "Beta", "Gamma"),
            Vault.sortedSavedEntries(items, Vault.SAVED_SORT_NAME).map { it.name },
        )
        assertEquals(
            listOf("Gamma", "Beta", "Alpha"),
            Vault.sortedSavedEntries(items, Vault.SAVED_SORT_RECENT).map { it.name },
        )
        assertEquals(
            listOf("Beta", "Alpha", "Gamma"),
            Vault.sortedSavedEntries(items, Vault.SAVED_SORT_CHANGED).map { it.name },
        )
        val stamped = Vault.touchLastUsed(items, alpha, whenStamp = "2024-05-01T00:00:00Z")
        assertEquals("2024-05-01T00:00:00Z", stamped[0].lastUsed)
        assertEquals(alpha.modified, stamped[0].modified)
        assertEquals(alpha.password, stamped[0].password)
        val recovery = "alpha bravo charlie delta echo foxtrot golf hotel"
        val (blob, _) = Vault.create("passphrase-here", recovery, stamped)
        val loaded = Vault.open("passphrase-here", blob).items
        assertEquals("2024-05-01T00:00:00Z", loaded.first { it.name == "Alpha" }.lastUsed)
    }

    @Test
    fun passwordHistoryRestoreAndCap() {
        var items = listOf(SavedPassword("Site", "one"))
        for (secret in listOf("two", "three", "four", "five", "six", "seven")) {
            items = Vault.replaceEntryPassword(items, items[0], secret)
        }
        assertEquals("seven", items[0].password)
        assertEquals(Vault.MAX_PASSWORD_HISTORY, items[0].history.size)
        assertEquals(listOf("six", "five", "four", "three", "two"), items[0].history.map { it.password })
        val restored = Vault.restoreEntryPassword(items, items[0], 1)
        assertEquals("five", restored[0].password)
        assertEquals("seven", restored[0].history[0].password)
        assert(!restored[0].history.any { it.password == "five" })
        val recovery = "alpha bravo charlie delta echo foxtrot golf hotel"
        val (blob, _) = Vault.create("passphrase-here", recovery, restored)
        val loaded = Vault.open("passphrase-here", blob).items
        assertEquals("five", loaded[0].password)
        assertEquals(restored[0].history.map { it.password }, loaded[0].history.map { it.password })
    }

    @Test
    fun parsePasswordCsvAndMergeImported() {
        val text = """
            name,username,password,url,notes,category
            Email,me@example.com,secret-one,https://mail.example,work mail,web
            Bank,,abc123,https://bank.example,,finance
            "Quoted, Name",user,"pass,word",https://q.example,,
        """.trimIndent()
        val items = Vault.parsePasswordCsv(text)
        assertEquals(3, items.size)
        assertEquals("Email", items[0].name)
        assertEquals("me@example.com", items[0].username)
        assertEquals("secret-one", items[0].password)
        assertEquals("Quoted, Name", items[2].name)
        assertEquals("pass,word", items[2].password)
        val local = listOf(SavedPassword("Email", "different-secret"))
        val (merged, splits) = Vault.mergeEntries(local, items, conflictSuffix = " (imported)")
        assertEquals(1, splits)
        val names = merged.map { it.name }.toSet()
        assertEquals(setOf("Email", "Email (imported)", "Bank", "Quoted, Name"), names)
        assertThrows<VaultException> { Vault.parsePasswordCsv("title,login\nA,B\n") }
    }

    @Test
    fun formatPasswordCsvRoundTrips() {
        val items = listOf(
            SavedPassword(
                name = "Email",
                password = "secret-one",
                username = "me@example.com",
                url = "https://mail.example",
                notes = "work mail",
                category = "web",
            ),
            SavedPassword(
                name = "Quoted, Name",
                password = "pass,word",
                username = "user",
                url = "https://q.example",
            ),
        )
        val text = Vault.formatPasswordCsv(items)
        assert(text.startsWith("name,username,password,url,notes,category\n"))
        assert(text.contains("\"Quoted, Name\""))
        assert(text.contains("\"pass,word\""))
        val back = Vault.parsePasswordCsv(text)
        assertEquals(2, back.size)
        assertEquals("Email", back[0].name)
        assertEquals("secret-one", back[0].password)
        assertEquals("Quoted, Name", back[1].name)
        assertEquals("pass,word", back[1].password)
        assertThrows<VaultException> { Vault.formatPasswordCsv(emptyList()) }
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
