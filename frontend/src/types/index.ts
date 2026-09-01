export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface CandidateProfile {
  id?: number;
  user_id?: number;
  full_name?: string;
  email?: string;
  headline?: string;
  target_role?: string;
  experience_level?: string;
  experience_years?: number;
  bio?: string;
  phone?: string;
  university?: string;
  degree?: string;
  branch?: string;
  graduation_year?: number;
  skills?: string[];
  experience?: Array<Record<string, any>>;
  projects?: Array<Record<string, any>>;
  certifications?: string[];
  preferences?: Record<string, any>;
  github_url?: string;
  linkedin_url?: string;
  created_at?: string;
}

export interface Company {
  id: number;
  name: string;
  slug: string;
  description?: string;
  website?: string;
  target_roles: string[];
  culture_keywords: string[];
  roles?: Role[];
}

export interface Role {
  id: number;
  company_id: number;
  title: string;
  level: string;
  description?: string;
  required_skills: string[];
  key_topics: string[];
  interview_categories: string[];
}

export interface Question {
  id: number;
  topic: string;
  subtopic?: string;
  difficulty: string;
  question_type: string;
  question_text: string;
  expected_concepts: string[];
  follow_ups: string[];
}

export interface QuestionTurn {
  id?: number;
  turn_number?: number;
  question_text: string;
  difficulty?: string;
  focus_areas?: string[];
  candidate_response?: string;
  score_awarded?: number;
  evaluation_feedback?: string;
}

export interface InterviewState {
  current_topic?: string;
  difficulty: string;
  time_remaining_seconds: number;
  questions_asked_count: number;
  current_question_id?: number;
  skill_scores: Record<string, number>;
  weak_topics: string[];
  strong_topics: string[];
  covered_topics: string[];
  remaining_topics: string[];
  interview_stage: string;
}

export interface AnswerItem {
  id: number;
  question_id: number;
  question_text?: string;
  candidate_answer_text: string;
  created_at: string;
  evaluation?: {
    correctness_score?: number;
    relevance_score?: number;
    reasoning_score?: number;
    depth_score?: number;
    communication_score?: number;
    overall_question_score?: number;
    feedback_text?: string;
    evidence?: string[];
  };
}

export interface InterviewSession {
  id: number;
  candidate_id: number;
  company_id: number;
  role_id: number;
  company_name?: string;
  role_title?: string;
  mode: string;
  interview_type?: string;
  duration_minutes: number;
  remaining_seconds?: number;
  total_questions?: number;
  target_level: string;
  status: string;
  start_time?: string;
  end_time?: string;
  created_at: string;
  state?: InterviewState;
  current_question?: Question;
  answers?: AnswerItem[];
}

export interface Evaluation {
  correctness_score: number;
  relevance_score: number;
  reasoning_score: number;
  depth_score: number;
  communication_score: number;
  overall_question_score: number;
  evidence: string[];
  feedback_text: string;
  confidence_score: number;
  human_review_required: boolean;
}

export interface AnswerTurnResponse {
  evaluation: Evaluation;
  next_question?: Question;
  interview_state: InterviewState;
  is_completed: boolean;
  closing_message?: string;
  termination_reason?: string;
}

export interface FinalReport {
  id: number;
  interview_id: number;
  overall_score: number;
  topic_scores: Record<string, number>;
  rubric_scores: Record<string, number>;
  strengths: string[];
  weaknesses: string[];
  difficult_topics: string[];
  recommendations: string[];
  executive_summary: string;
  created_at: string;
}

export interface JobMatchBreakdown {
  skills_score: number;
  experience_score: number;
  education_score: number;
  projects_score: number;
}

export interface JobMatchResult {
  role_id: number;
  role_title: string;
  company_id: number;
  company_name: string;
  role_level: string;
  overall_score: number;
  breakdown: JobMatchBreakdown;
  matched_skills: string[];
  missing_skills: string[];
  what_you_have?: string[];
  what_you_are_missing?: string[];
  is_eligible?: boolean;
  eligibility_reason?: string;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
}

export interface ResumeProfile {
  id: number;
  resume_id: number;
  raw_text: string;
  explicit_facts: Record<string, any>;
  model_inferred: Record<string, any>;
  skills: string[];
  projects: Array<Record<string, any>>;
  education: Array<Record<string, any>>;
  experience: Array<Record<string, any>>;
  technologies: string[];
  parsed_at: string;
}

export interface ResumeItem {
  id: number;
  user_id: number;
  filename: string;
  file_size: number;
  mime_type: string;
  created_at: string;
  resume_profile?: ResumeProfile;
}
