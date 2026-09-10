import type {BottomTabScreenProps} from '@react-navigation/bottom-tabs';
import type {CompositeScreenProps} from '@react-navigation/native';
import type {NativeStackScreenProps} from '@react-navigation/native-stack';

export type AuthStackParamList = {
  Phone: undefined;
  Otp: undefined;
};

export type RootStackParamList = {
  Auth: undefined;
  Home: undefined;
  Profile: undefined;
  Permissions: undefined;
};

export type AppStackParamList = {
  Main: undefined;
  Permissions: undefined;
};

export type MainTabsParamList = {
  Home: undefined;
  Favorites: undefined;
  Profile: undefined;
};

export type PhoneScreenProps = NativeStackScreenProps<
  AuthStackParamList,
  'Phone'
>;

export type OtpScreenProps = NativeStackScreenProps<AuthStackParamList, 'Otp'>;

export type HomeScreenProps = CompositeScreenProps<
  BottomTabScreenProps<MainTabsParamList, 'Home'>,
  NativeStackScreenProps<RootStackParamList>
>;

export type FavoritesScreenProps = CompositeScreenProps<
  BottomTabScreenProps<MainTabsParamList, 'Favorites'>,
  NativeStackScreenProps<RootStackParamList>
>;

export type ProfileScreenProps = CompositeScreenProps<
  BottomTabScreenProps<MainTabsParamList, 'Profile'>,
  NativeStackScreenProps<RootStackParamList>
>;

export type PermissionsScreenProps = NativeStackScreenProps<
  RootStackParamList,
  'Permissions'
>;
