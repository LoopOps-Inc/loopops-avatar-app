import React from 'react';
import { StyleSheet, View, SafeAreaView, StatusBar } from 'react-native';
import { registerRootComponent } from 'expo';
import { theme } from './src/styles/theme';
import './src/i18n';
import { WebViewContainer } from './src/components/WebViewContainer';

export default function App() {
  const webAppUrl = 'http://localhost:8080';

  const handleTriggerNom151 = (formId: string, taxId: string) => {
    console.log(`Firma NOM-151 disparada desde la web: formulario ${formId}, RFC ${taxId}`);
  };

  const handleSessionInitialized = (threadId: string) => {
    console.log(`Sesión iniciada con threadId: ${threadId}`);
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={theme.colors.background} />
      <View style={styles.viewport}>
        <WebViewContainer
          webAppUrl={webAppUrl}
          onTriggerNom151={handleTriggerNom151}
          onSessionInitialized={handleSessionInitialized}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  viewport: {
    flex: 1,
  },
});

registerRootComponent(App);
