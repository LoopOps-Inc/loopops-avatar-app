import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { LoginView } from '../components/LoginView';
import { Alert } from 'react-native';

// Mock Alert
jest.spyOn(Alert, 'alert');

// Mock @expo/vector-icons
jest.mock('@expo/vector-icons', () => {
  const { View } = require('react-native');
  return {
    Feather: (props: any) => <View testID={`mock-icon-${props.name}`} />,
  };
});

describe('LoginView Component', () => {
  it('renders inputs with default credentials and supports typing', () => {
    const mockOnLoginSuccess = jest.fn();
    const { getByLabelText, getByPlaceholderText } = render(
      <LoginView onLoginSuccess={mockOnLoginSuccess} />,
    );

    const emailInput = getByLabelText('Correo electrónico');
    const passwordInput = getByLabelText('Contraseña');

    expect(emailInput.props.value).toBe('cliente@ejemplo.com');
    expect(passwordInput.props.value).toBe('password123');

    // Type new email
    fireEvent.changeText(emailInput, 'user@test.com');
    expect(emailInput.props.value).toBe('user@test.com');
  });

  it('toggles password visibility when eye icon is pressed', () => {
    const { getByLabelText } = render(<LoginView onLoginSuccess={jest.fn()} />);

    const passwordInput = getByLabelText('Contraseña');
    const eyeBtn = getByLabelText('Toggle password visibility');

    // Initially password should be secure
    expect(passwordInput.props.secureTextEntry).toBe(true);

    // Press toggle
    fireEvent.press(eyeBtn);
    expect(passwordInput.props.secureTextEntry).toBe(false);

    // Press toggle again
    fireEvent.press(eyeBtn);
    expect(passwordInput.props.secureTextEntry).toBe(true);
  });

  it('validates fields and calls onLoginSuccess on click', () => {
    const mockOnLoginSuccess = jest.fn();
    const { getByLabelText } = render(<LoginView onLoginSuccess={mockOnLoginSuccess} />);

    const loginBtn = getByLabelText('Inicia sesión');
    fireEvent.press(loginBtn);

    expect(mockOnLoginSuccess).toHaveBeenCalledWith({
      correo: 'cliente@ejemplo.com',
      contrasena: 'password123',
    });
  });

  it('alerts if fields are empty or invalid', () => {
    const mockOnLoginSuccess = jest.fn();
    const { getByLabelText } = render(<LoginView onLoginSuccess={mockOnLoginSuccess} />);

    const emailInput = getByLabelText('Correo electrónico');
    const loginBtn = getByLabelText('Inicia sesión');

    // Make email empty
    fireEvent.changeText(emailInput, '');
    fireEvent.press(loginBtn);

    expect(Alert.alert).toHaveBeenCalledWith(
      'Correo requerido',
      'Por favor, introduce tu correo electrónico.',
    );
    expect(mockOnLoginSuccess).not.toHaveBeenCalled();
  });
});
