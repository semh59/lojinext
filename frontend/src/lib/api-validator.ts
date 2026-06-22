import { z } from "zod";
import { errorTracker } from "../services/error-tracker";

/**
 * Validates API response data against a given Zod schema.
 * In development, it throws warning to console or error tracker.
 * In production, it logs the error but returns the data to prevent UI break.
 */
export function validateResponse<T extends z.ZodTypeAny>(
  schema: T,
  data: any,
  context: string = "API Validation",
): z.infer<T> {
  const result = schema.safeParse(data);

  if (!result.success) {
    const errorDetails = result.error.format();
    const message = `[Zod Validation Error] at ${context}: ${JSON.stringify(
      errorDetails,
    )}`;

    console.warn(message, { data });

    // Capture in error tracker for analysis
    errorTracker.capture(new Error(message), {
      severity: "warning",
    });

    // 🚨 CRITICAL FIX: Safe Fallback
    // Instead of just returning potentially corrupt 'data',
    // we try to use Zod's default matching to keep UI stable.
    try {
      // If the schema has a default value or is optional, this might give a safer empty state
      return schema.parse(undefined);
    } catch {
      // If no default exists, we reluctantly return the original data
      // but the error is already logged.
      return data as z.infer<T>;
    }
  }

  return result.data;
}

/**
 * A helper to wrap async API calls with validation.
 */
export async function safeApiCall<T extends z.ZodTypeAny>(
  schema: T,
  apiPromise: Promise<any>,
  context: string = "API",
): Promise<z.infer<T>> {
  const data = await apiPromise;
  return validateResponse(schema, data, context);
}
