module.exports = {
  preset: '@react-native/jest-preset',
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  testTimeout: 15000,
  setupFiles: ['<rootDir>/__tests__/setup.ts'],
  testMatch: ['**/__tests__/**/*.test.[jt]s?(x)'],
  testPathIgnorePatterns: [
    '<rootDir>/__tests__/setup.ts',
    '<rootDir>/__tests__/__mocks__/',
  ],
  transformIgnorePatterns: [
    'node_modules/(?!(react-native|@react-native|react-native-paper|react-native-vector-icons|react-native-config|react-native-safe-area-context|react-native-screens|@react-navigation|react-i18next|i18next|@ronradtke/react-native-markdown-display)/)',
  ],
  moduleNameMapper: {
    '^react-native-config$':
      '<rootDir>/__tests__/__mocks__/react-native-config.ts',
    '^@react-native-clipboard/clipboard$':
      '<rootDir>/__tests__/__mocks__/clipboard.ts',
    '\\.(ttf|otf|woff2?|eot)$':
      '<rootDir>/__tests__/__mocks__/font-asset-stub.js',
  },
  collectCoverage: true,
  collectCoverageFrom: [
    'src/services/api/**/*.ts',
    'src/features/auth/**/*.ts',
    'src/features/chat/**/*.ts',
  ],
  coverageThreshold: {
    global: {
      statements: 90,
      branches: 85,
      functions: 90,
      lines: 90,
    },
  },
};
