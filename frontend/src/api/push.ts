import {
  getVapidPublicKeyApiV1PushVapidPublicKeyGet,
  subscribeApiV1PushSubscribePost,
  unsubscribeApiV1PushSubscribeDelete,
} from "../generated/api/push/push";
import type {
  VapidPublicKeyResponse,
  PushSubscriptionRequest,
  PushSubscriptionResponse,
} from "../generated/types";

export type {
  VapidPublicKeyResponse,
  PushSubscriptionRequest,
  PushSubscriptionResponse,
};

export const pushService = {
  /** RV2.PWA — public key + push_enabled durumu. */
  getVapidPublicKey: async (): Promise<VapidPublicKeyResponse> => {
    return getVapidPublicKeyApiV1PushVapidPublicKeyGet() as unknown as Promise<VapidPublicKeyResponse>;
  },

  subscribe: async (
    payload: PushSubscriptionRequest,
  ): Promise<PushSubscriptionResponse> => {
    return subscribeApiV1PushSubscribePost(
      payload,
    ) as unknown as Promise<PushSubscriptionResponse>;
  },

  unsubscribe: async (endpoint: string): Promise<void> => {
    await unsubscribeApiV1PushSubscribeDelete({ endpoint });
  },
};
