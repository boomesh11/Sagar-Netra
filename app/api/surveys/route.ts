import { NextResponse } from "next/server";
import { fetchSurveys, addSurvey } from "@/lib/api";

export async function GET() {
  const surveys = await fetchSurveys();
  return NextResponse.json(surveys);
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const created = await addSurvey(body);
    return NextResponse.json(created, { status: 201 });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Failed to create survey" }, { status: 400 });
  }
}
