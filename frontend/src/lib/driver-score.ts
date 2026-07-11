// sofor.score / manual_score are on a 0.1-2.0 scale (app/schemas/sofor.py's
// Field(ge=0.1, le=2.0)) — not a 0-5 star count. DriverScoreModal.tsx
// already bucketed this correctly; DriverGrid.tsx/DriverTable.tsx instead
// rendered the raw score as a star index (`index < driver.score`), so a
// driver with an average manual score of 1.0 showed only 1/5 stars,
// reading as a poor performer. Centralized here so every star-rating
// render site uses the same 5-bucket scale.
export function scoreToStars(score: number): number {
  if (score >= 1.8) return 5;
  if (score >= 1.5) return 4;
  if (score >= 1.2) return 3;
  if (score >= 0.8) return 2;
  return 1;
}
