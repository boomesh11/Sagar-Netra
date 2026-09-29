import { NextResponse } from "next/server";
import { fetchDetections, submitDetectionReview } from "@/lib/api";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const surveyId = searchParams.get("surveyId") || "SN-2026-0007";
  const verified = searchParams.get("verified") !== "false";
  const detections = await fetchDetections(surveyId, verified);
  return NextResponse.json(detections);
}

export async function POST(request: Request) {
  try {
    const { detectionId, review } = await request.json();
    const result = await submitDetectionReview(detectionId, review);
    return NextResponse.json(result);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 400 });
  }
}
