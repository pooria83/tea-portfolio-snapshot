package com.tea.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Parcelable
import com.google.android.gms.auth.api.phone.SmsRetriever
import com.google.android.gms.auth.api.phone.SmsRetrieverStatusCodes

/**
 * Receives the SMS Retrieval broadcast fired by Google Play services when the
 * SMS User Consent API finds the OTP message. The user must approve a system
 * consent dialog; the consent activity launched here only starts that dialog
 * and hands the approved message back to [SmsOtpModule].
 */
class SmsUserConsentReceiver : BroadcastReceiver() {

  override fun onReceive(context: Context, intent: Intent) {
    if (intent.action != SmsRetriever.SMS_RETRIEVED_ACTION) {
      return
    }
    val status = intent.extras?.get(SmsRetriever.EXTRA_STATUS) as? com.google.android.gms.common.api.Status
    if (status != null && status.statusCode != SmsRetrieverStatusCodes.SUCCESS) {
      return
    }

    val consentIntent: Intent? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
      intent.extras?.getParcelable(SmsRetriever.EXTRA_CONSENT_INTENT, Intent::class.java)
    } else {
      @Suppress("DEPRECATION")
      intent.extras?.getParcelable<Intent>(SmsRetriever.EXTRA_CONSENT_INTENT) as? Intent
    }
    if (consentIntent == null) {
      // Fallback for older Play services versions that deliver a PendingIntent.
      val pending: Parcelable? = intent.extras?.getParcelable(SmsRetriever.EXTRA_CONSENT_INTENT)
      if (pending == null) {
        return
      }
    }

    val launch = Intent(context, SmsConsentActivity::class.java).apply {
      addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
      putExtra(SmsConsentActivity.EXTRA_CONSENT_INTENT, consentIntent as Parcelable)
    }
    context.startActivity(launch)
  }
}