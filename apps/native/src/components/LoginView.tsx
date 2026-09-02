import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { LoginViewProps } from '../types';

export const LoginView: React.FC<LoginViewProps> = ({ onLoginSuccess, isLoading = false }) => {
  const [email, setEmail] = useState('cliente@ejemplo.com');
  const [password, setPassword] = useState('password123');
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = () => {
    if (!email.trim()) {
      Alert.alert('Correo requerido', 'Por favor, introduce tu correo electrónico.');
      return;
    }
    if (!password.trim()) {
      Alert.alert('Contraseña requerida', 'Por favor, introduce tu contraseña.');
      return;
    }

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      Alert.alert('Formato inválido', 'Por favor, introduce un correo electrónico válido.');
      return;
    }

    onLoginSuccess({ correo: email, contrasena: password });
  };

  const handleFaceID = () => {
    Alert.alert(
      'Simulación de Face ID',
      '¿Deseas ingresar utilizando la autenticación biométrica guardada?',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Ingresar',
          onPress: () => {
            onLoginSuccess({ correo: 'faceid_mocked@actinver.com', contrasena: 'biometric_token' });
          },
        },
      ],
    );
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
    >
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        {/* Header Section */}
        <View style={styles.headerContainer}>
          <Text style={styles.appTitle}>Actinver Trade</Text>
          <Text style={styles.welcomeText}>Te damos</Text>
          <Text style={styles.welcomeText}>la bienvenida</Text>
        </View>

        {/* Form Fields */}
        <View style={styles.formContainer}>
          {/* Correo electrónico */}
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Correo electrónico</Text>
            <TextInput
              style={styles.textInput}
              value={email}
              onChangeText={setEmail}
              placeholder="cliente@ejemplo.com"
              placeholderTextColor="#9ca3af"
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              accessibilityLabel="Correo electrónico"
            />
          </View>

          {/* Contraseña */}
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Contraseña</Text>
            <View style={styles.passwordContainer}>
              <TextInput
                style={styles.passwordInput}
                value={password}
                onChangeText={setPassword}
                placeholder="Contraseña"
                placeholderTextColor="#9ca3af"
                secureTextEntry={!showPassword}
                autoCapitalize="none"
                autoCorrect={false}
                accessibilityLabel="Contraseña"
              />
              <TouchableOpacity
                onPress={() => setShowPassword(!showPassword)}
                style={styles.eyeButton}
                accessibilityLabel="Toggle password visibility"
              >
                <Feather name={showPassword ? 'eye-off' : 'eye'} size={20} color="#9ca3af" />
              </TouchableOpacity>
            </View>
          </View>

          {/* Olvidaste tu contraseña */}
          <TouchableOpacity
            style={styles.forgotPasswordButton}
            onPress={() =>
              Alert.alert('Recuperación', 'Se ha enviado un enlace para restablecer tu contraseña.')
            }
          >
            <Text style={styles.forgotPasswordText}>¿Olvidaste tu contraseña?</Text>
          </TouchableOpacity>
        </View>

        {/* Biometrics Block */}
        <View style={styles.biometricsContainer}>
          <TouchableOpacity
            style={styles.biometricsButton}
            onPress={handleFaceID}
            accessibilityLabel="Ingresar con Face ID"
          >
            <Feather name="aperture" size={24} color="#00a896" style={styles.biometricsIcon} />
            <Text style={styles.biometricsText}>Ingresar con Face ID</Text>
          </TouchableOpacity>
        </View>

        {/* Primary Submit Button */}
        <View style={styles.buttonContainer}>
          <TouchableOpacity
            style={[styles.primaryButton, isLoading && styles.disabledButton]}
            onPress={handleLogin}
            disabled={isLoading}
            accessibilityRole="button"
            accessibilityLabel="Inicia sesión"
          >
            {isLoading ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <Text style={styles.primaryButtonText}>Inicia sesión</Text>
            )}
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#ffffff', // High fidelity white background
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: Platform.OS === 'ios' ? 40 : 20,
    paddingBottom: 40,
    justifyContent: 'space-between',
  },
  headerContainer: {
    marginTop: 40,
    marginBottom: 32,
  },
  appTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#041e41',
    marginBottom: 12,
  },
  welcomeText: {
    fontSize: 32,
    fontWeight: '300',
    color: '#041e41',
    lineHeight: 38,
  },
  formContainer: {
    marginBottom: 24,
  },
  inputGroup: {
    marginBottom: 20,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#041e41',
    marginBottom: 8,
  },
  textInput: {
    height: 48,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 8,
    paddingHorizontal: 16,
    fontSize: 16,
    color: '#1f2937',
    backgroundColor: '#f9fafb',
  },
  passwordContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 8,
    backgroundColor: '#f9fafb',
    height: 48,
  },
  passwordInput: {
    flex: 1,
    height: '100%',
    paddingHorizontal: 16,
    fontSize: 16,
    color: '#1f2937',
  },
  eyeButton: {
    paddingHorizontal: 12,
    height: '100%',
    justifyContent: 'center',
    alignItems: 'center',
  },
  forgotPasswordButton: {
    alignSelf: 'flex-end',
    marginTop: 8,
  },
  forgotPasswordText: {
    fontSize: 14,
    color: '#5b84c4',
    fontWeight: '500',
  },
  biometricsContainer: {
    alignItems: 'center',
    marginVertical: 24,
  },
  biometricsButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 20,
  },
  biometricsIcon: {
    marginRight: 8,
  },
  biometricsText: {
    fontSize: 16,
    fontWeight: '500',
    color: '#041e41',
  },
  buttonContainer: {
    marginTop: 'auto',
  },
  primaryButton: {
    height: 52,
    backgroundColor: '#041e41',
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  disabledButton: {
    backgroundColor: '#6b7280',
  },
  primaryButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: 'bold',
  },
});

export default LoginView;
