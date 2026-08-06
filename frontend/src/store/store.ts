import { configureStore } from '@reduxjs/toolkit';
import uiReducer from './slices/uiSlice';
import ticketsReducer from './slices/ticketsSlice';

export const store = configureStore({
  reducer: {
    ui: uiReducer,
    tickets: ticketsReducer,
  },
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
// Inferred type: {ui: UiState, tickets: TicketsState}
export type AppDispatch = typeof store.dispatch;
