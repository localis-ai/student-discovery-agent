export { productSchema } from '@/infrastructure/db/product-schema';
export { users } from '@/modules/users/users.table';
export { versions } from '@/modules/versions/versions.table';
export {
  experiences,
  experienceDrafts,
  experienceReleases,
  experienceActive,
  experienceReports,
} from '@/modules/experiences/experiences.table';
export { idempotencyRecords } from '@/infrastructure/db/idempotency.table';
export { authSessions, authRefreshTokens, authRegistrationLimits } from '@/modules/auth/auth.table';
export { agentDraft, agentReleases, agentActive, agentDebugRuns, auditEvents } from '@/modules/agent/agent.table';
