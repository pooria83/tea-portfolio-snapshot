package com.tea.app

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import com.google.android.gms.auth.api.phone.SmsRetriever

/**
 * Transparent activity that hosts the Google SMS User Consent dialog. The
 * consent intent comes from [SmsUserConsentReceiver]; the result (the full SMS
 * text, or a user cancellation) is forwarded to [SmsOtpModule] which emits it
 * to JavaScript.
 */
class SmsConsentActivity : Activity() {

  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    val consent = intent.extras?.getParcelable<Intent>(EXTRA_CONSENT_INTENT)
    if (consent == null) {
      SmsOtpModule.onConsentCancelled()
      finish()
      return
    }
    startActivityForResult(consent, REQUEST_CODE_SMS_CONSENT)
  }

  override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
    super.onActivityResult(requestCode, resultCode, data)
    if (requestCode != REQUEST_CODE_SMS_CONSENT) {
      finish()
      return
    }
    if (resultCode == Activity.RESULT_OK) {
      val message = data?.getStringExtra(SmsRetriever.EXTRA_SMS_MESSAGE)
      if (message != null) {
        SmsOtpModule.onConsentResult(message)
      } else {
        SmsOtpModule.onConsentCancelled()
      }
    } else {
      SmsOtpModule.onConsentCancelled()
    }
    finish()
  }

  companion object {
    const val EXTRA_CONSENT_INTENT = "extra_consent_intent"
    private const val REQUEST_CODE_SMS_CONSENT = 8801
  }
}