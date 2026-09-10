const config = {
  apps: {
    'ios.debug': {
      type: 'ios.app',
      binaryPath:
        'ios/build/Build/Products/Debug-iphonesimulator/ProductGraphMobile.app',
      build:
        'xcodebuild -workspace ios/ProductGraphMobile.xcworkspace -scheme ProductGraphMobile -configuration Debug -sdk iphonesimulator -derivedDataPath ios/build',
    },
    'android.debug': {
      type: 'android.apk',
      binaryPath: 'android/app/build/outputs/apk/debug/app-debug.apk',
      build:
        'cd android && ./gradlew assembleDebug assembleAndroidTest -DtestBuildType=debug',
    },
  },
  devices: {
    simulator: {
      type: 'ios.simulator',
      device: {
        type: 'iPhone 16',
      },
    },
    emulator: {
      type: 'android.emulator',
      device: {
        avdName: 'Pixel_6_API_35',
      },
    },
  },
  configurations: {
    'ios.sim.debug': {
      app: 'ios.debug',
      device: 'simulator',
    },
    'android.emu.debug': {
      app: 'android.debug',
      device: 'emulator',
    },
  },
};

export default config;
