import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { InvestorPicker } from './InvestorPicker';
import { listInvestors, mintDevToken } from '@/services/advisor-service';
import { clearDevAuth, getDevAuth } from '@/services/dev-auth';
import { setLocale } from '@/i18n';

vi.mock('@/services/advisor-service', () => ({
  listInvestors: vi.fn(),
  mintDevToken: vi.fn(),
}));

const investorsFixture = {
  investors: [
    {
      id_cliente_pk: 1,
      numero_cliente_unico: 200001,
      nombre_completo: 'Mariano Gonzales Santiago',
      rfc: 'DAXI800214FE8',
      correo_electronico: 'mariano.gonzales@gmail.com',
      perfil_riesgo: 'Agresivo',
      total_contratos: 4,
    },
    {
      id_cliente_pk: 2,
      numero_cliente_unico: 200002,
      nombre_completo: 'Marisol Farías Trejo',
      rfc: 'DUCS581214R21',
      correo_electronico: 'marisol.farias@gmail.com',
      perfil_riesgo: 'Agresivo',
      total_contratos: 4,
    },
  ],
  total: 2,
};

describe('InvestorPicker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearDevAuth();
    setLocale('es');
  });

  it('renders the investor list once loaded', async () => {
    vi.mocked(listInvestors).mockResolvedValue(investorsFixture);

    render(<InvestorPicker />);

    const select = await screen.findByLabelText('Actuar como');
    expect(select).toBeInTheDocument();
    expect(
      screen.getByText('200001 · Mariano Gonzales Santiago · Agresivo'),
    ).toBeInTheDocument();
    expect(screen.getByText('200002 · Marisol Farías Trejo · Agresivo')).toBeInTheDocument();
  });

  it('mints and stores a dev token when a client is selected', async () => {
    vi.mocked(listInvestors).mockResolvedValue(investorsFixture);
    vi.mocked(mintDevToken).mockResolvedValue({
      access_token: 'tok',
      client_id: '200001',
      token_type: 'Bearer',
      expires_in: 900,
    });

    render(<InvestorPicker />);
    fireEvent.change(await screen.findByLabelText('Actuar como'), { target: { value: '200001' } });

    await waitFor(() => expect(mintDevToken).toHaveBeenCalledWith('200001'));
    await waitFor(() => expect(getDevAuth()?.accessToken).toBe('tok'));
    expect(getDevAuth()?.clientId).toBe('200001');
  });

  it('clears the stored token when returning to the demo client', async () => {
    vi.mocked(listInvestors).mockResolvedValue(investorsFixture);
    vi.mocked(mintDevToken).mockResolvedValue({
      access_token: 'tok',
      client_id: '200001',
      token_type: 'Bearer',
      expires_in: 900,
    });

    render(<InvestorPicker />);
    const select = await screen.findByLabelText('Actuar como');
    fireEvent.change(select, { target: { value: '200001' } });
    await waitFor(() => expect(getDevAuth()).not.toBeNull());

    fireEvent.change(select, { target: { value: '' } });

    expect(getDevAuth()).toBeNull();
    expect(mintDevToken).toHaveBeenCalledTimes(1);
  });

  it('keeps the previous identity and shows an error when minting fails', async () => {
    vi.mocked(listInvestors).mockResolvedValue(investorsFixture);
    vi.mocked(mintDevToken)
      .mockResolvedValueOnce({
        access_token: 'tok',
        client_id: '200001',
        token_type: 'Bearer',
        expires_in: 900,
      })
      .mockRejectedValueOnce(new Error('mint failed'));

    render(<InvestorPicker />);
    const select = await screen.findByLabelText('Actuar como');
    fireEvent.change(select, { target: { value: '200001' } });
    await waitFor(() => expect(getDevAuth()?.accessToken).toBe('tok'));

    fireEvent.change(select, { target: { value: '200002' } });

    expect(await screen.findByRole('alert')).toHaveTextContent('mint failed');
    await waitFor(() => expect(select).toHaveValue('200001'));
    expect(getDevAuth()?.accessToken).toBe('tok');
  });

  it('shows a load error when the investor list fails', async () => {
    vi.mocked(listInvestors).mockRejectedValue(new Error('boom'));

    render(<InvestorPicker />);

    expect(await screen.findByText('No se pudo cargar los clientes')).toBeInTheDocument();
  });
});
