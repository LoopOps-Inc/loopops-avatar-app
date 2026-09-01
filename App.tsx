import { useMemo } from 'react';
import {
  Image,
  SafeAreaView,
  StatusBar,
  StyleSheet,
  Text,
  useColorScheme,
  View,
} from 'react-native';
import { actinverAvatar } from './src/config/avatar';
import { colors, fontSize, getTheme, radius, spacing } from './src/theme';

function App() {
  const isDarkMode = useColorScheme() === 'dark';
  const theme = useMemo(() => getTheme(isDarkMode), [isDarkMode]);

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: theme.colors.surface }]}>
      <StatusBar barStyle={isDarkMode ? 'light-content' : 'dark-content'} />
      <View style={styles.container}>
        <Image
          source={{ uri: actinverAvatar.previewImageUrl }}
          style={styles.avatarPreview}
          accessibilityLabel="Actinver avatar preview"
        />
        <Text style={[styles.title, { color: theme.colors.content }]}>
          Actinver Avatar
        </Text>
        <Text style={[styles.subtitle, { color: theme.colors.contentSub }]}>
          {actinverAvatar.voiceName} · {actinverAvatar.language.toUpperCase()}
        </Text>
        <Text style={[styles.hint, { color: theme.colors.contentMuted }]}>
          Live Avatar integration ready
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing[6],
  },
  avatarPreview: {
    width: 160,
    height: 160,
    borderRadius: radius.full,
    marginBottom: spacing[6],
    backgroundColor: colors.neutral[30],
  },
  title: {
    fontSize: fontSize['3xl'],
    fontWeight: '700',
    marginBottom: spacing[2],
  },
  subtitle: {
    fontSize: fontSize.lg,
    textAlign: 'center',
    marginBottom: spacing[2],
  },
  hint: {
    fontSize: fontSize.base,
    textAlign: 'center',
  },
});

export default App;
