'use client';

<<<<<<< HEAD
=======
import { useRef } from 'react';
>>>>>>> origin/add/voice-to-text-service
import { Provider } from 'react-redux';
import { store } from '../store/store';

export default function StoreProvider({
  children,
}: {
  children: React.ReactNode;
}) {
<<<<<<< HEAD
  return <Provider store={store}>{children}</Provider>;
=======
  // Ensure the store is only created once per request on the server
  // and once per application lifecycle on the client
  const storeRef = useRef<typeof store>(null);
  
  if (!storeRef.current) {
    storeRef.current = store;
  }

  return <Provider store={storeRef.current}>{children}</Provider>;
>>>>>>> origin/add/voice-to-text-service
}
