import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { theme } from '../styles/theme';
import { ActinverLogo } from './ActinverLogo';

export const SplashView: React.FC = () => {
  return (
    <View style={styles.container}>
      <View style={styles.logoContainer}>
        <ActinverLogo size={120} caretColor="#041e41" dotColor="#50bfa4" />
      </View>
      <View style={styles.textContainer}>
        <Text style={styles.brandTitle}>Actinver</Text>
        <Text style={styles.brandSubtitle}>Trade</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#ffffff', // High fidelity white background as shown in mockups
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoContainer: {
    marginBottom: 24,
  },
  textContainer: {
    alignItems: 'center',
  },
  brandTitle: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#041e41', // Navy Blue primary brand color
    textAlign: 'center',
    lineHeight: 38,
  },
  brandSubtitle: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#041e41', // Navy Blue primary brand color
    textAlign: 'center',
    lineHeight: 38,
  },
});

export default SplashView;
