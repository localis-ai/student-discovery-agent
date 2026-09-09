# Generated API types

Các file `*-api.d.ts` trong thư mục này được **sinh tự động** từ OpenAPI spec của
backend, KHÔNG chỉnh tay.

Sinh lại bằng:

```bash
pnpm gen:api
```

Lệnh này chạy `openapi-typescript` trên:

- `../sda-backend/docs/openapi/user-api.yaml` → `user-api.d.ts`
- `../sda-backend/docs/openapi/admin-api.yaml` → `admin-api.d.ts`

Import type trong module, ví dụ:

```ts
import type { paths, components } from '@/types/api/user-api';
type User = components['schemas']['UserResponse'];
```
