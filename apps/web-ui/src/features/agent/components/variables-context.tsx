'use client';

import { createContext, useContext } from 'react';

export interface VariablesPanel {
  /** Opens the Biến sheet; with `create`, straight into a new declaration that reports its name once saved. */
  openVariables: (request?: { create: true; onCreated: (name: string) => void }) => void;
}

export const VariablesPanelContext = createContext<VariablesPanel | null>(null);

/** The open-the-Biến-sheet action, or null outside the chatflow editor (e.g. in isolated form tests). */
export const useVariablesPanel = () => useContext(VariablesPanelContext);
