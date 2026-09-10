import {MD3LightTheme, MD3DarkTheme} from 'react-native-paper';

export const lightTheme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: '#9333EA',
    primaryContainer: '#EDE0FF',
    onPrimary: '#FFFFFF',
    secondary: '#7C5CFC',
    tertiary: '#E8DEF8',
    error: '#B3261E',
    surface: '#FFFBFE',
    background: '#FFFBFE',
  },
};

export const darkTheme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    primary: '#D0BCFF',
    primaryContainer: '#4F378B',
    onPrimary: '#381E72',
    onPrimaryContainer: '#EDE0FF',
    secondary: '#CCC2DC',
    tertiary: '#E8DEF8',
    error: '#F2B8B5',
    surface: '#1C1B1F',
    background: '#1C1B1F',
  },
};
