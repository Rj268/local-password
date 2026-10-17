package app.localpassword

import android.app.Activity
import android.os.Bundle
import android.view.View
import android.view.autofill.AutofillManager
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.text.InputType

/** A synthetic login screen installed only with the instrumentation APK. */
class AutofillFixtureActivity : Activity() {
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val username = EditText(this).apply {
            id = View.generateViewId()
            hint = "Fixture username"
            setAutofillHints(View.AUTOFILL_HINT_USERNAME)
            importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_YES
        }
        val password = EditText(this).apply {
            id = View.generateViewId()
            hint = "Fixture password"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
            setAutofillHints(View.AUTOFILL_HINT_PASSWORD)
            importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_YES
        }
        layout.addView(username)
        layout.addView(password)
        layout.addView(Button(this).apply {
            isAllCaps = false
            text = "Request Autofill"
            setOnClickListener {
                password.requestFocus()
                getSystemService(AutofillManager::class.java).requestAutofill(password)
            }
        })
        setContentView(layout)
    }
}
