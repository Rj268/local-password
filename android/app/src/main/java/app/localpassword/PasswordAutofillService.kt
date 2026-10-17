package app.localpassword

import android.app.PendingIntent
import android.app.assist.AssistStructure
import android.content.Intent
import android.service.autofill.AutofillService
import android.service.autofill.Dataset
import android.service.autofill.FillCallback
import android.service.autofill.FillRequest
import android.service.autofill.FillResponse
import android.service.autofill.SaveCallback
import android.service.autofill.SaveRequest
import android.view.autofill.AutofillId
import android.widget.RemoteViews
import java.util.Locale
import java.util.concurrent.atomic.AtomicInteger

class PasswordAutofillService : AutofillService() {
    override fun onFillRequest(
        request: FillRequest,
        cancellationSignal: android.os.CancellationSignal,
        callback: FillCallback,
    ) {
        try {
            if (cancellationSignal.isCanceled) {
                callback.onSuccess(null)
                return
            }
            val structure = request.fillContexts.lastOrNull()?.structure
            val fields = structure?.let { AutofillTargetFields.from(it) }
            if (structure?.activityComponent?.packageName == packageName || fields?.passwordId == null) {
                callback.onSuccess(null)
                return
            }
            val authIntent = Intent(this, AutofillAuthenticationActivity::class.java)
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                if (android.os.Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0
            val authentication = PendingIntent.getActivity(
                this,
                requestIds.incrementAndGet(),
                authIntent,
                flags,
            )
            val presentation = RemoteViews(packageName, R.layout.autofill_suggestion).apply {
                setTextViewText(R.id.autofill_label, fields.webDomain?.let { "Use saved password for $it?\nLocal Password" } ?: "Use saved password?\nLocal Password")
            }
            @Suppress("DEPRECATION") // RemoteViews constructor supports API 26+, our minimum SDK.
            val lockedDataset = Dataset.Builder(presentation)
                .apply {
                    setValue(fields.passwordId, null, presentation)
                    fields.usernameId?.let { setValue(it, null, presentation) }
                }
                .setAuthentication(authentication.intentSender)
                .build()
            callback.onSuccess(FillResponse.Builder().addDataset(lockedDataset).build())
        } catch (_: Exception) {
            callback.onFailure("Local Password could not prepare Autofill for this screen.")
        }
    }

    override fun onSaveRequest(request: SaveRequest, callback: SaveCallback) {
        // No SaveInfo is offered until we implement a user-authenticated save flow.
        callback.onFailure("Saving new logins through Autofill is not available yet.")
    }

    companion object {
        private val requestIds = AtomicInteger()
    }
}

internal data class AutofillTargetFields(
    val usernameId: AutofillId?,
    val passwordId: AutofillId?,
    val webDomain: String?,
) {
    companion object {
        fun from(structure: AssistStructure): AutofillTargetFields {
            var username: AutofillId? = null
            var password: AutofillId? = null
            var domain: String? = null

            fun visit(node: AssistStructure.ViewNode, inheritedDomain: String?) {
                val nodeDomain = node.webDomain?.trim()?.takeIf { it.isNotEmpty() } ?: inheritedDomain
                val id = node.autofillId
                val hints = node.autofillHints.orEmpty().map { it.lowercase(Locale.ROOT) }
                if (password == null && id != null && AutofillFieldRules.isPassword(node.inputType, hints)) {
                    password = id
                    domain = nodeDomain
                }
                if (username == null && id != null && AutofillFieldRules.isUsername(node.inputType, hints)) username = id

                for (index in 0 until node.childCount) visit(node.getChildAt(index), nodeDomain)
            }

            for (index in 0 until structure.windowNodeCount) {
                visit(structure.getWindowNodeAt(index).rootViewNode, null)
            }
            return AutofillTargetFields(username, password, domain)
        }
    }
}
