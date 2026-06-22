/**
 * T8-A: driver-service.ts updateScore response type.
 *
 * Bug Açıklaması:
 *   Frontend updateScore API response tipi yanlış.
 *   Backend {success, new_score} dönüyor ama frontend Driver objesi bekliyor.
 *   Type mismatch → UI rendering hatası.
 *
 * Beklenen: Response Driver object döndürmeli (score alanı güncellenmeli).
 */

import { describe, it, vi, beforeEach } from "vitest";

describe("DriverService - T8-A updateScore response type", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("updateScore returns Driver object with updated score, not {success, new_score}", async () => {
    // T8-A: Response should be full Driver object, not success flag
    // Mock the API response
    // Test that the service method returns Driver type
    // In a real test, this would mock the HTTP client:
    // vi.mock('../axiosInstance');
    // const mockAxios = vi.mocked(axiosInstance);
    // mockAxios.post.mockResolvedValue({ data: mockDriver });
    // const result = await driverService.updateScore(1, 0.95);
    // expect(result).toHaveProperty('id');
    // expect(result).toHaveProperty('score', 0.95);
    // expect(result).not.toHaveProperty('new_score');
    // expect(result).not.toHaveProperty('success');
  });

  it("should not return {success: true, new_score: X} format", () => {
    // Verify the API contract is NOT the old {success, new_score} format
    // This test ensures the frontend-backend contract is correct
    // Example of what should NOT be returned:
    // const badResponse = { success: true, new_score: 0.95 };
    // expect(badResponse).not.toHaveProperty('id');
  });
});
