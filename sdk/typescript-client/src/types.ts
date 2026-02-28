export interface APIErrorModel {
  "code": string;
  "details"?: Record<string, unknown> | unknown;
  "message": string;
}

export interface AgentProductivityMetrics {
  "accepted_mvps": number;
  "agent_id": string;
  "agent_name": string;
  "attempts": number;
  "penalties": number;
  "penalty_total": number;
}

export interface AgentProductivityResponse {
  "metrics": AgentProductivityMetrics[];
  "run_id": string;
}

export interface ArtifactDownloadMetadataResponse {
  "artifact_id": string;
  "artifact_type": string;
  "content_hash": string;
  "download_url": string;
  "storage_key": string;
  "submission_id": string;
}

export interface ArtifactIngestInput {
  "artifact_type": ArtifactType;
  "content_base64": string;
  "filename": string;
}

export type ArtifactType = "web_bundle" | "cli_package" | "api_service" | "notebook";

export interface ArtifactUploadResponse {
  "artifact_type": ArtifactType;
  "content_hash": string;
  "created_at": string;
  "id": string;
  "storage_key": string;
  "submission_id": string;
  "updated_at": string;
}

export interface BodyUploadArtifactSubmissionsSubmissionIdArtifactsPost {
  "file": string;
}

export interface ChallengeCreateRequest {
  "complexity_slider": number;
  "iteration_window_seconds": number;
  "minimum_quality_threshold": number;
  "prompt": string;
  "risk_appetite": "conservative" | "balanced" | "aggressive";
  "title": string;
}

export interface ChallengeResponse {
  "complexity_slider": number;
  "created_at": string;
  "id": string;
  "iteration_window_seconds": number;
  "minimum_quality_threshold": number;
  "prompt": string;
  "risk_appetite": string;
  "title": string;
  "updated_at": string;
}

export interface ChallengeUpdateRequest {
  "complexity_slider"?: number | unknown;
  "iteration_window_seconds"?: number | unknown;
  "minimum_quality_threshold"?: number | unknown;
  "prompt"?: string | unknown;
  "risk_appetite"?: "conservative" | "balanced" | "aggressive" | unknown;
  "title"?: string | unknown;
}

export interface CheckpointVarianceMetrics {
  "checkpoint_id": string;
  "inter_judge_variance": number;
  "scored_items": number;
}

export interface HTTPValidationError {
  "detail"?: ValidationError[];
}

export interface JudgeDisagreementMetrics {
  "domain": string;
  "judge_profile_id": string;
  "max_absolute_disagreement": number;
  "mean_absolute_disagreement": number;
  "scored_items": number;
}

export interface JudgeDisagreementResponse {
  "checkpoint_variance": CheckpointVarianceMetrics[];
  "judge_metrics": JudgeDisagreementMetrics[];
  "run_id": string;
}

export interface JudgeProfileInput {
  "domain": string;
  "head_judge"?: boolean;
  "profile_prompt": string;
  "scoring_style": string;
}

export interface JudgeProfileRegisterJSONRequest {
  "profiles": JudgeProfileInput[];
}

export interface JudgeProfileResponse {
  "challenge_id": string;
  "created_at": string;
  "domain": string;
  "head_judge": boolean;
  "id": string;
  "profile_prompt": string;
  "scoring_style": string;
  "source_type": string;
  "updated_at": string;
}

export interface JudgeProfileURLRequest {
  "max_bytes"?: number;
  "timeout_seconds"?: number;
  "url": string;
}

export interface LeaderboardItemResponse {
  "active_penalties": PenaltySnippet[];
  "final_score": number;
  "judge_rationale_snippets": string[];
  "rank": number;
  "score_breakdown": Record<string, unknown>;
  "submission_id": string;
  "tie_break_metadata": Record<string, unknown>;
}

export interface LeaderboardResponse {
  "generated_at": string;
  "items": LeaderboardItemResponse[];
  "run_id": string;
}

export interface MVPArtifactDownload {
  "artifact_id": string;
  "artifact_type": string;
  "content_hash": string;
  "download_url": string;
  "storage_key": string;
}

export interface MVPBundleItem {
  "accepted_at": string | unknown;
  "agent_id": string;
  "artifacts": MVPArtifactDownload[];
  "submission_id": string;
}

export interface MVPBundlesResponse {
  "bundles": MVPBundleItem[];
  "run_id": string;
}

