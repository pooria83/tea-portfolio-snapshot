declare module 'react-native-vector-icons/MaterialIcons' {
  import type {Component} from 'react';
  import type {TextProps} from 'react-native';

  export interface IconProps extends TextProps {
    name: string;
    size?: number;
    color?: string;
  }

  export default class Icon extends Component<IconProps> {}
}

declare module 'react-native-config' {
  interface Config {
    API_BASE_URL: string;
    ENV: 'development' | 'staging' | 'production';
    GOOGLE_CLIENT_ID: string;
    SENTRY_DSN: string;
    IMAGE_OPTIMIZER_URL: string;
  }
  const Config: Config;
  export default Config;
}
