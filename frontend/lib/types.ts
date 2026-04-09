export type CounselingStage =
  | "intake"
  | "ready_for_summary"
  | "active_counseling"
  | "upgrade_required"
  | "completed";

export type MessageRole = "assistant" | "user";

export interface IntakeQuestion {
  question_id: string;
  prompt: string;
  profile_field: string;
  help_text?: string | null;
  options: string[];
  allows_multiple: boolean;
}

export interface UserProfile {
  current_stage?: string | null;
  target_region?: string | null;
  goals: string[];
  interests: string[];
  avoidances: string[];
  priorities: string[];
  strengths: string[];
  constraints: string[];
  decision_pain?: string | null;
  notes?: string | null;
}

export interface ConversationMessage {
  message_id: string;
  role: MessageRole;
  kind: string;
  content: string;
  created_at: string;
}

export interface QuotaState {
  actor_type: "guest" | "user";
  actor_id: string;
  trial_limit: number;
  trial_used: number;
  trial_remaining: number;
  paid_total: number;
  paid_used: number;
  paid_remaining: number;
  total_remaining: number;
  requires_upgrade: boolean;
  can_chat: boolean;
}

export interface SessionProgressResponse {
  session_id: string;
  stage: CounselingStage;
  counselor_message: string;
  current_question?: IntakeQuestion | null;
  answered_count: number;
  total_questions: number;
  user_profile: UserProfile;
  can_complete: boolean;
  conversation: ConversationMessage[];
  quota: QuotaState;
}

export interface RecommendationDirection {
  title: string;
  fit_reason: string;
  evidence_summary: string;
  action_tip?: string | null;
}

export interface RiskTradeoff {
  direction_title: string;
  risk: string;
  reality_check: string;
}

export interface CounselingSummary {
  situation_summary: string;
  recommended_directions: RecommendationDirection[];
  risks_and_tradeoffs: RiskTradeoff[];
  next_actions: string[];
  closing_message: string;
}

export interface EvidenceItem {
  dataset_id: string;
  dataset_title: string;
  table_id: string;
  table_title: string;
  snapshot_date?: string | null;
  source_path: string;
  score?: number | null;
  excerpt: string;
  query_rows: Array<Record<string, unknown>>;
}

export interface SessionStatusResponse {
  session: {
    session_id: string;
    stage: CounselingStage;
    opening_question?: string | null;
    current_question_id?: string | null;
    user_profile: UserProfile;
    conversation: ConversationMessage[];
    final_summary?: CounselingSummary | null;
  };
  current_question?: IntakeQuestion | null;
  answered_count: number;
  total_questions: number;
  can_complete: boolean;
  quota: QuotaState;
}

export interface SessionSummaryResponse {
  session_id: string;
  stage: CounselingStage;
  summary: CounselingSummary;
  evidence: EvidenceItem[];
  trace_id?: string | null;
  provider?: string | null;
  model?: string | null;
  quota: QuotaState;
  conversation: ConversationMessage[];
}

export interface FollowupResponse {
  session_id: string;
  stage: CounselingStage;
  answer: string;
  trace_id?: string | null;
  conversation: ConversationMessage[];
  quota: QuotaState;
}

export interface AuthState {
  actor_type: "guest" | "user";
  guest_id?: string | null;
  user?: {
    user_id: string;
    email: string;
    email_verified_at: string | null;
  } | null;
  quota: QuotaState;
}

export interface EmailStartResponse {
  email: string;
  sent: boolean;
  verification_code?: string | null;
}

export interface EmailVerifyResponse {
  actor_type: "user";
  user: {
    user_id: string;
    email: string;
    email_verified_at: string | null;
  };
  quota: QuotaState;
}

export interface CheckoutResponse {
  checkout_url: string;
  order_id: string;
}
