import React, { useState, useEffect } from 'react';
import { StyleSheet, View, SafeAreaView, StatusBar } from 'react-native';
import { registerRootComponent } from 'expo';
import { theme } from './src/styles/theme';
import './src/i18n';
import { WebViewContainer } from './src/components/WebViewContainer';
import { SplashView } from './src/components/SplashView';
import { LoginView } from './src/components/LoginView';
import { AppState, LoginCredentials } from './src/types';

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<AppState>('SPLASH');
  const [isAuthenticating, setIsAuthenticating] = useState<boolean>(false);
  const webAppUrl = 'http://localhost:8080';

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (currentScreen === 'SPLASH') {
      timer = setTimeout(() => {
        setCurrentScreen('LOGIN');
      }, 2000);
    }
    return () => {
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [currentScreen]);

  const handleLoginSuccess = (credentials: LoginCredentials) => {
    setIsAuthenticating(true);
    // Simulate a brief authentication network lag before proceeding
    setTimeout(() => {
      setIsAuthenticating(false);
      setCurrentScreen('AUTHENTICATED');
    }, 800);
  };

  const handleTriggerNom151 = (formId: string, taxId: string) => {
    console.log(`Firma NOM-151 disparada desde la web: formulario ${formId}, RFC ${taxId}`);
  };

  const handleSessionInitialized = (threadId: string) => {
    console.log(`Sesión iniciada con threadId: ${threadId}`);
  };

  const renderContent = () => {
    switch (currentScreen) {
      case 'SPLASH':
        return <SplashView />;
      case 'LOGIN':
        return <LoginView onLoginSuccess={handleLoginSuccess} isLoading={isAuthenticating} />;
      case 'AUTHENTICATED':
        return (
          <WebViewContainer
            webAppUrl={webAppUrl}
            onTriggerNom151={handleTriggerNom151}
            onSessionInitialized={handleSessionInitialized}
          />
        );
      default:
        return <SplashView />;
    }
  };

  const isDarkScreen = currentScreen === 'AUTHENTICATED';

  return (
    <SafeAreaView
      style={[
        styles.container,
        {
          backgroundColor: isDarkScreen ? theme.colors.background : '#ffffff',
        },
      ]}
    >
      <StatusBar
        barStyle={isDarkScreen ? 'light-content' : 'dark-content'}
        backgroundColor={isDarkScreen ? theme.colors.background : '#ffffff'}
      />
      <View style={styles.viewport}>{renderContent()}</View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  viewport: {
    flex: 1,
  },
});

registerRootComponent(App);
