export interface Profile {
  headline: string; phone: string; location: string; summary: string; years_experience: string | number;
  skills: string[]; desired_roles: string[]; desired_locations: string[]; remote_preference: "any" | "remote" | "hybrid" | "onsite";
  links: Record<string, string>; notice_period_days: number | null;
}
export interface User { id: number; email: string; first_name: string; last_name: string; is_staff: boolean; profile: Profile }

export interface Source { slug: string; name: string; kind: string; attribution: string; terms_url: string }
export interface Job {
  id: number; title: string; company: string; location: string; is_remote: boolean; employment_type: string; skills: string[];
  min_experience: number | null; max_experience: number | null; salary_text: string; apply_url: string; posted_at: string | null;
  last_checked_at: string; is_active: boolean; imported_by_me: boolean; source: Source; match_score: number | null;
  match_verdict: string | null; is_saved: boolean; application_status: string | null; snippet: string;
  description?: string; match?: Match | null; possible_duplicate_application?: { id: number; job__title: string; job__company: string; status: string } | null;
  note?: string; duplicate?: boolean;
}
export interface Match {
  score: number; verdict: string; factors: { factor: string; max: number; score: number; detail: string }[];
  matched_skills: string[]; missing_skills: string[]; eligibility: { likely_eligible: boolean; warnings: string[] }; tip: string;
}
export interface JobList { count: number; page: number; pages: number; has_resume: boolean; results: Job[] }

export interface ResumeSummary {
  id: number; title: string; source: "upload" | "builder"; original_filename: string; file_type: string; page_count: number;
  skills: string[]; is_primary: boolean; analysis_at: string | null; analysis_score: number | null; has_file: boolean;
  latest_version: number | null; created_at: string; updated_at: string;
}
export interface Analysis {
  score: number; grade: string; checks: { id: string; label: string; passed: boolean; weight: number; detail: string; fix: string }[];
  strengths: string[]; improvements: { issue: string; fix: string }[]; stats: Record<string, number>; skills: string[];
  job_fit?: { skill_coverage_pct: number | null; matched_skills: string[]; missing_skills: string[]; missing_keywords: string[] };
}
export interface ResumeDetail extends ResumeSummary { parsed_data: any; analysis: Analysis | Record<string, never> }
export interface ResumeContent {
  basics: { name: string; email: string; phone: string; location: string; headline: string; links: Record<string, string> };
  summary: string;
  experience: { company: string; title: string; location: string; start: string; end: string; bullets: string[] }[];
  education: { school: string; degree: string; start: string; end: string; details: string }[];
  skills: string[];
  projects: { name: string; description: string; bullets: string[] }[];
  certifications: string[];
}
export interface ResumeVersion { version_no: number; template: string; content: ResumeContent; note: string; created_at: string }
export interface AIResult { text: string; engine: "ollama" | "rules"; model: string; note: string }

export type AppStatus = "wishlist" | "preparing" | "applied" | "interviewing" | "offer" | "rejected" | "withdrawn";
export interface Application {
  id: number; job_id: number | null; job_title: string; company: string; location: string; apply_url: string; status: AppStatus;
  position: number; match_score: number | null; resume_id: number | null; resume_title: string | null; applied_at: string | null;
  applied_via: string; submission_confirmed: boolean; review_confirmed_at: string | null; has_cover_letter: boolean;
  updated_at: string; created_at: string;
  cover_letter?: string; notes?: string;
  activities?: { id: number; kind: string; message: string; created_at: string }[];
  attempts?: Attempt[];
  reminders?: { id: number; title: string; due_at: string; done: boolean }[];
}
export interface Attempt { id: number; attempt_no: number; state: string; host: string; fields_filled: string[]; fields_skipped: string[]; error: string; created_at: string }
export interface Reminder { id: number; title: string; due_at: string; done: boolean; application_id: number | null; overdue: boolean }
export interface Notification { id: number; kind: string; title: string; body: string; link: string; is_read: boolean; created_at: string }

export interface Dashboard {
  counts: Record<AppStatus, number>; total_applications: number; response_rate: number | null; saved_jobs: number;
  weekly: { label: string; applied: number }[];
  reminders: { id: number; title: string; due_at: string; overdue: boolean; application_id: number | null }[];
  recent_activity: { id: number; kind: string; message: string; created_at: string; application_id: number; label: string }[];
  resume: { id: number; title: string; score: number | null } | null;
  profile_completeness: { percent: number; missing: string[] };
  unread_notifications: number;
  usage: Record<string, { used: number; limit: number }>;
  ai: { enabled: boolean; ready: boolean; model: string; reachable: boolean; model_installed: boolean };
}
export interface AIStatus { enabled: boolean; reachable: boolean; model: string; model_installed: boolean; installed_models: string[]; ready: boolean; base_url: string }

export interface Conversation { id: number; title: string; job_id: number | null; updated_at: string; messages?: ChatMessage[] }
export interface ChatMessage { id: number; role: "user" | "assistant"; content: string; engine?: string; note?: string }
export interface InterviewQuestion { id: number; text: string; type: string; skill?: string; tips?: string[] }
export interface Interview {
  id: number; role_title: string; kind: string; status: string; engine: string; total: number; answered: number; summary: any;
  questions?: InterviewQuestion[]; answers?: { question_index: number; answer: string; score: number; feedback: any }[]; next_index?: number | null;
}
export interface SkillGapResult {
  target: string; required: string[]; have: string[]; missing: string[]; coverage_pct: number | null; known_role: boolean; note: string | null;
  roadmap: { phases: { title: string; weeks: string; skills: string[]; est_hours: number; milestone: string; resources: Record<string, any> }[]; total_hours: number; total_weeks: number; hours_per_week: number };
  ai: AIResult | null;
}
export interface Goal { id: number; title: string; target_role: string; target_date: string | null; status: string; skills_needed: string[]; completed_skills: string[]; progress: number; roadmap: SkillGapResult["roadmap"] }
