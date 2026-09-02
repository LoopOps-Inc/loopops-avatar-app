/**
 * Representa los estados del ciclo de vida visual de la aplicación.
 */
export type AppState = 'SPLASH' | 'LOGIN' | 'AUTHENTICATED';

/**
 * Datos del formulario de inicio de sesión.
 */
export interface LoginCredentials {
  correo: string;
  contrasena: string;
}

/**
 * Props para el componente de logotipo personalizado de Actinver.
 */
export interface ActinverLogoProps {
  size?: number;
  caretColor?: string;
  dotColor?: string;
}

/**
 * Props para la pantalla de inicio de sesión simulada.
 */
export interface LoginViewProps {
  onLoginSuccess: (credentials: LoginCredentials) => void;
  isLoading?: boolean;
}
