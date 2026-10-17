package app.localpassword

/** Filters the existing generator alphabet; randomness and generation remain in Generator. */
data class CharacterOptions(
    val uppercase: Boolean = true,
    val lowercase: Boolean = true,
    val digits: Boolean = true,
    val symbols: Boolean = true,
    val excludeAmbiguous: Boolean = false,
    val excluded: String = "",
) {
    fun pool(): String {
        val base = Generator.characterPool(digits, uppercase || lowercase, symbols)
        val omitted = excluded.toSet() + if (excludeAmbiguous) "0Oo1lI|".toSet() else emptySet()
        val result = base.filter { character ->
            character !in omitted &&
                (uppercase || character !in 'A'..'Z') &&
                (lowercase || character !in 'a'..'z')
        }
        if (result.isEmpty()) throw VaultException("These exclusions leave no characters. Enable a character type or remove an exclusion.")
        return result
    }
}
