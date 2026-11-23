'use client';

import { createContext, useContext } from 'react';

export interface FlowOption { id: string; title: string }

/** The chatflow's flows as the editor of one flow sees them: goto_flow picks its target among the others. */
export interface FlowsEditorContext {
  flows: FlowOption[];
  currentFlowId: string;
}

export const FlowsContext = createContext<FlowsEditorContext | null>(null);

/** The flows, or null outside the chatflow editor (e.g. in isolated form tests). */
export const useFlows = () => useContext(FlowsContext);
