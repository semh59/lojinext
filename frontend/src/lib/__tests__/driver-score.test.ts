import { describe, expect, it } from "vitest";
import { scoreToStars } from "../driver-score";

describe("scoreToStars", () => {
  it("maps a midpoint manual score (1.0) to 2 stars, not 1", () => {
    // Regression: DriverGrid/DriverTable used to render `index < score`
    // directly (score is 0.1-2.0, not a 0-5 star count), so a driver with
    // an average score of 1.0 showed only 1/5 stars.
    expect(scoreToStars(1.0)).toBe(2);
  });

  it("maps the scale's max (2.0) to 5 stars", () => {
    expect(scoreToStars(2.0)).toBe(5);
  });

  it("maps the scale's min (0.1) to 1 star", () => {
    expect(scoreToStars(0.1)).toBe(1);
  });

  it("buckets the full 0.1-2.0 range monotonically", () => {
    expect(scoreToStars(0.79)).toBe(1);
    expect(scoreToStars(0.8)).toBe(2);
    expect(scoreToStars(1.19)).toBe(2);
    expect(scoreToStars(1.2)).toBe(3);
    expect(scoreToStars(1.49)).toBe(3);
    expect(scoreToStars(1.5)).toBe(4);
    expect(scoreToStars(1.79)).toBe(4);
    expect(scoreToStars(1.8)).toBe(5);
  });
});
