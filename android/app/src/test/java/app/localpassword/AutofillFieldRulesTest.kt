package app.localpassword

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class AutofillFieldRulesTest {
    @Test fun uriIsNotNumericPassword() {
        assertFalse(AutofillFieldRules.isPassword(0x11, emptyList()))
        assertTrue(AutofillFieldRules.isPassword(0x12, emptyList()))
    }
    @Test fun recognizesExistingPasswordFields() {
        assertTrue(AutofillFieldRules.isPassword(0x81, emptyList()))
        assertTrue(AutofillFieldRules.isPassword(0xe1, emptyList()))
        assertTrue(AutofillFieldRules.isPassword(0, listOf("password")))
    }
    @Test fun doesNotFillNewPasswordOrOtpFields() {
        assertFalse(AutofillFieldRules.isPassword(0x81, listOf("newPassword")))
        assertFalse(AutofillFieldRules.isPassword(2, listOf("smsOTPCode")))
        assertFalse(AutofillFieldRules.isUsername(1, listOf("newUsername")))
    }
    @Test fun detectsEmailWithoutHintsAndAvoidsPasswordAsUsername() {
        assertTrue(AutofillFieldRules.isUsername(0x21, emptyList()))
        assertTrue(AutofillFieldRules.isUsername(0xd1, emptyList()))
        assertFalse(AutofillFieldRules.isUsername(0x81, listOf("username")))
        assertFalse(AutofillFieldRules.isUsername(1, listOf("userAddress")))
    }
}