export interface PaginatedLeaderboardResponse {
  "generated_at": string;
  "has_more": boolean;
  "items": LeaderboardItemResponse[];
  "next_cursor": string | unknown;
  "run_id": string;
}

export interface PenaltySnippet {
  "explanation": string;
  "penalty_type": string;
  "value": number;
}

export interface ReplayDiffResponse {
  "checkpoint_id": string;
  "run_id": string;
  "submissions": ReplayDiffSubmissionMetrics[];
}

export interface ReplayDiffSubmissionMetrics {
  "absolute_delta": number;
  "delta": number;
  "direction": string;
  "original_final_score": number;
  "original_rank": number;
  "rank_shift": number;
  "replay_final_score": number;
  "replay_rank": number;
  "submission_id": string;
}

export interface RepositorySubmissionSourceRequest {
  "agent_id": string;
  "commit": string;
  "repository_url": string;
  "value_hypothesis": string;
}

export interface RepositorySubmissionSourceResponse {
  "artifact_id": string;
  "ingestion_job": Record<string, unknown>;
  "resolved_commit": string;
  "submission": SubmissionResponse;
}

export interface RotateChallengeKeyResponse {
  "api_key": string;
  "challenge_id": string;
  "created_at": string;
  "id": string;
  "key_last4": string;
  "key_prefix": string;
}

export interface RunCancelResponse {
  "killed_containers": string[];
  "revoked_task_ids": string[];
  "run_id": string;
  "state": RunState;
}

export interface RunResponse {
  "challenge_id": string;
  "config_snapshot": Record<string, unknown>;
  "created_at": string;
  "ended_at": string | unknown;
  "id": string;
  "started_at": string | unknown;
  "state": RunState;
  "updated_at": string;
}

export type RunState = "created" | "running" | "canceling" | "completed" | "canceled" | "failed";

export interface RunStateTransitionRequest {
  "state": RunState;
}

export interface RunTimelineResponse {
  "events": TimelineEvent[];
  "run_id": string;
}

export interface ScoringReplayRequest {
  "checkpoint_id"?: string | unknown;
}

export interface ScoringReplayResponse {
  "active_policies": Record<string, unknown>;
  "active_weights": Record<string, unknown>;
  "captured_at": string;
  "checkpoint_id": string;
  "config_snapshot": Record<string, unknown>;
  "run_id": string;
  "submissions": ScoringReplaySubmission[];
}

export interface ScoringReplaySubmission {
  "components": Record<string, unknown>;
  "original_final_score": number;
  "replay_final_score": number;
  "submission_id": string;
}

export interface ScoringWeightsPayload {
  "criteria": number;
  "feasibility": number;
  "novelty": number;
  "quality": number;
  "similarity_penalty": number;
  "too_safe_penalty": number;
}

export interface ScoringWeightsUpdateRequest {
  "effective_from": string;
  "expected_config_version": number;
  "weights": ScoringWeightsPayload;
}

export interface ScoringWeightsUpdateResponse {
  "config_version": number;
  "created_at": string;
  "effective_from": string;
  "id": string;
  "run_id": string;
  "updated_at": string;
  "weights": ScoringWeightsPayload;
}

export interface SubmissionCreateRequest {
  "agent_id": string;
  "value_hypothesis": string;
}

export interface SubmissionIngestRequest {
  "agent_id": string;
  "artifacts": ArtifactIngestInput[];
  "value_hypothesis": string;
}

export interface SubmissionIngestResponse {
  "artifact_ids": string[];
  "submission": SubmissionResponse;
}

export interface SubmissionResponse {
  "accepted_at": string | unknown;
  "agent_id": string;
  "created_at": string;
  "human_testing_required": boolean;
  "id": string;
  "run_id": string;
  "state": string;
  "summary": string;
  "updated_at": string;
  "value_hypothesis": string;
}

export type SubmissionState = "pending" | "scored" | "accepted" | "rejected";

export interface SubmissionStateTransitionRequest {
  "state": SubmissionState;
}

export interface SubmissionValidationResponse {
  "errors": string[];
  "submission_id": string;
  "valid": boolean;
}

export interface TimelineEvent {
  "entity_id": string;
  "event_type": string;
  "occurred_at": string;
  "payload": Record<string, unknown>;
}

export interface ValidationError {
  "ctx"?: Record<string, unknown>;
  "input"?: unknown;
  "loc": string | number[];
  "msg": string;
  "type": string;
}
