import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AdvisorRoute } from './AdvisorPage';
import { ackFirstTurnDisclosures, createAdvisorSession, getClientConfig } from '@/services/advisor-service';
import { setLocale } from '@/i18n';

vi.mock('@/services/advisor-service', () => ({
  createAdvisorSession: vi.fn(),
  ackFirstTurnDisclosures: vi.fn(),
  getClientConfig: vi.fn(),
  sendAdvisorMessage: vi.fn(),
  ackVoiceConsent: vi.fn(),
  createAvatarSession: vi.fn(),
  stopAvatarSession: vi.fn(),
  avatarPreflight: vi.fn(),
}));

const sessionFixture = {
  thread_id: 'th_1',
  capabilities: { chat: true, voice: true, advisory: true, transactional: false },
  disclosures_required: [],
  client: { first_name: 'Rodrigo', risk_category: 'moderado' },
};

describe('AdvisorRoute', () => {
  beforeEach(() => {
    vi.mocked(createAdvisorSession).mockReset();
    vi.mocked(ackFirstTurnDisclosures).mockReset();
    vi.mocked(getClientConfig).mockReset();
    vi.mocked(createAdvisorSession).mockResolvedValue(sessionFixture);
    vi.mocked(ackFirstTurnDisclosures).mockResolvedValue(undefined);
    vi.mocked(getClientConfig).mockResolvedValue({ kill_switch: false });
    setLocale('es');
  });

  it('acks disclosures and greets the client by name', async () => {
    render(<AdvisorRoute />);

    expect(await screen.findByText(/Rodrigo/i)).toBeInTheDocument();
    expect(ackFirstTurnDisclosures).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('radio', { name: 'Video' })).toBeInTheDocument();
  });

  it('shows the kill switch banner when the backend disables the advisor', async () => {
    vi.mocked(getClientConfig).mockResolvedValue({
      kill_switch: true,
      kill_switch_message: 'Mantenimiento programado',
    });

    render(<AdvisorRoute />);

    expect(await screen.findByText('Mantenimiento programado')).toBeInTheDocument();
  });
});
