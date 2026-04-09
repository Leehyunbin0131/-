import { SessionExperience } from "@/components/chat/SessionExperience";

export default async function SessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;

  return <SessionExperience sessionId={sessionId} />;
}
