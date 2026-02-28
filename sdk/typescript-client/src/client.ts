export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface RequestOptions<TBody = unknown> {
  headers?: Record<string, string>;
  body?: TBody;
  signal?: AbortSignal;
}

export class ApiClient {
  constructor(private readonly baseUrl: string, private readonly defaultHeaders: Record<string, string> = {}) {}

  async request<TResponse, TBody = unknown>(method: HttpMethod, path: string, options: RequestOptions<TBody> = {}): Promise<TResponse> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: { 'content-type': 'application/json', ...this.defaultHeaders, ...(options.headers ?? {}) },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
    if (!response.ok) {
      throw new Error(`SDK request failed: ${response.status} ${response.statusText}`);
    }
    if (response.status === 204) {
      return undefined as TResponse;
    }
    return (await response.json()) as TResponse;
  }
}

export async function rootGet(
  client: ApiClient, options: RequestOptions = {}
): Promise<Record<string, unknown>> {
  return client.request<Record<string, unknown>>('GET', `/`);
}

export async function downloadArtifactArtifactsArtifactIdDownloadGet(
  client: ApiClient, params: { artifact_id: string; }, options: RequestOptions = {}
): Promise<unknown> {
  return client.request<unknown>('GET', `/artifacts/${encodeURIComponent(params.artifact_id)}/download`);
}

export async function getArtifactMetadataArtifactsArtifactIdMetadataGet(
  client: ApiClient, params: { artifact_id: string; }, options: RequestOptions = {}
): Promise<ArtifactDownloadMetadataResponse> {
  return client.request<ArtifactDownloadMetadataResponse>('GET', `/artifacts/${encodeURIComponent(params.artifact_id)}/metadata`);
}

export async function createChallengeChallengesPost(
  client: ApiClient, body: unknown, options: RequestOptions = {}
): Promise<ChallengeResponse> {
  return client.request<ChallengeResponse>('POST', `/challenges`, { body });
}

