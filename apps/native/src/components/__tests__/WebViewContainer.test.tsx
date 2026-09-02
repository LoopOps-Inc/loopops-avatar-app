import React from 'react';
import { render } from '@testing-library/react-native';
import { WebViewContainer } from '../WebViewContainer';

// Mock react-native-webview
jest.mock('react-native-webview', () => {
  const { View } = require('react-native');
  return {
    WebView: (props: any) => <View testID="mock-webview" {...props} />,
  };
});

describe('WebViewContainer Web-Native Bridge Test', () => {
  it('should render webview with correct target URL containing embed query param', () => {
    const triggerNomMock = jest.fn();
    const sessionMock = jest.fn();

    const { getByTestId } = render(
      <WebViewContainer
        webAppUrl="http://localhost:8080"
        onTriggerNom151={triggerNomMock}
        onSessionInitialized={sessionMock}
      />
    );

    const webViewComponent = getByTestId('mock-webview');
    expect(webViewComponent.props.source.uri).toBe('http://localhost:8080/advisor?embed=1');
  });

  it('should inject correct javascript bridge initializations into web context', () => {
    const { getByTestId } = render(
      <WebViewContainer
        webAppUrl="http://localhost:8080"
        onTriggerNom151={jest.fn()}
        onSessionInitialized={jest.fn()}
      />
    );

    const webViewComponent = getByTestId('mock-webview');
    expect(webViewComponent.props.injectedJavaScript).toContain('window.isReactNativeWebView = true;');
    expect(webViewComponent.props.injectedJavaScript).toContain('TRIGGER_NOM_151');
  });
});
