import React from 'react';
import { View, StyleSheet } from 'react-native';
import { ActinverLogoProps } from '../types';

export const ActinverLogo: React.FC<ActinverLogoProps> = ({
  size = 120,
  caretColor = '#041e41', // Navy Blue/Brand Ink
  dotColor = '#00a896', // Teal representativo
}) => {
  const strokeWidth = size * 0.14;

  return (
    <View style={[styles.container, { width: size, height: size }]}>
      {/* Caret/Chevron representing stylized "A" */}
      <View style={styles.caretWrapper}>
        <View
          style={[
            styles.leg,
            styles.leftLeg,
            {
              backgroundColor: caretColor,
              width: strokeWidth,
              height: size * 0.72,
              borderRadius: strokeWidth / 2,
              transform: [{ rotate: '20deg' }, { translateX: -size * 0.12 }],
            },
          ]}
        />
        <View
          style={[
            styles.leg,
            styles.rightLeg,
            {
              backgroundColor: caretColor,
              width: strokeWidth,
              height: size * 0.72,
              borderRadius: strokeWidth / 2,
              transform: [{ rotate: '-20deg' }, { translateX: size * 0.12 }],
            },
          ]}
        />
      </View>
      {/* The iconic central dot */}
      <View
        style={[
          styles.dot,
          {
            backgroundColor: dotColor,
            width: size * 0.22,
            height: size * 0.22,
            borderRadius: (size * 0.22) / 2,
            bottom: size * 0.18,
          },
        ]}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  caretWrapper: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
  },
  leg: {
    position: 'absolute',
    top: '12%',
  },
  leftLeg: {},
  rightLeg: {},
  dot: {
    position: 'absolute',
    zIndex: 10,
  },
});

export default ActinverLogo;
