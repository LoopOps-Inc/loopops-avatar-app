import { useMemo } from 'react';
import {
  SafeAreaView,
  StatusBar,
  StyleSheet,
  Text,
  useColorScheme,
  View,
} from 'react-native';
import { fontSize, getTheme, spacing } from './src/theme';

function App() {
  const isDarkMode = useColorScheme() === 'dark';
  const theme = useMemo(() => getTheme(isDarkMode), [isDarkMode]);

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: theme.colors.surface }]}>
      <StatusBar barStyle={isDarkMode ? 'light-content' : 'dark-content'} />
      <View style={styles.container}>
        <Text style={[styles.title, { color: theme.colors.content }]}>
          Actinver Avatar
        </Text>
        <Text style={[styles.subtitle, { color: theme.colors.contentSub }]}>
          React Native 0.87 — ready for Live Avatar integration
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
  title: {
    fontSize: fontSize['3xl'],
    fontWeight: '700',
    marginBottom: spacing[2],
  },
  subtitle: {
    fontSize: fontSize.lg,
    textAlign: 'center',
    lineHeight: fontSize.lg * 1.375,
  },
});

export default App;
