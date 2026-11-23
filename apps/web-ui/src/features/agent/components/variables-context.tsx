'use client';

import { createContext, useContext } from 'react';
import type { ChatflowWorkflow, NodeTypeCatalog } from '../types';

/** Variable actions of the chatflow editor, shared by the start node panel, the assign node and the node I/O lists. */
export interface VariablesPanel {
  workflow: ChatflowWorkflow;
  catalog?: NodeTypeCatalog;
  readOnly: boolean;
  /** Opens the variable dialog: on `conv.<name>`, or on a new declaration (null) that reports its name once saved. */
  edit: (name: string | null, onCreated?: (name: string) => void) => void;
  /** Asks to remove an unused variable. */
  remove: (name: string) => void;
  /** Selects a node on the canvas and opens its panel. */
  jumpToNode: (nodeId: string) => void;
}

export const VariablesPanelContext = createContext<VariablesPanel | null>(null);

/** The variable actions, or null outside the chatflow editor (e.g. in isolated form tests). */
export const useVariablesPanel = () => useContext(VariablesPanelContext);
