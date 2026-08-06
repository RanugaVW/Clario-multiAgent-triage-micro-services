import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface Ticket {
  id: string;
  status: string;
  title: string;
  description: string;
  category: string | null;
  priority: string | null;
  sentiment: string | null;
  created_at: string;
}

interface TicketsState {
  items: Ticket[];
  selectedTicketId: string | null;
  loading: boolean;
  error: string | null;
}

const initialState: TicketsState = {
  items: [],
  selectedTicketId: null,
  loading: false,
  error: null,
};

export const ticketsSlice = createSlice({
  name: 'tickets',
  initialState,
  reducers: {
    setTickets: (state, action: PayloadAction<Ticket[]>) => {
      state.items = action.payload;
    },
    addTicket: (state, action: PayloadAction<Ticket>) => {
      state.items.unshift(action.payload);
    },
    updateTicket: (state, action: PayloadAction<Ticket>) => {
      const index = state.items.findIndex(t => t.id === action.payload.id);
      if (index !== -1) {
        state.items[index] = action.payload;
      }
    },
    setSelectedTicketId: (state, action: PayloadAction<string | null>) => {
      state.selectedTicketId = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
});

export const { setTickets, addTicket, updateTicket, setSelectedTicketId, setLoading, setError } = ticketsSlice.actions;

export default ticketsSlice.reducer;
