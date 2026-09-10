import * as React from 'react';
import {Image, StyleSheet, View} from 'react-native';
import {useTheme} from 'react-native-paper';

interface AvatarProps {
  url: string | null;
  size?: number;
}

export default function Avatar({url, size = 96}: AvatarProps) {
  const theme = useTheme();

  return (
    <View
      style={[
        styles.container,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: theme.colors.primaryContainer,
        },
      ]}>
      {url ? (
        <Image
          source={{uri: url}}
          style={{width: size, height: size, borderRadius: size / 2}}
          resizeMode="cover"
          accessibilityLabel="avatar"
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
});
