import React from 'react';
import { Text, View, StyleSheet } from 'react-native';
import { greet } from '@thread/shared';

export default function App() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{greet('Mobile')}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  title: { fontSize: 24, fontWeight: 'bold' },
});
