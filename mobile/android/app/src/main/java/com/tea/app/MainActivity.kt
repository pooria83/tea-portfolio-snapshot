package com.tea.app

import android.content.Context
import android.os.Bundle
import com.facebook.react.ReactActivity
import com.facebook.react.ReactActivityDelegate
import com.facebook.react.defaults.DefaultNewArchitectureEntryPoint.fabricEnabled
import com.facebook.react.defaults.DefaultReactActivityDelegate
import com.facebook.react.modules.i18nmanager.I18nUtil
import com.zoontek.rnbootsplash.RNBootSplash
import java.util.Locale

class MainActivity : ReactActivity() {

  /**
   * Returns the name of the main component registered from JavaScript. This is used to schedule
   * rendering of the component.
   */
  override fun getMainComponentName(): String = "TEA"

  override fun onCreate(savedInstanceState: Bundle?) {
    applyRtlLayoutDirection()
    RNBootSplash.init(this, R.style.BootTheme)
    super.onCreate(null)
  }

  /**
   * Applies the RTL layout direction before the root view is laid out, using the
   * language chosen in the app (persisted by LanguagePreferencesModule) or the
   * device locale as a fallback. This is what makes the layout direction
   * correct from the first frame after the user changes the language.
   */
  private fun applyRtlLayoutDirection() {
    val prefs = getSharedPreferences(LanguagePreferencesModule.PREFS_NAME, Context.MODE_PRIVATE)
    val lang = prefs.getString(LanguagePreferencesModule.KEY_LANG, null)
        ?: Locale.getDefault().language
    val rtl = lang == "ar" || lang == "fa"
    I18nUtil.instance.forceRTL(this, rtl)
    I18nUtil.instance.allowRTL(this, true)
  }

  /**
   * Returns the instance of the [ReactActivityDelegate]. We use [DefaultReactActivityDelegate]
   * which allows you to enable New Architecture with a single boolean flags [fabricEnabled]
   */
  override fun createReactActivityDelegate(): ReactActivityDelegate =
      DefaultReactActivityDelegate(this, mainComponentName, fabricEnabled)
}
