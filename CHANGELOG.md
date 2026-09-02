# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-09-02

### Added

- **Mobile Splash Screen (`apps/native/src/components/SplashView.tsx`)**: Introduced a dedicated landing screen featuring the custom, scale-independent vector-drawn Actinver logo and stylized vertical brand text.
- **Actinver Brand Logo (`apps/native/src/components/ActinverLogo.tsx`)**: Built a robust, pure-view component representing the stylized brand chevron caret and iconic teal dot using standard React Native elements and stylesheet rotations.
- **Login Screen with Mock Validation (`apps/native/src/components/LoginView.tsx`)**: Created a high-fidelity login interface including email and password text inputs, password toggle-visibility icon (using `@expo/vector-icons`), simulated Face ID biometric approval flow, and an "Inicia sesión CTA" button.
- **State-Driven App Lifecycle Engine (`apps/native/App.tsx`)**: Replaced direct WebView rendering with a finite-state machine transitions loop (`SPLASH` ➔ `LOGIN` ➔ `AUTHENTICATED`).
  - `SPLASH`: Automatically transitions to `LOGIN` after a 2-second timeout.
  - `LOGIN`: Authenticates credentials (mocked) and transitions to `AUTHENTICATED`.
  - `AUTHENTICATED`: Dynamically loads the `WebViewContainer` target URL appending the `/demo` sub-route.
- **Types Definitions (`apps/native/src/types/index.ts`)**: Structured the type definitions and prop contracts supporting states, logins, and customized components.

### Changed

- **App Entrance configuration (`apps/native/App.tsx`)**: Wrapped layouts in safe-area views with custom conditional status-bar and color styles matching active theme specifications.
