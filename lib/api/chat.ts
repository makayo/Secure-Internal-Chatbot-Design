/**
 * Chat API endpoints
 */

import { apiClient } from './client';

export interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant' | 'system';
  timestamp: string;
  conversationId?: string;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

export interface SendMessageRequest {
  message: string;
  conversationId?: string;
}

export interface SendMessageResponse {
  message: Message;
  conversationId: string;
}

export interface ChatHistoryResponse {
  messages: Message[];
  conversationId: string;
}

export const chatApi = {
  async sendMessage(data: SendMessageRequest): Promise<SendMessageResponse> {
    return apiClient.post<SendMessageResponse>('/chat/message', data);
  },

  async getConversations(): Promise<Conversation[]> {
    return apiClient.get<Conversation[]>('/chat/conversations');
  },

  async getConversationHistory(conversationId: string): Promise<ChatHistoryResponse> {
    return apiClient.get<ChatHistoryResponse>(`/chat/conversations/${conversationId}`);
  },

  async deleteConversation(conversationId: string): Promise<void> {
    return apiClient.delete(`/chat/conversations/${conversationId}`);
  },

  async clearConversation(conversationId: string): Promise<void> {
    return apiClient.delete(`/chat/conversations/${conversationId}/messages`);
  },
};

