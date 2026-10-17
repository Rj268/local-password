@file:OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package app.localpassword

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

@Composable
fun SavedPane(model: PasswordModel) {
    val colors = MaterialTheme.colorScheme
    // Resolve by name against live ViewModel data; never retain a snapshot of a password in navigation.
    val selected = if (model.unlocked) model.saved.firstOrNull { it.name == model.selectedEntryName } else null
    LaunchedEffect(model.selectedEntryName, selected?.name, model.unlocked) {
        if (model.selectedEntryName != null && selected == null) model.closeEntry()
    }
    BackHandler(enabled = selected != null) { model.closeEntry() }
    if (selected != null) {
        TextButton(onClick = model::closeEntry) { Text("Back to Vault") }
        ScreenSurface {
            CredentialDetailsContent(model, selected, colors.onSurface, colors.onSurfaceVariant)
        }
    } else {
        ScreenSurface {
            Text("Saved passwords", style = MaterialTheme.typography.titleLarge)
            when {
                !model.hasVault() -> {
                    Text("Save your first password to set up the vault. You’ll choose a passphrase and receive a recovery key to write down. You can also import an existing vault in Settings.")
                    Button(onClick = { model.section = "create" }) { Text("Create a password") }
                }
                !model.unlocked -> {
                    Text("Unlock with your passphrase or recovery key to see your entries.")
                    Button(onClick = { model.askUnlock = true }, enabled = !model.busy,
                        modifier = Modifier.fillMaxWidth()) { Text("Unlock Vault") }
                }
                else -> {
                    if (model.lastRemoved != null) {
                        Text("Entry removed. You can undo this removal.")
                        TextButton(onClick = model::undoRemove, enabled = !model.busy) { Text("Undo removal") }
                    }
                    val health = model.passwordHealthSummary()
                    Text("Password health", style = MaterialTheme.typography.titleMedium)
                    Text(if (health.attentionCount == 0) "No findings from these local checks."
                        else "${health.attentionCount} active entries to review.")
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
                        listOf(HealthReview.WEAK to "${health.weakCount} potentially weak",
                            HealthReview.REUSED to "${health.reuseCount} reuse groups",
                            HealthReview.OLDER to "${health.staleCount} older entries").forEach { (reason, label) ->
                            FilterChip(selected = model.needsAttentionOnly && model.healthReview == reason,
                                onClick = { model.reviewHealth(reason) }, label = { Text(label) })
                        }
                    }
                    Text("Local estimates, not a breach check. Reuse means identical passwords. Older means no recorded change in ${Vault.STALE_PASSWORD_DAYS} days; age alone does not mean a password is unsafe.",
                        style = MaterialTheme.typography.bodySmall, color = colors.onSurfaceVariant)
                    OutlinedTextField(value = model.savedQuery, onValueChange = { model.savedQuery = it },
                        modifier = Modifier.fillMaxWidth(), singleLine = true, label = { Text("Search Vault") },
                        supportingText = { Text("Name, username, website, notes or category") },
                        trailingIcon = { if (model.savedQuery.isNotEmpty()) TextButton(onClick = { model.savedQuery = "" }) { Text("Clear") } })
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
                        FilterChip(selected = model.favoritesOnly, onClick = { model.favoritesOnly = !model.favoritesOnly }, label = { Text("Favorites") })
                        FilterChip(selected = model.needsAttentionOnly && model.healthReview == HealthReview.ALL,
                            onClick = { if (model.needsAttentionOnly && model.healthReview == HealthReview.ALL) model.needsAttentionOnly = false
                                else model.reviewHealth(HealthReview.ALL) }, label = { Text("Needs attention") })
                        FilterChip(selected = model.archivedOnly, onClick = { model.archivedOnly = !model.archivedOnly }, label = { Text("Archived") })
                    }
                    Text("Sort by", style = MaterialTheme.typography.labelLarge)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
                        listOf(Vault.SAVED_SORT_NAME to "Name", Vault.SAVED_SORT_RECENT to "Recent", Vault.SAVED_SORT_CHANGED to "Changed").forEach { (mode, label) ->
                            FilterChip(selected = model.savedSortMode == mode, onClick = { model.savedSortMode = mode }, label = { Text(label) })
                        }
                    }
                    if (model.categories().isNotEmpty()) {
                        Text("Category", style = MaterialTheme.typography.labelLarge)
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
                            FilterChip(selected = model.categoryFilter == "all", onClick = { model.categoryFilter = "all" }, label = { Text("All categories") })
                            model.categories().forEach { category ->
                                FilterChip(selected = model.categoryFilter == category, onClick = { model.categoryFilter = category }, label = { Text(category) })
                            }
                        }
                    }
                    val matches = model.filteredSaved()
                    Text("${matches.size} ${if (matches.size == 1) "entry" else "entries"}", style = MaterialTheme.typography.labelLarge)
                    if (matches.isEmpty()) {
                        Text(if (model.saved.isEmpty()) "No passwords saved yet." else "No entries match these filters.")
                        if (model.savedQuery.isNotBlank() || model.favoritesOnly || model.needsAttentionOnly || model.archivedOnly || model.categoryFilter != "all") {
                            TextButton(onClick = model::resetVaultFilters) { Text("Clear search and filters") }
                        }
                    }
                    matches.forEach { item ->
                        CredentialRow(item, enabled = !model.busy, onOpen = { model.openEntry(item.name) },
                            onFavorite = { model.toggleFavorite(item) })
                    }
                }
            }
        }
    }
    SavedPaneDialogs(model, colors.onSurfaceVariant, colors.onSurface)
}

@Composable
private fun CredentialRow(item: SavedPassword, enabled: Boolean, onOpen: () -> Unit, onFavorite: () -> Unit) {
    Surface(onClick = onOpen, enabled = enabled, shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.surfaceContainerLow, modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(AppSpacing.medium), horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(item.name, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                val subtitle = listOf(item.username.ifBlank { item.url }, item.category).filter { it.isNotBlank() }.joinToString(" · ")
                if (subtitle.isNotEmpty()) Text(subtitle, style = MaterialTheme.typography.bodyMedium, maxLines = 2,
                    overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(if (item.archived) "Archived · View details" else "View details", style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary)
            }
            TextButton(onClick = onFavorite, enabled = enabled,
                modifier = Modifier.semantics { contentDescription = if (item.favorite) "Remove ${item.name} from favorites" else "Add ${item.name} to favorites" }) {
                Text(if (item.favorite) "★" else "☆", style = MaterialTheme.typography.titleLarge)
            }
        }
    }
}
