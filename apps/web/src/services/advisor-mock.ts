import type { SessionResponse } from '@loopops/contracts';
import type { SuggestionChip } from '@/mocks/schemas';
import { rodrigoFixture } from '@/mocks';
import { resolveMockScenario } from '@/mocks/scenarios';
import type { AdvisorSseHandlers } from './advisor-types';

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function createMockAdvisorSession(): SessionResponse {
  return {
    thread_id: 'th_mock_rodrigo',
    capabilities: {
      chat: true,
      voice: false,
      advisory: false,
      transactional: false,
    },
    disclosures_required: [
      { id: 'AI_ASSISTANT', version: '2026-08', acknowledged: true },
      { id: 'SERVICES_GUIDE', version: '2026-06', acknowledged: true },
    ],
    client: {
      first_name: rodrigoFixture.user.firstName,
      risk_category: rodrigoFixture.investorProfile.riskCategory,
    },
  };
}

export type MockMessageMeta = {
  chips?: SuggestionChip[];
};

export async function sendMockAdvisorMessage(
  message: string,
  handlers: AdvisorSseHandlers,
): Promise<MockMessageMeta> {
  const scenario = resolveMockScenario(message);
  const words = scenario.speech.split(' ');

  for (let i = 0; i < words.length; i++) {
    handlers.onToken((i > 0 ? ' ' : '') + words[i]);
    await delay(28);
  }

  for (const component of scenario.uiPayload) {
    handlers.onUi(component);
  }

  handlers.onDone({
    turn_id: 'tn_mock',
    evidence_id: 'ev_mock',
    service_type: 'no_asesorado',
  });

  return { chips: scenario.chips };
}