export async function updateChallengeChallengesChallengeIdPatch(
  client: ApiClient, params: { challenge_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<ChallengeResponse> {
  return client.request<ChallengeResponse>('PATCH', `/challenges/${encodeURIComponent(params.challenge_id)}`, { body });
}

export async function rotateChallengeApiKeyChallengesChallengeIdApiKeysRotatePost(
  client: ApiClient, params: { challenge_id: string; }, options: RequestOptions = {}
): Promise<RotateChallengeKeyResponse> {
  return client.request<RotateChallengeKeyResponse>('POST', `/challenges/${encodeURIComponent(params.challenge_id)}/api-keys/rotate`);
}

export async function registerJudgeProfilesCsvChallengesChallengeIdJudgeProfilesCsvPost(
  client: ApiClient, params: { challenge_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<JudgeProfileResponse[]> {
  return client.request<JudgeProfileResponse[]>('POST', `/challenges/${encodeURIComponent(params.challenge_id)}/judge-profiles/csv`, { body });
}

export async function registerJudgeProfilesJsonChallengesChallengeIdJudgeProfilesJsonPost(
  client: ApiClient, params: { challenge_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<JudgeProfileResponse[]> {
  return client.request<JudgeProfileResponse[]>('POST', `/challenges/${encodeURIComponent(params.challenge_id)}/judge-profiles/json`, { body });
}

export async function registerJudgeProfileUrlChallengesChallengeIdJudgeProfilesUrlPost(
  client: ApiClient, params: { challenge_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<JudgeProfileResponse[]> {
  return client.request<JudgeProfileResponse[]>('POST', `/challenges/${encodeURIComponent(params.challenge_id)}/judge-profiles/url`, { body });
}

export async function registerJudgeProfilesYamlChallengesChallengeIdJudgeProfilesYamlPost(
  client: ApiClient, params: { challenge_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<JudgeProfileResponse[]> {
  return client.request<JudgeProfileResponse[]>('POST', `/challenges/${encodeURIComponent(params.challenge_id)}/judge-profiles/yaml`, { body });
}

export async function startRunChallengesChallengeIdRunsStartPost(
  client: ApiClient, params: { challenge_id: string; }, options: RequestOptions = {}
): Promise<RunResponse> {
  return client.request<RunResponse>('POST', `/challenges/${encodeURIComponent(params.challenge_id)}/runs/start`);
}

export async function cancelRunChallengesChallengeIdRunsRunIdCancelPost(
  client: ApiClient, params: { challenge_id: string; run_id: string; }, options: RequestOptions = {}
): Promise<RunCancelResponse> {
  return client.request<RunCancelResponse>('POST', `/challenges/${encodeURIComponent(params.challenge_id)}/runs/${encodeURIComponent(params.run_id)}/cancel`);
}

export async function transitionRunStateChallengesChallengeIdRunsRunIdStatePost(
  client: ApiClient, params: { challenge_id: string; run_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<RunResponse> {
  return client.request<RunResponse>('POST', `/challenges/${encodeURIComponent(params.challenge_id)}/runs/${encodeURIComponent(params.run_id)}/state`, { body });
}

export async function healthHealthGet(
  client: ApiClient, options: RequestOptions = {}
): Promise<unknown> {
  return client.request<unknown>('GET', `/health`);
}

export async function readinessReadinessGet(
  client: ApiClient, options: RequestOptions = {}
): Promise<unknown> {
  return client.request<unknown>('GET', `/readiness`);
}

export async function getAgentProductivityMetricsRunsRunIdAnalyticsAgentsProductivityGet(
  client: ApiClient, params: { run_id: string; }, options: RequestOptions = {}
): Promise<AgentProductivityResponse> {
  return client.request<AgentProductivityResponse>('GET', `/runs/${encodeURIComponent(params.run_id)}/analytics/agents/productivity`);
}

export async function getJudgeDisagreementMetricsRunsRunIdAnalyticsJudgesDisagreementGet(
  client: ApiClient, params: { run_id: string; }, options: RequestOptions = {}
): Promise<JudgeDisagreementResponse> {
  return client.request<JudgeDisagreementResponse>('GET', `/runs/${encodeURIComponent(params.run_id)}/analytics/judges/disagreement`);
}

export async function getReplayDiffMetricsRunsRunIdAnalyticsReplayDiffGet(
  client: ApiClient, params: { run_id: string; }, options: RequestOptions = {}
): Promise<ReplayDiffResponse> {
  return client.request<ReplayDiffResponse>('GET', `/runs/${encodeURIComponent(params.run_id)}/analytics/replay/diff`);
}

export async function exportRunBundleRunsRunIdExportGet(
  client: ApiClient, params: { run_id: string; }, options: RequestOptions = {}
): Promise<unknown> {
  return client.request<unknown>('GET', `/runs/${encodeURIComponent(params.run_id)}/export`);
}

export async function getLeaderboardRunsRunIdLeaderboardGet(
  client: ApiClient, params: { run_id: string; }, options: RequestOptions = {}
): Promise<LeaderboardResponse> {
  return client.request<LeaderboardResponse>('GET', `/runs/${encodeURIComponent(params.run_id)}/leaderboard`);
}

export async function getLeaderboardPaginatedRunsRunIdLeaderboardPaginatedGet(
  client: ApiClient, params: { run_id: string; }, options: RequestOptions = {}
): Promise<PaginatedLeaderboardResponse> {
  return client.request<PaginatedLeaderboardResponse>('GET', `/runs/${encodeURIComponent(params.run_id)}/leaderboard/paginated`);
}

export async function getMvpBundlesRunsRunIdMvpBundlesGet(
  client: ApiClient, params: { run_id: string; }, options: RequestOptions = {}
): Promise<MVPBundlesResponse> {
  return client.request<MVPBundlesResponse>('GET', `/runs/${encodeURIComponent(params.run_id)}/mvp-bundles`);
}

export async function streamRunRealtimeUpdatesSseRunsRunIdRealtimeSseGet(
  client: ApiClient, params: { run_id: string; }, options: RequestOptions = {}
): Promise<unknown> {
  return client.request<unknown>('GET', `/runs/${encodeURIComponent(params.run_id)}/realtime/sse`);
}

export async function replayRunScoringRunsRunIdReplayPost(
  client: ApiClient, params: { run_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<ScoringReplayResponse> {
  return client.request<ScoringReplayResponse>('POST', `/runs/${encodeURIComponent(params.run_id)}/replay`, { body });
}

export async function updateScoringWeightsRunsRunIdScoringWeightsPost(
  client: ApiClient, params: { run_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<ScoringWeightsUpdateResponse> {
  return client.request<ScoringWeightsUpdateResponse>('POST', `/runs/${encodeURIComponent(params.run_id)}/scoring-weights`, { body });
}

export async function createSubmissionRunsRunIdSubmissionsPost(
  client: ApiClient, params: { run_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<SubmissionResponse> {
  return client.request<SubmissionResponse>('POST', `/runs/${encodeURIComponent(params.run_id)}/submissions`, { body });
}

export async function ingestSubmissionTransactionalRunsRunIdSubmissionsIngestPost(
  client: ApiClient, params: { run_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<SubmissionIngestResponse> {
  return client.request<SubmissionIngestResponse>('POST', `/runs/${encodeURIComponent(params.run_id)}/submissions/ingest`, { body });
}

export async function attachRepositorySubmissionSourceRunsRunIdSubmissionsRepositorySourcePost(
  client: ApiClient, params: { run_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<RepositorySubmissionSourceResponse> {
  return client.request<RepositorySubmissionSourceResponse>('POST', `/runs/${encodeURIComponent(params.run_id)}/submissions/repository-source`, { body });
}

export async function transitionSubmissionStateRunsRunIdSubmissionsSubmissionIdStatePost(
  client: ApiClient, params: { run_id: string; submission_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<SubmissionResponse> {
  return client.request<SubmissionResponse>('POST', `/runs/${encodeURIComponent(params.run_id)}/submissions/${encodeURIComponent(params.submission_id)}/state`, { body });
}

export async function getRunTimelineRunsRunIdTimelineGet(
  client: ApiClient, params: { run_id: string; }, options: RequestOptions = {}
): Promise<RunTimelineResponse> {
  return client.request<RunTimelineResponse>('GET', `/runs/${encodeURIComponent(params.run_id)}/timeline`);
}

export async function uploadArtifactSubmissionsSubmissionIdArtifactsPost(
  client: ApiClient, params: { submission_id: string; }, body: unknown, options: RequestOptions = {}
): Promise<ArtifactUploadResponse> {
  return client.request<ArtifactUploadResponse>('POST', `/submissions/${encodeURIComponent(params.submission_id)}/artifacts`, { body });
}

export async function validateSubmissionMandatoryRequirementsSubmissionsSubmissionIdValidationGet(
  client: ApiClient, params: { submission_id: string; }, options: RequestOptions = {}
): Promise<SubmissionValidationResponse> {
  return client.request<SubmissionValidationResponse>('GET', `/submissions/${encodeURIComponent(params.submission_id)}/validation`);
}
