export type CounselingStage =
  | "intake"
  | "ready_for_summary"
  | "active_counseling"
  | "completed";

export type SummaryJobStatus = "none" | "running" | "failed";

export type MessageRole = "assistant" | "user";

export interface IntakeQuestion {
  question_id: string;
  prompt: string;
  profile_field: string;
  help_text?: string | null;
  options: string[];
  allows_multiple: boolean;
  input_type: string;
  placeholder?: string | null;
}

export interface UserProfile {
  student_status?: string | null;
  interest_fields: string[];
  student_record_grade?: string | null;
  mock_exam_score?: string | null;
  converted_score?: string | null;
  admission_plan?: string | null;
  track_preferences: string[];
  target_region?: string | null;
  residence_preference?: string | null;
  constraints: string[];
  blocked_tracks: string[];
  notes?: string | null;
}

export interface ConversationMessage {
  message_id: string;
  role: MessageRole;
  kind: string;
  content: string;
  created_at: string;
  request_id?: string | null;
}

export interface QuotaState {
  actor_type: "guest";
  actor_id: string;
  limit: number;
  used: number;
  remaining: number;
  exhausted: boolean;
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

export interface RecommendationOption {
  university: string;
  major: string;
  track: string;
  campus_or_region?: string | null;
  fit_reason: string;
  evidence_summary: string;
  dorm_note?: string | null;
  tuition_note?: string | null;
  next_step?: string | null;
  metrics_line?: string | null;
  source_file_hint?: string | null;
}

export interface CounselingSummary {
  overview: string;
  recommended_options: RecommendationOption[];
  next_actions: string[];
  closing_message: string;
}

export interface EvidenceItem {
  dataset_id?: string | null;
  dataset_title?: string | null;
  school_name?: string | null;
  region?: string | null;
  snapshot_date?: string | null;
  source_path: string;
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
    summary_job_status?: SummaryJobStatus;
    summary_job_error?: string | null;
    followup_job_status?: SummaryJobStatus;
    followup_job_error?: string | null;
    followup_pending_client_request_id?: string | null;
  };
  current_question?: IntakeQuestion | null;
  answered_count: number;
  total_questions: number;
  can_complete: boolean;
  quota: QuotaState;
}

export interface CompleteSessionAcceptedResponse {
  session_id: string;
  summary_job_status: SummaryJobStatus;
  message: string;
}

export interface FollowupAcceptedResponse {
  session_id: string;
  client_request_id: string;
  followup_job_status: SummaryJobStatus;
  message: string;
}

export interface SessionSummaryResponse {
  session_id: string;
  stage: CounselingStage;
  summary: CounselingSummary;
  evidence: EvidenceItem[];
  trace_id?: string | null;
  provider?: string | null;
  model?: string | null;
  grounding_mode?: string | null;
  used_web_search?: boolean;
  used_file_input?: boolean;
  file_ids: string[];
  file_count: number;
  region_filter?: string | null;
  quota: QuotaState;
  conversation: ConversationMessage[];
}

export interface FollowupResponse {
  session_id: string;
  stage: CounselingStage;
  answer: string;
  trace_id?: string | null;
  grounding_mode?: string | null;
  used_web_search?: boolean;
  used_file_input?: boolean;
  file_ids: string[];
  file_count: number;
  region_filter?: string | null;
  conversation: ConversationMessage[];
  quota: QuotaState;
}
