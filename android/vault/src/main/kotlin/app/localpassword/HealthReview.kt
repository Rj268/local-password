package app.localpassword

import java.time.LocalDate

/** Local review hints only; these checks do not establish password entropy or breach status. */
enum class HealthReview {
    ALL, WEAK, REUSED, OLDER;

    fun matches(item: SavedPassword, peers: List<SavedPassword>, today: LocalDate? = null): Boolean = when (this) {
        ALL -> Vault.entryNeedsAttention(item, peers, today)
        WEAK -> Generator.isWeakPassword(item.password)
        REUSED -> peers.count { it.password == item.password } > 1
        OLDER -> Vault.entryIsStale(item, today = today)
    }
}
