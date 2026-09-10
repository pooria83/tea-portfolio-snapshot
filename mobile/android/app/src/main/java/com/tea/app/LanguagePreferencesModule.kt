package com.tea.app

import android.content.Context
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.module.annotations.ReactModule

@ReactModule(name = LanguagePreferencesModule.NAME)
class LanguagePreferencesModule(
  reactContext: ReactApplicationContext,
) : ReactContextBaseJavaModule(reactContext) {

  override fun getName(): String = NAME

  /**
   * Persists the interface language so the next app launch can apply the RTL
   * layout direction before the first frame (see MainActivity).
   */
  @ReactMethod
  fun setLanguage(lang: String) {
    reactApplicationContext
      .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
      .edit()
      .putString(KEY_LANG, lang)
      .apply()
  }

  /**
   * Closes the app completely so the next launch starts a fresh process and
   * applies the new layout direction. The activity is removed from the
   * recents list so reopening it always starts from scratch.
   */
  @ReactMethod
  fun exitApp() {
    val activity = reactApplicationContext.currentActivity ?: return
    activity.runOnUiThread {
      activity.finishAndRemoveTask()
      android.os.Process.killProcess(android.os.Process.myPid())
    }
  }

  companion object {
    const val NAME = "LanguagePreferences"
    const val PREFS_NAME = "app_language"
    const val KEY_LANG = "lang"
  }
}
