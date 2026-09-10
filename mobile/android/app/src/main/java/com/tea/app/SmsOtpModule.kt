package com.tea.app

import com.facebook.react.bridge.Arguments
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.bridge.WritableMap
import com.facebook.react.modules.core.DeviceEventManagerModule
import com.google.android.gms.auth.api.phone.SmsRetriever

/**
 * Exposes the SMS User Consent flow to JavaScript. React Native JS calls
 * [startListening] while the user is waiting for the OTP message; when the
 * user approves (or rejects) reading the message, this module emits an
 * [EVENT_NAME] event carrying the message text or a cancellation flag.
 */
class SmsOtpModule(reactContext: ReactApplicationContext) :
  ReactContextBaseJavaModule(reactContext) {

  override fun getName(): String = NAME

  override fun initialize() {
    super.initialize()
    instance = this
  }

  override fun onCatalystInstanceDestroy() {
    super.onCatalystInstanceDestroy()
    if (instance === this) {
      instance = null
    }
  }

  /** Starts listening for the next OTP message via the SMS User Consent API. */
  @ReactMethod
  fun startListening() {
    val activity = reactApplicationContext.currentActivity
    if (activity == null) {
      emitCancelled()
      return
    }
    SmsRetriever.getClient(activity)
      .startSmsUserConsent(null)
      .addOnFailureListener { emitCancelled() }
  }

  private fun deliverMessage(message: String) {
    val map = Arguments.createMap()
    map.putString("message", message)
    emit(map)
  }

  private fun deliverCancelled() {
    emitCancelled()
  }

  private fun emitCancelled() {
    val map = Arguments.createMap()
    map.putBoolean("cancelled", true)
    emit(map)
  }

  private fun emit(map: WritableMap) {
    reactApplicationContext
      .getJSModule(DeviceEventManagerModule.RCTDeviceEventEmitter::class.java)
      .emit(EVENT_NAME, map)
  }

  companion object {
    const val NAME = "SmsOtp"
    const val EVENT_NAME = "SmsOtpEvent"

    @Volatile
    private var instance: SmsOtpModule? = null

    /** Called from [SmsConsentActivity] when the user approves reading a message. */
    fun onConsentResult(message: String) {
      instance?.deliverMessage(message)
    }

    /** Called from [SmsConsentActivity] when the user dismisses the consent dialog. */
    fun onConsentCancelled() {
      instance?.deliverCancelled()
    }
  }
}