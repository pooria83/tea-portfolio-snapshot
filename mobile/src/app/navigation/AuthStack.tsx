import * as React from 'react';
import {createNativeStackNavigator} from '@react-navigation/native-stack';
import PhoneScreen from '../screens/auth/PhoneScreen';
import OtpScreen from '../screens/auth/OtpScreen';
import type {AuthStackParamList} from '../../types/navigation';
import {useTheme} from 'react-native-paper';

const Stack = createNativeStackNavigator<AuthStackParamList>();

export default function AuthStack() {
  const theme = useTheme();

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: {backgroundColor: theme.colors.surface},
        headerTintColor: theme.colors.onSurface,
        headerTitleStyle: {color: theme.colors.onSurface},
        contentStyle: {backgroundColor: theme.colors.background},
        headerShown: false,
      }}>
      <Stack.Screen name="Phone" component={PhoneScreen} />
      <Stack.Screen name="Otp" component={OtpScreen} />
    </Stack.Navigator>
  );
}
