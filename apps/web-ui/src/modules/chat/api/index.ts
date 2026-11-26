import { createChatApi, type ChatApi } from './chat-api';
import { createMockTransport } from './mock-transport';
import { httpTransport } from './transport';

/**
 * Chọn nguồn dữ liệu chat. Mặc định gọi BFF thật (studio-api /api/v1/conversations); mock chỉ bật khi build với
 * NEXT_PUBLIC_CHAT_MOCK=true, để một bản build quên đặt biến không âm thầm chạy dữ liệu giả.
 */
export const CHAT_MOCK_ENABLED = process.env.NEXT_PUBLIC_CHAT_MOCK === 'true';

let instance: ChatApi | null = null;

export function getChatApi(): ChatApi {
  if (!instance) {
    instance = createChatApi(
      CHAT_MOCK_ENABLED ? createMockTransport({ delayMs: 250 }) : httpTransport,
    );
  }
  return instance;
}

export { createChatApi, type ChatApi, type ChatTurnInput } from './chat-api';
export { createMockTransport } from './mock-transport';
