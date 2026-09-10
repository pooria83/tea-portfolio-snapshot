import * as React from 'react';
import {createNativeStackNavigator} from '@react-navigation/native-stack';
import {useTheme} from 'react-native-paper';
import MainTabs from './MainTabs';
import PermissionsScreen from '../screens/PermissionsScreen';
import type {AppStackParamList} from '../../types/navigation';

const Stack = createNativeStackNavigator<AppStackParamList>();

export default function AppStack() {
  const theme = useTheme();

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: {backgroundColor: theme.colors.surface},
        headerTintColor: theme.colors.onSurface,
        headerTitleStyle: {color: theme.colors.onSurface},
        contentStyle: {backgroundColor: theme.colors.background},
      }}>
      <Stack.Screen
        name="Main"
        component={MainTabs}
        options={{headerShown: false}}
      />
      <Stack.Screen
        name="Permissions"
        component={PermissionsScreen}
        options={{title: ''}}
      />
    </Stack.Navigator>
  );
}
