package app.localpassword

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class CharacterOptionsTest {
    @Test fun defaultsPreserveExistingAlphabet() {
        assertEquals(Generator.characterPool(true, true, true), CharacterOptions().pool())
    }
    @Test fun casesCanBeSelectedIndependently() {
        assertEquals("ABCDEFGHIJKLMNOPQRSTUVWXYZ", CharacterOptions(lowercase = false, digits = false, symbols = false).pool())
        assertEquals("abcdefghijklmnopqrstuvwxyz", CharacterOptions(uppercase = false, digits = false, symbols = false).pool())
    }
    @Test fun exclusionsAreAppliedBeforeGenerationAndEstimation() {
        val pool = CharacterOptions(excludeAmbiguous = true, excluded = "abc@%abc").pool()
        assertFalse(pool.any { it in "0Oo1lI|abc@%" })
        assertEquals(pool.length, pool.toSet().size)
        assertTrue(Generator.characterBits(16, pool) < Generator.characterBits(16, CharacterOptions().pool()))
        repeat(50) {
            val result = Generator.password(16, pool)
            assertEquals(16, result.length)
            assertTrue(result.all { it in pool })
            assertTrue(result.any { it in 'A'..'Z' })
            assertTrue(result.any { it in 'a'..'z' })
            assertTrue(result.any { it in '0'..'9' })
            assertTrue(result.any { !it.isLetterOrDigit() })
        }
    }
    @Test fun emptyChoicesAndFullyExcludedAlphabetsAreRejected() {
        assertThrows<VaultException> { CharacterOptions(false, false, false, false).pool() }
        assertThrows<VaultException> { CharacterOptions(false, false, true, false, excluded = "0123456789").pool() }
    }
    @Test fun shortPasswordsStillRespectThePool() {
        val pool = CharacterOptions().pool()
        repeat(20) { assertTrue(Generator.password(1, pool).single() in pool) }
    }
}
