import React, { useRef, useEffect, useState } from 'react';
import {
  StyleSheet,
  View,
  Text,
  ActivityIndicator,
  PermissionsAndroid,
  Platform,
} from 'react-native';
import { WebView, WebViewMessageEvent } from 'react-native-webview';
import { theme } from '../styles/theme';

interface WebViewContainerProps {
  webAppUrl: string;
  onTriggerNom151: (formId: string, taxId: string) => void;
  onSessionInitialized: (threadId: string) => void;
}

export const WebViewContainer: React.FC<WebViewContainerProps> = ({
  webAppUrl,
  onTriggerNom151,
  onSessionInitialized,
}) => {
  const webViewRef = useRef<WebView>(null);
  const [hasPermissionChecked, setHasPermissionChecked] = useState<boolean>(
    Platform.OS !== 'android',
  );

  // Injected JavaScript script to facilitate immediate setup of the WebView Bridge
  const injectedJavaScript = `
    (function() {
      window.isReactNativeWebView = true;
      
      // Listen for events sent back from React Native
      window.addEventListener('message', function(event) {
        try {
          var data = JSON.parse(event.data);
          if (data.type === 'NOM_151_COMPLETED') {
            // Dispatch a custom event to the web app's document
            var customEvent = new CustomEvent('nom151Completed', { detail: data.payload });
            window.dispatchEvent(customEvent);
          }
        } catch (e) {
          console.error("Error parsing RN message: ", e);
        }
      });

      // Simple hook to override default web sign flow
      window.triggerNativeNom151 = function(formId, taxId) {
        window.ReactNativeWebView.postMessage(JSON.stringify({
          type: 'TRIGGER_NOM_151',
          payload: { formId: formId, taxId: taxId || 'XAXX010101000' }
        }));
      };

      // Notify RN that bridge is online
      window.ReactNativeWebView.postMessage(JSON.stringify({
        type: 'MOBILE_INIT',
        payload: { ready: true }
      }));
    })();
    true; // note: this is required for injectedJavaScript to succeed
  `;

  // Handle native Android permission requests on mount
  useEffect(() => {
    const requestAndroidPermissions = async () => {
      if (Platform.OS === 'android') {
        try {
          // Request mic permission upfront to ensure WebView doesn't experience race conditions
          const granted = await PermissionsAndroid.request(
            PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
            {
              title: 'Permiso de Micrófono',
              message:
                'La aplicación requiere acceso a tu micrófono para poder interactuar por voz con el asesor virtual.',
              buttonNeutral: 'Preguntar luego',
              buttonNegative: 'Cancelar',
              buttonPositive: 'Permitir',
            },
          );
          if (granted === PermissionsAndroid.RESULTS.GRANTED) {
            console.log('Permiso de micrófono otorgado nativamente en Android.');
          } else {
            console.log('Permiso de micrófono denegado nativamente en Android.');
          }
        } catch (err) {
          console.warn('Error al solicitar el permiso de micrófono nativo:', err);
        } finally {
          setHasPermissionChecked(true);
        }
      }
    };

    requestAndroidPermissions();
  }, []);

  // Public method to complete the NOM-151 signature and notify WebView
  const sendSignatureCompleted = (evidenceHash: string, timestamp: string) => {
    const responseMessage = {
      type: 'NOM_151_COMPLETED',
      payload: {
        success: true,
        hash: evidenceHash,
        timestamp: timestamp,
      },
    };
    webViewRef.current?.injectJavaScript(
      `window.postMessage(JSON.stringify(${JSON.stringify(responseMessage)}), '*');`,
    );
  };

  const handleMessage = (event: WebViewMessageEvent) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      console.log('Received Bridge Message from WebView: ', data);

      if (data.type === 'TRIGGER_NOM_151') {
        onTriggerNom151(data.payload.formId, data.payload.taxId);
      } else if (data.type === 'SESSION_START' || data.type === 'MOBILE_INIT') {
        const generatedThreadId = data.payload.threadId || 'embedded_session_thread';
        onSessionInitialized(generatedThreadId);
      }
    } catch (e) {
      console.warn('Failed to parse WebView message: ', event.nativeEvent.data, e);
    }
  };

  if (!hasPermissionChecked) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={theme.colors.brandGoldBright} />
        <Text style={styles.loadingText}>Verificando permisos de audio...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <WebView
        ref={webViewRef}
        source={{ uri: `${webAppUrl}/demo` }}
        injectedJavaScript={injectedJavaScript}
        onMessage={handleMessage}
        mediaPlaybackRequiresUserAction={false}
        androidCameraPermissionGrantType="grant"
        style={styles.webview}
        startInLoadingState={true}
        renderLoading={() => (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={theme.colors.brandGoldBright} />
            <Text style={styles.loadingText}>Iniciando Consulta Digital...</Text>
          </View>
        )}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  webview: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  loadingContainer: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: theme.colors.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 15,
    color: theme.colors.brandGoldBright,
    fontSize: 14,
    fontWeight: 'bold',
  },
});
export default WebViewContainer;
