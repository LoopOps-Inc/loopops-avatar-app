# LoopOps Avatar App

React Native mobile app for the Actinver talking-head avatar (HeyGen Live Avatar + custom LLM backend).

## Stack

- React Native **0.87.1**
- React **19.2.3**
- TypeScript

## Prerequisites

Follow the [React Native environment setup](https://reactnative.dev/docs/set-up-your-environment) for iOS and/or Android.

- Node.js >= 22.11.0
- Xcode (iOS)
- Android Studio (Android)

## Install

```sh
npm install
```

### iOS (first time or after native dependency changes)

```sh
bundle install
bundle exec pod install --project-directory=ios
```

## Run

Start Metro:

```sh
npm start
```

In another terminal:

```sh
npm run ios
# or
npm run android
```

## Project structure

```
.
├── AGENTS.md              # Agent instructions index
├── GEMINI.md              # Gemini-specific rules
├── DESIGN.md              # Design token mirror for agents
├── .cursor/rules/         # Cursor agent rules
├── .agents/rules/         # Cross-IDE agent rules
├── knowledge/             # Architecture docs (read before coding)
├── src/theme/             # Design tokens (tokens.ts, getTheme)
├── App.tsx                # Root component
├── index.js               # Entry point
├── android/               # Android native project
├── ios/                   # iOS native project
└── __tests__/             # Jest tests
```

## Agent docs

Before working on a feature, read the relevant file in `knowledge/`. Start with `knowledge/README.md`.
