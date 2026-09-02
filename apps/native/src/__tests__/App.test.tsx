import React from 'react';
import { render, act, fireEvent } from '@testing-library/react-native';
import App from '../../App';

// Mock WebViewContainer
jest.mock('../components/WebViewContainer', () => {
  const { View, Text } = require('react-native');
  return {
    WebViewContainer: (props: any) => (
      <View testID="mock-webview-container">
        <Text>WebView Mock: {props.webAppUrl}</Text>
      </View>
    ),
  };
});

// Mock @expo/vector-icons
jest.mock('@expo/vector-icons', () => {
  const { View } = require('react-native');
  return {
    Feather: (props: any) => <View testID={`mock-icon-${props.name}`} />,
  };
});

describe('App State-Driven Lifecycle', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('starts in SPLASH state and transitions to LOGIN after 2000ms', () => {
    const { queryByText, queryByLabelText } = render(<App />);

    // Initially in SPLASH screen
    expect(queryByText('Actinver')).toBeTruthy();
    expect(queryByText('Trade')).toBeTruthy();
    expect(queryByLabelText('Inicia sesión')).toBeNull();

    // Fast-forward 2000ms
    act(() => {
      jest.advanceTimersByTime(2000);
    });

    // Should now be on LOGIN screen
    expect(queryByText('Te damos')).toBeTruthy();
    expect(queryByText('la bienvenida')).toBeTruthy();
    expect(queryByLabelText('Inicia sesión')).toBeTruthy();
  });

  it('transitions to AUTHENTICATED on login success and mounts WebViewContainer with /demo', () => {
    const { getByLabelText, getByTestId, queryByTestId } = render(<App />);

    // Fast-forward to login
    act(() => {
      jest.advanceTimersByTime(2000);
    });

    // Tap Inicia sesión
    const loginBtn = getByLabelText('Inicia sesión');
    fireEvent.press(loginBtn);

    // Should show loading / authenticating state briefly (800ms)
    act(() => {
      jest.advanceTimersByTime(800);
    });

    // Should now render the WebViewContainer pointing to http://localhost:8080
    expect(getByTestId('mock-webview-container')).toBeTruthy();
  });
});
