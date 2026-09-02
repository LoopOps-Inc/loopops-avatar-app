import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { InvestorPicker } from './InvestorPicker';
import { listInvestors, mintDevToken } from '@/services/advisor-service';
import { clearDevAuth } from '@/services/dev-auth';
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

    const select = await screen.findByLabelText('Inversionista');
    expect(select).toBeInTheDocument();
    expect(screen.getByText('200001 · Mariano Gonzales Santiago · Agresivo')).toBeInTheDocument();
    expect(screen.getByText('200002 · Marisol Farías Trejo · Agresivo')).toBeInTheDocument();
  });

  it('does not remint when a client is selected', async () => {
    vi.mocked(listInvestors).mockResolvedValue(investorsFixture);

    render(<InvestorPicker />);
    fireEvent.change(await screen.findByLabelText('Inversionista'), {
      target: { value: '200001' },
    });

    expect(mintDevToken).not.toHaveBeenCalled();
    expect(await screen.findByLabelText('Inversionista')).toHaveValue('200001');
  });

  it('does not remint when returning to the demo client', async () => {
    vi.mocked(listInvestors).mockResolvedValue(investorsFixture);

    render(<InvestorPicker />);
    const select = await screen.findByLabelText('Inversionista');
    fireEvent.change(select, { target: { value: '200001' } });
    fireEvent.change(select, { target: { value: '' } });

    expect(mintDevToken).not.toHaveBeenCalled();
    expect(select).toHaveValue('');
  });

  it('shows a load error when the investor list fails', async () => {
    vi.mocked(listInvestors).mockRejectedValue(new Error('boom'));

    render(<InvestorPicker />);

    expect(await screen.findByText('No se pudo cargar los clientes')).toBeInTheDocument();
    expect(mintDevToken).not.toHaveBeenCalled();
  });
});
