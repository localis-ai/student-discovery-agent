import type { Chatflow, ChatflowFlow, ChatflowRouter, ChatflowWorkflow } from '../../types';
import { nextUniqueId } from './edit';
import { CHATFLOW_IDENTIFIER_RE, CHATFLOW_LIMITS, RESERVED_FLOW_IDS, RESERVED_NODE_IDS } from './rules';

export const MAX_FLOWS = CHATFLOW_LIMITS.flows;
export const MAX_FLOW_EXAMPLES = CHATFLOW_LIMITS.flow_examples;
export { RESERVED_FLOW_IDS };
/** How the runtime router picked a flow (the debug run's route.method), in words. */
export const ROUTE_METHODS: Record<string, string> = {
  trigger: 'điều kiện kích hoạt', single: 'chỉ một nghiệp vụ định tuyến được', classifier: 'phân loại theo mô tả',
  default: 'nghiệp vụ mặc định',
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

/** Whether a draft `workflow` has the flows shape the Studio tabs read from (the JSON tab accepts anything). */
export function isRenderableChatflow(value: unknown): value is Chatflow {
  if (!isRecord(value) || !isRecord(value.router) || !Array.isArray(value.flows) || value.flows.length === 0) return false;
  return value.flows.every(flow => isRecord(flow) && typeof flow.id === 'string' && typeof flow.entry === 'string'
    && Array.isArray(flow.nodes) && flow.nodes.every(node => isRecord(node) && typeof node.id === 'string' && typeof node.type === 'string')
    && (flow.edges === undefined || (Array.isArray(flow.edges) && flow.edges.every(edge =>
      isRecord(edge) && typeof edge.id === 'string' && typeof edge.source === 'string' && typeof edge.target === 'string'))));
}

export function findFlow(chat: Chatflow, flowId: string): ChatflowFlow | undefined {
  return chat.flows.find(flow => flow.id === flowId);
}

export function allNodeIds(chat: Chatflow): string[] {
  return chat.flows.flatMap(flow => flow.nodes.map(node => node.id));
}

export function flowOfNode(chat: Chatflow, nodeId: string): string | undefined {
  return chat.flows.find(flow => flow.nodes.some(node => node.id === nodeId))?.id;
}

/**
 * One flow as the graph editors see it, or undefined when no flow has that id. Never falls back to another flow:
 * edits made on a substituted view would be written back under the wrong id (see withFlowView).
 */
export function flowView(chat: Chatflow, flowId: string): ChatflowWorkflow | undefined {
  const flow = findFlow(chat, flowId);
  return flow && flowViewOf(chat, flow);
}

/** A flow of `chat` as the graph editors see it: its graph plus the chatflow's shared variables and budget. */
export function flowViewOf(chat: Chatflow, flow: ChatflowFlow): ChatflowWorkflow {
  return {
    entry: flow.entry,
    nodes: flow.nodes,
    edges: flow.edges ?? [],
    variables: chat.variables ?? [],
    ...(chat.budget ? { budget: chat.budget } : {}),
    takenNodeIds: chat.flows.filter(item => item !== flow).flatMap(item => item.nodes.map(node => node.id)),
  };
}

/** A flow's trigger, which reads variables just as node configs do. */
export interface FlowTrigger { flow: string; title: string; trigger: unknown }

/** The all-flows view: every node, plus the flows' triggers. */
export type FlowsView = ChatflowWorkflow & { triggers?: FlowTrigger[] };

/**
 * Every flow's nodes as one read-only graph (no edges): what variable usage, renames and the variables panel look
 * at, since conversation variables are shared by every flow and node ids are unique across them.
 */
export function allFlowsView(chat: Chatflow): FlowsView {
  return {
    entry: chat.flows[0]?.entry ?? '',
    nodes: chat.flows.flatMap(flow => flow.nodes),
    edges: [],
    variables: chat.variables ?? [],
    ...(chat.budget ? { budget: chat.budget } : {}),
    triggers: chat.flows.filter(flow => flow.trigger).map(flow => ({ flow: flow.id, title: flow.title, trigger: flow.trigger })),
  };
}

/** Writes an edited view back: the graph to its flow, variables and budget to the chatflow. */
export function withFlowView(chat: Chatflow, flowId: string, view: ChatflowWorkflow): Chatflow {
  // An unknown id would drop the edit without a trace; fail loudly instead.
  if (!findFlow(chat, flowId)) throw new Error(`Không tìm thấy nghiệp vụ ${flowId}.`);
  const { variables, budget, entry, nodes, edges } = view;
  return {
    ...chat,
    ...(variables !== undefined ? { variables } : {}),
    ...(budget !== undefined ? { budget } : {}),
    flows: chat.flows.map(flow => (flow.id === flowId ? { ...flow, entry, nodes, edges: edges ?? [] } : flow)),
  };
}

export function addFlow(chat: Chatflow, input: { id: string; title: string; description?: string }): Chatflow {
  const taken = new Set(allNodeIds(chat));
  const wanted = `${input.id}_start`.slice(0, 40);
  const startId = taken.has(wanted) || RESERVED_NODE_IDS.has(wanted) ? nextUniqueId(taken, wanted, RESERVED_NODE_IDS) : wanted;
  const flow: ChatflowFlow = {
    id: input.id, title: input.title, description: input.description ?? '', examples: [],
    entry: startId, nodes: [{ id: startId, type: 'start', ui: { position: { x: 0, y: 0 } } }], edges: [],
  };
  return { ...chat, flows: [...chat.flows, flow] };
}

type FlowPatch = Partial<Pick<ChatflowFlow, 'id' | 'title' | 'description' | 'examples' | 'trigger' | 'routable'>>;

/** Changes a flow's profile; a new id is carried to the router's default and every goto_flow naming it. */
export function updateFlow(chat: Chatflow, flowId: string, patch: FlowPatch): Chatflow {
  const renamed = patch.id !== undefined && patch.id !== flowId ? patch.id : null;
  const flows = chat.flows.map(flow => {
    const next = flow.id === flowId ? { ...flow, ...patch } : flow;
    if (!renamed) return next;
    return {
      ...next,
      nodes: next.nodes.map(node => (node.type === 'goto_flow' && node.config?.flow === flowId
        ? { ...node, config: { ...node.config, flow: renamed } } : node)),
    };
  });
  const router = renamed && chat.router.default_flow === flowId ? { ...chat.router, default_flow: renamed } : chat.router;
  return { ...chat, router, flows };
}

export function updateRouter(chat: Chatflow, patch: Partial<ChatflowRouter>): Chatflow {
  return { ...chat, router: { ...chat.router, ...patch } };
}

export function setDefaultFlow(chat: Chatflow, flowId: string): Chatflow {
  return updateRouter(chat, { default_flow: flowId });
}

export interface GotoLink { from: string; to: string; nodeId: string }

export function gotoLinks(chat: Chatflow): GotoLink[] {
  return chat.flows.flatMap(flow => flow.nodes
    .filter(node => node.type === 'goto_flow' && typeof node.config?.flow === 'string')
    .map(node => ({ from: flow.id, to: node.config!.flow as string, nodeId: node.id })));
}

/** Why a flow cannot be removed yet; empty when it can. */
export function flowRemovalBlockers(chat: Chatflow, flowId: string): string[] {
  const out: string[] = [];
  if (chat.router.default_flow === flowId) out.push('Đây là nghiệp vụ mặc định.');
  for (const link of gotoLinks(chat)) {
    if (link.to === flowId && link.from !== flowId) {
      out.push(`Node ${link.nodeId} (${findFlow(chat, link.from)?.title ?? link.from}) chuyển tới nghiệp vụ này.`);
    }
  }
  return out;
}

export function removeFlow(chat: Chatflow, flowId: string): Chatflow {
  return { ...chat, flows: chat.flows.filter(flow => flow.id !== flowId) };
}

/** Moves a flow up or down: the order is the order triggers are tried in. */
export function moveFlow(chat: Chatflow, flowId: string, delta: -1 | 1): Chatflow {
  const index = chat.flows.findIndex(flow => flow.id === flowId);
  const target = index + delta;
  if (index < 0 || target < 0 || target >= chat.flows.length) return chat;
  const flows = [...chat.flows];
  [flows[index], flows[target]] = [flows[target]!, flows[index]!];
  return { ...chat, flows };
}

/** Problems with a flow id typed in the form; null when it can be used. */
export function flowIdProblem(chat: Chatflow, id: string, currentId?: string): string | null {
  if (!CHATFLOW_IDENTIFIER_RE.test(id)) return 'Chỉ chữ thường, số và dấu _, bắt đầu bằng chữ, tối đa 40 ký tự.';
  if (RESERVED_FLOW_IDS.has(id)) return 'Không dùng other hoặc error.';
  if (id !== currentId && chat.flows.some(flow => flow.id === id)) return 'Id này đã có nghiệp vụ khác dùng.';
  return null;
}
