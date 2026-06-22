import { submitFeedbackApiV1FeedbackPost } from "../generated/api/feedback/feedback";

export interface FeedbackPayload {
  message: string;
  page?: string;
}

export async function sendFeedback(payload: FeedbackPayload): Promise<void> {
  await submitFeedbackApiV1FeedbackPost(payload);
}
