package app.localpassword

import android.text.InputType
import java.util.Locale

/** Pure classification so overlapping numeric/text variation constants cannot cross-match. */
internal object AutofillFieldRules {
    fun isPassword(inputType: Int, hints: List<String>): Boolean {
        val normalized = hints.map { it.lowercase(Locale.ROOT) }
        if (normalized.any { it == "newpassword" || it == "new-password" }) return false
        if (normalized.any { it == "password" || it == "current-password" }) return true
        val variation = inputType and InputType.TYPE_MASK_VARIATION
        return when (inputType and InputType.TYPE_MASK_CLASS) {
            InputType.TYPE_CLASS_TEXT -> variation == InputType.TYPE_TEXT_VARIATION_PASSWORD ||
                variation == InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD
            InputType.TYPE_CLASS_NUMBER -> variation == InputType.TYPE_NUMBER_VARIATION_PASSWORD
            else -> false
        }
    }

    fun isUsername(inputType: Int, hints: List<String>): Boolean {
        val normalized = hints.map { it.lowercase(Locale.ROOT) }
        if (normalized.any { it == "newusername" || it == "new-username" }) return false
        if (isPassword(inputType, hints)) return false
        if (normalized.any { it == "username" || it == "emailaddress" || it == "email" }) return true
        val variation = inputType and InputType.TYPE_MASK_VARIATION
        return inputType and InputType.TYPE_MASK_CLASS == InputType.TYPE_CLASS_TEXT &&
            (variation == InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS ||
                variation == InputType.TYPE_TEXT_VARIATION_WEB_EMAIL_ADDRESS)
    }
}
