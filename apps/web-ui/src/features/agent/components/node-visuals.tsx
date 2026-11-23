import {
  Bot,
  Box,
  LibraryBig,
  MessageSquareText,
  Play,
  Shuffle,
  Sparkles,
  Split,
  Tags,
  UserRoundPen,
  Variable,
  Wrench,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';

interface NodeVisual {
  icon: LucideIcon;
  /** Icon tile background and foreground. */
  tile: string;
  /** Branch dot on the canvas, in the same hue as the tile. */
  dot: string;
  /** The same hue as a plain background, for markers outside the canvas. */
  swatch: string;
}

// One hue per family of nodes, so the colour says what a step does; the icon tells nodes of one family apart.
// Full class strings, so Tailwind's scanner keeps them.
const ENTRY = { tile: 'bg-primary text-primary-foreground', dot: '!bg-primary', swatch: 'bg-primary' };
const FLOW = { tile: 'bg-cyan-600 text-white', dot: '!bg-cyan-600', swatch: 'bg-cyan-600' };
const AI = { tile: 'bg-indigo-600 text-white', dot: '!bg-indigo-600', swatch: 'bg-indigo-600' };
// Violet, not green: green is Studio's own colour (the start node), so knowledge must not read as the entry.
const KNOWLEDGE = { tile: 'bg-violet-600 text-white', dot: '!bg-violet-600', swatch: 'bg-violet-600' };
const OUTPUT = { tile: 'bg-orange-500 text-white', dot: '!bg-orange-500', swatch: 'bg-orange-500' };

const VISUALS: Record<string, NodeVisual> = {
  start: { icon: Play, ...ENTRY },
  // Flow control: decides where the turn goes next or sets state for later steps.
  if_else: { icon: Split, ...FLOW },
  intent_classifier: { icon: Tags, ...FLOW },
  assign: { icon: Variable, ...FLOW },
  goto_flow: { icon: Shuffle, ...FLOW },
  // Model calls.
  llm: { icon: Sparkles, ...AI },
  agent: { icon: Bot, ...AI },
  profile_propose: { icon: UserRoundPen, ...AI },
  // Knowledge and tools the turn reads from.
  knowledge_retrieval: { icon: LibraryBig, ...KNOWLEDGE },
  tool: { icon: Wrench, ...KNOWLEDGE },
  // What the student sees.
  answer: { icon: MessageSquareText, ...OUTPUT },
};

const UNKNOWN: NodeVisual = { icon: Box, tile: 'bg-muted-foreground text-background', dot: '!bg-muted-foreground', swatch: 'bg-muted-foreground' };

export function nodeVisual(type: string): NodeVisual {
  return VISUALS[type] ?? UNKNOWN;
}

export function NodeIcon({ type, size = 'md', className }: { type: string; size?: 'sm' | 'md'; className?: string }) {
  const { icon: Icon, tile } = nodeVisual(type);
  return (
    <span
      aria-hidden
      className={cn(
        'inline-flex shrink-0 items-center justify-center',
        size === 'sm' ? 'size-5 rounded-md' : 'size-7 rounded-lg',
        tile,
        className,
      )}
    >
      <Icon className={size === 'sm' ? 'size-3' : 'size-4'} strokeWidth={2.25} />
    </span>
  );
}
